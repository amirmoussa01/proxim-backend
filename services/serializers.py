from rest_framework import serializers
from .models import Category, Service, ServiceImage, ServiceParameter, ServiceParameterOption, Availability


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class ServiceParameterOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceParameterOption
        fields = '__all__'


class ServiceParameterSerializer(serializers.ModelSerializer):
    options = ServiceParameterOptionSerializer(many=True, read_only=True)

    class Meta:
        model = ServiceParameter
        fields = '__all__'


class ServiceImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ServiceImage
        fields = '__all__'

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = '__all__'


class PrestatireDetailSerializer(serializers.SerializerMethodField):
    pass


class ServiceSerializer(serializers.ModelSerializer):
    images = ServiceImageSerializer(many=True, read_only=True)
    parametres = ServiceParameterSerializer(many=True, read_only=True)
    disponibilites = AvailabilitySerializer(many=True, read_only=True)
    categorie_nom = serializers.CharField(source='categorie.nom', read_only=True)
    prestatire_nom = serializers.SerializerMethodField()
    prestatire_detail = serializers.SerializerMethodField()
    note_moyenne = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = '__all__'
        read_only_fields = ['prestatire', 'date_creation', 'date_modification']

    def get_prestatire_nom(self, obj):
        return f'{obj.prestatire.prenom} {obj.prestatire.nom}'

    def get_prestatire_detail(self, obj):
        p = obj.prestatire
        avatar_url = None
        if p.avatar:
            avatar_url = p.avatar.url
        nb_services = p.services.filter(is_available=True).count()
        return {
            'id': p.id,
            'nom': f'{p.prenom} {p.nom}',
            'niveau': p.niveau,
            'is_verified': p.is_verified,
            'avatar_url': avatar_url,
            'nb_services': nb_services,
            'bio': getattr(p, 'bio', ''),
        }

    def get_note_moyenne(self, obj):
        return None


class ServiceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        exclude = ['prestatire', 'date_creation', 'date_modification']

    def validate(self, data):
        pricing_type = data.get('pricing_type')
        prix_base = data.get('prix_base')
        if pricing_type and pricing_type != 'SUR_DEVIS' and not prix_base:
            raise serializers.ValidationError(
                'prix_base est obligatoire sauf pour les services sur devis'
            )
        return data