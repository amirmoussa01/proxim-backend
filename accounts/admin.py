from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ClientProfile, PrestatireProfile, KYCDocument
from notifications.utils import notif_kyc_valide, notif_kyc_rejete
from django.utils import timezone

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['email']
    list_display = ['email', 'role', 'is_email_verified', 'is_active']
    list_filter = ['role', 'is_email_verified', 'is_active']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Infos', {'fields': ('phone', 'role', 'google_id')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_email_verified')}),
    )
    add_fieldsets = (
        (None, {'fields': ('email', 'password1', 'password2', 'role')}),
    )
    search_fields = ['email']


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'nom', 'prenom', 'adresse']


@admin.register(PrestatireProfile)
class PrestatireProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'nom', 'prenom', 'niveau', 'is_verified', 'note_moyenne']
    list_filter = ['niveau', 'is_verified']


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ['prestatire', 'type_document', 'statut', 'date_soumission']
    list_filter = ['statut', 'type_document']

    def save_model(self, request, obj, form, change):
        if change:
            ancien = KYCDocument.objects.get(pk=obj.pk)
            if ancien.statut != obj.statut:
                obj.date_validation = timezone.now()
                super().save_model(request, obj, form, change)
                if obj.statut == 'valide':
                    # Verifier si tous les docs sont valides
                    docs = KYCDocument.objects.filter(prestatire=obj.prestatire)
                    tous_valides = all(d.statut == 'valide' for d in docs)
                    if tous_valides:
                        obj.prestatire.is_verified = True
                        obj.prestatire.save()
                        notif_kyc_valide(obj.prestatire)
                elif obj.statut == 'rejete':
                    notif_kyc_rejete(obj.prestatire)
                return
        super().save_model(request, obj, form, change)


