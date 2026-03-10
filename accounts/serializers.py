from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from .models import ClientProfile, PrestatireProfile, KYCDocument

User = get_user_model()


class InscriptionClientSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)
    nom = serializers.CharField()
    prenom = serializers.CharField()

    class Meta:
        model = User
        fields = ['email', 'phone', 'password', 'password2', 'nom', 'prenom']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError('Les mots de passe ne correspondent pas')
        return data

    def create(self, validated_data):
        nom = validated_data.pop('nom')
        prenom = validated_data.pop('prenom')
        validated_data.pop('password2')

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            phone=validated_data.get('phone', ''),
            role=User.ROLE_CLIENT,
        )

        ClientProfile.objects.create(user=user, nom=nom, prenom=prenom)

        code = get_random_string(6, allowed_chars='0123456789')
        user.email_verification_code = code
        user.save()

        send_mail(
            subject='Proxim - Verification email',
            message=f'Votre code de verification est : {code}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

        return user


class InscriptionPrestatireSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)
    nom = serializers.CharField()
    prenom = serializers.CharField()
    bio = serializers.CharField(required=False, allow_blank=True)
    date_naissance = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'email', 'phone', 'password', 'password2',
            'nom', 'prenom', 'bio', 'date_naissance'
        ]

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError('Les mots de passe ne correspondent pas')
        return data

    def create(self, validated_data):
        nom = validated_data.pop('nom')
        prenom = validated_data.pop('prenom')
        bio = validated_data.pop('bio', '')
        date_naissance = validated_data.pop('date_naissance', None)
        validated_data.pop('password2')

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            phone=validated_data.get('phone', ''),
            role=User.ROLE_PRESTATAIRE,
        )

        PrestatireProfile.objects.create(
            user=user,
            nom=nom,
            prenom=prenom,
            bio=bio,
            date_naissance=date_naissance,
        )

        code = get_random_string(6, allowed_chars='0123456789')
        user.email_verification_code = code
        user.save()

        send_mail(
            subject='Proxim - Verification email',
            message=f'Votre code de verification est : {code}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

        return user


class VerificationEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class ConnexionSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'role', 'is_email_verified']


class ClientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ClientProfile
        fields = '__all__'


class PrestatireProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = PrestatireProfile
        fields = '__all__'


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()