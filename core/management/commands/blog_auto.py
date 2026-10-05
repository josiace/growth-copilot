from django.core.management.base import BaseCommand
from core import blog_auto

class Command(BaseCommand):
    help = "Publie les articles dont le délai de validation est écoulé et génère les nouveaux selon le rythme réglé."

    def handle(self, *args, **options):
        for ligne in blog_auto.run():
            self.stdout.write(ligne)
