"""Compare ce que l'agent a proposé avec ce que les humains ont fait.

C'est l'outil de la phase d'observation : avant d'autoriser une action, on
regarde si l'agent aurait pris la même décision que le soignant. Une règle
qui propose beaucoup et que personne ne suit n'est pas une règle utile —
c'est du bruit qui finit par être ignoré.

    python manage.py agent_comparer           # 30 derniers jours
    python manage.py agent_comparer --jours 60
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from dossier.models import DecisionAgent, Relance, Suivi


class Command(BaseCommand):
    help = "Mesure l'accord entre les décisions de l'agent et celles des humains."

    def add_arguments(self, parser):
        parser.add_argument(
            "--jours", type=int, default=30, help="Fenêtre d'observation (30).",
        )

    def handle(self, *args, **options):
        depuis = timezone.now() - timedelta(days=options["jours"])
        decisions = DecisionAgent.objects.filter(cree_le__gte=depuis)

        if not decisions.exists():
            self.stdout.write(
                "Aucune décision enregistrée sur la période. Lancez "
                "`manage.py agent_decision` en simulation."
            )
            return

        simulation = decisions.filter(mode="simulation")
        appliquees = decisions.filter(mode="appliquee")
        annulees = appliquees.filter(annulee_le__isnull=False)

        confirmees, ignorees = [], []
        for d in simulation:
            if d.action == "suivi_controle":
                suivi = Suivi.objects.filter(
                    patient=d.patient, description__startswith=d.resume[:40]
                ).exists()
            else:
                suivi = Relance.objects.filter(
                    patient=d.patient, objet=d.resume[:200]
                ).exists()
            (confirmees if suivi else ignorees).append(d)

        self.stdout.write("")
        self.stdout.write(f"Période : {options['jours']} derniers jours")
        self.stdout.write("")
        self.stdout.write(f"  Simulation      : {simulation.count()} décision(s)")
        self.stdout.write(f"  Appliquées      : {appliquees.count()} décision(s)")
        self.stdout.write(f"  Annulées        : {annulees.count()} décision(s)")
        self.stdout.write("")

        if simulation.exists():
            taux = 100 * len(confirmees) / simulation.count()
            self.stdout.write(
                f"  Accord humain   : {len(confirmees)}/{simulation.count()} "
                f"({taux:.0f} %)"
            )
            self.stdout.write("")

            if ignorees:
                self.stdout.write("Décisions que personne n'a suivies :")
                for d in ignorees[:15]:
                    self.stdout.write(
                        f"  {d.patient.numero_dossier if d.patient else '—':<10} "
                        f"{d.resume[:70]}"
                    )
                self.stdout.write("")
                self.stdout.write(
                    "Une règle peu suivie est soit mal calibrée, soit inutile. "
                    "C'est le moment de la retirer ou d'ajuster son seuil."
                )
            else:
                self.stdout.write(
                    "Toutes les propositions ont été suivies : la règle est "
                    "calibrée, l'autonomie peut être envisagée."
                )
