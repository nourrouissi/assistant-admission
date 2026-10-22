"""
Formulaire des coordonnées du prospect, validé par Django.

Le LLM extrait les coordonnées des messages du prospect ; c'est ce formulaire,
et non le LLM, qui décide si elles sont valides.

Les doublons ne sont pas vérifiés ici, mais au clic sur « Confirmer » (services.py) :
pendant la collecte, le chatbot ne révèle pas si un e-mail ou un téléphone est déjà enregistré.
"""

import re

import phonenumbers
from django import forms

# Lettres (accents compris), séparées par un espace, un tiret ou une apostrophe
NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:[ '’-][^\W\d_]+)*$")


class ApplicantForm(forms.Form):
    last_name = forms.CharField(label="Nom", min_length=2, max_length=60)
    first_name = forms.CharField(label="Prénom", min_length=2, max_length=60)
    email = forms.EmailField(label="E-mail", max_length=254)
    phone = forms.CharField(label="Téléphone", max_length=30)

    def _clean_name(self, field: str) -> str:
        value = " ".join(self.cleaned_data[field].split())
        if not NAME_PATTERN.fullmatch(value):
            raise forms.ValidationError("Lettres uniquement (espaces, tirets et apostrophes acceptés).")
        return value

    def clean_last_name(self) -> str:
        return self._clean_name("last_name")

    def clean_first_name(self) -> str:
        return self._clean_name("first_name")

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()

    def clean_phone(self) -> str:
        """Numéro tunisien (8 chiffres, avec ou sans +216) ou international (+XXX) -> format E.164."""
        try:
            number = phonenumbers.parse(self.cleaned_data["phone"], "TN")
        except phonenumbers.NumberParseException:
            number = None
        if number is None or not phonenumbers.is_valid_number(number):
            raise forms.ValidationError("Numéro de téléphone invalide.")
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
