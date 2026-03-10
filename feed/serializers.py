from rest_framework import serializers
from .models import Post, PostImage, Like, Comment, Favorite
from accounts.serializers import PrestatireProfileSerializer


class PostImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = '__all__'
        read_only_fields = ['post']


class CommentSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    contenu_affiche = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ['user', 'post', 'date', 'is_deleted']

    def get_contenu_affiche(self, obj):
        if obj.is_deleted:
            return 'Commentaire supprime'
        return obj.contenu


class PostSerializer(serializers.ModelSerializer):
    images = PostImageSerializer(many=True, read_only=True)
    commentaires = CommentSerializer(many=True, read_only=True)
    prestatire_detail = PrestatireProfileSerializer(source='prestatire', read_only=True)
    total_likes = serializers.SerializerMethodField()
    total_commentaires = serializers.SerializerMethodField()
    user_a_like = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = '__all__'
        read_only_fields = ['prestatire', 'date_publication']

    def get_total_likes(self, obj):
        return obj.likes.count()

    def get_total_commentaires(self, obj):
        return obj.commentaires.filter(is_deleted=False).count()

    def get_user_a_like(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False


class PostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['contenu', 'service']

    def validate_contenu(self, value):
        if not value.strip():
            raise serializers.ValidationError('Le contenu ne peut pas etre vide')
        return value


class FavoriteSerializer(serializers.ModelSerializer):
    prestatire_detail = PrestatireProfileSerializer(source='prestatire', read_only=True)

    class Meta:
        model = Favorite
        fields = '__all__'
        read_only_fields = ['client', 'date']