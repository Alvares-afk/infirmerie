"""Modèle de données de l'infirmerie.

Deux objets centraux :
  - Patient    : la fiche, l'identité, l'état clinique permanent
  - Consultation : un acte daté, qui porte le bilan de santé

Le bilan est rattaché à une consultation, pas au patient : c'est ce qui
permet de répondre à "quel était son bilan au 12 mars ?".
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Sexe(models.TextChoices):
    F = "F", "Féminin"
    M = "M", "Masculin"
    A = "A", "Autre"


# ---------------------------------------------------------------- Patient


class Allergie(models.Model):
    """Allergie connue. Alerte affichée à l'ouverture de toute consultation."""

    patient = models.ForeignKey(
        "Patient", on_delete=models.CASCADE, related_name="allergies", verbose_name="patient"
    )
    substance = models.CharField("substance", max_length=200)
    reaction = models.CharField("réaction observée", max_length=300, blank=True)
    gravite = models.CharField(
        "gravité", max_length=20,
        choices=[("legere", "Légère"), ("moderee", "Modérée"), ("severe", "Sévère")],
        default="legere",
    )

    class Meta:
        verbose_name = "allergie"
        verbose_name_plural = "allergies"
        ordering = ["-gravite", "substance"]

    def __str__(self):
        return f"{self.substance} ({self.get_gravite_display()})"


class Patient(models.Model):
    nom = models.CharField("nom", max_length=100)
    prenom = models.CharField("prénom", max_length=100)
    date_naissance = models.DateField("date de naissance")
    sexe = models.CharField("sexe", max_length=1, choices=Sexe.choices, default=Sexe.F)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.CharField("email", max_length=200, blank=True)
    adresse = models.TextField("adresse", blank=True)

    numero_dossier = models.CharField("n° de dossier", max_length=20, unique=True, blank=True)
    medecin_traitant = models.CharField("médecin traitant", max_length=200, blank=True)
    notes = models.TextField("notes administratives", blank=True)
    actif = models.BooleanField("actif", default=True)

    cree_le = models.DateTimeField("créé le", auto_now_add=True)
    modifie_le = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "patient"
        verbose_name_plural = "patients"
        ordering = ["nom", "prenom"]
        indexes = [models.Index(fields=["nom", "prenom"])]

    def __str__(self):
        return f"{self.nom} {self.prenom}"

    @property
    def age(self):
        today = timezone.localdate()
        b = self.date_naissance
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))

    @property
    def initiales(self):
        return f"{self.prenom[0] if self.prenom else ''}{self.nom[0] if self.nom else ''}".upper()

    def dernier_bilan(self):
        b = Bilan.objects.filter(consultation__patient=self).order_by("-date").first()
        return b

    def allergies_known(self):
        return self.allergies.all()


# ---------------------------------------------------------- Consultation


class Consultation(models.Model):
    patient = models.ForeignKey(
        "Patient", on_delete=models.CASCADE, related_name="consultations", verbose_name="patient"
    )
    date = models.DateField("date", default=timezone.localdate)
    soignant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True, verbose_name="soignant",
    )

    motif = models.TextField("motif de consultation", blank=True)
    diagnostic = models.TextField("diagnostic", blank=True)
    observations = models.TextField("observations", blank=True)

    constantes = models.JSONField(
        "constantes", blank=True, null=True,
        help_text="Tension, pouls, température, poids, taille, IMC",
    )
    prescription = models.TextField("prescription", blank=True)
    statut = models.CharField(
        "statut", max_length=20,
        choices=[("ouverte", "Ouverte"), ("cloturee", "Clôturée")],
        default="ouverte",
    )

    cree_le = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "consultation"
        verbose_name_plural = "consultations"
        ordering = ["-date", "-cree_le"]

    def __str__(self):
        return f"{self.patient} — {self.date}"

    @property
    def a_des_alertes(self):
        return self.patient.allergies.exists()

    @property
    def imc(self):
        c = self.constantes or {}
        try:
            poid = float(str(c.get("poids", "")).replace(",", "."))
            taille = float(str(c.get("taille", "")).replace(",", "."))
        except (TypeError, ValueError):
            return None
        if taille <= 0:
            return None
        return round(poid / (taille / 100) ** 2, 1)


