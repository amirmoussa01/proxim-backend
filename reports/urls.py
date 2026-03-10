from django.urls import path
from . import views

urlpatterns = [
    path('creer/', views.creer_signalement, name='creer-signalement'),
    path('mes-signalements/', views.mes_signalements, name='mes-signalements'),
]