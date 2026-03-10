from django.urls import path
from . import views

urlpatterns = [
    path('', views.mes_notifications, name='mes-notifications'),
    path('non-lues/', views.notifications_non_lues, name='notifications-non-lues'),
    path('<int:pk>/lue/', views.marquer_lue, name='marquer-lue'),
    path('toutes-lues/', views.marquer_toutes_lues, name='toutes-lues'),
    path('<int:pk>/supprimer/', views.supprimer_notification, name='supprimer-notification'),
]