from .settings import *
import os

DEBUG = False

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRESQL_ADDON_DB'),
        'USER': os.environ.get('POSTGRESQL_ADDON_USER'),
        'PASSWORD': os.environ.get('POSTGRESQL_ADDON_PASSWORD'),
        'HOST': os.environ.get('POSTGRESQL_ADDON_HOST'),
        'PORT': os.environ.get('POSTGRESQL_ADDON_PORT', '5432'),
    }
}

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

CORS_ALLOW_ALL_ORIGINS = True