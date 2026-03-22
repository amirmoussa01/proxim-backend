from django.urls import path
from . import views

urlpatterns = [
    # Favoris services
    path('favoris/services/toggle/', views.toggle_favori_service),
    path('favoris/services/', views.mes_favoris_services),

    # Posts
    path('', views.liste_posts),
    path('posts/<int:pk>/', views.detail_post),
    path('creer/', views.creer_post),
    path('posts/<int:pk>/supprimer/', views.supprimer_post),
    path('posts/<int:pk>/images/', views.ajouter_image_post),
    path('posts/<int:pk>/like/', views.toggle_like),
    path('posts/<int:pk>/commentaires/', views.ajouter_commentaire),
    path('commentaires/<int:pk>/supprimer/', views.supprimer_commentaire),

    # Favoris prestataires
    path('favoris/toggle/', views.toggle_favori),
    path('favoris/', views.mes_favoris),
]