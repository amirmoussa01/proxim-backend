from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.db.models import Q
import math
from .models import Category, Service, ServiceImage, ServiceParameter, ServiceParameterOption, Availability
from .serializers import (
    CategorySerializer,
    ServiceSerializer,
    ServiceCreateSerializer,
    ServiceImageSerializer,
    ServiceParameterSerializer,
    ServiceParameterOptionSerializer,
    AvailabilitySerializer,
)


# ─── UTILITAIRE DISTANCE ──────────────────────────────────────

def calculer_distance_km(lat1, lon1, lat2, lon2):
    """Calcul distance Haversine entre deux points GPS en km"""
    R = 6371  # Rayon terre en km
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return round(R * c, 1)


# ─── CATEGORIES ───────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def liste_categories(request):
    categories = Category.objects.filter(is_active=True)
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def creer_categorie(request):
    if not request.user.is_staff:
        return Response(
            {'error': 'Permission refusee'},
            status=status.HTTP_403_FORBIDDEN
        )
    serializer = CategorySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── SERVICES ─────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def liste_services(request):
    services = Service.objects.filter(is_available=True).select_related(
        'prestatire', 'categorie'
    ).prefetch_related('images', 'parametres__options', 'disponibilites')

    categorie = request.query_params.get('categorie')
    prix_min = request.query_params.get('prix_min')
    prix_max = request.query_params.get('prix_max')
    recherche = request.query_params.get('q')
    sponsorise = request.query_params.get('sponsorise')
    # ← Nouveaux paramètres distance
    lat_client = request.query_params.get('lat')
    lon_client = request.query_params.get('lon')
    distance_max = request.query_params.get('distance_max')  # en km

    if categorie:
        services = services.filter(categorie__id=categorie)
    if prix_min:
        services = services.filter(prix_base__gte=prix_min)
    if prix_max:
        services = services.filter(prix_base__lte=prix_max)
    if recherche:
        services = services.filter(
            Q(titre__icontains=recherche) |
            Q(description__icontains=recherche) |
            Q(categorie__nom__icontains=recherche)
        )
    if sponsorise:
        services = services.filter(is_sponsored=True)

    # Sérialiser avec distance si position fournie
    services_data = []
    for service in services:
        data = ServiceSerializer(service).data

        # Calculer distance si position client fournie
        if lat_client and lon_client:
            # Utiliser lat/lon du service si dispo, sinon celle du prestataire
            s_lat = service.latitude or (
                service.prestatire.latitude if service.prestatire.latitude else None
            )
            s_lon = service.longitude or (
                service.prestatire.longitude if service.prestatire.longitude else None
            )

            if s_lat and s_lon:
                distance = calculer_distance_km(
                    lat_client, lon_client, s_lat, s_lon
                )
                data['distance_km'] = distance

                # Filtrer par distance max si demandé
                if distance_max and distance > float(distance_max):
                    continue
            else:
                data['distance_km'] = None
        else:
            data['distance_km'] = None

        services_data.append(data)

    # Trier par distance si position fournie
    if lat_client and lon_client:
        services_data.sort(
            key=lambda x: x.get('distance_km') or 9999
        )

    return Response(services_data)


