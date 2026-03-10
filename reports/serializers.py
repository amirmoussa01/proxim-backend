from rest_framework import serializers
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    reporter_email = serializers.CharField(source='reporter.email', read_only=True)
    cible_email = serializers.CharField(source='cible_user.email', read_only=True)

    class Meta:
        model = Report
        fields = '__all__'
        read_only_fields = ['reporter', 'statut', 'date']


class ReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['cible_user', 'raison', 'description']

    def validate(self, data):
        request = self.context.get('request')
        if request and data['cible_user'] == request.user:
            raise serializers.ValidationError(
                'Vous ne pouvez pas vous signaler vous-meme'
            )
        return data