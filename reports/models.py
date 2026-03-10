from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Report(models.Model):
    RAISON_COMPORTEMENT = 'COMPORTEMENT'
    RAISON_ARNAQUE = 'ARNAQUE'
    RAISON_CONTENU = 'CONTENU_INAPPROPRIE'
    RAISON_AUTRE = 'AUTRE'

    RAISON_CHOICES = [
        (RAISON_COMPORTEMENT, 'Comportement inapproprie'),
        (RAISON_ARNAQUE, 'Arnaque'),
        (RAISON_CONTENU, 'Contenu inapproprie'),
        (RAISON_AUTRE, 'Autre'),
    ]

    STATUT_ATTENTE = 'EN_ATTENTE'
    STATUT_TRAITE = 'TRAITE'
    STATUT_REJETE = 'REJETE'

    STATUT_CHOICES = [
        (STATUT_ATTENTE, 'En attente'),
        (STATUT_TRAITE, 'Traite'),
        (STATUT_REJETE, 'Rejete'),
    ]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='signalements_envoyes')
    cible_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='signalements_recus')
    raison = models.CharField(max_length=30, choices=RAISON_CHOICES)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=STATUT_ATTENTE)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Signalement'
        verbose_name_plural = 'Signalements'
        ordering = ['-date']

    def __str__(self):
        return f'Signalement #{self.id} - {self.reporter} - {self.raison}'