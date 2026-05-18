from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction as db_transaction
from decimal import Decimal
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


COMMISSION_TAUX = Decimal('0.05')


def get_or_create_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def crediter_wallet(user, montant, description):
    wallet = get_or_create_wallet(user)
    solde_avant = wallet.solde
    wallet.solde += Decimal(str(montant))
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
    if wallet.solde < Decimal(str(montant)):
        return None, 'Solde insuffisant'
    solde_avant = wallet.solde
    wallet.solde -= Decimal(str(montant))
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
    transactions = wallet.transactions.all()[:20]
    return Response({
        'solde': str(wallet.solde),
        'devise': wallet.devise,
        'transactions': [
            {
                'id': t.id,
                'type': t.type,
                'montant': str(t.montant),
                'solde_avant': str(t.solde_avant),
                'solde_apres': str(t.solde_apres),
                'description': t.description,
                'date': t.date.isoformat(),
            }
            for t in transactions
        ],
    })


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
                fonds_bloques=True,  # ← fonds bloqués, pas encore virés
            )

            # ← SUPPRIMÉ : crediter_wallet immédiat vers prestataire
            # Le virement se fait uniquement après validation admin

            order.statut = Order.STATUT_EN_COURS
            order.save()

            try:
                notif_paiement_recu(payment)
            except Exception:
                pass

            return Response({
                'message': 'Paiement effectue avec succes via Wallet. Fonds en attente de validation.',
                'payment_id': payment.id,
            }, status=status.HTTP_201_CREATED)

    return Response(
        {'error': 'Methode de paiement non supportee'},
        status=status.HTTP_400_BAD_REQUEST
    )


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
        payment.fonds_bloques = True  # ← fonds bloqués
        payment.save()

        # ← SUPPRIMÉ : crediter_wallet immédiat vers prestataire

        payment.order.statut = Order.STATUT_EN_COURS
        payment.order.save()

    try:
        notif_paiement_recu(payment)
    except Exception:
        pass

    return Response({
        'message': 'Paiement confirme. Fonds en attente de validation admin.',
        'payment_id': payment.id,
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirmer_paiement_kkiapay(request):
    if not request.user.is_client:
        return Response(
            {'error': 'Seuls les clients peuvent payer'},
            status=status.HTTP_403_FORBIDDEN
        )

    order_id = request.data.get('order_id')
    montant = request.data.get('montant')
    transaction_id = request.data.get('transaction_id')

    if not order_id or not montant:
        return Response(
            {'error': 'order_id et montant requis'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        order = Order.objects.get(
            id=order_id,
            client=request.user.client_profile,
        )
    except Order.DoesNotExist:
        return Response(
            {'error': 'Commande introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    if hasattr(order, 'payment') and order.payment.statut == 'SUCCES':
        return Response(
            {'message': 'Commande deja payee'},
            status=status.HTTP_200_OK
        )

    try:
        montant_decimal = Decimal(str(montant))
    except Exception:
        return Response(
            {'error': 'Montant invalide'},
            status=status.HTTP_400_BAD_REQUEST
        )

    commission = round(montant_decimal * COMMISSION_TAUX, 2)
    montant_prestataire = round(montant_decimal - commission, 2)

    with db_transaction.atomic():
        payment, _ = Payment.objects.update_or_create(
            order=order,
            defaults={
                'client': request.user.client_profile,
                'montant_total': montant_decimal,
                'commission_plateforme': commission,
                'montant_prestatire': montant_prestataire,
                'methode': 'MOBILE_MONEY',
                'statut': 'SUCCES',
                'fonds_bloques': True,  # ← fonds bloqués, pas encore virés
                'fedapay_transaction_id': str(transaction_id or ''),
            }
        )

        # ← SUPPRIMÉ : crediter_wallet immédiat vers prestataire
        # L'admin déclenchera le virement après validation de fin de service

        order.statut = Order.STATUT_EN_COURS
        order.save()

    try:
        notif_paiement_recu(payment)
    except Exception:
        pass

    return Response({
        'message': 'Paiement confirme ! Fonds en attente de validation admin.',
        'payment_id': payment.id,
        'statut': payment.statut,
    }, status=status.HTTP_201_CREATED)