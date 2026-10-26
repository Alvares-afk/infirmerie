"""Purge des dossiers dont la conservation n'est plus justifiée.

Une donnée de santé ne se garde pas indéfiniment : passé le délai fixé avec
l'établissement, elle doit disparaître. Cette commande est le seul moyen de
le faire, et elle est volontairement lente à armer.

Trois garde-fous :

  1. **Simulation par défaut.** Sans `--confirmer`, rien n'est supprimé :
     la commande affiche ce qu'elle ferait, dossier par dossier.
  2. **Date obligatoire.** Pas de « tout supprimer » implicite : il faut
     dire avant quelle date.
  3. **Trace permanente.** La suppression est inscrite au journal d'audit
     avec le nombre de dossiers ; le journal, lui, n'est jamais purgé.

La dernière activité retenue est la plus récente entre la consultation, le
bilan et la relance. Un dossier sans aucune activité est daté de sa
création : on ne peut pas le considérer comme ancien par hasard.
"""

from datetime import date, datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from dossier.audit import Action, journaliser
from dossier.models import Bilan, Consultation, Patient, Relance


def _date_saisie(valeur):
    try:
        return datetime.strptime(valeur, "%Y-%m-%d").date()
    except ValueError:
        raise CommandError(
            f"Date invalide : « {valeur} ». Format attendu : AAAA-MM-JJ."
        )


class Command(BaseCommand):
    help = "Supprime les dossiers dont la dernière activité est antérieure à une date."

    def add_arguments(self, parser):
        parser.add_argument(
            "--avant",
            required=True,
            help="Date seuil (AAAA-MM-JJ) : les dossiers sans activité depuis "
                 "cette date sont concernés.",
        )
        parser.add_argument(
            "--confirmer",
            action="store_true",
            help="Supprime réellement. Sans cette option, la commande ne fait "
                 "qu'afficher ce qu'elle supprimerait.",
        )
        parser.add_argument(
            "--motif",
            default="",
            help="Motif inscrit au journal d'audit (ex. « conservation 5 ans »).",
        )

    def handle(self, *args, **options):
        seuil = _date_saisie(options["avant"])

        if seuil >= timezone.localdate():
            raise CommandError(
                "La date seuil doit être passée. Pour purger les dossiers "
                "inactifs depuis plus de cinq ans, indiquez par exemple "
                "la date d'il y a cinq ans."
            )

        limites = {}

        def retenir(pid, quand):
            if pid and (pid not in limites or quand > limites[pid]):
                limites[pid] = quand

        for ligne in Consultation.objects.values("patient_id").annotate(
            derniere=Max("date")
        ):
            retenir(ligne["patient_id"], ligne["derniere"])

        # Un bilan n'a pas de patient direct : il pend à la consultation.
        for ligne in Bilan.objects.values("consultation__patient_id").annotate(
            derniere=Max("date")
        ):
            retenir(ligne["consultation__patient_id"], ligne["derniere"])

        # Une relance compte aussi : un rappel récent prouve que le dossier
        # est encore suivi. On retient la plus récente de ses trois dates.
        for relance in Relance.objects.all():
            dates = [d for d in (
                relance.redigee_le, relance.validee_le, relance.envoyee_le
            ) if d]
            if dates:
                retenir(relance.patient_id, max(dates).date())

        concernes = []
        for patient in Patient.objects.all().order_by("numero_dossier"):
            derniere = limites.get(patient.pk)
            if derniere is None:
                derniere = patient.cree_le.date()
            if derniere < seuil:
                concernes.append((patient, derniere))

        if not concernes:
            self.stdout.write(
                f"Aucun dossier inactif depuis le {seuil:%d/%m/%Y}. Rien à purger."
            )
            return

        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            f"{len(concernes)} dossier(s) inactif(s) depuis avant le {seuil:%d/%m/%Y} :"
        ))
        self.stdout.write("")
        for patient, derniere in concernes:
            self.stdout.write(
                f"  {patient.numero_dossier:<10} dernière activité : "
                f"{derniere:%d/%m/%Y}"
            )

        if not options["confirmer"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Simulation : rien n'a été supprimé.\n"
                "Relancez avec --confirmer pour supprimer réellement."
            ))
            return

        nombre = len(concernes)
        with transaction.atomic():
            for patient, _ in concernes:
                patient.delete()
            journaliser(
                None,
                Action.SUPPRESSION,
                objet=f"purge de {nombre} dossier(s) antérieurs au {seuil:%d/%m/%Y}"
                      + (f" — {options['motif']}" if options["motif"] else ""),
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{nombre} dossier(s) supprimé(s). Opération inscrite au journal."
        ))
        self.stdout.write(
            "Pensez à vérifier la sauvegarde : elle contient encore ces dossiers "
            "si elle est antérieure à la purge."
        )
