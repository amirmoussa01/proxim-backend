from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction as db_transaction
from django.conf import settings
from .models import Wallet, Transaction, Payment, Withdrawal
from .serializers import (
    WalletSerializer,
    TransactionSerializer,
    PaymentSerializer,
    PaymentCreateSerializer,
    WithdrawalSerializer,
    WithdrawalCreateSerializer,
)
from orders.models import Order
from notifications.utils import notif_paiement_recu, notif_retrait_traite

COMMISSION_TAUX = 0.10


def get_or_create_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def crediter_wallet(user, montant, description):
    wallet = get_or_create_wallet(user)
    solde_avant = wallet.solde
    wallet.solde += montant
    wallet.save()
    Transaction.objects.create(
        wallet=wallet,
        type='CREDIT',
        montant=montant,
        solde_avant=solde_avant,
        solde_apres=wallet.solde,
        description=description,
    )
    return wallet


def debiter_wallet(user, montant, description):
    wallet = get_or_create_wallet(user)
    if wallet.solde < montant:
        return None, 'Solde insuffisant'
    solde_avant = wallet.solde
    wallet.solde -= montant
    wallet.save()
    Transaction.objects.create(
        wallet=wallet,
        type='DEBIT',
        montant=montant,
        solde_avant=solde_avant,
        solde_apres=wallet.solde,
        description=description,
    )
    return wallet, None


# ─── WALLET ───────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mon_wallet(request):
    wallet = get_or_create_wallet(request.user)
    serializer = WalletSerializer(wallet)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def historique_transactions(request):
    wallet = get_or_create_wallet(request.user)
    transactions = wallet.transactions.all().order_by('-date')
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


