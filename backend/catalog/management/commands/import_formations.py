"""Commande : python manage.py import_formations [--file chemin.xlsx]"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog.importer import import_formations

DEFAULT_FILE = settings.BASE_DIR / "data" / "diplome_specialite.xlsx"


class Command(BaseCommand):
    help = "Importe ou met à jour les formations depuis le fichier Excel « diplôme spécialité »."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help="Chemin du fichier .xlsx")

    def handle(self, *args, **options):
        path: Path = options["file"]
        if not path.exists():
            raise CommandError(f"Fichier introuvable : {path}")

        try:
            report = import_formations(path)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f"{report.total} formations importées ({report.created} créées, "
            f"{report.updated} mises à jour, {report.skipped} lignes vides ignorées)."
        ))
        # Formations absentes du fichier : désactivées (conservées pour l'historique)
        plural = "s" if report.deactivated > 1 else ""
        self.stdout.write(
            f"{report.deactivated} formation{plural} désactivée{plural} (absente{plural} du fichier)."
        )
        if report.warnings:
            self.stdout.write(self.style.WARNING(
                f"\n{len(report.warnings)} anomalies à faire vérifier par l'équipe :"
            ))
            for warning in report.warnings:
                self.stdout.write(f"  - {warning}")