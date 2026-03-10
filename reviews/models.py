from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Review(models.Model):
    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='review'
    )
    client = models.ForeignKey(
        'accounts.ClientProfile', on_delete=models.CASCADE, related_name='avis'
    )
    prestatire = models.ForeignKey(
        'accounts.PrestatireProfile', on_delete=models.CASCADE, related_name='avis'
    )
    note = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    commentaire = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avis'
        verbose_name_plural = 'Avis'
        ordering = ['-date']

    def __str__(self):
        return f'Avis #{self.id} - {self.note}/5 - {self.prestatire}'