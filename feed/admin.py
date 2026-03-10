from django.contrib import admin
from .models import Post, PostImage, Like, Comment, Favorite


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'prestatire', 'is_active', 'date_publication']


@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ['post', 'ordre']


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ['post', 'user', 'date']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['post', 'user', 'is_deleted', 'date']


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['client', 'prestatire', 'date']
