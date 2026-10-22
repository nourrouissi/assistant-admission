"""
Indexation du document « Procédure d'admission » dans la base vectorielle.

Le document est découpé par section numérotée (« 1. … » à « 6. … »). Les
sections 1 à 5 sont indexées. La section 6 (« Questions sans réponse dans le
document ») contient des consignes pour le chatbot : elle est reprise dans le
prompt (voir rag.py), pas dans la base.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from docx import Document

from . import retrieval
from .models import ProcedureChunk

# Sections indexées : 1 à 5
LAST_INDEXED_SECTION = 5

_SECTION_TITLE = re.compile(r"^(\d+)\.\s+(.+)$")


@dataclass
class Section:
    number: int
    title: str
    lines: list[str]

    @property
    def text(self) -> str:
        """Texte de l'extrait : titre de la section + contenu complet (puces comprises)."""
        return "\n".join([f"{self.number}. {self.title}", *self.lines])


def _is_bullet(paragraph) -> bool:
    """Vrai si le paragraphe est un élément de liste à puces ou numérotée du document."""
    p_pr = paragraph._p.pPr
    return p_pr is not None and p_pr.numPr is not None


def read_sections(path: Path) -> list[Section]:
    """Sections 1 à 5 du document, dans l'ordre."""
    sections: list[Section] = []
    for paragraph in Document(path).paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        title = None if _is_bullet(paragraph) else _SECTION_TITLE.match(text)
        if title:
            sections.append(Section(int(title.group(1)), title.group(2).strip(), []))
        elif sections:  # le titre général du document, avant la section 1, n'est pas un extrait
            sections[-1].lines.append(f"- {text}" if _is_bullet(paragraph) else text)
    return [section for section in sections if section.number <= LAST_INDEXED_SECTION]


def index_procedure(path: Path) -> int:
    """Indexe les sections 1 à 5 ; relancer la commande met à jour sans créer de doublons."""
    sections = read_sections(path)
    for section in sections:
        ProcedureChunk.objects.update_or_create(
            section_number=section.number,
            defaults={
                "title": section.title,
                "content": section.text,
                "embedding": retrieval.embed_passage(section.text),
            },
        )
    return len(sections)
