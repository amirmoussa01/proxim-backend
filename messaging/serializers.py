from rest_framework import serializers
from .models import Conversation, Message
from accounts.serializers import ClientProfileSerializer, PrestatireProfileSerializer


class MessageSerializer(serializers.ModelSerializer):
    expediteur_email = serializers.CharField(source='expediteur.email', read_only=True)
    contenu_affiche = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = '__all__'
        read_only_fields = ['expediteur', 'conversation', 'date_envoi', 'is_deleted']

    def get_contenu_affiche(self, obj):
        if obj.is_deleted:
            return 'Message supprime'
        return obj.contenu


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['contenu', 'image']

    def validate(self, data):
        if not data.get('contenu') and not data.get('image'):
            raise serializers.ValidationError(
                'Un message doit contenir du texte ou une image'
            )
        return data


class ConversationSerializer(serializers.ModelSerializer):
    client_detail = ClientProfileSerializer(source='client', read_only=True)
    prestatire_detail = PrestatireProfileSerializer(source='prestatire', read_only=True)
    dernier_message = serializers.SerializerMethodField()
    messages_non_lus = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = '__all__'

    def get_dernier_message(self, obj):
        dernier = obj.messages.filter(is_deleted=False).last()
        if dernier:
            return MessageSerializer(dernier).data
        return None

    def get_messages_non_lus(self, obj):
        user = self.context.get('request').user
        return obj.messages.filter(is_read=False, is_deleted=False).exclude(
            expediteur=user
        ).count()