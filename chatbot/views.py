from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .gemini_service import chat_with_gemini


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chatbot_message(request):
    message = request.data.get('message', '').strip()
    historique = request.data.get('historique', [])

    if not message:
        return Response(
            {'error': 'Message vide'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(message) > 500:
        return Response(
            {'error': 'Message trop long (max 500 caractères)'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Limiter l'historique aux 10 derniers échanges
    historique = historique[-10:]

    reponse = chat_with_gemini(message, historique)

    return Response({
        'reponse': reponse,
        'role': 'model',
    }, status=status.HTTP_200_OK)