# ------------------------------------------------------------ Bilan santé


class Bilan(models.Model):
    """Bilan de santé : une série de mesures datées et interprétées.

    Chaque ligne porte sa propre fourchette de référence, car elle dépend
    du dosage, du sexe et parfois de l'âge.
    """

    consultation = models.ForeignKey(
        "Consultation", on_delete=models.CASCADE, related_name="bilans", verbose_name="consultation"
    )
    date = models.DateField("date du bilan", default=timezone.localdate)
    type_examen = models.CharField(
        "type d'examen", max_length=100, blank=True,
        help_text="Bilan sanguin, imagerie, ECG…",
    )
    compte_rendu = models.TextField("compte rendu", blank=True)
    laboratoire = models.CharField("laboratoire", max_length=200, blank=True)

    class Meta:
        verbose_name = "bilan de santé"
        verbose_name_plural = "bilans de santé"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"Bilan du {self.date} — {self.get_patient_nom()}"

    def get_patient_nom(self):
        return str(self.consultation.patient)

    @property
    def nb_mesures(self):
        return self.mesures.count()

    @property
    def a_des_anomalies(self):
        return any(m.anormalite != "normal" for m in self.mesures.all())

    def resume(self):
        """Résumé court : nb de mesures, dont combien hors normes."""
        mesures = list(self.mesures.all())
        anomalies = [m for m in mesures if m.anormalite != "normal"]
        return {"total": len(mesures), "anomalies": len(anomalies), "liste": anomalies}


class Mesure(models.Model):
    """Une ligne d'analyse : un paramètre, une valeur, une norme."""

    bilan = models.ForeignKey(
        "Bilan", on_delete=models.CASCADE, related_name="mesures", verbose_name="bilan"
    )
    parametre = models.CharField("paramètre", max_length=120)
    valeur = models.CharField("valeur", max_length=60)
    unite = models.CharField("unité", max_length=30, blank=True)

    norme_min = models.FloatField("norme min", null=True, blank=True)
    norme_max = models.FloatField("norme max", null=True, blank=True)
    reference = models.CharField("référence", max_length=200, blank=True)

    class Meta:
        verbose_name = "mesure"
        verbose_name_plural = "mesures"
        ordering = ["parametre"]

    def __str__(self):
        return f"{self.parametre} : {self.valeur} {self.unite}"

    @property
    def valeur_numerique(self):
        try:
            return float(str(self.valeur).replace(",", ".").strip().split()[0])
        except (ValueError, IndexError):
            return None

    @property
    def anormalite(self):
        """normal | bas | haut — interprete la valeur contre les normes.

        Une valeur non numérique (ex. "négatif") n'est pas classée ici :
        elle doit être jugée à la lecture, par le soignant.
        """
        v = self.valeur_numerique
        if v is None:
            return "inconnu"
        if self.norme_min is not None and v < self.norme_min:
            return "bas"
        if self.norme_max is not None and v > self.norme_max:
            return "haut"
        return "normal"

    @property
    def est_anormal(self):
        return self.anormalite in ("bas", "haut")

    @property
    def libelle_anomalie(self):
        return {"bas": "Bas", "haut": "Haut", "inconnu": "À qualifier"}.get(
            self.anormalite, "Normal"
        )


# ------------------------------------------------------- Suivi des dossiers


class Suivi(models.Model):
    """Tâche de suivi : relance, bilan à refaire, point à vérifier.

    Sert notamment à ne pas laisser passer un bilan devenu vieux.
    """

    patient = models.ForeignKey(
        "Patient", on_delete=models.CASCADE, related_name="suivis", verbose_name="patient"
    )
    description = models.CharField("description", max_length=300)
    echeance = models.DateField("échéance", null=True, blank=True)
    fait = models.BooleanField("fait", default=False)
    cree_le = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "suivi"
        verbose_name_plural = "suivis"
        ordering = ["fait", "echeance", "-cree_le"]

    def __str__(self):
        return self.description

    @property
    def en_retard(self):
        from datetime import date
        return bool(self.echeance and not self.fait and self.echeance < date.today())
