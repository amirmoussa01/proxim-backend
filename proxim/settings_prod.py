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

BREVO_API_KEY = config('BREVO_API_KEY', default='')

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

CORS_ALLOW_ALL_ORIGINS = True