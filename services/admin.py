from django.contrib import admin
from .models import Category, Service, ServiceImage, ServiceParameter, ServiceParameterOption, Availability


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['nom', 'is_active']


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['titre', 'prestatire', 'categorie', 'pricing_type', 'prix_base', 'is_available']
    list_filter = ['pricing_type', 'is_available', 'is_sponsored']


@admin.register(ServiceImage)
class ServiceImageAdmin(admin.ModelAdmin):
    list_display = ['service', 'is_principale', 'ordre']


@admin.register(ServiceParameter)
class ServiceParameterAdmin(admin.ModelAdmin):
    list_display = ['nom', 'service', 'type', 'is_required']


@admin.register(ServiceParameterOption)
class ServiceParameterOptionAdmin(admin.ModelAdmin):
    list_display = ['label', 'parametre', 'prix_supplementaire']


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ['service', 'jour', 'heure_debut', 'heure_fin', 'is_available']
