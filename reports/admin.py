from django.contrib import admin
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['reporter', 'cible_user', 'raison', 'statut', 'date']
    list_filter = ['raison', 'statut']
