"""Commande : python manage.py index_procedure [--file chemin.docx]"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from knowledge.indexing import index_procedure


class Command(BaseCommand):
    help = "Indexe le document « Procédure d'admission » dans la base vectorielle."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=Path, default=settings.PROCEDURE_DOCUMENT, help="Chemin du fichier .docx")

    def handle(self, *args, **options):
        path: Path = options["file"]
        if not path.exists():
            raise CommandError(f"Fichier introuvable : {path}")
        count = index_procedure(path)
        self.stdout.write(self.style.SUCCESS(f"{count} sections indexées."))
