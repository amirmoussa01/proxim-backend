from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Inscription
    path('inscription/client/', views.inscription_client, name='inscription-client'),
    path('inscription/prestataire/', views.inscription_prestatire, name='inscription-prestataire'),

    # Verification email
    path('verification-email/', views.verification_email, name='verification-email'),

    # Connexion
    path('connexion/', views.connexion, name='connexion'),
    path('connexion/google/', views.connexion_google, name='connexion-google'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('mot-de-passe-oublie/', views.mot_de_passe_oublie),
    path('reinitialisation-mot-de-passe/', views.reinitialisation_mot_de_passe),
    path('changer-mot-de-passe/', views.changer_mot_de_passe, name='changer-mot-de-passe'),
    path('supprimer-compte/', views.supprimer_compte, name='supprimer-compte'),

    # Profil
    path('profil/', views.mon_profil, name='mon-profil'),
    path('profil/modifier/', views.modifier_profil, name='modifier-profil'),

    # Deconnexion
    path('deconnexion/', views.deconnexion, name='deconnexion'),
]