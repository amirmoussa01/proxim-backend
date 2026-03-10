from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email obligatoire')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    ROLE_CLIENT = 'client'
    ROLE_PRESTATAIRE = 'prestataire'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_CLIENT, 'Client'),
        (ROLE_PRESTATAIRE, 'Prestataire'),
        (ROLE_ADMIN, 'Administrateur'),
    ]

    username = None
    objects = UserManager()
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CLIENT)
    is_email_verified = models.BooleanField(default=False)
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    email_verification_code = models.CharField(max_length=6, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return f'{self.email} ({self.role})'

    @property
    def is_client(self):
        return self.role == self.ROLE_CLIENT

    @property
    def is_prestataire(self):
        return self.role == self.ROLE_PRESTATAIRE


class ClientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    nom = models.CharField(max_length=100, blank=True)
    prenom = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/clients/', blank=True, null=True)
    adresse = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil Client'
        verbose_name_plural = 'Profils Clients'

    def __str__(self):
        return f'{self.prenom} {self.nom}'


class PrestatireProfile(models.Model):
    NIVEAU_BRONZE = 'bronze'
    NIVEAU_ARGENT = 'argent'
    NIVEAU_OR = 'or'
    NIVEAU_EXPERT = 'expert'

    NIVEAU_CHOICES = [
        (NIVEAU_BRONZE, 'Bronze'),
        (NIVEAU_ARGENT, 'Argent'),
        (NIVEAU_OR, 'Or'),
        (NIVEAU_EXPERT, 'Expert'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='prestatire_profile')
    nom = models.CharField(max_length=100, blank=True)
    prenom = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/prestatires/', blank=True, null=True)
    bio = models.TextField(blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    date_naissance = models.DateField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    niveau = models.CharField(max_length=20, choices=NIVEAU_CHOICES, default=NIVEAU_BRONZE)
    note_moyenne = models.DecimalField(
        max_digits=3, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    nombre_avis = models.PositiveIntegerField(default=0)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil Prestataire'
        verbose_name_plural = 'Profils Prestataires'

    def __str__(self):
        return f'{self.prenom} {self.nom}'


class KYCDocument(models.Model):
    TYPE_CNI = 'CNI'
    TYPE_SELFIE = 'selfie'
    TYPE_JUSTIFICATIF = 'justificatif'

    TYPE_CHOICES = [
        (TYPE_CNI, 'Carte Nationale Identite'),
        (TYPE_SELFIE, 'Selfie'),
        (TYPE_JUSTIFICATIF, 'Justificatif adresse'),
    ]

    STATUT_ATTENTE = 'en_attente'
    STATUT_VALIDE = 'valide'
    STATUT_REJETE = 'rejete'

    STATUT_CHOICES = [
        (STATUT_ATTENTE, 'En attente'),
        (STATUT_VALIDE, 'Valide'),
        (STATUT_REJETE, 'Rejete'),
    ]

    prestatire = models.ForeignKey(
        PrestatireProfile, on_delete=models.CASCADE, related_name='kyc_documents'
    )
    type_document = models.CharField(max_length=20, choices=TYPE_CHOICES)
    fichier = models.FileField(upload_to='kyc/')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=STATUT_ATTENTE)
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Document KYC'
        verbose_name_plural = 'Documents KYC'

    def __str__(self):
        return f'{self.prestatire} - {self.type_document} - {self.statut}'