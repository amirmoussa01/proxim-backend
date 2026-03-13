from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.utils import timezone
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    MessageCreateSerializer,
)
from notifications.utils import notif_nouveau_message

# ─── CONVERSATIONS ────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_conversations(request):
    user = request.user

    if user.is_client:
        try:
            conversations = Conversation.objects.filter(
                client=user.client_profile
            ).prefetch_related('messages').select_related('prestatire')
        except Exception:
            return Response(
                {'error': 'Profil client introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )

    elif user.is_prestataire:
        try:
            conversations = Conversation.objects.filter(
                prestatire=user.prestatire_profile
            ).prefetch_related('messages').select_related('client')
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

    serializer = ConversationSerializer(
        conversations, many=True, context={'request': request}
    )
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def creer_ou_ouvrir_conversation(request):
    if not request.user.is_client:
        return Response(
            {'error': 'Seul un client peut initier une conversation'},
            status=status.HTTP_403_FORBIDDEN
        )

    prestatire_id = request.data.get('prestatire_id')
    order_id = request.data.get('order_id', None)

    if not prestatire_id:
        return Response(
            {'error': 'prestatire_id est obligatoire'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        from accounts.models import PrestatireProfile
        prestatire = PrestatireProfile.objects.get(pk=prestatire_id)
        client = request.user.client_profile
    except Exception:
        return Response(
            {'error': 'Prestataire introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    conversation, created = Conversation.objects.get_or_create(
        client=client,
        prestatire=prestatire,
    )

    if order_id and not conversation.order:
        try:
            from orders.models import Order
            order = Order.objects.get(pk=order_id)
            conversation.order = order
            conversation.save()
        except Exception:
            pass

    serializer = ConversationSerializer(conversation, context={'request': request})
    return Response(
        serializer.data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


# ─── MESSAGES ─────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def messages_conversation(request, pk):
    user = request.user

    try:
        if user.is_client:
            conversation = Conversation.objects.get(pk=pk, client=user.client_profile)
        elif user.is_prestataire:
            conversation = Conversation.objects.get(pk=pk, prestatire=user.prestatire_profile)
        else:
            return Response(
                {'error': 'Acces refuse'},
                status=status.HTTP_403_FORBIDDEN
            )
    except Conversation.DoesNotExist:
        return Response(
            {'error': 'Conversation introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Marquer les messages comme lus
    conversation.messages.filter(
        is_read=False
    ).exclude(expediteur=user).update(is_read=True)

    messages = conversation.messages.all()
    serializer = MessageSerializer(messages, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def envoyer_message(request, pk):
    user = request.user

    try:
        if user.is_client:
            conversation = Conversation.objects.get(pk=pk, client=user.client_profile)
        elif user.is_prestataire:
            conversation = Conversation.objects.get(pk=pk, prestatire=user.prestatire_profile)
        else:
            return Response(
                {'error': 'Acces refuse'},
                status=status.HTTP_403_FORBIDDEN
            )
    except Conversation.DoesNotExist:
        return Response(
            {'error': 'Conversation introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = MessageCreateSerializer(data=request.data)
    if serializer.is_valid():
        message = serializer.save(
            conversation=conversation,
            expediteur=user,
        )
        # Sécurisé — ne bloque pas si la notif plante
        try:
            notif_nouveau_message(message)
        except Exception:
            pass
        conversation.dernier_message_date = timezone.now()
        conversation.save()
        return Response(
            MessageSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_message(request, pk):
    try:
        message = Message.objects.get(pk=pk, expediteur=request.user)
    except Message.DoesNotExist:
        return Response(
            {'error': 'Message introuvable ou non autorise'},
            status=status.HTTP_404_NOT_FOUND
        )

    message.is_deleted = True
    message.date_suppression = timezone.now()
    message.save()

    return Response(
        {'message': 'Message supprime'},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def total_non_lus(request):
    user = request.user

    if user.is_client:
        try:
            conversations = Conversation.objects.filter(client=user.client_profile)
        except Exception:
            return Response({'total': 0})
    elif user.is_prestataire:
        try:
            conversations = Conversation.objects.filter(prestatire=user.prestatire_profile)
        except Exception:
            return Response({'total': 0})
    else:
        return Response({'total': 0})

    total = Message.objects.filter(
        conversation__in=conversations,
        is_read=False,
        is_deleted=False,
    ).exclude(expediteur=user).count()

    return Response({'total_non_lus': total})