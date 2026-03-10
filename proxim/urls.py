from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.contrib.auth import get_user_model
def create_admin(request):
    User = get_user_model()
    if not User.objects.filter(email='adminproxim@gmail.com').exists():
        User.objects.create_superuser(
            email='adminproxim@gmail.com',
            password='admin123',
        )
        return JsonResponse({'ok': 'Superuser cree'})
    return JsonResponse({'ok': 'Existe deja'})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/services/', include('services.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/messaging/', include('messaging.urls')),
    path('api/feed/', include('feed.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/reviews/', include('reviews.urls')),
    path('api/reports/', include('reports.urls')),
    path('init-admin/', create_admin),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)