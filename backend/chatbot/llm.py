"""
Modèles de langage de l'assistant, tous appelés via une API compatible OpenAI.

Chaîne de secours : modèle principal -> second modèle du même fournisseur
(quota séparé) -> autre fournisseur. Un modèle sans nom ou sans clé dans le
.env est simplement absent de la chaîne. Les noms de modèles ne sont jamais
écrits dans le code.

Temps de réponse :
  - un modèle dont le quota journalier est épuisé (erreur 429 « per day ») est mis
    de côté pendant QUOTA_PAUSE_SECONDS : les messages suivants passent directement
    au modèle suivant, sans attendre une nouvelle erreur ;
  - en cas d'erreur, un modèle suivi d'un autre passe la main sans réessayer ;
    seul le dernier de la chaîne réessaie une fois.
"""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from openai import RateLimitError

logger = logging.getLogger(__name__)

# Délai maximal d'un appel avant de passer au modèle suivant (secondes)
TIMEOUT_SECONDS = 20

# Durée pendant laquelle un modèle au quota journalier épuisé est écarté de la chaîne (secondes)
QUOTA_PAUSE_SECONDS = 600

# Modèle -> instant (time.monotonic) jusqu'auquel il est écarté
_paused_until: dict[str, float] = {}


def _is_daily_quota(error: BaseException) -> bool:
    """Quota journalier épuisé (Gemini : « …PerDay… », Groq : « requests per day ») ; pas une limite par minute."""
    text = str(error).lower()
    return isinstance(error, RateLimitError) and ("perday" in text or "per day" in text)


class _QuotaWatcher(BaseCallbackHandler):
    """Met un modèle de côté quand son fournisseur répond « quota journalier épuisé »."""

    def __init__(self, key: str) -> None:
        self.key = key

    def on_llm_error(self, error: BaseException, **kwargs) -> None:
        if _is_daily_quota(error):
            _paused_until[self.key] = time.monotonic() + QUOTA_PAUSE_SECONDS
            logger.warning("LLM : quota journalier épuisé pour %s, modèle écarté %d s", self.key, QUOTA_PAUSE_SECONDS)


def _is_paused(key: str) -> bool:
    return _paused_until.get(key, 0) > time.monotonic()


def chat_models() -> list[ChatOpenAI]:
    """
    Les modèles configurés, dans l'ordre de la chaîne de secours. Température 0.
    Les modèles au quota journalier épuisé sont retirés, sauf s'ils le sont tous (on réessaie alors).
    """
    candidates = [
        (settings.LLM_PRIMARY_BASE_URL, settings.LLM_PRIMARY_API_KEY, settings.LLM_PRIMARY_MODEL),
        (settings.LLM_PRIMARY_BASE_URL, settings.LLM_PRIMARY_API_KEY, settings.LLM_SECONDARY_MODEL),
        (settings.LLM_FALLBACK_BASE_URL, settings.LLM_FALLBACK_API_KEY, settings.LLM_FALLBACK_MODEL),
    ]
    configured = [(url, key, model) for url, key, model in candidates if url and key and model]
    if not configured:
        raise ImproperlyConfigured("Aucun modèle de langage configuré : voir les variables LLM_* du fichier .env.")
    chain = [candidate for candidate in configured if not _is_paused(f"{candidate[0]}|{candidate[2]}")] or configured
    return [
        ChatOpenAI(
            base_url=url, api_key=key, model=model, temperature=0, timeout=TIMEOUT_SECONDS,
            max_retries=1 if position == len(chain) - 1 else 0,     # seul le dernier réessaie
            callbacks=[_QuotaWatcher(f"{url}|{model}")],
        )
        for position, (url, key, model) in enumerate(chain)
    ]


class EmptyResponse(Exception):
    """Le modèle a répondu sans rien produire (ex. Gemini : « MALFORMED_FUNCTION_CALL »)."""


def _reject_empty(output):
    """
    Une réponse vide n'est pas une erreur pour l'API : sans ce contrôle, la chaîne de secours
    ne se déclencherait pas et le prospect ne recevrait rien. Vide = aucune sortie structurée,
    ou un message sans texte ni appel d'outil.
    """
    if output is None:
        raise EmptyResponse
    if isinstance(output, AIMessage) and not output.tool_calls:
        content = output.content
        text = content if isinstance(content, str) else "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
        if not text.strip():
            raise EmptyResponse
    return output


def with_fallbacks(runnables: list[Runnable]) -> Runnable:
    """
    Enchaîne des modèles déjà préparés (sortie structurée, outils) : le suivant prend le relais
    en cas d'erreur ou de réponse vide.
    """
    checked = [runnable | RunnableLambda(_reject_empty) for runnable in runnables]
    first, *others = checked
    return first.with_fallbacks(others) if others else first
