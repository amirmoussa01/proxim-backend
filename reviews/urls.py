from django.urls import path
from . import views

urlpatterns = [
    path('creer/', views.creer_avis, name='creer-avis'),
    path('mes-avis/', views.mes_avis, name='mes-avis'),
    path('prestataire/<int:pk>/', views.avis_prestatire, name='avis-prestataire'),
]