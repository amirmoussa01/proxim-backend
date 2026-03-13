from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Conversation(models.Model):
    client = models.ForeignKey(
        'accounts.ClientProfile',
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    prestatire = models.ForeignKey(
        'accounts.PrestatireProfile',
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    dernier_message_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        ordering = ['-dernier_message_date']
        unique_together = ('client', 'prestatire')

    def __str__(self):
        return f'Conversation {self.client} - {self.prestatire}'


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
    )
    expediteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages')
    contenu = models.TextField(blank=True)
    image = models.URLField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    date_envoi = models.DateTimeField(auto_now_add=True)
    date_suppression = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['date_envoi']

    def __str__(self):
        return f'Message #{self.id} - {self.expediteur}'