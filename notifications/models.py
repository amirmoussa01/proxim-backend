from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Notification(models.Model):
    TYPE_CHOICES = [
        ('NOUVEAU_MESSAGE', 'Nouveau message'),
        ('COMMANDE_RECUE', 'Commande recue'),
        ('COMMANDE_ACCEPTEE', 'Commande acceptee'),
        ('COMMANDE_TERMINEE', 'Commande terminee'),
        ('COMMANDE_ANNULEE', 'Commande annulee'),
        ('NOUVEAU_STATUT', 'Nouveau statut'),
        ('PAIEMENT_RECU', 'Paiement recu'),
        ('RETRAIT_TRAITE', 'Retrait traite'),
        ('NOUVEL_AVIS', 'Nouvel avis'),
        ('NOUVEAU_PRESTATAIRE_PROCHE', 'Nouveau prestataire proche'),
        ('KYC_VALIDE', 'KYC valide'),
        ('KYC_REJETE', 'KYC rejete'),
    ]

    destinataire = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications'
    )
    type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    titre = models.CharField(max_length=255)
    contenu = models.TextField()
    is_read = models.BooleanField(default=False)
    lien_objet_id = models.PositiveIntegerField(blank=True, null=True)
    lien_objet_type = models.CharField(max_length=50, blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-date']

    def __str__(self):
        return f'Notification #{self.id} - {self.type} - {self.destinataire}'