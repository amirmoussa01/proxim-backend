from django.urls import path
from . import views

urlpatterns = [
    # Commandes
    path('creer/', views.creer_commande, name='creer-commande'),
    path('mes-commandes/', views.mes_commandes, name='mes-commandes'),
    path('<int:pk>/', views.detail_commande, name='detail-commande'),
    path('<int:pk>/statut/', views.changer_statut_commande, name='changer-statut'),
    path('<int:pk>/prix-final/', views.definir_prix_final, name='prix-final'),

    # Negociation
    path('<int:pk>/negociation/', views.envoyer_negociation, name='envoyer-negociation'),
    path('<int:pk>/negociation/liste/', views.liste_negotiations, name='liste-negotiations'),
]