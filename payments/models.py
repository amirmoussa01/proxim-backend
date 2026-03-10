from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    solde = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    devise = models.CharField(max_length=10, default='FCFA')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'

    def __str__(self):
        return f'Wallet - {self.user} - {self.solde} {self.devise}'


class Transaction(models.Model):
    TYPE_CREDIT = 'CREDIT'
    TYPE_DEBIT = 'DEBIT'

    TYPE_CHOICES = [
        (TYPE_CREDIT, 'Credit'),
        (TYPE_DEBIT, 'Debit'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    solde_avant = models.DecimalField(max_digits=12, decimal_places=2)
    solde_apres = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-date']

    def __str__(self):
        return f'Transaction #{self.id} - {self.type} - {self.montant}'


class Payment(models.Model):
    METHODE_MOBILE_MONEY = 'MOBILE_MONEY'
    METHODE_CARTE = 'CARTE'
    METHODE_WALLET = 'WALLET'

    METHODE_CHOICES = [
        (METHODE_MOBILE_MONEY, 'Mobile Money'),
        (METHODE_CARTE, 'Carte bancaire'),
        (METHODE_WALLET, 'Wallet'),
    ]

    STATUT_ATTENTE = 'EN_ATTENTE'
    STATUT_SUCCES = 'SUCCES'
    STATUT_ECHOUE = 'ECHOUE'
    STATUT_REMBOURSE = 'REMBOURSE'

    STATUT_CHOICES = [
        (STATUT_ATTENTE, 'En attente'),
        (STATUT_SUCCES, 'Succes'),
        (STATUT_ECHOUE, 'Echoue'),
        (STATUT_REMBOURSE, 'Rembourse'),
    ]

    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='payment'
    )
    client = models.ForeignKey(
        'accounts.ClientProfile', on_delete=models.CASCADE, related_name='paiements'
    )
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)
    commission_plateforme = models.DecimalField(max_digits=12, decimal_places=2)
    montant_prestatire = models.DecimalField(max_digits=12, decimal_places=2)
    methode = models.CharField(max_length=20, choices=METHODE_CHOICES)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=STATUT_ATTENTE)
    fedapay_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    date_paiement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-date_paiement']

    def __str__(self):
        return f'Paiement #{self.id} - {self.montant_total} - {self.statut}'


class Withdrawal(models.Model):
    STATUT_ATTENTE = 'EN_ATTENTE'
    STATUT_TRAITE = 'TRAITE'
    STATUT_REJETE = 'REJETE'

    STATUT_CHOICES = [
        (STATUT_ATTENTE, 'En attente'),
        (STATUT_TRAITE, 'Traite'),
        (STATUT_REJETE, 'Rejete'),
    ]

    prestatire = models.ForeignKey(
        'accounts.PrestatireProfile',
        on_delete=models.CASCADE,
        related_name='retraits'
    )
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=STATUT_ATTENTE)
    methode_retrait = models.CharField(max_length=50, default='MOBILE_MONEY')
    numero_mobile = models.CharField(max_length=20)
    date_demande = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Retrait'
        verbose_name_plural = 'Retraits'
        ordering = ['-date_demande']

    def __str__(self):
        return f'Retrait #{self.id} - {self.prestatire} - {self.montant}'