from django.db import models


class Category(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icone = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Categorie'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.nom


class Service(models.Model):
    PRICING_FIXE = 'FIXE'
    PRICING_PAR_UNITE = 'PAR_UNITE'
    PRICING_SUR_DEVIS = 'SUR_DEVIS'

    PRICING_CHOICES = [
        (PRICING_FIXE, 'Prix fixe'),
        (PRICING_PAR_UNITE, 'Par unite'),
        (PRICING_SUR_DEVIS, 'Sur devis'),
    ]

    prestatire = models.ForeignKey(
        'accounts.PrestatireProfile',
        on_delete=models.CASCADE,
        related_name='services'
    )
    categorie = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='services'
    )
    titre = models.CharField(max_length=200)
    description = models.TextField()
    pricing_type = models.CharField(max_length=20, choices=PRICING_CHOICES, default=PRICING_FIXE)
    prix_base = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    devise = models.CharField(max_length=10, default='FCFA')
    is_available = models.BooleanField(default=True)
    is_sponsored = models.BooleanField(default=False)
    localisation = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Service'
        verbose_name_plural = 'Services'

    def __str__(self):
        return f'{self.titre} - {self.prestatire}'


class ServiceImage(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='services/')
    is_principale = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Image Service'
        verbose_name_plural = 'Images Service'
        ordering = ['ordre']

    def __str__(self):
        return f'Image {self.ordre} - {self.service.titre}'


class ServiceParameter(models.Model):
    TYPE_NUMBER = 'NUMBER'
    TYPE_SELECT = 'SELECT'
    TYPE_BOOLEAN = 'BOOLEAN'

    TYPE_CHOICES = [
        (TYPE_NUMBER, 'Nombre'),
        (TYPE_SELECT, 'Selection'),
        (TYPE_BOOLEAN, 'Oui/Non'),
    ]

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='parametres')
    nom = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    unite = models.CharField(max_length=50, blank=True)
    is_required = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Parametre Service'
        verbose_name_plural = 'Parametres Service'
        ordering = ['ordre']

    def __str__(self):
        return f'{self.nom} - {self.service.titre}'


class ServiceParameterOption(models.Model):
    parametre = models.ForeignKey(
        ServiceParameter, on_delete=models.CASCADE, related_name='options'
    )
    label = models.CharField(max_length=100)
    prix_supplementaire = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Option Parametre'
        verbose_name_plural = 'Options Parametre'

    def __str__(self):
        return f'{self.label} - {self.parametre.nom}'


class Availability(models.Model):
    JOUR_CHOICES = [
        ('lundi', 'Lundi'),
        ('mardi', 'Mardi'),
        ('mercredi', 'Mercredi'),
        ('jeudi', 'Jeudi'),
        ('vendredi', 'Vendredi'),
        ('samedi', 'Samedi'),
        ('dimanche', 'Dimanche'),
    ]

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='disponibilites')
    jour = models.CharField(max_length=20, choices=JOUR_CHOICES)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    is_available = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Disponibilite'
        verbose_name_plural = 'Disponibilites'

    def __str__(self):
        return f'{self.service.titre} - {self.jour}'