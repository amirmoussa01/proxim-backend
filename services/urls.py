from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path('categories/', views.liste_categories, name='liste-categories'),
    path('categories/creer/', views.creer_categorie, name='creer-categorie'),

    # Services
    path('', views.liste_services, name='liste-services'),
    path('creer/', views.creer_service, name='creer-service'),
    path('mes-services/', views.mes_services, name='mes-services'),
    path('<int:pk>/', views.detail_service, name='detail-service'),
    path('<int:pk>/modifier/', views.modifier_service, name='modifier-service'),
    path('<int:pk>/supprimer/', views.supprimer_service, name='supprimer-service'),

    # Images
    path('<int:pk>/images/ajouter/', views.ajouter_image_service, name='ajouter-image'),
    path('images/<int:pk>/supprimer/', views.supprimer_image_service, name='supprimer-image'),

    # Parametres
    path('<int:pk>/parametres/ajouter/', views.ajouter_parametre, name='ajouter-parametre'),
    path('parametres/<int:pk>/supprimer/', views.supprimer_parametre, name='supprimer-parametre'),
    path('parametres/<int:pk>/options/ajouter/', views.ajouter_option_parametre, name='ajouter-option'),

    # Disponibilites
    path('<int:pk>/disponibilites/ajouter/', views.ajouter_disponibilite, name='ajouter-dispo'),
    path('disponibilites/<int:pk>/supprimer/', views.supprimer_disponibilite, name='supprimer-dispo'),
]