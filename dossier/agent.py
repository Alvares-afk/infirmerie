"""Agent de décision — socle, limité aux classes administratives.

Ce module répond à une question simple : « qu'est-ce que l'agent ferait, et
pourquoi ? » Il ne contient aucune intelligence artificielle. Il contient des
règles écrites, un catalogue d'actions fermé, et une trace de chaque décision.

Trois principes :

  - **Le catalogue est fermé.** L'agent ne peut choisir que parmi les actions
    déclarées ici, avec leur classe et leur réversibilité. Une action non
    déclarée n'existe pas.
  - **La simulation est le mode par défaut.** En simulation, l'agent écrit ce
    qu'il ferait et ne touche à rien. On compare avec ce qu'un soignant aurait
    fait, puis on règle les seuils.
  - **Aucune action de classe C.** Envoyer un message à un patient, modifier
    une mesure ou supprimer un dossier ne sont pas dans le catalogue, et ne
    doivent pas y entrer. Ces actes engagent le cabinet.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from .models import Bilan, Patient, Relance, StatutRelance, Suivi, TypeRelance

DELAI_BILAN = 365


@dataclass(frozen=True)
class Action:
    """Une action que l'agent a le droit d'envisager."""
    code: str
    libelle: str
    classe: str          # A = administratif, B = clinique réversible, C = interdit
    reversible: bool
    effet: str


CATALOGUE = {
    a.code: a for a in [
        Action(
            code="relance_suivi",
            libelle="Préparer une relance pour un suivi en retard",
            classe="A",
            reversible=True,
            effet="Crée un brouillon de relance, en attente de validation.",
        ),
        Action(
            code="relance_bilan",
            libelle="Préparer une relance pour un bilan ancien",
            classe="A",
            reversible=True,
            effet="Crée un brouillon de relance, en attente de validation.",
        ),
    ]
}


@dataclass
class Decision:
    regle: str
    action: Action
    patient: Patient
    resume: str
    motif: str
    corps: str

    @property
    def cle(self):
        return f"{self.regle}:{self.patient.pk}:{self.action.code}"


# ----------------------------------------------------------------- regles
def _suivis_en_retard(aujourdhui):
    for suivi in Suivi.objects.filter(
        fait=False, echeance__lt=aujourdhui
    ).select_related("patient"):
        yield Decision(
            regle="suivi_echeance_depassee",
            action=CATALOGUE["relance_suivi"],
            patient=suivi.patient,
            resume=f"Suivi en retard : {suivi.description[:120]}",
            motif=f"Échéance du {suivi.echeance:%d/%m/%Y} dépassée.",
            corps=(
                f"Bonjour,\n\nUn contrôle prévu le {suivi.echeance:%d/%m/%Y} "
                f"n'a pas encore été réalisé : {suivi.description}.\n\n"
                f"Souhaitez-vous convenir d'un rendez-vous ?\n\nL'infirmerie"
            ),
        )


def _bilans_anciens(aujourdhui):
    seuil = aujourdhui - timedelta(days=DELAI_BILAN)
    for patient in Patient.objects.all():
        dernier = (
            Bilan.objects.filter(consultation__patient=patient)
            .order_by("-date").first()
        )
        if dernier is None or dernier.date > seuil:
            continue
        yield Decision(
            regle="bilan_plus_de_douze_mois",
            action=CATALOGUE["relance_bilan"],
            patient=patient,
            resume="Bilan de santé à renouveler",
            motif=f"Dernier bilan le {dernier.date:%d/%m/%Y}.",
            corps=(
                "Bonjour,\n\n"
                f"Votre dernier bilan de santé date du {dernier.date:%d/%m/%Y}.\n"
                "Il est recommandé de le renouveler.\n\n"
                "Souhaitez-vous convenir d'un rendez-vous ?\n\nL'infirmerie"
            ),
        )


REGLES = [_suivis_en_retard, _bilans_anciens]


# -------------------------------------------------------------- execution
def decisions(aujourdhui=None):
    """Toutes les décisions que l'agent prendrait aujourd'hui.

    Ne modifie rien : c'est une lecture.
    """
    aujourdhui = aujourdhui or timezone.localdate()
    return [d for regle in REGLES for d in regle(aujourdhui)]


def deja_traitee(decision, mode):
    """Vrai si cette décision a déjà été enregistrée dans ce mode."""
    from .models import DecisionAgent

    return DecisionAgent.objects.filter(
        regle=decision.regle,
        action=decision.action.code,
        patient=decision.patient,
        mode=mode,
        annulee_le__isnull=True,
    ).exists()


def relance_deja_ouverte(decision):
    """Vrai si un brouillon (ou une relance validée) couvre déjà ce motif.

    Sans ce contrôle, l'agent créerait un doublon de ce que
    `preparer_relances` a déjà déposé — deux lettres pour la même personne.
    """
    return Relance.objects.filter(
        patient=decision.patient,
        objet=decision.resume[:200],
        statut__in=[StatutRelance.BROUILLON, StatutRelance.VALIDEE],
    ).exists()


def appliquer(decision):
    """Exécute une décision de classe A : crée un brouillon de relance.

    Renvoie une description de l'objet créé, ou lève une exception si
    l'action n'est pas dans le catalogue — garde-fou contre l'ajout
    silencieux d'une action non prévue.
    """
    action = CATALOGUE.get(decision.action.code)
    if action is None:
        raise ValueError(f"Action inconnue : {decision.action.code}")
    if action.classe not in ("A", "B"):
        raise ValueError(f"Action de classe {action.classe} : exécution interdite.")
    if not action.reversible:
        raise ValueError("Action irréversible : elle exige une validation humaine.")

    type_relance = (
        TypeRelance.BILAN if action.code == "relance_bilan" else TypeRelance.SOIN
    )
    relance = Relance.objects.create(
        patient=decision.patient,
        type_relance=type_relance,
        objet=decision.resume[:200],
        corps=decision.corps,
        motif=decision.motif,
        statut=StatutRelance.BROUILLON,
    )
    return f"relance#{relance.pk}"
