from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['destinataire', 'type', 'titre', 'is_read', 'date']
    list_filter = ['type', 'is_read']