from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from .models import Post, PostImage, Like, Comment, Favorite, FavoriService
from .serializers import (
    PostSerializer,
    PostCreateSerializer,
    PostImageSerializer,
    CommentSerializer,
    FavoriteSerializer,
)
from accounts.models import ClientProfile
import cloudinary.uploader

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_favori_service(request):
    service_id = request.data.get('service')
    if not service_id:
        return Response({'error': 'service requis'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        client = request.user.client_profile
    except Exception:
        return Response({'error': 'Profil client introuvable'}, status=status.HTTP_403_FORBIDDEN)
    try:
        from services.models import Service
        service = Service.objects.get(id=service_id)
    except Exception:
        return Response({'error': 'Service introuvable'}, status=status.HTTP_404_NOT_FOUND)
    
    favori, created = FavoriService.objects.get_or_create(client=client, service=service)
    if not created:
        favori.delete()
        return Response({'favori': False})
    return Response({'favori': True}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_favoris_services(request):
    try:
        client = request.user.client_profile
    except Exception:
        return Response({'error': 'Profil client introuvable'}, status=status.HTTP_403_FORBIDDEN)
    favoris = FavoriService.objects.filter(client=client).select_related('service')
    from services.serializers import ServiceSerializer
    services = [f.service for f in favoris]
    data = ServiceSerializer(services, many=True).data
    return Response(data)
# ─── POSTS ────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def liste_posts(request):
    posts = Post.objects.filter(
        is_active=True
    ).select_related(
        'prestatire'
    ).prefetch_related('images', 'likes', 'commentaires')

    prestatire_id = request.query_params.get('prestatire')
    if prestatire_id:
        posts = posts.filter(prestatire__id=prestatire_id)

    serializer = PostSerializer(posts, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def detail_post(request, pk):
    try:
        post = Post.objects.select_related(
            'prestatire'
        ).prefetch_related(
            'images', 'likes', 'commentaires'
        ).get(pk=pk, is_active=True)
        serializer = PostSerializer(post, context={'request': request})
        return Response(serializer.data)
    except Post.DoesNotExist:
        return Response(
            {'error': 'Post introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def creer_post(request):
    if not request.user.is_prestataire:
        return Response(
            {'error': 'Seuls les prestataires peuvent publier'},
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        prestatire = request.user.prestatire_profile
    except Exception:
        return Response(
            {'error': 'Profil prestataire introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    contenu = request.data.get('contenu', '')
    service_id = request.data.get('service', None)
    video_url = None

    # Upload vidéo si présente
    if 'video' in request.FILES:
        try:
            result = cloudinary.uploader.upload(
                request.FILES['video'],
                folder='posts/videos/',
                resource_type='video',
            )
            # Vérifier la durée — Cloudinary retourne la durée en secondes
            duration = result.get('duration', 0)
            if duration > 30:
                # Supprimer la vidéo uploadée
                cloudinary.uploader.destroy(
                    result.get('public_id'),
                    resource_type='video'
                )
                return Response(
                    {'error': 'La vidéo ne doit pas dépasser 30 secondes'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            video_url = result.get('secure_url')
        except Exception as e:
            return Response(
                {'error': f'Erreur upload vidéo : {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    if not contenu and not video_url:
        return Response(
            {'error': 'Un post doit contenir du texte ou une vidéo'},
            status=status.HTTP_400_BAD_REQUEST
        )

    from services.models import Service as Svc
    service = None
    if service_id:
        try:
            service = Svc.objects.get(pk=service_id)
        except Exception:
            pass

    post = Post.objects.create(
        prestatire=prestatire,
        contenu=contenu,
        service=service,
        video_url=video_url,
    )

    # Upload images si présentes
    images = request.FILES.getlist('images')
    for i, img in enumerate(images):
        try:
            result = cloudinary.uploader.upload(
                img,
                folder='posts/images/',
                resource_type='image',
            )
            PostImage.objects.create(
                post=post,
                image=result.get('secure_url'),
                ordre=i,
            )
        except Exception:
            pass

    return Response(
        PostSerializer(post, context={'request': request}).data,
        status=status.HTTP_201_CREATED
    )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_post(request, pk):
    try:
        post = Post.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
        post.is_active = False
        post.save()
        return Response(
            {'message': 'Post supprime'},
            status=status.HTTP_200_OK
        )
    except Post.DoesNotExist:
        return Response(
            {'error': 'Post introuvable ou non autorise'},
            status=status.HTTP_404_NOT_FOUND
        )


# ─── IMAGES POST ──────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def ajouter_image_post(request, pk):
    try:
        post = Post.objects.get(pk=pk, prestatire=request.user.prestatire_profile)
    except Post.DoesNotExist:
        return Response(
            {'error': 'Post introuvable ou non autorise'},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = PostImageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(post=post)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── LIKES ────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_like(request, pk):
    try:
        post = Post.objects.get(pk=pk, is_active=True)
    except Post.DoesNotExist:
        return Response(
            {'error': 'Post introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    like, created = Like.objects.get_or_create(post=post, user=request.user)

    if not created:
        like.delete()
        return Response({
            'message': 'Like retire',
            'liked': False,
            'total_likes': post.likes.count()
        })

    return Response({
        'message': 'Post aime',
        'liked': True,
        'total_likes': post.likes.count()
    }, status=status.HTTP_201_CREATED)


# ─── COMMENTAIRES ─────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ajouter_commentaire(request, pk):
    try:
        post = Post.objects.get(pk=pk, is_active=True)
    except Post.DoesNotExist:
        return Response(
            {'error': 'Post introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = CommentSerializer(data=request.data)
    if serializer.is_valid():
        commentaire = serializer.save(post=post, user=request.user)
        return Response(
            CommentSerializer(commentaire).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def supprimer_commentaire(request, pk):
    try:
        commentaire = Comment.objects.get(pk=pk, user=request.user)
        commentaire.is_deleted = True
        commentaire.save()
        return Response(
            {'message': 'Commentaire supprime'},
            status=status.HTTP_200_OK
        )
    except Comment.DoesNotExist:
        return Response(
            {'error': 'Commentaire introuvable ou non autorise'},
            status=status.HTTP_404_NOT_FOUND
        )


# ─── FAVORIS ──────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_favori(request):
    if not request.user.is_client:
        return Response(
            {'error': 'Seuls les clients peuvent ajouter des favoris'},
            status=status.HTTP_403_FORBIDDEN
        )

    prestatire_id = request.data.get('prestatire_id')
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

    favori, created = Favorite.objects.get_or_create(client=client, prestatire=prestatire)

    if not created:
        favori.delete()
        return Response({
            'message': 'Favori retire',
            'favori': False,
        })

    return Response({
        'message': 'Prestataire ajoute aux favoris',
        'favori': True,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_favoris(request):
    if not request.user.is_client:
        return Response(
            {'error': 'Acces refuse'},
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        favoris = Favorite.objects.filter(
            client=request.user.client_profile
        ).select_related('prestatire')
        serializer = FavoriteSerializer(favoris, many=True)
        return Response(serializer.data)
    except Exception:
        return Response(
            {'error': 'Profil client introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )