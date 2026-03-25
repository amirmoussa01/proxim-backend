from rest_framework import serializers
from .models import Order, OrderStatusHistory, Negotiation
from accounts.serializers import ClientProfileSerializer, PrestatireProfileSerializer
from services.serializers import ServiceSerializer


class NegotiationSerializer(serializers.ModelSerializer):
    expediteur_email = serializers.CharField(source='expediteur.email', read_only=True)

    class Meta:
        model = Negotiation
        fields = '__all__'
        read_only_fields = ['expediteur', 'date']


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.CharField(source='changed_by.email', read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
    negotiations = NegotiationSerializer(many=True, read_only=True)
    historique_statuts = OrderStatusHistorySerializer(many=True, read_only=True)
    client_detail = ClientProfileSerializer(source='client', read_only=True)
    prestatire_detail = PrestatireProfileSerializer(source='prestatire', read_only=True)
    service_detail = ServiceSerializer(source='service', read_only=True)
    review = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()

    def get_review(self, obj):
        if hasattr(obj, 'review'):
            return {
                'id': obj.review.id,
                'note': obj.review.note,
                'commentaire': obj.review.commentaire,
            }
        return None

    def get_payment(self, obj):
        if hasattr(obj, 'payment'):
            return {
                'id': obj.payment.id,
                'statut': obj.payment.statut,
                'montant_total': str(obj.payment.montant_total),
            }
        return None

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = [
            'client', 'prestatire', 'statut',
            'prix_final', 'date_commande'
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'service', 'prix_propose',
            'parametres_choisis', 'notes_client',
            'date_debut_prevue', 'date_fin_prevue'
        ]


class OrderUpdateStatutSerializer(serializers.Serializer):
    statut = serializers.ChoiceField(choices=[
        'EN_NEGOCIATION', 'ACCEPTE', 'EN_COURS', 'TERMINE', 'ANNULE'
    ])
    commentaire = serializers.CharField(required=False, allow_blank=True)


class NegotiationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Negotiation
        fields = ['message', 'prix_propose']