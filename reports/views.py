from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Report
from .serializers import ReportSerializer, ReportCreateSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def creer_signalement(request):
    serializer = ReportCreateSerializer(
        data=request.data,
        context={'request': request}
    )
    if serializer.is_valid():
        signalement = serializer.save(reporter=request.user)
        return Response(
            ReportSerializer(signalement).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_signalements(request):
    signalements = Report.objects.filter(
        reporter=request.user
    ).order_by('-date')
    serializer = ReportSerializer(signalements, many=True)
    return Response(serializer.data)