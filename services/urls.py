from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path('categories/', views.liste_categories, name='liste_categories'),
    path('categories/creer/', views.creer_categorie, name='creer_categorie'),

    # Services
    path('', views.liste_services, name='liste_services'),
    path('creer/', views.creer_service, name='creer_service'),
    path('mes-services/', views.mes_services, name='mes_services'),
    path('<int:pk>/', views.detail_service, name='detail_service'),
    path('<int:pk>/modifier/', views.modifier_service, name='modifier_service'),
    path('<int:pk>/supprimer/', views.supprimer_service, name='supprimer_service'),

    # Images d'un service (gestion individuelle)
    path('<int:pk>/images/', views.images_service, name='images_service'),
    path('<int:pk>/images/ajouter/', views.ajouter_image_service, name='ajouter_image_service'),
    path('<int:pk>/images/reordonner/', views.reordonner_images_service, name='reordonner_images_service'),

    # Image individuelle (pk = ID de l'image)
    path('images/<int:pk>/supprimer/', views.supprimer_image_service, name='supprimer_image_service'),
    path('images/<int:pk>/principale/', views.definir_image_principale, name='definir_image_principale'),

    # Parametres
    path('<int:pk>/parametres/ajouter/', views.ajouter_parametre, name='ajouter_parametre'),
    path('parametres/<int:pk>/modifier/', views.modifier_parametre, name='modifier_parametre'),
    path('parametres/<int:pk>/supprimer/', views.supprimer_parametre, name='supprimer_parametre'),
    path('parametres/<int:pk>/options/ajouter/', views.ajouter_option_parametre, name='ajouter_option_parametre'),

    # Disponibilites
    path('<int:pk>/disponibilites/', views.disponibilites_service, name='disponibilites_service'),
    path('<int:pk>/disponibilites/ajouter/', views.ajouter_disponibilite, name='ajouter_disponibilite'),
    path('disponibilites/<int:pk>/modifier/', views.modifier_disponibilite, name='modifier_disponibilite'),
    path('disponibilites/<int:pk>/supprimer/', views.supprimer_disponibilite, name='supprimer_disponibilite'),
]