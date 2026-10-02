"""Modèle de données de l'infirmerie.

Deux objets centraux :
  - Patient    : la fiche, l'identité, l'état clinique permanent
  - Consultation : un acte daté, qui porte le bilan de santé

Le bilan est rattaché à une consultation, pas au patient : c'est ce qui
permet de répondre à "quel était son bilan au 12 mars ?".
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Laboratoire(models.Model):
    """Un laboratoire de référence.

    Les fourchettes ne sont pas universelles : elles dépendent de la
    méthode d'analyse et de l'appareil. Elles sont donc rattachées à un
    laboratoire nommé, jamais codées en dur dans l'application.

    Une fourchette est *signée* : `valide_par` et `date_validation`
    disent qui l'a validée et quand. Sans ça, une référence saisie par
    erreur serait indiscernable d'une référence validée par un biologiste.
    """

    nom = models.CharField("nom du laboratoire", max_length=200)
    description = models.TextField("description", blank=True)
    actif = models.BooleanField("actif", default=True)

    valide_par = models.CharField("références validées par", max_length=150, blank=True)
    date_validation = models.DateField("validées le", null=True, blank=True)

    cree_le = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "laboratoire"
        verbose_name_plural = "laboratoires"
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def nb_references(self):
        return self.intervalles.count()


class ReferenceIntervalle(models.Model):
    """Une fourchette de référence, pour un paramètre et un contexte donnés.

    Le contexte est ce qui distingue une fourchette d'une autre : le
    sexe, l'âge, la période de validité. Un paramètre peut ainsi avoir
    plusieurs intervalles sans qu'aucun ne soit « le bon » par défaut —
    la résolution se fait par priorité explicite, jamais par écrasement.
    """

    laboratoire = models.ForeignKey(
        Laboratoire, on_delete=models.CASCADE, related_name="intervalles",
        verbose_name="laboratoire",
    )

    code = models.CharField("code", max_length=30, db_index=True)
    libelle = models.CharField("libellé", max_length=200)
    unite = models.CharField("unité", max_length=30, blank=True)

    norme_min = models.FloatField("norme basse", null=True, blank=True)
    norme_max = models.FloatField("norme haute", null=True, blank=True)

    # Contexte de validité
    sexe = models.CharField(
        "sexe", max_length=1, default="",
        help_text="H, F, M = tous les sexes, vide = tous",
    )
    age_min = models.IntegerField("âge min (années)", null=True, blank=True)
    age_max = models.IntegerField("âge max (années)", null=True, blank=True)

    # Période de validité : une fourchette abrogée reste consultable, pour
    # pouvoir démontrer ce qui s'appliquait à la date d'un soin.
    date_debut = models.DateField("en vigueur depuis", null=True, blank=True)
    date_fin = models.DateField("abrogée le", null=True, blank=True)

    class Meta:
        verbose_name = "fourchette de référence"
        verbose_name_plural = "fourchettes de référence"
        ordering = ["laboratoire", "libelle"]
        indexes = [models.Index(fields=["code", "sexe", "age_min", "age_max"])]

    def __str__(self):
        return f"{self.libelle} [{self.sexe or 'T'}] {self.norme_min}–{self.norme_max} {self.unite}"

    @property
    def est_applicable(self):
        """Une fourchette sans borne haute ET sans borne basse ne sert à rien."""
        return self.norme_min is not None or self.norme_max is not None

    def contient(self, valeur):
        """Compare une valeur. Ne conclut que si les deux bornes sont là.

        Une seule borne ne permet pas de conclure « normal » : un minimum
        sans maximum ne dit rien sur un résultat élevé.
        """
        if self.norme_min is None or self.norme_max is None:
            return None
        if valeur < self.norme_min:
            return "bas"
        if valeur > self.norme_max:
            return "haut"
        return "normal"


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
        """normal | bas | haut | inconnu — compare la valeur aux normes.

        Règle d'or : ne jamais conclure sans norme complète. On ne peut
        affirmer « normal » que si la valeur est bornée des deux côtés : un
        minimum sans maximum ne dit rien sur un résultat élevé.

        Trois cas distincts, tous en « inconnu » :
          - la valeur n'est pas numérique (« négatif », « traces »)
          - aucune borne n'est renseignée
          - une seule des deux bornes l'est

        Sans cette distinction, un résultat dont on ignore la norme
        s'afficherait comme normal — donc rassurant. Or les fourchettes ne
        sont pas encore alignées sur le laboratoire de l'établissement :
        c'est le cas le plus fréquent aujourd'hui.
        """
        v = self.valeur_numerique
        if v is None:
            return "inconnu"
        if self.norme_min is None or self.norme_max is None:
            return "inconnu"
        if v < self.norme_min:
            return "bas"
        if v > self.norme_max:
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


# ------------------------------------------------------------------ Relances


class TypeRelance(models.TextChoices):
    SOIN = "soin", "Relance de soin"
    VACCIN = "vaccin", "Rappel de vaccin"
    BILAN = "bilan", "Bilan à refaire"
    ADMIN = "administratif", "Rappel administratif"


class StatutRelance(models.TextChoices):
    BROUILLON = "brouillon", "En attente de validation"
    VALIDEE = "validee", "Validée — à envoyer"
    ENVOYEE = "envoyee", "Envoyée"
    ABANDONNEE = "abandonnee", "Abandonnée"


class Relance(models.Model):
    """Une relance rédigée par l'agent, en attente de validation humaine.

    ⚠ Cette application n'envoie RIEN. Elle rédige des brouillons ; la
    validation puis l'envoi restent des décisions humaines. Un champ
    « envoyée » documenterait un envoi fait ailleurs, jamais une action
    automatique : c'est ce qui distingue cet outil d'un automate.
    """

    patient = models.ForeignKey(
        "Patient", on_delete=models.CASCADE, related_name="relances", verbose_name="patient"
    )
    type_relance = models.CharField(
        "type", max_length=20, choices=TypeRelance.choices, default=TypeRelance.SOIN
    )

    objet = models.CharField("objet", max_length=200)
    corps = models.TextField("message rédigé")
    motif = models.TextField(
        "pourquoi cette relance", blank=True,
        help_text="Ce qui a déclenché la proposition, en termes factuels",
    )

    statut = models.CharField(
        "statut", max_length=20, choices=StatutRelance.choices, default=StatutRelance.BROUILLON
    )

    # Traçabilité de la validation humaine
    redigee_le = models.DateTimeField("rédigée le", auto_now_add=True)
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="relances_validees", verbose_name="validée par",
    )
    validee_le = models.DateTimeField("validée le", null=True, blank=True)
    envoyee_le = models.DateTimeField("envoyée le", null=True, blank=True)

    class Meta:
        verbose_name = "relance"
        verbose_name_plural = "relances"
        ordering = ["-redigee_le"]
        indexes = [models.Index(fields=["statut", "-redigee_le"])]

    def __str__(self):
        return f"{self.get_type_relance_display()} — {self.patient} — {self.objet}"

    @property
    def est_envoyee_automatiquement(self):
        """Toujours faux. Ce champ existe pour le dire dans le code."""
        return False

    @property
    def peut_etre_validee(self):
        return self.statut == StatutRelance.BROUILLON

    @property
    def age_jours(self):
        return (timezone.now() - self.redigee_le).days
