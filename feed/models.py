from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Post(models.Model):
    prestatire = models.ForeignKey(
        'accounts.PrestatireProfile',
        on_delete=models.CASCADE,
        related_name='posts'
    )
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts'
    )
    contenu = models.TextField()
    is_active = models.BooleanField(default=True)
    date_publication = models.DateTimeField(auto_now_add=True)
    video_url = models.URLField(blank=True, null=True) 

    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        ordering = ['-date_publication']

    def __str__(self):
        return f'Post #{self.id} - {self.prestatire}'


class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='images')
    image = models.URLField() 
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Image Post'
        verbose_name_plural = 'Images Post'
        ordering = ['ordre']

    def __str__(self):
        return f'Image {self.ordre} - Post #{self.post.id}'


class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='likes')
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Like'
        verbose_name_plural = 'Likes'
        unique_together = ('post', 'user')

    def __str__(self):
        return f'Like - {self.user} - Post #{self.post.id}'


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='commentaires')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commentaires')
    contenu = models.TextField()
    is_deleted = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Commentaire'
        verbose_name_plural = 'Commentaires'
        ordering = ['date']

    def __str__(self):
        return f'Commentaire #{self.id} - Post #{self.post.id}'


class Favorite(models.Model):
    client = models.ForeignKey(
        'accounts.ClientProfile',
        on_delete=models.CASCADE,
        related_name='favoris'
    )
    prestatire = models.ForeignKey(
        'accounts.PrestatireProfile',
        on_delete=models.CASCADE,
        related_name='favoris'
    )
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Favori'
        verbose_name_plural = 'Favoris'
        unique_together = ('client', 'prestatire')

    def __str__(self):
        return f'Favori - {self.client} - {self.prestatire}'

class FavoriService(models.Model):
    client = models.ForeignKey(
        'accounts.ClientProfile',
        on_delete=models.CASCADE,
        related_name='favoris_services'
    )
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.CASCADE,
        related_name='favoris'
    )
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Favori Service'
        verbose_name_plural = 'Favoris Services'
        unique_together = ('client', 'service')

    def __str__(self):
        return f'Favori - {self.client} - {self.service.titre}'