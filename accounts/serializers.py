from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from .models import ClientProfile, PrestatireProfile, KYCDocument
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException


def envoyer_email_brevo(destinataire, sujet, contenu):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = settings.BREVO_API_KEY

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": destinataire}],
        sender={"email": "alamiralamir979@gmail.com", "name": "Proxim"},
        subject=sujet,
        text_content=contenu,
    )

    try:
        api_instance.send_transac_email(send_smtp_email)
        return True
    except ApiException:
        return False
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

        envoyer_email_brevo(
            destinataire=user.email,
            sujet='Proxim - Verification email',
            contenu=f'Votre code de verification est : {code}',
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

        envoyer_email_brevo(
            destinataire=user.email,
            sujet='Proxim - Verification email',
            contenu=f'Votre code de verification est : {code}',
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
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = ClientProfile
        fields = '__all__'

    def get_avatar(self, obj):
        if obj.avatar:
            return obj.avatar.url
        return None


class PrestatireProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = PrestatireProfile
        fields = '__all__'

    def get_avatar(self, obj):
        if obj.avatar:
            return obj.avatar.url
        return None

class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()