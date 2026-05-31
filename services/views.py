from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
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
    R = 6371
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
        return Response({'error': 'Permission refusee'}, status=status.HTTP_403_FORBIDDEN)
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
    lat_client = request.query_params.get('lat')
    lon_client = request.query_params.get('lon')
    distance_max = request.query_params.get('distance_max')

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

    services_data = []
    for service in services:
        data = ServiceSerializer(service).data
        if lat_client and lon_client:
            s_lat = service.latitude or (service.prestatire.latitude if service.prestatire.latitude else None)
            s_lon = service.longitude or (service.prestatire.longitude if service.prestatire.longitude else None)
            if s_lat and s_lon:
                distance = calculer_distance_km(lat_client, lon_client, s_lat, s_lon)
                data['distance_km'] = distance
                if distance_max and distance > float(distance_max):
                    continue
            else:
                data['distance_km'] = None
        else:
            data['distance_km'] = None
        services_data.append(data)

    if lat_client and lon_client:
        services_data.sort(key=lambda x: x.get('distance_km') or 9999)

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
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        if lat and lon:
            s_lat = service.latitude or (service.prestatire.latitude if service.prestatire.latitude else None)
            s_lon = service.longitude or (service.prestatire.longitude if service.prestatire.longitude else None)
            if s_lat and s_lon:
                data['distance_km'] = calculer_distance_km(lat, lon, s_lat, s_lon)
            else:
                data['distance_km'] = None
        return Response(data)
    except Service.DoesNotExist:
        return Response({'error': 'Service introuvable'}, status=status.HTTP_404_NOT_FOUND)


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
        return Response({'error': 'Profil prestataire introuvable'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ServiceCreateSerializer(data=request.data)
    if serializer.is_valid():
        service = serializer.save(prestatire=prestatire)

        # Remplir lat/lon depuis le prestataire si non fournis
        modifie = False
        if service.latitude is None and prestatire.latitude:
            service.latitude = prestatire.latitude
            modifie = True
        if service.longitude is None and prestatire.longitude:
            service.longitude = prestatire.longitude
            modifie = True
        if modifie:
            service.save(update_fields=['latitude', 'longitude'])

        return Response(ServiceSerializer(service).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def modifier_service(request, pk):
    """
    Modification d'un service avec gestion complète des images.

    Champs texte : titre, description, pricing_type, prix_base, etc.

    Gestion images via body multipart :
      - images_a_supprimer : IDs séparés par virgule  ex: "12,15"
      - images             : fichiers image (clé répétée)
      - image_principale   : ID de l'image à définir comme principale
    """
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response({'error': 'Service introuvable ou non autorise'}, status=status.HTTP_404_NOT_FOUND)

    # ── 1. Modifier les champs texte ──────────────────────────
    serializer = ServiceCreateSerializer(service, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()

    # ── 2. Supprimer les images demandées ─────────────────────
    ids_a_supprimer_raw = request.data.get('images_a_supprimer', '')
    if ids_a_supprimer_raw:
        try:
            if isinstance(ids_a_supprimer_raw, list):
                ids_a_supprimer = [int(i) for i in ids_a_supprimer_raw if str(i).strip()]
            else:
                ids_a_supprimer = [
                    int(i.strip())
                    for i in str(ids_a_supprimer_raw).split(',')
                    if i.strip()
                ]
            images_a_supprimer = ServiceImage.objects.filter(
                pk__in=ids_a_supprimer,
                service=service,
            )
            avait_principale = images_a_supprimer.filter(is_principale=True).exists()
            images_a_supprimer.delete()

            # Promouvoir la suivante si la principale était supprimée
            if avait_principale:
                premiere = service.images.order_by('ordre').first()
                if premiere:
                    premiere.is_principale = True
                    premiere.save()
        except (ValueError, TypeError):
            pass

    # ── 3. Ajouter les nouvelles images via Cloudinary ────────
    # CloudinaryField gère l'upload automatiquement quand on lui
    # passe un InMemoryUploadedFile via le serializer.
    nouvelles_images = request.FILES.getlist('images')
    nb_existantes = service.images.count()

    for i, img_file in enumerate(nouvelles_images):
        if nb_existantes + i >= 10:
            break
        # On passe directement le fichier au serializer —
        # CloudinaryField se charge de l'upload vers Cloudinary
        img_serializer = ServiceImageSerializer(
            data={
                'service': service.id,
                'image': img_file,
                'is_principale': False,
                'ordre': nb_existantes + i,
            }
        )
        if img_serializer.is_valid():
            img_serializer.save(service=service)
        # Si invalide on passe silencieusement pour ne pas bloquer

    # Si aucune image principale n'existe encore, promouvoir la première
    if not service.images.filter(is_principale=True).exists():
        premiere = service.images.order_by('ordre').first()
        if premiere:
            premiere.is_principale = True
            premiere.save()

    # ── 4. Changer l'image principale si demandé ──────────────
    image_principale_id = request.data.get('image_principale')
    if image_principale_id:
        try:
            img = ServiceImage.objects.get(
                pk=int(image_principale_id),
                service=service,
            )
            service.images.filter(is_principale=True).update(is_principale=False)
            img.is_principale = True
            img.save()
        except (ServiceImage.DoesNotExist, ValueError, TypeError):
            pass

    # ── 5. Retourner le service complet mis à jour ─────────────
    service.refresh_from_db()
    return Response(ServiceSerializer(service).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_service(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
        service.delete()
        return Response({'message': 'Service supprime avec succes'}, status=status.HTTP_204_NO_CONTENT)
    except Service.DoesNotExist:
        return Response({'error': 'Service introuvable ou non autorise'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_services(request):
    if not request.user.is_prestataire:
        return Response({'error': 'Acces refuse'}, status=status.HTTP_403_FORBIDDEN)
    try:
        prestatire = request.user.prestatire_profile
        services = Service.objects.filter(prestatire=prestatire).prefetch_related(
            'images', 'parametres__options', 'disponibilites'
        )
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)
    except Exception:
        return Response({'error': 'Profil prestataire introuvable'}, status=status.HTTP_404_NOT_FOUND)


# ─── IMAGES SERVICE (endpoints individuels) ───────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def images_service(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response({'error': 'Service introuvable ou non autorise'}, status=status.HTTP_404_NOT_FOUND)
    images = service.images.all().order_by('ordre')
    return Response(ServiceImageSerializer(images, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def ajouter_image_service(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response({'error': 'Service introuvable ou non autorise'}, status=status.HTTP_404_NOT_FOUND)

    if service.images.count() >= 10:
        return Response(
            {'error': 'Limite atteinte : 10 images maximum par service'},
            status=status.HTTP_400_BAD_REQUEST
        )

    img_file = request.FILES.get('image')
    if not img_file:
        return Response({'error': 'Aucune image fournie'}, status=status.HTTP_400_BAD_REQUEST)

    is_principale = request.data.get('is_principale', 'false').lower() == 'true'
    if is_principale:
        service.images.filter(is_principale=True).update(is_principale=False)

    img_serializer = ServiceImageSerializer(
        data={
            'service': service.id,
            'image': img_file,
            'is_principale': is_principale,
            'ordre': service.images.count(),
        }
    )
    if img_serializer.is_valid():
        img_serializer.save(service=service)
        return Response(img_serializer.data, status=status.HTTP_201_CREATED)
    return Response(img_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_image_service(request, pk):
    try:
        image = ServiceImage.objects.get(pk=pk, service__prestatire=request.user.prestatire_profile)
        etait_principale = image.is_principale
        service = image.service
        image.delete()
        if etait_principale:
            prochaine = service.images.order_by('ordre').first()
            if prochaine:
                prochaine.is_principale = True
                prochaine.save()
        return Response({'message': 'Image supprimee'}, status=status.HTTP_204_NO_CONTENT)
    except ServiceImage.DoesNotExist:
        return Response({'error': 'Image introuvable'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def definir_image_principale(request, pk):
    try:
        image = ServiceImage.objects.select_related('service').get(
            pk=pk, service__prestatire=request.user.prestatire_profile
        )
    except ServiceImage.DoesNotExist:
        return Response({'error': 'Image introuvable'}, status=status.HTTP_404_NOT_FOUND)

    image.service.images.filter(is_principale=True).update(is_principale=False)
    image.is_principale = True
    image.save()
    return Response(ServiceImageSerializer(image).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def reordonner_images_service(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response({'error': 'Service introuvable ou non autorise'}, status=status.HTTP_404_NOT_FOUND)

    ordre_ids = request.data.get('ordre', [])
    if not isinstance(ordre_ids, list):
        return Response({'error': 'ordre doit etre une liste d IDs'}, status=status.HTTP_400_BAD_REQUEST)

    ids_service = set(service.images.values_list('id', flat=True))
    for img_id in ordre_ids:
        if img_id not in ids_service:
            return Response(
                {'error': f'Image {img_id} n appartient pas a ce service'},
                status=status.HTTP_400_BAD_REQUEST
            )

    for index, img_id in enumerate(ordre_ids):
        ServiceImage.objects.filter(pk=img_id).update(ordre=index)

    return Response(ServiceImageSerializer(service.images.order_by('ordre'), many=True).data)


# ─── PARAMETRES ───────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ajouter_parametre(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response({'error': 'Service introuvable ou non autorise'}, status=status.HTTP_404_NOT_FOUND)
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
        return Response({'error': 'Parametre introuvable'}, status=status.HTTP_404_NOT_FOUND)
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
        return Response({'message': 'Parametre supprime'}, status=status.HTTP_204_NO_CONTENT)
    except ServiceParameter.DoesNotExist:
        return Response({'error': 'Parametre introuvable'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ajouter_option_parametre(request, pk):
    try:
        parametre = ServiceParameter.objects.get(
            pk=pk, service__prestatire=request.user.prestatire_profile
        )
    except ServiceParameter.DoesNotExist:
        return Response({'error': 'Parametre introuvable'}, status=status.HTTP_404_NOT_FOUND)
    serializer = ServiceParameterOptionSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(parametre=parametre)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── DISPONIBILITES ───────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def disponibilites_service(request, pk):
    try:
        service = Service.objects.get(pk=pk)
        dispos = service.disponibilites.filter(is_available=True)
        return Response(AvailabilitySerializer(dispos, many=True).data)
    except Service.DoesNotExist:
        return Response({'error': 'Service introuvable'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ajouter_disponibilite(request, pk):
    try:
        service = Service.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Service.DoesNotExist:
        return Response({'error': 'Service introuvable ou non autorise'}, status=status.HTTP_404_NOT_FOUND)
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
        return Response({'error': 'Disponibilite introuvable'}, status=status.HTTP_404_NOT_FOUND)
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
        return Response({'message': 'Disponibilite supprimee'}, status=status.HTTP_204_NO_CONTENT)
    except Availability.DoesNotExist:
        return Response({'error': 'Disponibilite introuvable'}, status=status.HTTP_404_NOT_FOUND)