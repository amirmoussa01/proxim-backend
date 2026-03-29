from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ClientProfile, PrestatireProfile, KYCDocument
from notifications.utils import notif_kyc_valide, notif_kyc_rejete
from django.utils import timezone

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['email']
    # Ajout de fcm_token dans la liste pour voir rapidement qui a un token
    list_display = ['email', 'role', 'is_email_verified', 'is_active', 'fcm_token']
    list_filter = ['role', 'is_email_verified', 'is_active']
    
    # Configuration des champs dans la vue de modification
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Infos Personnelles', {'fields': ('phone', 'role', 'google_id')}),
        ('Firebase Cloud Messaging', {
            'fields': ('fcm_token',),
            'description': 'Ce jeton est généré par l\'application mobile pour les notifications push.'
        }),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_email_verified')}),
    )
    
    # Configuration pour la création d'un utilisateur via l'admin
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'role', 'fcm_token'),
        }),
    )
    search_fields = ['email', 'fcm_token']


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'nom', 'prenom', 'adresse']
    search_fields = ['user__email', 'nom', 'prenom']


@admin.register(PrestatireProfile)
class PrestatireProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'nom', 'prenom', 'niveau', 'is_verified', 'note_moyenne']
    list_filter = ['niveau', 'is_verified']
    search_fields = ['user__email', 'nom', 'prenom']


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ['prestatire', 'type_document', 'statut', 'date_soumission']
    list_filter = ['statut', 'type_document']

    def save_model(self, request, obj, form, change):
        if change:
            # On récupère la version actuelle en base de données avant la modification
            ancien = KYCDocument.objects.get(pk=obj.pk)
            
            # Si le statut vient de changer
            if ancien.statut != obj.statut:
                obj.date_validation = timezone.now()
                # On sauvegarde d'abord l'objet pour mettre à jour le statut
                super().save_model(request, obj, form, change)
                
                if obj.statut == 'valide':
                    # Vérifier si TOUS les documents de ce prestataire sont maintenant valides
                    docs = KYCDocument.objects.filter(prestatire=obj.prestatire)
                    tous_valides = all(d.statut == 'valide' for d in docs)
                    
                    if tous_valides:
                        obj.prestatire.is_verified = True
                        obj.prestatire.save()
                        # Envoi de la notification push via Firebase
                        notif_kyc_valide(obj.prestatire)
                        
                elif obj.statut == 'rejete':
                    # Notification de rejet
                    notif_kyc_rejete(obj.prestatire)
                return
                
        # Si ce n'est pas un changement de statut, sauvegarde normale
        super().save_model(request, obj, form, change)
