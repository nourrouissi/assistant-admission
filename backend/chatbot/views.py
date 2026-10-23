"""API du chatbot : POST /api/chat/"""

import uuid

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from config.i18n import DEFAULT_LANGUAGE, LANGUAGES, detect_language, use_language

from .graph import register, registration_action, registration_stage, reply

ACTIONS = ["register", "confirm", "modify", "cancel"]


class ChatRequestSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
    message = serializers.CharField(required=False, max_length=2000)
    action = serializers.ChoiceField(choices=ACTIONS, required=False)
    formation_id = serializers.IntegerField(required=False)
    lang = serializers.ChoiceField(choices=LANGUAGES, required=False, default=DEFAULT_LANGUAGE)

    def validate(self, data):
        if ("message" in data) == ("action" in data):
            raise serializers.ValidationError("Envoyer soit « message », soit « action ».")
        if data.get("action") == "register" and "formation_id" not in data:
            raise serializers.ValidationError({"formation_id": "Obligatoire pour l'action « register »."})
        return data


class ChatView(APIView):
    """
    Entrée (un seul des deux) :
      - {"session_id": "...", "message": "..."}                    message écrit (coordonnées comprises)
      Champ facultatif « lang » : langue de l'interface, fr (par défaut), en ou ar. Un message écrit
      reçoit sa réponse dans sa propre langue ; « lang » est alors renvoyé dans la sortie.
      - {"session_id": "...", "action": "...", ...}                bouton de l'interface :
          register (+ formation_id)  bouton « S'inscrire » d'une carte
          confirm | modify | cancel  boutons du récapitulatif (cancel aussi pendant la collecte)
    Sortie : {"session_id": "...", "blocks": [...], "registration": "collect" | "summary" | null}
      - {"type": "text", "text": "..."}
      - {"type": "formations", "items": [cartes : diplôme, spécialité, école, critères (+ éligibilité)]}
      - {"type": "registration_summary", "formation": carte, "applicant": {...}, "actions": [...]}
      - {"type": "registration_result", "outcome": "created" | "duplicate" | "unavailable" | "cancelled"}
          fin de l'inscription ; si « created » : aussi "status" (« Nouvelle ») et "formation" (carte)
      `registration` : étape de l'inscription en cours (collecte des coordonnées ou récapitulatif), sinon null.

    Nombre de requêtes limité par adresse IP (CHAT_RATE_LIMIT) : chaque message appelle un LLM
    et peut créer une demande d'inscription.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"

    def post(self, request):
        data = ChatRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        session_id = values["session_id"] or str(uuid.uuid4())

        # Langue de la réponse : celle du message écrit par le prospect ; à défaut (bouton, message
        # neutre comme un nom ou un numéro), celle de l'interface (français par défaut)
        language = detect_language(values["message"], values["lang"]) if "message" in values else values["lang"]
        with use_language(language):
            if "message" in values:
                blocks = reply(session_id, values["message"])
            elif values["action"] == "register":
                blocks = register(session_id, values["formation_id"])
            else:
                blocks = registration_action(session_id, values["action"])
        payload = {"session_id": session_id, "blocks": blocks, "registration": registration_stage(session_id)}
        if language != DEFAULT_LANGUAGE or values["lang"] != DEFAULT_LANGUAGE:
            payload["lang"] = language      # l'interface passe dans la langue de la réponse
        return Response(payload)
