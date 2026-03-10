from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer


def envoyer_notification(destinataire, type_notif, titre, contenu, objet_id=None, objet_type=None):
    Notification.objects.create(
        destinataire=destinataire,
        type=type_notif,
        titre=titre,
        contenu=contenu,
        lien_objet_id=objet_id,
        lien_objet_type=objet_type,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_notifications(request):
    notifications = Notification.objects.filter(
        destinataire=request.user
    ).order_by('-date')
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications_non_lues(request):
    notifications = Notification.objects.filter(
        destinataire=request.user,
        is_read=False
    ).order_by('-date')
    serializer = NotificationSerializer(notifications, many=True)
    return Response({
        'total': notifications.count(),
        'notifications': serializer.data,
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def marquer_lue(request, pk):
    try:
        notification = Notification.objects.get(pk=pk, destinataire=request.user)
        notification.is_read = True
        notification.save()
        return Response({'message': 'Notification marquee comme lue'})
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notification introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def marquer_toutes_lues(request):
    Notification.objects.filter(
        destinataire=request.user,
        is_read=False
    ).update(is_read=True)
    return Response({'message': 'Toutes les notifications marquees comme lues'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_notification(request, pk):
    try:
        notification = Notification.objects.get(pk=pk, destinataire=request.user)
        notification.delete()
        return Response({'message': 'Notification supprimee'})
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notification introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )