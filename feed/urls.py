from django.urls import path
from . import views

urlpatterns = [
    # Posts
    path('', views.liste_posts, name='liste-posts'),
    path('creer/', views.creer_post, name='creer-post'),
    path('<int:pk>/', views.detail_post, name='detail-post'),
    path('<int:pk>/supprimer/', views.supprimer_post, name='supprimer-post'),

    # Images
    path('<int:pk>/images/ajouter/', views.ajouter_image_post, name='ajouter-image-post'),

    # Likes
    path('<int:pk>/like/', views.toggle_like, name='toggle-like'),

    # Commentaires
    path('<int:pk>/commenter/', views.ajouter_commentaire, name='ajouter-commentaire'),
    path('commentaires/<int:pk>/supprimer/', views.supprimer_commentaire, name='supprimer-commentaire'),

    # Favoris
    path('favoris/', views.mes_favoris, name='mes-favoris'),
    path('favoris/toggle/', views.toggle_favori, name='toggle-favori'),
]