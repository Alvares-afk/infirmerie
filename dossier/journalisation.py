"""Journal d'accès aux données de santé.

Ce que l'on trace, et pourquoi :
  - qui a ouvert quel dossier, quand
  - qui a créé ou modifié une consultation, un bilan, un traitement
  - les échecs d'accès : un secretariat qui tente d'atteindre un dossier
    clinique laisse une trace, ce qui permet de le détecter

Ce que l'on ne trace jamais : ni le contenu d'un bilan, ni une valeur
chiffrée, ni le motif d'une consultation. Le journal dit QUEL dossier a été
ouvert, jamais CE QU'IL CONTIENT. Un journal d'accès contenant les valeurs
de biologie serait lui-même un fichier de données de santé à protéger.
"""

from django.conf import settings
from django.db import models


class Action(models.TextChoices):
    LECTURE = "lecture", "Consultation du dossier"
    CREATION = "creation", "Création"
    MODIFICATION = "modification", "Modification"
    SUPPRESSION = "suppression", "Suppression"
    ACCES_REFUSE = "refus", "Accès refusé"


class JournalAcces(models.Model):
    """Une ligne d'audit. Écrite en append-only, jamais modifiée ensuite."""

    horodatage = models.DateTimeField("horodatage", auto_now_add=True, db_index=True)

    # Qui
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="journaux", verbose_name="utilisateur",
    )
    identifiant_utilisateur = models.CharField(
        "identifiant (conservé même si le compte est supprimé)", max_length=150, blank=True
    )
    role = models.CharField("rôle au moment de l'action", max_length=30, blank=True)

    # Quoi — on garde la référence, jamais le contenu
    patient = models.ForeignKey(
        "Patient", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="journaux", verbose_name="patient",
    )
    numero_dossier = models.CharField("n° de dossier", max_length=20, blank=True)
    objet = models.CharField("objet concerné", max_length=120, blank=True)

    # Comment
    action = models.CharField("action", max_length=20, choices=Action.choices)
    details = models.CharField("détail", max_length=200, blank=True)
    adresse_ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)

    class Meta:
        verbose_name = "journal d'accès"
        verbose_name_plural = "journal d'accès"
        ordering = ["-horodatage"]
        indexes = [models.Index(fields=["-horodatage", "action"])]

    def __str__(self):
        return f"{self.horodatage:%d/%m/%Y %H:%M} — {self.utilisateur} — {self.get_action_display()}"
