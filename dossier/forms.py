"""Formulaires de saisie."""

from django import forms
from django.forms import inlineformset_factory

from .models import Allergie, Bilan, Consultation, Mesure, Patient, Suivi


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            "nom", "prenom", "date_naissance", "sexe", "telephone",
            "email", "adresse", "numero_dossier", "medecin_traitant", "notes",
        ]
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
            "adresse": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_date_naissance(self):
        d = self.cleaned_data["date_naissance"]
        from django.utils import timezone
        if d > timezone.localdate():
            raise forms.ValidationError("La date de naissance ne peut pas être dans le futur.")
        if d.year < 1900:
            raise forms.ValidationError("Date de naissance invalide.")
        return d


class ConsultationForm(forms.ModelForm):
    # Les constantes sont stockées en JSON mais saisies dans des champs dédiés
    tension_arterielle = forms.CharField(
        label="tension artérielle", max_length=20, required=False,
        help_text="systolique/diastolique",
        widget=forms.TextInput(attrs={"placeholder": "120/80"}),
    )
    pouls = forms.IntegerField(label="pouls (bpm)", required=False)
    temperature = forms.DecimalField(
        label="température (°C)", required=False, decimal_places=1, max_digits=5,
    )
    saturation = forms.IntegerField(label="SpO2 (%)", required=False, min_value=0, max_value=100)
    poids = forms.DecimalField(label="poids (kg)", required=False, decimal_places=1, max_digits=6)
    taille = forms.DecimalField(label="taille (cm)", required=False, decimal_places=1, max_digits=6)

    class Meta:
        model = Consultation
        fields = ["date", "motif", "diagnostic", "observations", "prescription"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "motif": forms.Textarea(attrs={"rows": 2}),
            "diagnostic": forms.Textarea(attrs={"rows": 2}),
            "observations": forms.Textarea(attrs={"rows": 3}),
            "prescription": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.constantes:
            for champ, cle in (
                ("tension_arterielle", "tension"),
                ("pouls", "pouls"),
                ("temperature", "temperature"),
                ("saturation", "saturation"),
                ("poids", "poids"),
                ("taille", "taille"),
            ):
                if self.instance.constantes.get(cle) not in (None, ""):
                    self.fields[champ].initial = self.instance.constantes[cle]

    def clean(self):
        cleaned = super().clean()
        c = {}
        for champ in ("tension_arterielle", "pouls", "temperature", "saturation", "poids", "taille"):
            v = cleaned.get(champ)
            if v not in (None, ""):
                cle = "tension" if champ == "tension_arterielle" else champ
                c[cle] = str(v)
        self.instance.constantes = c or None

        # Contrôle de cohérence taille/poids : au-delà, l'IMC n'a pas de sens
        try:
            p = float(str(c.get("poids", "")).replace(",", "."))
            t = float(str(c.get("taille", "")).replace(",", "."))
        except (TypeError, ValueError):
            return cleaned
        if t and (t < 50 or t > 250):
            self.add_error("taille", "Taille hors limites plausibles (50–250 cm).")
        if p and (p < 1 or p > 400):
            self.add_error("poids", "Poids hors limites plausibles (1–400 kg).")
        return cleaned


class AllergieForm(forms.ModelForm):
    class Meta:
        model = Allergie
        fields = ["substance", "reaction", "gravite"]


class BilanForm(forms.ModelForm):
    class Meta:
        model = Bilan
        fields = ["date", "type_examen", "laboratoire", "compte_rendu"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "type_examen": forms.TextInput(attrs={"placeholder": "Bilan sanguin complet"}),
            "compte_rendu": forms.Textarea(attrs={"rows": 3}),
        }


class MesureForm(forms.ModelForm):
    class Meta:
        model = Mesure
        fields = ["parametre", "valeur", "unite", "norme_min", "norme_max", "reference"]
        widgets = {
            "parametre": forms.TextInput(attrs={"placeholder": "Glycémie à jeun"}),
            "valeur": forms.TextInput(attrs={"placeholder": "1,05"}),
            "unite": forms.TextInput(attrs={"placeholder": "g/L"}),
        }


MesureFormSet = inlineformset_factory(
    Bilan, Mesure, form=MesureForm, extra=3, can_delete=True
)


class SuiviForm(forms.ModelForm):
    class Meta:
        model = Suivi
        fields = ["description", "echeance"]
        widgets = {"echeance": forms.DateInput(attrs={"type": "date"})}
