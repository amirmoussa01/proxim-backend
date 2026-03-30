from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ClientProfile, PrestatireProfile, KYCDocument
from notifications.utils import notif_kyc_valide, notif_kyc_rejete
from django.utils import timezone

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['email']
    list_display = ['email', 'role', 'is_email_verified', 'is_active', 'fcm_token']
    list_filter = ['role', 'is_email_verified', 'is_active']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Infos Personnelles', {'fields': ('phone', 'role', 'google_id')}),
        ('Firebase Cloud Messaging', {'fields': ('fcm_token',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_email_verified')}),
    )
    add_fieldsets = (
        (None, {'fields': ('email', 'password', 'role', 'fcm_token')}),
    )
    search_fields = ['email', 'fcm_token']

@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ['prestatire', 'type_document', 'statut', 'date_soumission']
    list_filter = ['statut', 'type_document']

    def save_model(self, request, obj, form, change):
        if change:
            ancien = KYCDocument.objects.get(pk=obj.pk)
            print(f"[ADMIN DEBUG] Changement statut: {ancien.statut} -> {obj.statut}")

            if ancien.statut != obj.statut:
                obj.date_validation = timezone.now()
                super().save_model(request, obj, form, change)

                if obj.statut == 'valide':
                    docs = KYCDocument.objects.filter(prestatire=obj.prestatire)
                    tous_valides = all(d.statut == 'valide' for d in docs)
                    
                    print(f"[ADMIN DEBUG] Tous documents valides ? {tous_valides}")

                    # On force l'appel de la notification pour le TEST même si tous_valides est False
                    # Une fois que ça marche, tu pourras remettre l'indentation correcte
                    print(f"[ADMIN DEBUG] Appel de notif_kyc_valide pour {obj.prestatire.user.email}")
                    notif_kyc_valide(obj.prestatire)
                    
                    if tous_valides:
                        obj.prestatire.is_verified = True
                        obj.prestatire.save()

                elif obj.statut == 'rejete':
                    print(f"[ADMIN DEBUG] Appel de notif_kyc_rejete")
                    notif_kyc_rejete(obj.prestatire)
                return

        super().save_model(request, obj, form, change)

# On garde les autres classes Admin telles quelles
admin.site.register(ClientProfile)
admin.site.register(PrestatireProfile)
