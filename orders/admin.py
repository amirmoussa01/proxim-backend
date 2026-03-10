from django.contrib import admin
from .models import Order, OrderStatusHistory, Negotiation


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'prestatire', 'service', 'statut', 'prix_final', 'date_commande']
    list_filter = ['statut']


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['order', 'statut', 'changed_by', 'date']


@admin.register(Negotiation)
class NegotiationAdmin(admin.ModelAdmin):
    list_display = ['order', 'expediteur', 'prix_propose', 'date']
