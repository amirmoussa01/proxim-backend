from django.urls import path
from . import views

urlpatterns = [
    path('wallet/', views.mon_wallet, name='mon-wallet'),
    path('transactions/', views.historique_transactions, name='historique-transactions'),
    path('initier/', views.initier_paiement, name='initier-paiement'),
    path('confirmer/', views.confirmer_paiement_fedapay, name='confirmer-paiement'),
    path('historique/', views.historique_paiements, name='historique-paiements'),
    path('retrait/', views.demander_retrait, name='demander-retrait'),
    path('retraits/', views.historique_retraits, name='historique-retraits'),
]