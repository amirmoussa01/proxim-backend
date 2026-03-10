from django.urls import path
from . import views

urlpatterns = [
    # Conversations
    path('conversations/', views.mes_conversations, name='mes-conversations'),
    path('conversations/creer/', views.creer_ou_ouvrir_conversation, name='creer-conversation'),

    # Messages
    path('conversations/<int:pk>/messages/', views.messages_conversation, name='messages-conversation'),
    path('conversations/<int:pk>/envoyer/', views.envoyer_message, name='envoyer-message'),
    path('messages/<int:pk>/supprimer/', views.supprimer_message, name='supprimer-message'),

    # Non lus
    path('non-lus/', views.total_non_lus, name='total-non-lus'),
]