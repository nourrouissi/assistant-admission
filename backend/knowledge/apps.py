import os
import sys
import threading

from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge"
    verbose_name = "Procédure d'admission"

    def ready(self):
        # Serveur de développement (processus relancé par le rechargement automatique) :
        # le modèle d'embeddings est chargé en arrière-plan dès le démarrage.
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") == "true":
            from .retrieval import warm_up

            threading.Thread(target=warm_up, daemon=True).start()
