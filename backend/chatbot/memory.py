"""
Mémoire des conversations (checkpointer LangGraph).

- « postgres » (par défaut) : les conversations sont enregistrées dans PostgreSQL, la
  base déjà utilisée par le projet. Elles survivent à un redémarrage du serveur et
  sont partagées entre plusieurs processus.
- « memory » : conversations gardées en mémoire vive (tests automatisés).
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

# Connexions ouvertes en même temps vers PostgreSQL pour la mémoire des conversations
POOL_SIZE = 5


def conninfo() -> str:
    """Chaîne de connexion PostgreSQL construite à partir des réglages Django."""
    from psycopg.conninfo import make_conninfo

    db = settings.DATABASES["default"]
    return make_conninfo(
        dbname=db["NAME"], user=db["USER"], password=db["PASSWORD"], host=db["HOST"], port=db["PORT"],
    )


def postgres_checkpointer(info: str | None = None):
    """Checkpointer PostgreSQL ; crée ses tables au premier lancement (opération idempotente)."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        info or conninfo(),
        min_size=1,
        max_size=POOL_SIZE,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    saver = PostgresSaver(pool)
    saver.setup()
    return saver


def checkpointer() -> BaseCheckpointSaver:
    if settings.CHAT_MEMORY == "memory":
        return MemorySaver()
    if settings.CHAT_MEMORY == "postgres":
        return postgres_checkpointer()
    raise ImproperlyConfigured("CHAT_MEMORY : valeurs possibles « postgres » ou « memory ».")
