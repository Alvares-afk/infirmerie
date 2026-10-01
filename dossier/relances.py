"""Rédaction des relances.

L'agent rédige des brouillons de relance ; il n'envoie rien. La validation
et l'envoi restent des décisions humaines.

Règle appliquée à la lettre : **ne rien inventer**. Une relance n'est
proposée que lorsqu'un fait existe dans le dossier — une échéance dépassée,
un bilan absent, un suivi non fait. Aucun fait n'est déduit, extrapolé, ni
supposé. Si un élément manque, la relance le dit explicitement plutôt que de
combler le trou.

Le vocabulaire est administratif et factuel. Aucune formule de diagnostic,
aucune interprétation de résultat. Le message propose un rendez-vous ; il
n'affirme rien sur l'état de santé.
"""

from datetime import timedelta

from django.utils import timezone

from .models import (
    Consultation, Relance, StatutRelance, Suivi, TypeRelance,
)

# Délai au-delà duquel un bilan est considéré comme à refaire.
DELAI_BILAN_JOURS = 365


def _dernier_bilan(patient):
    from .models import Bilan
    return Bilan.objects.filter(consultation__patient=patient).order_by("-date").first()


def _signes(patient):
    """Signes factuels d'appel, dans l'ordre du plus au moins urgent.

    Chaque motif est un TUPLE (type, objet, corps, motif) ou None. Rien
    n'est produit si aucun fait ne le justifie.
    """
    aujourdhui = timezone.localdate()
    propositions = []

    # 1. Suivis échus — une échéance est déjà dépassée
    for s in patient.suivis.filter(fait=False).order_by("echeance"):
        if not s.echeance:
            continue
        retard = (aujourdhui - s.echeance).days
        if retard <= 0:
            continue

        from .models import TypeRelance as T
        type_relance = T.BILAN if "bilan" in s.description.lower() else T.SOIN

        corps = (
            f"Bonjour,\n\n"
            f"Lors de votre dernière visite à l'infirmerie, il avait été prévu "
            f"de : {s.description}.\n\n"
            f"Cette échéance était fixée au {s.echeance:%d/%m/%Y}. "
            f"Elle n'apparaît pas comme réalisée à ce jour.\n\n"
            f"Pouvez-vous me confirmer si vous souhaitez que nous fixions "
            f"un rendez-vous pour la réaliser ?\n\n"
            f"Bien cordialement,\nL'infirmerie"
        )
        motif = (
            f"Suivi « {s.description} », échéance du {s.echeance:%d/%m/%Y}, "
            f"non marqué comme réalisé ({retard} jour(s) de retard)."
        )
        propositions.append((type_relance, f"Relance : {s.description}", corps, motif))

    # 2. Bilan ancien — dépassement de plus d'un an
    bilan = _dernier_bilan(patient)
    if bilan and bilan.date < aujourdhui - timedelta(days=DELAI_BILAN_JOURS):
        age_jours = (aujourdhui - bilan.date).days
        corps = (
            f"Bonjour,\n\n"
            f"Le dernier bilan de santé enregistré à votre dossier date du "
            f"{bilan.date:%d/%m/%Y}, soit environ {age_jours // 365} an(s).\n\n"
            f"Un bilan de contrôle est généralement proposé à cette échéance. "
            f"Pouvez-vous me confirmer si vous souhaitez que nous en fixions un ?\n\n"
            f"Bien cordialement,\nL'infirmerie"
        )
        motif = (
            f"Dernier bilan du {bilan.date:%d/%m/%Y} — plus de "
            f"{DELAI_BILAN_JOURS} jours ({age_jours} jours)."
        )
        propositions.append((
            TypeRelance.BILAN,
            "Bilan de santé à renouveler",
            corps,
            motif,
        ))

    # 3. Aucune consultation depuis longtemps — fait factuel, sans commentaire
    derniere = (
        Consultation.objects.filter(patient=patient)
        .order_by("-date")
        .first()
    )
    if not derniere:
        corps = (
            f"Bonjour,\n\n"
            f"Vous êtes enregistré(e) au dossier de l'infirmerie "
            f"({patient.numero_dossier or 'sans numéro'}).\n\n"
            f"Aucune consultation n'y figure à ce jour. "
            f"Souhaitez-vous prendre rendez-vous pour un premier bilan ?\n\n"
            f"Bien cordialement,\nL'infirmerie"
        )
        motif = "Aucune consultation enregistrée pour ce patient."
        propositions.append((
            TypeRelance.ADMIN,
            "Premier rendez-vous proposé",
            corps,
            motif,
        ))
    elif derniere.date < aujourdhui - timedelta(days=730):
        corps = (
            f"Bonjour,\n\n"
            f"Votre dernière visite à l'infirmerie date du "
            f"{derniere.date:%d/%m/%Y}.\n\n"
            f"Si vous le souhaitez, un point de suivi peut être proposé. "
            f"Dites-moi si cela vous intéresse.\n\n"
            f"Bien cordialement,\nL'infirmerie"
        )
        motif = (
            f"Dernière consultation le {derniere.date:%d/%m/%Y} "
            f"— plus de 2 ans."
        )
        propositions.append((
            TypeRelance.ADMIN,
            "Proposition de suivi après longue absence",
            corps,
            motif,
        ))

    return propositions


def proposer_relances(patient, *, enregistrer=True):
    """Rédige les relances justifiées pour un patient.

    Ne crée AUCUNE relance si aucun fait ne le justifie — une relance sans
    motif est du bruit, et le bruit fait ignorer les relances utiles.

    Une relance déjà rédigée pour le même motif n'est pas dupliquée : la
    proposer deux fois n'apporterait rien à personne.
    """
    propositions = _signes(patient)
    creees = []

    for type_relance, objet, corps, motif in propositions:
        # Pas de doublon : on cherche un brouillon ou une relance validée
        # portant le même objet.
        deja = Relance.objects.filter(
            patient=patient,
            objet=objet,
            statut__in=[StatutRelance.BROUILLON, StatutRelance.VALIDEE],
        ).first()
        if deja:
            continue

        if not enregistrer:
            creees.append((type_relance, objet, corps, motif))
            continue

        relance = Relance.objects.create(
            patient=patient,
            type_relance=type_relance,
            objet=objet,
            corps=corps,
            motif=motif,
            statut=StatutRelance.BROUILLON,
        )
        creees.append(relance)

    return creees


def proposer_relances_global(*, enregistrer=True) -> list:
    """Passe sur tous les patients actifs et rédige ce qui est justifié."""
    from .models import Patient

    resultat = []
    patients = Patient.objects.filter(actif=True).prefetch_related("suivis")
    for p in patients:
        resultat.extend(proposer_relances(p, enregistrer=enregistrer))
    return resultat
