from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Order, OrderStatusHistory, Negotiation
from .serializers import (
    OrderSerializer,
    OrderCreateSerializer,
    OrderUpdateStatutSerializer,
    NegotiationSerializer,
    NegotiationCreateSerializer,
)
from notifications.utils import (
    notif_commande_recue,
    notif_commande_acceptee,
    notif_commande_terminee,
    notif_commande_annulee,
    notif_nouveau_statut,
    notif_nouvelle_negociation,
)


# ─── COMMANDES ────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def creer_commande(request):
    if not request.user.is_client:
        return Response(
            {'error': 'Seuls les clients peuvent passer des commandes'},
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        client = request.user.client_profile
    except Exception:
        return Response(
            {'error': 'Profil client introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = OrderCreateSerializer(data=request.data)
    if serializer.is_valid():
        service = serializer.validated_data['service']
        order = serializer.save(
            client=client,
            prestatire=service.prestatire,
            statut=Order.STATUT_NEGOCIATION,
        )
        OrderStatusHistory.objects.create(
            order=order,
            statut=Order.STATUT_NEGOCIATION,
            changed_by=request.user,
            commentaire='Commande creee',
        )
        notif_commande_recue(order)
        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_commandes(request):
    user = request.user

    if user.is_client:
        try:
            commandes = Order.objects.filter(
                client=user.client_profile
            ).select_related(
                'service', 'prestatire'
            ).prefetch_related('negotiations', 'historique_statuts')
        except Exception:
            return Response(
                {'error': 'Profil client introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )

    elif user.is_prestataire:
        try:
            commandes = Order.objects.filter(
                prestatire=user.prestatire_profile
            ).select_related(
                'service', 'client'
            ).prefetch_related('negotiations', 'historique_statuts')
        except Exception:
            return Response(
                {'error': 'Profil prestataire introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )
    else:
        return Response(
            {'error': 'Acces refuse'},
            status=status.HTTP_403_FORBIDDEN
        )

    statut = request.query_params.get('statut')
    if statut:
        commandes = commandes.filter(statut=statut)

    serializer = OrderSerializer(commandes, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detail_commande(request, pk):
    user = request.user

    try:
        if user.is_client:
            order = Order.objects.get(pk=pk, client=user.client_profile)
        elif user.is_prestataire:
            order = Order.objects.get(pk=pk, prestatire=user.prestatire_profile)
        else:
            return Response(
                {'error': 'Acces refuse'},
                status=status.HTTP_403_FORBIDDEN
            )
    except Order.DoesNotExist:
        return Response(
            {'error': 'Commande introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = OrderSerializer(order)
    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def changer_statut_commande(request, pk):
    user = request.user

    try:
        if user.is_client:
            order = Order.objects.get(pk=pk, client=user.client_profile)
        elif user.is_prestataire:
            order = Order.objects.get(pk=pk, prestatire=user.prestatire_profile)
        else:
            return Response(
                {'error': 'Acces refuse'},
                status=status.HTTP_403_FORBIDDEN
            )
    except Order.DoesNotExist:
        return Response(
            {'error': 'Commande introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = OrderUpdateStatutSerializer(data=request.data)
    if serializer.is_valid():
        nouveau_statut = serializer.validated_data['statut']
        commentaire = serializer.validated_data.get('commentaire', '')

        # Verifications des transitions de statut
        transitions_client = {
            Order.STATUT_NEGOCIATION: [Order.STATUT_ANNULE],
            Order.STATUT_ACCEPTE: [Order.STATUT_ANNULE],
        }
        transitions_prestatire = {
            Order.STATUT_NEGOCIATION: [Order.STATUT_ACCEPTE, Order.STATUT_ANNULE],
            Order.STATUT_ACCEPTE: [Order.STATUT_EN_COURS, Order.STATUT_ANNULE],
            Order.STATUT_EN_COURS: [Order.STATUT_TERMINE, Order.STATUT_ANNULE],
        }

        if user.is_client:
            transitions = transitions_client
        else:
            transitions = transitions_prestatire

        statuts_autorises = transitions.get(order.statut, [])
        if nouveau_statut not in statuts_autorises:
            return Response(
                {'error': f'Transition {order.statut} → {nouveau_statut} non autorisee'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.statut = nouveau_statut
        order.save()

        OrderStatusHistory.objects.create(
            order=order,
            statut=nouveau_statut,
            changed_by=user,
            commentaire=commentaire,
        )
        if nouveau_statut == Order.STATUT_ACCEPTE:
            notif_commande_acceptee(order)
        elif nouveau_statut == Order.STATUT_TERMINE:
            notif_commande_terminee(order)
        elif nouveau_statut == Order.STATUT_ANNULE:
            notif_commande_annulee(order, annule_par=user)
        else:
            notif_nouveau_statut(order, nouveau_statut)

        return Response(OrderSerializer(order).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def definir_prix_final(request, pk):
    if not request.user.is_prestataire:
        return Response(
            {'error': 'Seul le prestataire peut definir le prix final'},
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        order = Order.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Commande introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    prix_final = request.data.get('prix_final')
    if not prix_final:
        return Response(
            {'error': 'prix_final est obligatoire'},
            status=status.HTTP_400_BAD_REQUEST
        )

    order.prix_final = prix_final
    order.save()
    return Response(OrderSerializer(order).data)


# ─── NEGOCIATION ──────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def envoyer_negociation(request, pk):
    user = request.user

    try:
        if user.is_client:
            order = Order.objects.get(pk=pk, client=user.client_profile)
        elif user.is_prestataire:
            order = Order.objects.get(pk=pk, prestatire=user.prestatire_profile)
        else:
            return Response(
                {'error': 'Acces refuse'},
                status=status.HTTP_403_FORBIDDEN
            )
    except Order.DoesNotExist:
        return Response(
            {'error': 'Commande introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    if order.statut != Order.STATUT_NEGOCIATION:
        return Response(
            {'error': 'La negociation est fermee pour cette commande'},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = NegotiationCreateSerializer(data=request.data)
    if serializer.is_valid():
        negociation = serializer.save(order=order, expediteur=user)
        notif_nouvelle_negociation(negociation)
        return Response(
            NegotiationSerializer(negociation).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def liste_negotiations(request, pk):
    user = request.user

    try:
        if user.is_client:
            order = Order.objects.get(pk=pk, client=user.client_profile)
        elif user.is_prestataire:
            order = Order.objects.get(pk=pk, prestatire=user.prestatire_profile)
        else:
            return Response(
                {'error': 'Acces refuse'},
                status=status.HTTP_403_FORBIDDEN
            )
    except Order.DoesNotExist:
        return Response(
            {'error': 'Commande introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    negotiations = order.negotiations.all()
    serializer = NegotiationSerializer(negotiations, many=True)
    return Response(serializer.data)