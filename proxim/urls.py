from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from admin_dashboard import views as adv
from django.views.generic import TemplateView

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
    path('api/chatbot/', include('chatbot.urls')),
    path('admin-dashboard/login/', adv.login_view, name='admin_login'),
    path('admin-dashboard/logout/', adv.logout_view, name='admin_logout'),
    path('admin-dashboard/', include('admin_dashboard.urls')),

    path(
        'legal/conditions-utilisation/',
        TemplateView.as_view(template_name='legal/conditions_utilisation.html'),
        name='conditions_utilisation',
    ),
    path(
        'legal/politique-confidentialite/',
        TemplateView.as_view(template_name='legal/politique_confidentialite.html'),
        name='politique_confidentialite',
    ),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)