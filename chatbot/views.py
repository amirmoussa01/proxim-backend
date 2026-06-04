from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .gemini_service import chat_with_groq
import re


def extraire_service_ids(reponse: str) -> list:
    """Extrait les IDs de services depuis les balises [VOIR_SERVICE:ID]."""
    ids = re.findall(r'\[VOIR_SERVICE:(\d+)\]', reponse)
    return [int(i) for i in ids]


def nettoyer_reponse(reponse: str) -> str:
    """Garde les balises lisibles pour Flutter qui les parse."""
    return reponse


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

    historique = historique[-10:]

    reponse = chat_with_groq(message, historique)

    # Extraire les service_ids pour que Flutter puisse afficher des boutons
    service_ids = extraire_service_ids(reponse)

    # Récupérer les données minimales des services cités
    services_cites = []
    if service_ids:
        from services.models import Service
        from services.serializers import ServiceSerializer
        services = Service.objects.filter(
            id__in=service_ids, is_available=True
        ).select_related('prestatire', 'categorie').prefetch_related('images')
        for s in services:
            prix = f"{s.prix_base} {s.devise}" if s.prix_base else "Sur devis"
            image = s.images.filter(is_principale=True).first()
            image_url = image.image.url if image and image.image else None
            services_cites.append({
                'id': s.id,
                'titre': s.titre,
                'prix': prix,
                'localisation': s.localisation or '',
                'categorie': s.categorie.nom if s.categorie else '',
                'prestataire': f"{s.prestatire.prenom} {s.prestatire.nom}".strip(),
                'note': float(s.prestatire.note_moyenne),
                'is_verified': s.prestatire.is_verified,
                'image_url': image_url,
            })

    return Response({
        'reponse': reponse,
        'role': 'model',
        'service_ids': service_ids,
        'services_cites': services_cites,
    }, status=status.HTTP_200_OK)