"""
Configuration Django du projet « Assistant d'admission ».

Toutes les valeurs sensibles ou propres à l'environnement (clé secrète, base de
données, e-mails, clés API) sont lues dans le fichier .env situé à la racine du
projet. Voir .env.example pour la liste des variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# BASE_DIR = dossier backend/ ; le .env est un niveau au-dessus (racine du projet),
# partagé avec docker-compose.yml : une seule source de configuration.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    """Lit une variable booléenne du .env ("true", "1", "yes" -> True)."""
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    """Lit une liste séparée par des virgules ("a,b,c" -> ["a", "b", "c"])."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --- Sécurité ---------------------------------------------------------------
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]   # obligatoire : erreur claire si absente
DEBUG = env_bool("DJANGO_DEBUG", False)         # False par défaut : plus sûr
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# --- Applications -------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Bibliothèques tierces
    "rest_framework",
    "corsheaders",
    # Applications du projet : ajoutées au fil des étapes
    "catalog",      # Formations : normalisation, import Excel, recherche, éligibilité
    "knowledge",    # Procédure d'admission : indexation et RAG
    "chatbot",      # Assistant conversationnel : agent LangGraph et API /api/chat/
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",   # doit être placé avant CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Base de données : PostgreSQL + pgvector (conteneur Docker) ---------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "admission"),
        "USER": os.getenv("POSTGRES_USER", "admission"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Langue et fuseau horaire ------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Tunis"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- API REST -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# --- CORS : autorise uniquement le frontend Angular ---------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:4200")

# --- E-mails : Mailpit en développement, Brevo en démo et en production --------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "127.0.0.1")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "admissions@example.test")
BUSINESS_TEAM_EMAILS = env_list("BUSINESS_TEAM_EMAILS", "admissions@example.test")
# Contact affiché quand l'assistant oriente vers le service des admissions
ADMISSIONS_CONTACT = os.getenv("ADMISSIONS_CONTACT", "admissions@test.local")

# --- Assistant : modèles de langage (API compatible OpenAI) ---------------------------
# Chaîne de secours : modèle principal -> second modèle (même fournisseur) -> autre fournisseur.
# Les noms de modèles sont uniquement dans le .env, jamais dans le code.
LLM_PRIMARY_BASE_URL = os.getenv("LLM_PRIMARY_BASE_URL", "")
LLM_PRIMARY_API_KEY = os.getenv("LLM_PRIMARY_API_KEY", "")
LLM_PRIMARY_MODEL = os.getenv("LLM_PRIMARY_MODEL", "")
LLM_SECONDARY_MODEL = os.getenv("LLM_SECONDARY_MODEL", "")
LLM_FALLBACK_BASE_URL = os.getenv("LLM_FALLBACK_BASE_URL", "")
LLM_FALLBACK_API_KEY = os.getenv("LLM_FALLBACK_API_KEY", "")
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "")

# --- Assistant : embeddings et document de procédure -----------------------------------
EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "local")
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "")
PROCEDURE_DOCUMENT = BASE_DIR / "data" / "procedure_admission.docx"