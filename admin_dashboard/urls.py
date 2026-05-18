from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    # Home
    path('', views.dashboard_home, name='home'),

    # Utilisateurs
    path('utilisateurs/', views.utilisateurs, name='utilisateurs'),
    path('utilisateurs/<int:user_id>/toggle/', views.toggle_user, name='toggle_user'),
    path('utilisateurs/<int:user_id>/verifier-email/', views.verifier_email_user, name='verifier_email_user'),
    path('utilisateurs/<int:user_id>/changer-role/', views.changer_role_user, name='changer_role_user'),
    path('utilisateurs/<int:user_id>/changer-niveau/', views.changer_niveau_user, name='changer_niveau_user'),
    path('utilisateurs/<int:user_id>/supprimer/', views.supprimer_user, name='supprimer_user'),
    path('utilisateurs/<int:user_id>/notifier/', views.envoyer_notification_user, name='envoyer_notification_user'),
    path('utilisateurs/<int:user_id>/detail/', views.detail_user, name='detail_user'),
    path('utilisateurs/<int:user_id>/pdf/', views.exporter_user_pdf, name='exporter_user_pdf'),
    path('utilisateurs/<int:user_id>/modifier-profil/', views.modifier_profil_user, name='modifier_profil_user'),

    # Services
    path('services/', views.services, name='services'),
    path('services/<int:service_id>/toggle/', views.toggle_service, name='toggle_service'),
    path('services/<int:service_id>/supprimer/', views.supprimer_service, name='supprimer_service'),

    # Commandes
    path('commandes/', views.commandes, name='commandes'),
    path('commandes/<int:commande_id>/detail/', views.detail_commande, name='detail_commande'),
    path('commandes/<int:commande_id>/valider-fin-service/', views.valider_fin_service, name='valider_fin_service'),  # ← NOUVEAU

    # Paiements
    path('paiements/', views.paiements, name='paiements'),

    # Retraits
    path('retraits/', views.retraits, name='retraits'),
    path('retraits/<int:retrait_id>/traiter/', views.traiter_retrait, name='traiter_retrait'),

    # KYC
    path('kyc/', views.kyc, name='kyc'),
    path('kyc/<int:kyc_id>/valider/', views.valider_kyc, name='valider_kyc'),
    path('kyc/<int:kyc_id>/rejeter/', views.rejeter_kyc, name='rejeter_kyc'),

    # Catégories
    path('categories/', views.categories, name='categories'),
    path('categories/creer/', views.creer_categorie, name='creer_categorie'),
    path('categories/<int:cat_id>/modifier/', views.modifier_categorie, name='modifier_categorie'),
    path('categories/<int:cat_id>/toggle/', views.toggle_categorie, name='toggle_categorie'),
    path('categories/<int:cat_id>/supprimer/', views.supprimer_categorie, name='supprimer_categorie'),

    # Signalements
    path('signalements/', views.signalements, name='signalements'),
    path('signalements/<int:sig_id>/traiter/', views.traiter_signalement, name='traiter_signalement'),

    # Avis
    path('avis/', views.avis, name='avis'),
    path('avis/<int:avis_id>/supprimer/', views.supprimer_avis, name='supprimer_avis'),

    # Posts feed
    path('posts/', views.posts, name='posts'),
    path('posts/<int:post_id>/toggle/', views.toggle_post, name='toggle_post'),
    path('posts/<int:post_id>/supprimer/', views.supprimer_post, name='supprimer_post'),

    # Messagerie
    path('messagerie/', views.messagerie, name='messagerie'),
    path('messagerie/<int:conv_id>/messages/', views.detail_conversation, name='detail_conversation'),
    path('messagerie/<int:conv_id>/signaler-message/', views.signaler_message, name='signaler_message'),
    path('messagerie/ecrire/', views.ecrire_utilisateurs, name='ecrire_utilisateurs'),

    # Wallet plateforme
    path('wallet/', views.wallet_plateforme, name='wallet'),

    # Notifications broadcast
    path('notifications/broadcast/', views.notifications_broadcast, name='notifications_broadcast'),

    # API graphes
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/graphe-commandes/', views.api_graphe_commandes, name='api_graphe_commandes'),
    path('api/graphe-revenus/', views.api_graphe_revenus, name='api_graphe_revenus'),
]