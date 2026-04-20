from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('utilisateurs/', views.utilisateurs, name='utilisateurs'),
    path('utilisateurs/<int:user_id>/toggle/', views.toggle_user, name='toggle_user'),
    path('utilisateurs/<int:user_id>/detail/', views.detail_user, name='detail_user'),
    path('services/', views.services, name='services'),
    path('services/<int:service_id>/toggle/', views.toggle_service, name='toggle_service'),
    path('services/<int:service_id>/supprimer/', views.supprimer_service, name='supprimer_service'),
    path('commandes/', views.commandes, name='commandes'),
    path('commandes/<int:commande_id>/detail/', views.detail_commande, name='detail_commande'),
    path('paiements/', views.paiements, name='paiements'),
    path('retraits/', views.retraits, name='retraits'),
    path('retraits/<int:retrait_id>/traiter/', views.traiter_retrait, name='traiter_retrait'),
    path('kyc/', views.kyc, name='kyc'),
    path('kyc/<int:kyc_id>/valider/', views.valider_kyc, name='valider_kyc'),
    path('kyc/<int:kyc_id>/rejeter/', views.rejeter_kyc, name='rejeter_kyc'),
    path('categories/', views.categories, name='categories'),
    path('categories/creer/', views.creer_categorie, name='creer_categorie'),
    path('categories/<int:cat_id>/toggle/', views.toggle_categorie, name='toggle_categorie'),
    path('categories/<int:cat_id>/supprimer/', views.supprimer_categorie, name='supprimer_categorie'),
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/graphe-commandes/', views.api_graphe_commandes, name='api_graphe_commandes'),
    path('api/graphe-revenus/', views.api_graphe_revenus, name='api_graphe_revenus'),
]
