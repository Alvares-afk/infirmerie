"""Fait tourner l'agent de décision.

Mode par défaut : **simulation**. L'agent écrit ce qu'il ferait, sans rien
créer. C'est le mode à laisser tourner deux semaines avant d'autoriser quoi
que ce soit.

    python manage.py agent_decision                 # simulation, affiche les décisions
    python manage.py agent_decision --appliquer     # exécute les actions de classe A

Ce que l'agent ne peut pas faire, quoi qu'on tape : une action absente du
catalogue, une action de classe C, une action irréversible. L'appel lève une
erreur plutôt que de passer outre.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from dossier.agent import (
    CATALOGUE, appliquer, decisions, deja_traitee, relance_deja_ouverte,
)
from dossier.audit import Action as ActionAudit, journaliser
from dossier.models import DecisionAgent, ModeDecision


class Command(BaseCommand):
    help = "Évalue les règles de l'agent et enregistre ses décisions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--appliquer", action="store_true",
            help="Exécute réellement les actions de classe A. Sans cette "
                 "option, tout est enregistré en simulation.",
        )

    def handle(self, *args, **options):
        mode = ModeDecision.APPLIQUEE if options["appliquer"] else ModeDecision.SIMULATION
        a_faire = decisions()

        self.stdout.write(
            f"Règles évaluées : {len(a_faire)} décision(s) — mode "
            f"{'application' if options['appliquer'] else 'simulation'}."
        )

        if not a_faire:
            return

        nouvelles = [
            d for d in a_faire
            if not deja_traitee(d, mode) and not relance_deja_ouverte(d)
        ]
        if not nouvelles:
            self.stdout.write("Aucune décision nouvelle.")
            return

        self.stdout.write("")
        for d in nouvelles:
            self.stdout.write(
                f"  [{d.action.classe}] {d.patient.numero_dossier:<10} "
                f"{d.action.libelle} — {d.motif}"
            )

        if mode == ModeDecision.SIMULATION:
            with transaction.atomic():
                for d in nouvelles:
                    DecisionAgent.objects.create(
                        regle=d.regle, action=d.action.code, classe=d.action.classe,
                        patient=d.patient, resume=d.resume[:240], motif=d.motif[:240],
                        mode=mode, reversible=d.action.reversible,
                    )
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Simulation : rien n'a été appliqué. Les décisions sont "
                "enregistrées pour comparaison."
            ))
            return

        with transaction.atomic():
            for d in nouvelles:
                objet = appliquer(d)
                DecisionAgent.objects.create(
                    regle=d.regle, action=d.action.code, classe=d.action.classe,
                    patient=d.patient, resume=d.resume[:240], motif=d.motif[:240],
                    mode=mode, reversible=d.action.reversible, objet_cree=objet,
                )
                journaliser(
                    None, ActionAudit.CREATION, patient=d.patient,
                    objet=f"agent : {d.action.code}",
                    details=f"règle {d.regle} → {objet}",
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{len(nouvelles)} action(s) appliquée(s). Chacune attend une "
            "validation humaine : rien n'a été envoyé."
        ))
