"""Briefing du point quotidien.

Répond à la question posée chaque matin : « qu'est-ce qui ne peut pas
attendre aujourd'hui ? »

Principe : le briefing PROPOSE, il ne décide pas. Chaque ligne est un
élément vérifiable, rattaché à une source dans l'application. Aucune
inférence clinique n'est faite : une valeur hors norme est signalée comme
telle, pas interprétée en « probablement X ».

La priorité est calculée, pas inventée. Trois critères, tous factuels :
  - une allergie sévère connue : la prescription peut être dangereuse
  - une valeur biologique hors norme : à connaître pour la visite
  - un suivi échu : une échéance est déjà dépassée
Plus un critère de fraîcheur : un bilan vieux de plus de 12 mois.
"""

from datetime import timedelta

from django.utils import timezone

from .models import Consultation, Patient, Suivi

# Priorités : 1 = à traiter en premier
PRIORITE_IMMEDIATE = 1   # allergie sévère
PRIORITE_HAUTE = 2       # valeur hors norme
PRIORITE_NORMALE = 3     # suivi échu, bilan à renouveler

LIBELLE_PRIORITE = {
    PRIORITE_IMMEDIATE: "Immédiat",
    PRIORITE_HAUTE: "Avant la visite",
    PRIORITE_NORMALE: "À planifier",
}


class ElementBriefing:
    """Une ligne du briefing. Volontairement simple et vérifiable."""

    def __init__(self, priorite, categorie, titre, patient=None,
                 detail="", source="", echeance=None):
        self.priorite = priorite
        self.categorie = categorie
        self.titre = titre
        self.patient = patient
        self.detail = detail
        self.source = source          # url de vérification, pas un texte
        self.echeance = echeance

    @property
    def libelle_priorite(self):
        return LIBELLE_PRIORITE.get(self.priorite, "")

    @property
    def ancre(self):
        """Clé stable pour lier le briefing à l'élément à l'écran."""
        return f"{self.categorie}-{getattr(self.patient, 'pk', 0)}"

    def __repr__(self):
        return f"<Element {self.categorie} P{self.priorite} {self.titre}>"


def _valeurs_hors_norme(patient):
    """Mesures hors norme du dernier bilan. Pas d'interprétation."""
    bilan = patient.dernier_bilan()
    if not bilan:
        return bilan, []
    return bilan, bilan.resume()["liste"]


def construire_briefing(patient: Patient, *, aujourdhui=None) -> list:
    """Lignes de briefing concernant UN patient. Ordonnées par priorité."""
    aujourdhui = aujourdhui or timezone.localdate()
    lignes = []

    # 1. Allergies sévères — priorité absolue, car la prescription peut nuire
    for a in patient.allergies.all():
        if a.gravite == "severe":
            lignes.append(ElementBriefing(
                priorite=PRIORITE_IMMEDIATE,
                categorie="allergie",
                titre=f"Allergie sévère : {a.substance}",
                patient=patient,
                detail=a.reaction or "réaction non renseignée",
                source=f"/patients/{patient.pk}/",
            ))

    # 2. Valeurs hors norme du dernier bilan
    #
    # On ne retient QUE les valeurs effectivement hors norme. Une mention
    # qualitative (« négatif », « traces ») a une anormalite valant
    # « inconnu » : elle n'est pas une anomalie, et ne doit donc pas produire
    # de ligne de briefing. Elle reste visible sur la page du bilan, où le
    # soignant la lit et la qualifie — ce qui est sa décision, pas la nôtre.
    bilan, anomalies = _valeurs_hors_norme(patient)
    for m in anomalies:
        if not m.est_anormal:
            continue
        lignes.append(ElementBriefing(
            priorite=PRIORITE_HAUTE,
            categorie="bilan",
            titre=f"{m.parametre} {m.valeur} {m.unite}".strip(),
            patient=patient,
            detail=f"{m.libelle_anomalie} — référence "
                   f"{m.norme_min} – {m.norme_max} {m.unite}".strip(),
            source=f"/bilans/{bilan.pk}/",
        ))

    # 3. Suivis échus — une échéance est déjà dépassée
    for s in patient.suivis.filter(fait=False).order_by("echeance"):
        echu = s.echeance and s.echeance < aujourdhui
        lignes.append(ElementBriefing(
            priorite=PRIORITE_NORMALE if echu else PRIORITE_HAUTE,
            categorie="suivi",
            titre=s.description,
            patient=patient,
            detail=f"échéance {s.echeance:%d/%m/%Y}" if s.echeance else "sans échéance",
            source=f"/patients/{patient.pk}/",
            echeance=s.echeance,
        ))

    # 4. Bilan à renouveler — plus de 12 mois
    if bilan and bilan.date < aujourdhui - timedelta(days=365):
        lignes.append(ElementBriefing(
            priorite=PRIORITE_NORMALE,
            categorie="fresqueur",
            titre="Bilan de plus de 12 mois",
            patient=patient,
            detail=f"dernier bilan le {bilan.date:%d/%m/%Y}",
            source=f"/bilans/{bilan.pk}/",
        ))

    lignes.sort(key=lambda e: (e.priorite, e.categorie, e.titre))
    return lignes


def briefing_du_jour(*, limite_patients=200) -> dict:
    """Le briefing complet, prêt à afficher ou à imprimer.

    Ne contient que des éléments factuels, chacun vérifiable dans
    l'application. Aucune conclusion clinique n'est formulée.
    """
    aujourdhui = timezone.localdate()

    lignes = []
    patients_avec_alertes = set()

    patients = (
        Patient.objects.filter(actif=True)
        .prefetch_related("allergies", "suivis")
        .order_by("nom", "prenom")
    )

    for p in patients[:limite_patients]:
        lignes.extend(construire_briefing(p, aujourdhui=aujourdhui))
        if lignes:
            patients_avec_alertes.add(p.pk)

    par_priorite = {}
    for ligne in lignes:
        par_priorite.setdefault(ligne.priorite, []).append(ligne)

    return {
        "date": aujourdhui,
        "lignes": lignes,
        "nb_lignes": len(lignes),
        "nb_patients_concernes": len({l.patient.pk for l in lignes if l.patient}),
        "immediats": par_priorite.get(PRIORITE_IMMEDIATE, []),
        "hauts": par_priorite.get(PRIORITE_HAUTE, []),
        "normaux": par_priorite.get(PRIORITE_NORMALE, []),
        "consultations_du_jour": Consultation.objects.filter(date=aujourdhui).count(),
        "patients_sans_rien": Patient.objects.filter(actif=True).count() - len(patients_avec_alertes),
    }
