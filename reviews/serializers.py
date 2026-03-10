from rest_framework import serializers
from .models import Review
from accounts.serializers import ClientProfileSerializer, PrestatireProfileSerializer


class ReviewSerializer(serializers.ModelSerializer):
    client_detail = ClientProfileSerializer(source='client', read_only=True)
    prestatire_detail = PrestatireProfileSerializer(source='prestatire', read_only=True)

    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['client', 'prestatire', 'date']


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['order', 'note', 'commentaire']

    def validate_note(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('La note doit etre entre 1 et 5')
        return value

    def validate_order(self, value):
        if value.statut != 'TERMINE':
            raise serializers.ValidationError(
                'Vous ne pouvez noter que les commandes terminees'
            )
        if hasattr(value, 'review'):
            raise serializers.ValidationError(
                'Vous avez deja note cette commande'
            )
        return value