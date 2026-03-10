from rest_framework import serializers
from .models import Wallet, Transaction, Payment, Withdrawal


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = '__all__'
        read_only_fields = ['user', 'solde', 'date_creation', 'date_modification']


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = [
            'wallet', 'solde_avant', 'solde_apres', 'date'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = [
            'commission_plateforme', 'montant_prestatire',
            'fedapay_transaction_id', 'date_paiement'
        ]


class PaymentCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    methode = serializers.ChoiceField(choices=[
        'MOBILE_MONEY', 'CARTE', 'WALLET'
    ])
    numero_mobile = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data['methode'] == 'MOBILE_MONEY' and not data.get('numero_mobile'):
            raise serializers.ValidationError(
                'numero_mobile est obligatoire pour Mobile Money'
            )
        return data


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = '__all__'
        read_only_fields = [
            'prestatire', 'statut',
            'date_demande', 'date_traitement'
        ]


class WithdrawalCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = ['montant', 'numero_mobile']

    def validate_montant(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le montant doit etre superieur a 0')
        return value