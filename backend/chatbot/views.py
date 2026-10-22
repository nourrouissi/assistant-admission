"""API du chatbot : POST /api/chat/"""

import uuid

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .graph import reply


class ChatRequestSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
    message = serializers.CharField(max_length=2000)


class ChatView(APIView):
    """
    Entrée  : {"session_id": "...", "message": "..."}  (sans session_id, une session est créée)
    Sortie  : {"session_id": "...", "blocks": [...]}
      - {"type": "text", "text": "..."}
      - {"type": "formations", "items": [cartes : diplôme, spécialité, école, critères (+ éligibilité)]}
    """

    def post(self, request):
        data = ChatRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        session_id = data.validated_data["session_id"] or str(uuid.uuid4())
        blocks = reply(session_id, data.validated_data["message"])
        return Response({"session_id": session_id, "blocks": blocks})