# ─── PAIEMENTS ────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initier_paiement(request):
    if not request.user.is_client:
        return Response(
            {'error': 'Seuls les clients peuvent effectuer un paiement'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = PaymentCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    order_id = serializer.validated_data['order_id']
    methode = serializer.validated_data['methode']
    numero_mobile = serializer.validated_data.get('numero_mobile', '')

    try:
        order = Order.objects.get(
            pk=order_id,
            client=request.user.client_profile,
            statut=Order.STATUT_ACCEPTE,
        )
    except Order.DoesNotExist:
        return Response(
            {'error': 'Commande introuvable ou non eligible au paiement'},
            status=status.HTTP_404_NOT_FOUND
        )

    if hasattr(order, 'payment'):
        return Response(
            {'error': 'Cette commande a deja un paiement'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not order.prix_final:
        return Response(
            {'error': 'Le prix final n a pas encore ete defini'},
            status=status.HTTP_400_BAD_REQUEST
        )

    montant_total = order.prix_final
    commission = round(montant_total * COMMISSION_TAUX, 2)
    montant_prestatire = montant_total - commission

    with db_transaction.atomic():
        if methode == 'WALLET':
            wallet, erreur = debiter_wallet(
                request.user,
                montant_total,
                f'Paiement commande #{order.id}'
            )
            if erreur:
                return Response(
                    {'error': erreur},
                    status=status.HTTP_400_BAD_REQUEST
                )

            payment = Payment.objects.create(
                order=order,
                client=request.user.client_profile,
                montant_total=montant_total,
                commission_plateforme=commission,
                montant_prestatire=montant_prestatire,
                methode=methode,
                statut='SUCCES',
            )

            crediter_wallet(
                order.prestatire.user,
                montant_prestatire,
                f'Paiement recu commande #{order.id}'
            )
            notif_paiement_recu(payment)

            order.statut = Order.STATUT_EN_COURS
            order.save()

            return Response({
                'message': 'Paiement effectue avec succes via Wallet',
                'payment': PaymentSerializer(payment).data,
            }, status=status.HTTP_201_CREATED)

        elif methode == 'MOBILE_MONEY':
            # Fedapay sandbox
            fedapay_response = initier_fedapay(
                montant=int(montant_total),
                numero=numero_mobile,
                description=f'Proxim - Commande #{order.id}',
            )

            payment = Payment.objects.create(
                order=order,
                client=request.user.client_profile,
                montant_total=montant_total,
                commission_plateforme=commission,
                montant_prestatire=montant_prestatire,
                methode=methode,
                statut='EN_ATTENTE',
                fedapay_transaction_id=fedapay_response.get('id', ''),
            )

            return Response({
                'message': 'Paiement Mobile Money initie',
                'payment': PaymentSerializer(payment).data,
                'fedapay': fedapay_response,
            }, status=status.HTTP_201_CREATED)

    return Response(
        {'error': 'Methode de paiement non supportee'},
        status=status.HTTP_400_BAD_REQUEST
    )


def initier_fedapay(montant, numero, description):
    # Sandbox Fedapay - on simule la reponse pour le dev
    return {
        'id': f'sandbox_{montant}_{numero}',
        'status': 'pending',
        'montant': montant,
        'numero': numero,
        'description': description,
        'message': 'Paiement Fedapay sandbox initie avec succes',
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirmer_paiement_fedapay(request):
    transaction_id = request.data.get('transaction_id')
    if not transaction_id:
        return Response(
            {'error': 'transaction_id est obligatoire'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        payment = Payment.objects.get(fedapay_transaction_id=transaction_id)
    except Payment.DoesNotExist:
        return Response(
            {'error': 'Paiement introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    with db_transaction.atomic():
        payment.statut = 'SUCCES'
        payment.save()

        crediter_wallet(
            payment.order.prestatire.user,
            payment.montant_prestatire,
            f'Paiement recu commande #{payment.order.id}'
        )
        notif_paiement_recu(payment)

        payment.order.statut = Order.STATUT_EN_COURS
        payment.order.save()

    return Response({
        'message': 'Paiement confirme avec succes',
        'payment': PaymentSerializer(payment).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def historique_paiements(request):
    if request.user.is_client:
        try:
            paiements = Payment.objects.filter(
                client=request.user.client_profile
            ).order_by('-date_paiement')
        except Exception:
            return Response([], status=status.HTTP_200_OK)
    elif request.user.is_prestataire:
        try:
            paiements = Payment.objects.filter(
                order__prestatire=request.user.prestatire_profile
            ).order_by('-date_paiement')
        except Exception:
            return Response([], status=status.HTTP_200_OK)
    else:
        return Response(
            {'error': 'Acces refuse'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = PaymentSerializer(paiements, many=True)
    return Response(serializer.data)


# ─── RETRAITS ─────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def demander_retrait(request):
    if not request.user.is_prestataire:
        return Response(
            {'error': 'Seuls les prestataires peuvent demander un retrait'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = WithdrawalCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    montant = serializer.validated_data['montant']
    wallet = get_or_create_wallet(request.user)

    if wallet.solde < montant:
        return Response(
            {'error': f'Solde insuffisant. Solde actuel : {wallet.solde} FCFA'},
            status=status.HTTP_400_BAD_REQUEST
        )

    with db_transaction.atomic():
        debiter_wallet(
            request.user,
            montant,
            f'Demande de retrait #{montant} FCFA'
        )

        retrait = Withdrawal.objects.create(
            prestatire=request.user.prestatire_profile,
            montant=montant,
            numero_mobile=serializer.validated_data['numero_mobile'],
            statut='EN_ATTENTE',
        )
        # Note: notif_retrait_traite sera appelée par l'admin quand il traite le retrait
    return Response({
        'message': 'Demande de retrait soumise avec succes',
        'retrait': WithdrawalSerializer(retrait).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def historique_retraits(request):
    if not request.user.is_prestataire:
        return Response(
            {'error': 'Acces refuse'},
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        retraits = Withdrawal.objects.filter(
            prestatire=request.user.prestatire_profile
        ).order_by('-date_demande')
        serializer = WithdrawalSerializer(retraits, many=True)
        return Response(serializer.data)
    except Exception:
        return Response([], status=status.HTTP_200_OK)