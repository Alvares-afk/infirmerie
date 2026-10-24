"""Relie une mesure saisie aux fourchettes de référence du laboratoire.

Sans ce lien, la table des fourchettes n'est qu'une bibliothèque : à la
saisie d'un bilan, le soignant devait retaper les bornes de mémoire. Deux
conséquences, toutes deux mauvaises :

  - une borne oubliée fait sortir la valeur en « à qualifier », donc la
    mesure ne signale plus rien ;
  - une borne tapée de travers fait signaler une anomalie qui n'existe pas.

Ici, une mesure enregistrée sans bornes les reçoit de la table, en tenant
compte du sexe et de l'âge du patient quand le laboratoire distingue.
"""

from .models import ReferenceIntervalle
from .unites import normaliser

# Le laboratoire note « H » pour homme, le dossier patient « M » pour masculin.
EQUIVALENCE_SEXE = {"F": "F", "M": "H", "A": None}


def sexe_reference(patient):
    """Sexe du patient dans le vocabulaire du laboratoire, ou None si indéterminé."""
    if patient is None:
        return None
    return EQUIVALENCE_SEXE.get(getattr(patient, "sexe", ""), None)


def _correspond(libelle_mesure, libelle_reference):
    """2 = libellé identique, 1 = l'un contient l'autre, 0 = sans rapport."""
    mesure = normaliser(libelle_mesure)
    reference = normaliser(libelle_reference)
    if not mesure or not reference:
        return 0
    if mesure == reference:
        return 2
    if reference in mesure or mesure in reference:
        return 1
    return 0


def fourchette_pour(libelle, patient=None):
    """La fourchette en vigueur qui correspond le mieux à ce libellé.

    Retourne None si aucune ne correspond : on ne devine pas une norme.
    """
    if not libelle:
        return None

    sexe = sexe_reference(patient)
    age = getattr(patient, "age", None) if patient is not None else None

    candidates = []
    for reference in ReferenceIntervalle.objects.filter(date_fin__isnull=True):
        score = _correspond(libelle, reference.libelle)
        if not score:
            continue

        # Sexe : « T » vaut pour tous. Un patient de sexe indéterminé
        # n'accepte que les fourchettes valables pour tous.
        if reference.sexe not in ("T", "") and reference.sexe != sexe:
            continue

        if age is not None:
            if reference.age_min is not None and age < reference.age_min:
                continue
            if reference.age_max is not None and age > reference.age_max:
                continue

        candidates.append((score, reference.date_debut, reference))

    if not candidates:
        return None

    # Le libellé exact d'abord, puis la fourchette la plus récente.
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return candidates[0][2]


def completer_mesures(bilan, patient=None):
    """Remplit les bornes et l'unité manquantes des mesures d'un bilan.

    Ne touche jamais à une borne déjà saisie : le soignant peut avoir une
    raison de retenir une autre valeur (enfant, grossesse, méthode
    particulière). On complète, on ne corrige pas.

    Retourne le nombre de mesures complétées.
    """
    patient = patient or getattr(bilan.consultation, "patient", None)
    completees = 0

    for mesure in bilan.mesures.all():
        if mesure.norme_min is not None and mesure.norme_max is not None:
            continue

        reference = fourchette_pour(mesure.parametre, patient)
        if reference is None:
            continue

        champs = []
        if mesure.norme_min is None and reference.norme_min is not None:
            mesure.norme_min = reference.norme_min
            champs.append("norme_min")
        if mesure.norme_max is None and reference.norme_max is not None:
            mesure.norme_max = reference.norme_max
            champs.append("norme_max")
        if not mesure.unite and reference.unite:
            mesure.unite = reference.unite
            champs.append("unite")
        if not mesure.reference:
            mesure.reference = reference.libelle
            champs.append("reference")

        if champs:
            mesure.save(update_fields=champs)
            completees += 1

    return completees
