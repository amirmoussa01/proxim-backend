from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Order(models.Model):
    STATUT_NEGOCIATION = 'EN_NEGOCIATION'
    STATUT_ACCEPTE = 'ACCEPTE'
    STATUT_EN_COURS = 'EN_COURS'
    STATUT_TERMINE = 'TERMINE'
    STATUT_ANNULE = 'ANNULE'

    STATUT_CHOICES = [
        (STATUT_NEGOCIATION, 'En negociation'),
        (STATUT_ACCEPTE, 'Accepte'),
        (STATUT_EN_COURS, 'En cours'),
        (STATUT_TERMINE, 'Termine'),
        (STATUT_ANNULE, 'Annule'),
    ]

    client = models.ForeignKey(
        'accounts.ClientProfile',
        on_delete=models.CASCADE,
        related_name='commandes'
    )
    prestatire = models.ForeignKey(
        'accounts.PrestatireProfile',
        on_delete=models.CASCADE,
        related_name='commandes'
    )
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.CASCADE,
        related_name='commandes'
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=STATUT_NEGOCIATION)
    prix_propose = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    prix_final = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    parametres_choisis = models.JSONField(default=dict, blank=True)
    notes_client = models.TextField(blank=True)
    date_commande = models.DateTimeField(auto_now_add=True)
    date_debut_prevue = models.DateTimeField(blank=True, null=True)
    date_fin_prevue = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Commande'
        verbose_name_plural = 'Commandes'
        ordering = ['-date_commande']

    def __str__(self):
        return f'Commande #{self.id} - {self.client} - {self.statut}'


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='historique_statuts')
    statut = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    commentaire = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Historique Statut'
        verbose_name_plural = 'Historiques Statuts'
        ordering = ['-date']

    def __str__(self):
        return f'Commande #{self.order.id} - {self.statut}'


class Negotiation(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='negotiations')
    expediteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='negotiations')
    message = models.TextField()
    prix_propose = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Negociation'
        verbose_name_plural = 'Negociations'
        ordering = ['date']

    def __str__(self):
        return f'Negociation #{self.id} - Commande #{self.order.id}'