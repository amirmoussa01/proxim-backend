from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        email = 'adminproxim@gmail.com'
        password = 'admin123'

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING('Superuser existe deja'))
            return

        User.objects.create_superuser(
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS('Superuser cree avec succes'))