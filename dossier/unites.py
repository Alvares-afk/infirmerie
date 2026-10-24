"""Cohérence entre l'unité d'un paramètre et ses bornes de référence.

Une valeur correcte peut devenir dangereuse à lire si son unité est fausse :
« 5,4 g/L » de glycémie se lirait comme rassurante alors que la norme en g/L
est 0,70–1,10 — 5,4 g/L serait une hyperglycémie sévère. Le nombre et les
bornes étaient justes (mmol/L), seule l'étiquette ne l'était pas.

Ce module porte la règle une seule fois, pour deux usages :

  - les tests (`dossier/test_garde_fous.py`), qui refusent une régression ;
  - la commande `manage.py verifier_unites`, qui contrôle le contenu réel de
    la base et signale les paramètres qu'aucune règle ne couvre encore.
"""

import unicodedata

# Motifs qui ne doivent jamais apparaître dans une page rendue : s'ils sont
# là, le moteur de template n'a pas interprété la balise et l'a recopiée.
BALISES_INTERDITES = ("{%", "{{", "%}", "}}")


def normaliser(texte):
    """Minuscules sans accents, pour comparer des libellés saisis à la main."""
    # µ (micro) disparaîtrait à la conversion ASCII : on le ramène à « u »
    # avant, sinon « µmol/L » et « umol/L » ne se reconnaîtraient pas.
    brut = str(texte).replace("µ", "u").replace("μ", "u")
    sans_accents = (
        unicodedata.normalize("NFKD", brut)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return sans_accents.lower().strip()


# Fourchettes au-delà desquelles l'unité est forcément fausse.
#
# Ce ne sont PAS les normes biologiques : ce sont les bornes physiologiques
# larges, au-delà desquelles la valeur ne peut pas exister chez un vivant.
# Un écart d'unité se trompe d'un facteur 10 à 100 ; une marge large suffit
# donc à le détecter sans jamais rejeter un vrai résultat, même extrême.
#
# Clé    : fragment de libellé normalisé (sans accents, minuscules).
# Valeur : {unité normalisée: (borne basse, borne haute)}.
#
# Les clés sont testées de la plus longue à la plus courte : « hemoglobine
# glyquee » doit l'emporter sur « hemoglobine », sinon un HbA1c en % serait
# jugé contre une hémoglobine en g/dL — et refusé à tort.
#
# Pour ajouter un paramètre : une entrée ici, avec ses unités possibles.
# Une clé et une unité s'écrivent en forme normalisée (sans accent, µ → u),
# sinon elles ne seront jamais atteintes.
FOURCHETTES_PLAUSIBLES = {
    # --- Hématologie (les 13 paramètres chargés par le laboratoire) ---------
    "hemoglobine glyquee": {
        "%": (2.0, 20.0),
        "mmol/mol": (10.0, 200.0),
    },
    "hemoglobine": {
        "g/dl": (2.0, 25.0),
        "g/l": (20.0, 250.0),
        "g/100ml": (2.0, 25.0),
    },
    "hematocrite": {
        "%": (5.0, 75.0),
        "l/l": (0.05, 0.75),
    },
    "erythrocytes": {
        "x10^6/mm3": (0.5, 10.0),
        "x10^12/l": (0.5, 10.0),
        "t/l": (0.5, 10.0),
        "millions/mm3": (0.5, 10.0),
    },
    "leucocytes": {
        "x10^3/mm3": (0.05, 200.0),
        "x10^9/l": (0.05, 200.0),
        "g/l": (0.05, 200.0),
        "milliers/mm3": (0.05, 200.0),
    },
    "globules blancs": {
        "x10^3/mm3": (0.05, 200.0),
        "x10^9/l": (0.05, 200.0),
        "g/l": (0.05, 200.0),
    },
    "plaquettes": {
        "x10^3/mm3": (1.0, 2000.0),
        "x10^9/l": (1.0, 2000.0),
        "g/l": (1.0, 2000.0),
        "milliers/mm3": (1.0, 2000.0),
    },
    "vgm": {
        "fl": (40.0, 150.0),
        "um3": (40.0, 150.0),
    },
    "vcm": {
        "fl": (40.0, 150.0),
    },
    "tcmh": {
        "pg": (10.0, 50.0),
    },
    "ccmh": {
        "g/dl": (20.0, 45.0),
        "g/l": (200.0, 450.0),
        "%": (20.0, 45.0),
    },
    # Formule leucocytaire : toujours en pourcentage.
    "neutrophiles": {"%": (0.0, 100.0)},
    "lymphocytes": {"%": (0.0, 100.0)},
    "monocytes": {"%": (0.0, 100.0)},
    "eosinophiles": {"%": (0.0, 100.0)},
    "basophiles": {"%": (0.0, 100.0)},
    # --- Biochimie ---------------------------------------------------------
    "glycemie": {
        "g/l": (0.2, 3.0),
        "mmol/l": (1.0, 40.0),
        "mg/dl": (20.0, 700.0),
    },
    "creatinine": {
        "umol/l": (10.0, 2000.0),
        "mg/l": (1.0, 100.0),
        "mg/dl": (0.1, 20.0),
    },
    "uree": {
        "g/l": (0.05, 5.0),
        "mmol/l": (1.0, 100.0),
        "mg/dl": (3.0, 300.0),
        "mg/l": (30.0, 3000.0),
    },
    "acide urique": {
        "mg/l": (5.0, 200.0),
        "mg/dl": (0.5, 20.0),
        "umol/l": (15.0, 1200.0),
    },
    "uricemie": {
        "mg/l": (5.0, 200.0),
        "umol/l": (15.0, 1200.0),
    },
    # La borne basse descend à 0,05 g/L pour couvrir le HDL, dont le
    # fragment « cholesterol » capte aussi le libellé.
    "cholesterol": {
        "g/l": (0.05, 10.0),
        "mmol/l": (0.1, 30.0),
        "mg/dl": (10.0, 800.0),
    },
    "ldl": {
        "g/l": (0.1, 6.0),
        "mmol/l": (0.2, 20.0),
        "mg/dl": (10.0, 400.0),
    },
    "hdl": {
        "g/l": (0.05, 3.0),
        "mmol/l": (0.1, 8.0),
        "mg/dl": (2.0, 150.0),
    },
    # Clé au singulier : elle attrape « triglycéride » et « triglycérides ».
    "triglyceride": {
        "g/l": (0.1, 15.0),
        "mmol/l": (0.1, 20.0),
        "mg/dl": (5.0, 1500.0),
    },
    "bilirubine": {
        "mg/l": (0.5, 300.0),
        "umol/l": (1.0, 500.0),
        "mg/dl": (0.05, 30.0),
    },
    "asat": {"ui/l": (0.0, 5000.0), "u/l": (0.0, 5000.0)},
    "alat": {"ui/l": (0.0, 5000.0), "u/l": (0.0, 5000.0)},
    "ggt": {"ui/l": (0.0, 5000.0), "u/l": (0.0, 5000.0)},
    "phosphatases": {"ui/l": (0.0, 3000.0), "u/l": (0.0, 3000.0)},
    "ferritine": {
        "ug/l": (0.5, 5000.0),
        "ng/ml": (0.5, 5000.0),
    },
    "crp": {
        "mg/l": (0.0, 500.0),
        "mg/dl": (0.0, 50.0),
    },
    "tsh": {
        "mui/l": (0.0, 200.0),
        "uui/ml": (0.0, 200.0),
        "ui/l": (0.0, 200.0),
    },
    "t4 libre": {
        "pmol/l": (1.0, 100.0),
        "ng/l": (1.0, 60.0),
    },
    "albumine": {
        "g/l": (5.0, 70.0),
        "g/dl": (0.5, 7.0),
    },
    "protides": {
        "g/l": (10.0, 130.0),
        "g/dl": (1.0, 13.0),
    },
    "proteines": {
        "g/l": (10.0, 130.0),
        "g/dl": (1.0, 13.0),
    },
    "natremie": {"mmol/l": (90.0, 200.0), "meq/l": (90.0, 200.0)},
    "sodium": {"mmol/l": (90.0, 200.0), "meq/l": (90.0, 200.0)},
    "kaliemie": {"mmol/l": (1.0, 10.0), "meq/l": (1.0, 10.0)},
    "potassium": {"mmol/l": (1.0, 10.0), "meq/l": (1.0, 10.0)},
    "calcium": {
        "mmol/l": (0.5, 5.0),
        "mg/l": (10.0, 200.0),
        "mg/dl": (1.0, 20.0),
    },
    "magnesium": {
        "mg/l": (2.0, 80.0),
        "mmol/l": (0.1, 3.5),
        "meq/l": (0.2, 7.0),
    },
    # « Transaminase (TGO/TGP) » désigne les deux enzymes d'un seul libellé :
    # même unité, donc une seule entrée suffit.
    "transaminase": {
        "ui/l": (0.0, 5000.0),
        "u/l": (0.0, 5000.0),
    },
}


def _entrees_triees():
    """Clés de la plus longue à la plus courte : le libellé le plus précis gagne."""
    return sorted(
        FOURCHETTES_PLAUSIBLES.items(), key=lambda kv: len(kv[0]), reverse=True
    )


def fragment_reconnu(parametre):
    """Retourne la clé de la table qui s'applique à ce libellé, ou None.

    Sert à répondre à la seule question qui compte pour l'exploitation :
    ce paramètre est-il couvert, ou passe-t-il sans contrôle ?
    """
    libelle = normaliser(parametre)
    for fragment, _unites in _entrees_triees():
        if fragment in libelle:
            return fragment
    return None


def incoherence_unite(parametre, unite, norme_min, norme_max):
    """Retourne un message si l'unité ne peut pas aller avec ces bornes.

    Ne juge que les paramètres présents dans la table : pour les autres,
    on ne sait rien, donc on ne dit rien. Un garde-fou qui crie au loup sur
    tout finit désactivé — c'est à `fragment_reconnu()` de dire ce qui
    échappe au contrôle, pas à cette fonction de le deviner.
    """
    libelle = normaliser(parametre)
    unite_basse = normaliser(unite).replace(" ", "")

    for fragment, unites in _entrees_triees():
        if fragment not in libelle:
            continue
        if unite_basse not in unites:
            return (
                f"unité « {unite} » non reconnue pour {parametre} "
                f"(attendu : {', '.join(sorted(unites))})"
            )
        plancher, plafond = unites[unite_basse]
        for borne, nom in ((norme_min, "min"), (norme_max, "max")):
            if borne is None:
                continue
            if not (plancher <= borne <= plafond):
                return (
                    f"{parametre} en {unite} : borne {nom} {borne} hors de "
                    f"[{plancher} ; {plafond}]. Ces bornes sont probablement "
                    f"exprimées dans une autre unité."
                )
        return None
    return None
