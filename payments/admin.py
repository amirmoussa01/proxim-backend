from django.contrib import admin
from .models import Wallet, Transaction, Payment, Withdrawal


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'solde', 'devise']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'type', 'montant', 'solde_apres', 'date']
    list_filter = ['type']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'montant_total', 'methode', 'statut', 'date_paiement']
    list_filter = ['statut', 'methode']


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['prestatire', 'montant', 'statut', 'date_demande']
    list_filter = ['statut']
