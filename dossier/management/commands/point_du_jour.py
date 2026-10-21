"""Point du jour en ligne de commande — pour le message du matin.

Usage :
    python manage.py point_du_jour                # texte prêt à envoyer
    python manage.py point_du_jour --enregistrer  # + marque ce qui a été vu
    python manage.py point_du_jour --json         # pour un autre outil
    python manage.py point_du_jour --avec-noms    # ajoute le nom du patient

Deux principes, et ils sont volontairement dissociés :

  - **Rien n'est filtré.** Tous les points d'attention sont listés chaque
    jour. Un élément déjà signalé reste présent : seule la mention « nouveau »
    change. Une panne d'envoi ne peut donc pas faire disparaître une alerte.
  - **Aucun nom par défaut.** Le message est destiné à sortir de la machine
    (téléphone). Le numéro de dossier suffit à retrouver le patient dans
    l'application. `--avec-noms` existe, mais c'est une décision à assumer :
    un nom de patient sur un service de messagerie, c'est une donnée
    nominative qui quitte le poste.

Sortie vide = rien à signaler. Un planificateur peut s'en servir pour
n'envoyer aucun message les jours sans rien.
"""

import hashlib

from django.core.management.base import BaseCommand
from django.utils import timezone

from dossier.briefing import briefing_du_jour
from dossier.models import Signalement

CATEGORIES = {
    "allergie": "Allergie",
    "bilan": "Bilan",
    "suivi": "Suivi",
    "fresqueur": "Fraîcheur",
}


def empreinte(ligne):
    """Clé stable d'un point d'attention.

    Le titre entre dans l'empreinte : une nouvelle valeur de ferritine
    produit une nouvelle empreinte, donc un « nouveau » — c'est voulu.
    Un simple changement de date, non.
    """
    brut = f"{ligne.categorie}|{getattr(ligne.patient, 'pk', 0)}|{ligne.titre}"
    return hashlib.sha1(brut.encode("utf-8")).hexdigest()[:16]


class Command(BaseCommand):
    help = "Affiche le point du jour, prêt à être envoyé au soignant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--enregistrer",
            action="store_true",
            help="Marque les points affichés comme vus (pour le « nouveau »).",
        )
        parser.add_argument(
            "--json", action="store_true", help="Sortie JSON au lieu du texte."
        )
        parser.add_argument(
            "--avec-noms",
            action="store_true",
            help="Ajoute le nom du patient (donnée nominative : à éviter si "
                 "le message sort du poste).",
        )

    def handle(self, *args, **options):
        data = briefing_du_jour()
        lignes = data["lignes"]

        if not lignes:
            return  # sortie vide : rien à signaler, rien à envoyer

        connues = set(Signalement.objects.values_list("empreinte", flat=True))
        elements = []
        for ligne in lignes:
            marque = empreinte(ligne)
            patient = ligne.patient
            if patient is None:
                identite = ""
            elif options["avec_noms"]:
                identite = f"{patient.numero_dossier} ({patient})"
            else:
                identite = patient.numero_dossier
            elements.append({
                "empreinte": marque,
                "nouveau": marque not in connues,
                "priorite": ligne.priorite,
                "priorite_libelle": ligne.libelle_priorite,
                "categorie": CATEGORIES.get(ligne.categorie, ligne.categorie),
                "patient": identite,
                "titre": ligne.titre,
                "detail": ligne.detail,
                "source": ligne.source,
            })

        # Tri global par priorité : le briefing est construit patient par
        # patient, donc l'allergie sévère d'un patient arrivé en fin de liste
        # se retrouverait après des suivis sans urgence.
        elements.sort(key=lambda e: (e["priorite"], e["patient"], e["titre"]))

        if options["json"]:
            self._sortie_json(data, elements)
        else:
            self._sortie_texte(data, elements)
        if options["enregistrer"]:
            self._enregistrer(elements)

    # ------------------------------------------------------------------
    def _sortie_texte(self, data, elements):
        nouveaux = [e for e in elements if e["nouveau"]]
        connus = [e for e in elements if not e["nouveau"]]

        entete = [
            f"Point du jour — {data['date']:%d/%m/%Y}",
            f"{data['nb_patients_concernes']} patient(s) concerné(s) · "
            f"{data['nb_lignes']} point(s)",
        ]
        if data["consultations_du_jour"]:
            entete.append(
                f"{data['consultations_du_jour']} consultation(s) aujourd'hui"
            )

        blocs = ["\n".join(entete)]
        for titre, groupe in (("NOUVEAU", nouveaux), ("DÉJÀ SIGNALÉ", connus)):
            if not groupe:
                continue
            corps = [f"{titre} ({len(groupe)})"]
            for e in groupe:
                ligne = f"• {e['patient']} · {e['titre']}"
                if e["detail"]:
                    ligne += f" — {e['detail']}"
                corps.append(ligne)
            blocs.append("\n".join(corps))

        self.stdout.write("\n\n".join(blocs))
        self.stdout.write("")

    def _sortie_json(self, data, elements):
        import json

        self.stdout.write(json.dumps({
            "date": data["date"].isoformat(),
            "nb_lignes": data["nb_lignes"],
            "nb_patients_concernes": data["nb_patients_concernes"],
            "consultations_du_jour": data["consultations_du_jour"],
            "elements": elements,
        }, ensure_ascii=False, indent=2))

    def _enregistrer(self, elements):
        maintenant = timezone.now()
        for e in elements:
            obj, cree = Signalement.objects.get_or_create(
                empreinte=e["empreinte"],
                defaults={"libelle": f"{e['patient']} · {e['titre']}"[:200]},
            )
            if not cree:
                obj.libelle = f"{e['patient']} · {e['titre']}"[:200]
            obj.nb_envois += 1
            obj.save(update_fields=["libelle", "nb_envois", "derniere_vue"])
