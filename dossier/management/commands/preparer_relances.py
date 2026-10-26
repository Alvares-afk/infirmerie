"""Préparation automatique des relances, sans jamais les envoyer.

Ce que cette commande fait : elle repère les situations qui appellent un
rappel et dépose un **brouillon** de relance pour chacune.

Ce qu'elle ne fait pas, et ne fera pas : envoyer quoi que ce soit, ni
valider à la place du soignant. Une relance part d'un humain, après
relecture. Deux raisons :

  - une valeur hors bornes n'est pas un diagnostic. Automatiser le message
    reviendrait à envoyer une inquiétude au patient sur la foi d'un chiffre ;
  - l'application n'a aucun accès réseau, par construction : c'est ce qui
    garantit que les dossiers ne sortent pas du poste.

Seuls les motifs **administratifs** sont préparés par défaut, parce qu'ils
ne souffrent aucune interprétation :

  - un suivi dont l'échéance est passée et qui n'est pas fait ;
  - un bilan de santé qui date de plus de douze mois.

Les anomalies biologiques ne sont préparées que si on le demande
explicitement (`--avec-anomalies`) : c'est un jugement clinique, il reste au
soignant.

Usage :
    python manage.py preparer_relances --essai
    python manage.py preparer_relances
    python manage.py preparer_relances --avec-anomalies
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from dossier.models import Bilan, Patient, Relance, Suivi
from dossier.models import StatutRelance, TypeRelance

DELAI_BILAN = 365  # jours


class Command(BaseCommand):
    help = "Dépose des brouillons de relance pour les situations à rappeler."

    def add_arguments(self, parser):
        parser.add_argument(
            "--essai", action="store_true",
            help="Affiche ce qui serait préparé, sans rien créer.",
        )
        parser.add_argument(
            "--avec-anomalies", dest="avec_anomalies", action="store_true",
            help="Prépare aussi une relance pour les valeurs hors bornes du "
                 "dernier bilan (jugement clinique : à relire).",
        )

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        aujourdhui = timezone.localdate()
        a_preparer = []

        # 1. Suivis en retard -------------------------------------------
        for suivi in Suivi.objects.filter(fait=False, echeance__lt=aujourdhui).select_related("patient"):
            a_preparer.append({
                "patient": suivi.patient,
                "type": TypeRelance.SOIN,
                "objet": f"Suivi en retard : {suivi.description[:150]}",
                "motif": f"Échéance du {suivi.echeance:%d/%m/%Y} dépassée.",
                "corps": (
                    f"Bonjour,\n\n"
                    f"Un contrôle prévu le {suivi.echeance:%d/%m/%Y} "
                    f"n'a pas encore été réalisé : {suivi.description}.\n\n"
                    f"Souhaitez-vous convenir d'un rendez-vous ?\n\n"
                    f"L'infirmerie"
                ),
            })

        # 2. Bilans de plus de douze mois --------------------------------
        seuil = aujourdhui - timedelta(days=DELAI_BILAN)
        for patient in Patient.objects.all():
            dernier = (
                Bilan.objects.filter(consultation__patient=patient)
                .order_by("-date")
                .first()
            )
            if dernier is None:
                continue  # jamais de bilan : décision du soignant, pas un rappel
            if dernier.date <= seuil:
                a_preparer.append({
                    "patient": patient,
                    "type": TypeRelance.BILAN,
                    "objet": "Bilan de santé à renouveler",
                    "motif": f"Dernier bilan le {dernier.date:%d/%m/%Y} "
                             f"(plus de {DELAI_BILAN // 365} an).",
                    "corps": (
                        "Bonjour,\n\n"
                        f"Votre dernier bilan de santé date du {dernier.date:%d/%m/%Y}.\n"
                        "Il est recommandé de le renouveler.\n\n"
                        "Souhaitez-vous convenir d'un rendez-vous ?\n\n"
                        "L'infirmerie"
                    ),
                })

        # 3. Anomalies biologiques — sur demande --------------------------
        if options["avec_anomalies"]:
            for patient in Patient.objects.all():
                dernier = (
                    Bilan.objects.filter(consultation__patient=patient)
                    .order_by("-date")
                    .first()
                )
                if dernier is None:
                    continue
                for mesure in dernier.mesures.all():
                    etat = getattr(mesure, "interpretation", None)
                    if etat not in ("haut", "bas"):
                        continue
                    a_preparer.append({
                        "patient": patient,
                        "type": TypeRelance.SOIN,
                        "objet": f"Résultat à expliquer : {mesure.parametre}",
                        "motif": f"{mesure.parametre} {mesure.valeur} {mesure.unite} "
                                 f"hors bornes au bilan du {dernier.date:%d/%m/%Y}.",
                        "corps": (
                            "Bonjour,\n\n"
                            f"Un résultat de votre bilan du {dernier.date:%d/%m/%Y} "
                            f"mérite une explication : {mesure.parametre}.\n\n"
                            "Merci de prendre contact avec l'infirmerie.\n\n"
                            "L'infirmerie"
                        ),
                    })

        # 4. Ne pas doubler une relance déjà en attente -------------------
        en_attente = set(
            Relance.objects.filter(
                statut__in=[StatutRelance.BROUILLON, StatutRelance.VALIDEE]
            ).values_list("patient_id", "objet")
        )
        nouveaux = [
            item for item in a_preparer
            if (item["patient"].pk, item["objet"]) not in en_attente
        ]

        if not nouveaux:
            self.stdout.write("Aucune relance à préparer : rien de nouveau.")
            return

        self.stdout.write("")
        self.stdout.write(f"{len(nouveaux)} relance(s) à préparer :")
        self.stdout.write("")
        for item in nouveaux:
            self.stdout.write(
                f"  {item['patient'].numero_dossier:<10} {item['objet'][:60]}"
            )
            self.stdout.write(f"             {item['motif']}")

        if options["essai"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Mode essai : aucun brouillon créé."
            ))
            return

        with transaction.atomic():
            for item in nouveaux:
                Relance.objects.create(
                    patient=item["patient"],
                    type_relance=item["type"],
                    objet=item["objet"][:200],
                    corps=item["corps"],
                    motif=item["motif"],
                    statut=StatutRelance.BROUILLON,
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{len(nouveaux)} brouillon(s) déposé(s). Rien n'a été envoyé : "
            "chaque relance attend une relecture."
        ))
