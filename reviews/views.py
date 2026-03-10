from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Avg
from .models import Review
from .serializers import ReviewSerializer, ReviewCreateSerializer
from django.db.models import Avg, Count
from notifications.utils import notif_nouvel_avis

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def creer_avis(request):
    if not request.user.is_client:
        return Response(
            {'error': 'Seuls les clients peuvent laisser un avis'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = ReviewCreateSerializer(data=request.data)
    if serializer.is_valid():
        order = serializer.validated_data['order']

        if order.client != request.user.client_profile:
            return Response(
                {'error': 'Vous ne pouvez noter que vos propres commandes'},
                status=status.HTTP_403_FORBIDDEN
            )

        review = serializer.save(
            client=request.user.client_profile,
            prestatire=order.prestatire,
        )

        # Mettre a jour note moyenne prestatire
        prestatire = order.prestatire
        stats = Review.objects.filter(prestatire=prestatire).aggregate(
            moyenne=Avg('note'), total=Count('id')
        )
        notif_nouvel_avis(review)
        prestatire.note_moyenne = stats['moyenne'] or 0
        prestatire.nombre_avis = stats['total'] or 0
        prestatire.save()

        return Response(
            ReviewSerializer(review).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def avis_prestatire(request, pk):
    from accounts.models import PrestatireProfile
    try:
        prestatire = PrestatireProfile.objects.get(pk=pk)
    except PrestatireProfile.DoesNotExist:
        return Response(
            {'error': 'Prestataire introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    avis = Review.objects.filter(
        prestatire=prestatire
    ).select_related('client')
    serializer = ReviewSerializer(avis, many=True)
    return Response({
        'note_moyenne': prestatire.note_moyenne,
        'nombre_avis': prestatire.nombre_avis,
        'avis': serializer.data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_avis(request):
    if request.user.is_client:
        avis = Review.objects.filter(client=request.user.client_profile)
    elif request.user.is_prestataire:
        avis = Review.objects.filter(prestatire=request.user.prestatire_profile)
    else:
        return Response(
            {'error': 'Acces refuse'},
            status=status.HTTP_403_FORBIDDEN
        )
    serializer = ReviewSerializer(avis, many=True)
    return Response(serializer.data)