from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from .models import ClientProfile, PrestatireProfile
from .serializers import (
    InscriptionClientSerializer,
    InscriptionPrestatireSerializer,
    VerificationEmailSerializer,
    ConnexionSerializer,
    UserSerializer,
    ClientProfileSerializer,
    PrestatireProfileSerializer,
    GoogleAuthSerializer,
)
import random
import string

User = get_user_model()


def get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def inscription_client(request):
    serializer = InscriptionClientSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'message': 'Compte client cree avec succes. Verifiez votre email.',
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def inscription_prestatire(request):
    serializer = InscriptionPrestatireSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'message': 'Compte prestataire cree avec succes. Verifiez votre email.',
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def verification_email(request):
    serializer = VerificationEmailSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        try:
            user = User.objects.get(email=email)
            if user.email_verification_code == code:
                user.is_email_verified = True
                user.email_verification_code = None
                user.save()
                tokens = get_tokens(user)
                return Response({
                    'message': 'Email verifie avec succes.',
                    'tokens': tokens,
                    'user': UserSerializer(user).data,
                }, status=status.HTTP_200_OK)
            return Response(
                {'error': 'Code incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'Utilisateur introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def connexion(request):
    serializer = ConnexionSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        user = authenticate(request, email=email, password=password)
        if user:
            if not user.is_email_verified:
                return Response(
                    {'error': 'Email non verifie. Verifiez votre boite mail.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            tokens = get_tokens(user)
            return Response({
                'message': 'Connexion reussie.',
                'tokens': tokens,
                'user': UserSerializer(user).data,
            }, status=status.HTTP_200_OK)
        return Response(
            {'error': 'Email ou mot de passe incorrect'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def connexion_google(request):
    serializer = GoogleAuthSerializer(data=request.data)
    if serializer.is_valid():
        token = serializer.validated_data['id_token']
        try:
            infos = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY
            )
            google_id = infos['sub']
            email = infos['email']
            prenom = infos.get('given_name', '')
            nom = infos.get('family_name', '')

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'google_id': google_id,
                    'is_email_verified': True,
                    'role': User.ROLE_CLIENT,
                }
            )

            if created:
                user.set_unusable_password()
                user.save()
                ClientProfile.objects.create(user=user, nom=nom, prenom=prenom)

            if not user.google_id:
                user.google_id = google_id
                user.save()

            tokens = get_tokens(user)
            return Response({
                'message': 'Connexion Google reussie.',
                'tokens': tokens,
                'user': UserSerializer(user).data,
                'created': created,
            }, status=status.HTTP_200_OK)

        except ValueError:
            return Response(
                {'error': 'Token Google invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def mot_de_passe_oublie(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email obligatoire'}, status=400)

    try:
        user = User.objects.get(email=email)
        code = ''.join(random.choices(string.digits, k=6))
        user.email_verification_code = code
        user.save()

        from .serializers import envoyer_email_brevo
        envoyer_email_brevo(
            destinataire=user.email,
            sujet='Proxim - Reinitialisation mot de passe',
            contenu=f'Votre code de reinitialisation est : {code}',
        )
        return Response({'message': 'Code envoye'})
    except User.DoesNotExist:
        return Response({'error': 'Aucun compte avec cet email'}, status=404)


@api_view(['POST'])
@permission_classes([AllowAny])
def reinitialisation_mot_de_passe(request):
    email = request.data.get('email')
    code = request.data.get('code')
    nouveau_password = request.data.get('nouveau_password')
    password2 = request.data.get('password2')

    if not all([email, code, nouveau_password, password2]):
        return Response({'error': 'Tous les champs sont obligatoires'}, status=400)

    if nouveau_password != password2:
        return Response({'error': 'Les mots de passe ne correspondent pas'}, status=400)

    if len(nouveau_password) < 8:
        return Response({'error': 'Minimum 8 caracteres'}, status=400)

    try:
        user = User.objects.get(email=email)
        if user.email_verification_code != code:
            return Response({'error': 'Code incorrect'}, status=400)

        user.set_password(nouveau_password)
        user.email_verification_code = ''
        user.save()
        return Response({'message': 'Mot de passe reinitialise avec succes'})
    except User.DoesNotExist:
        return Response({'error': 'Aucun compte avec cet email'}, status=404)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mon_profil(request):
    user = request.user
    data = UserSerializer(user).data

    if user.is_client:
        profile, created = ClientProfile.objects.get_or_create(
            user=user,
            defaults={'nom': '', 'prenom': ''}
        )
        data['profil'] = ClientProfileSerializer(profile).data

    elif user.is_prestataire:
        profile, created = PrestatireProfile.objects.get_or_create(
            user=user,
            defaults={'nom': '', 'prenom': '', 'bio': ''}
        )
        data['profil'] = PrestatireProfileSerializer(profile).data

    return Response(data, status=status.HTTP_200_OK)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def modifier_profil(request):
    user = request.user

    if user.is_client:
        try:
            profile = ClientProfile.objects.get(user=user)
            serializer = ClientProfileSerializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ClientProfile.DoesNotExist:
            return Response({'error': 'Profil introuvable'}, status=status.HTTP_404_NOT_FOUND)

    elif user.is_prestataire:
        try:
            profile = PrestatireProfile.objects.get(user=user)
            serializer = PrestatireProfileSerializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except PrestatireProfile.DoesNotExist:
            return Response({'error': 'Profil introuvable'}, status=status.HTTP_404_NOT_FOUND)

    return Response({'error': 'Role invalide'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deconnexion(request):
    try:
        refresh_token = request.data['refresh']
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'message': 'Deconnexion reussie.'}, status=status.HTTP_200_OK)
    except Exception:
        return Response({'error': 'Token invalide'}, status=status.HTTP_400_BAD_REQUEST)