@api_view(['GET'])
@permission_classes([AllowAny])
def detail_service(request, pk):
    try:
        service = Service.objects.select_related(
            'prestatire', 'categorie'
        ).prefetch_related(
            'images', 'parametres__options', 'disponibilites'
        ).get(pk=pk)
        data = ServiceSerializer(service).data

        # Distance si position fournie
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        if lat and lon:
            s_lat = service.latitude or (
                service.prestatire.latitude if service.prestatire.latitude else None
            )
            s_lon = service.longitude or (
                service.prestatire.longitude if service.prestatire.longitude else None
            )
            if s_lat and s_lon:
                data['distance_km'] = calculer_distance_km(lat, lon, s_lat, s_lon)
            else:
                data['distance_km'] = None

        return Response(data)
    except Service.DoesNotExist:
        return Response(
            {'error': 'Service introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def creer_service(request):
    if not request.user.is_prestataire:
        return Response(
            {'error': 'Seuls les prestataires peuvent creer des services'},
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        prestatire = request.user.prestatire_profile
    except Exception:
        return Response(
            {'error': 'Profil prestataire introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = ServiceCreateSerializer(data=request.data)
    if serializer.is_valid():
        service = serializer.save(prestatire=prestatire)
        return Response(
            ServiceSerializer(service).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def modifier_service(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response(
            {'error': 'Service introuvable ou non autorise'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = ServiceCreateSerializer(service, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(ServiceSerializer(service).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_service(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
        service.delete()
        return Response(
            {'message': 'Service supprime avec succes'},
            status=status.HTTP_204_NO_CONTENT
        )
    except Service.DoesNotExist:
        return Response(
            {'error': 'Service introuvable ou non autorise'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_services(request):
    if not request.user.is_prestataire:
        return Response(
            {'error': 'Acces refuse'},
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        prestatire = request.user.prestatire_profile
        services = Service.objects.filter(prestatire=prestatire).prefetch_related(
            'images', 'parametres__options', 'disponibilites'
        )
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)
    except Exception:
        return Response(
            {'error': 'Profil prestataire introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )


# ─── IMAGES ───────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def ajouter_image_service(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response(
            {'error': 'Service introuvable ou non autorise'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = ServiceImageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(service=service)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_image_service(request, pk):
    try:
        image = ServiceImage.objects.get(
            pk=pk, service__prestatire=request.user.prestatire_profile
        )
        image.delete()
        return Response(
            {'message': 'Image supprimee'},
            status=status.HTTP_204_NO_CONTENT
        )
    except ServiceImage.DoesNotExist:
        return Response(
            {'error': 'Image introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )


# ─── PARAMETRES ───────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ajouter_parametre(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response(
            {'error': 'Service introuvable ou non autorise'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = ServiceParameterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(service=service)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def modifier_parametre(request, pk):
    try:
        parametre = ServiceParameter.objects.get(
            pk=pk, service__prestatire=request.user.prestatire_profile
        )
    except ServiceParameter.DoesNotExist:
        return Response(
            {'error': 'Parametre introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = ServiceParameterSerializer(parametre, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_parametre(request, pk):
    try:
        parametre = ServiceParameter.objects.get(
            pk=pk, service__prestatire=request.user.prestatire_profile
        )
        parametre.delete()
        return Response(
            {'message': 'Parametre supprime'},
            status=status.HTTP_204_NO_CONTENT
        )
    except ServiceParameter.DoesNotExist:
        return Response(
            {'error': 'Parametre introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ajouter_option_parametre(request, pk):
    try:
        parametre = ServiceParameter.objects.get(
            pk=pk, service__prestatire=request.user.prestatire_profile
        )
    except ServiceParameter.DoesNotExist:
        return Response(
            {'error': 'Parametre introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = ServiceParameterOptionSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(parametre=parametre)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── DISPONIBILITES ───────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def disponibilites_service(request, pk):
    """Voir les disponibilités d'un service"""
    try:
        service = Service.objects.get(pk=pk)
        dispos = service.disponibilites.filter(is_available=True)
        serializer = AvailabilitySerializer(dispos, many=True)
        return Response(serializer.data)
    except Service.DoesNotExist:
        return Response(
            {'error': 'Service introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ajouter_disponibilite(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response(
            {'error': 'Service introuvable ou non autorise'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = AvailabilitySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(service=service)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def modifier_disponibilite(request, pk):
    try:
        dispo = Availability.objects.get(
            pk=pk, service__prestatire=request.user.prestatire_profile
        )
    except Availability.DoesNotExist:
        return Response(
            {'error': 'Disponibilite introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = AvailabilitySerializer(dispo, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_disponibilite(request, pk):
    try:
        dispo = Availability.objects.get(
            pk=pk, service__prestatire=request.user.prestatire_profile
        )
        dispo.delete()
        return Response(
            {'message': 'Disponibilite supprimee'},
            status=status.HTTP_204_NO_CONTENT
        )
    except Availability.DoesNotExist:
        return Response(
            {'error': 'Disponibilite introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )