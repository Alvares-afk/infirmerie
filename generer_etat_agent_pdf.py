"""Genere l'etat de l'agent Infirmerie : ce qu'il fait, forces, faiblesses.

Usage  : python generer_etat_agent_pdf.py
Sortie : Etat-agent-infirmerie-<date>.pdf

Le contenu est celui d'un etat des lieux verifie sur le code : chaque
affirmation correspond a un fichier, un test ou une commande reelle.
"""

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from generer_resume_pdf import (
    BORD,
    CLAIR,
    GRIS,
    ORANGE,
    ROUGE,
    VERT,
    encadre,
    pied,
    styles,
    tableau,
)

BASE = Path(__file__).resolve().parent


def construire():
    s = styles()
    aujourd_hui = date.today().strftime("%d/%m/%Y")
    F = []

    # ------------------------------------------------------------- page 1
    F.append(Paragraph("Agent Infirmerie", s["titre"]))
    F.append(Paragraph(
        f"État des lieux — ce qu'il fait, ses forces, ses faiblesses · {aujourd_hui}",
        s["sous_titre"],
    ))

    F.append(encadre(
        "À lire d'abord : ce n'est pas un agent autonome",
        ["« Agent Infirmerie » désigne deux choses distinctes. Une "
         "<b>spécification</b> (LAB 04) qui fixe son rôle, sa mission et sa règle "
         "d'or. Et une <b>application</b> qui la met en œuvre : 9 modèles de "
         "données, 12 écrans, 96 tests automatisés.<br/><br/>"
         "Rien ne s'exécute en arrière-plan : ni planificateur, ni tâche de fond, "
         "ni démon. <b>L'agent ne fait rien tant qu'un humain n'ouvre pas un "
         "écran.</b> C'est le point le plus important de cet état, et celui qui "
         "explique la plupart des faiblesses qui suivent."],
        s, couleur=ROUGE, fond="#fef2f2",
    ))
    F.append(Spacer(1, 10))

    F.append(Paragraph("1. Ce qu'il fait, étape par étape", s["h2"]))
    F.append(Paragraph(
        "La spécification décrit un workflow en cinq étapes. Voici où chacune "
        "en est réellement, vérifié dans le code et non dans les intentions.",
        s["corps"],
    ))
    F.append(Spacer(1, 4))
    F.append(tableau(
        ["Étape de la spec", "État réel"],
        [
            ["1. Recevoir et enregistrer",
             "<b>Fait.</b> Dossier patient, consultation, bilan, mesures, "
             "allergies, suivis."],
            ["2. Analyser et extraire",
             "<b>Partiel.</b> Extrait les valeurs d'un bilan <i>saisi à la main</i>. "
             "Ne lit aucun document : pas d'import de PDF de laboratoire."],
            ["3. Prioriser et signaler",
             "<b>Fait.</b> Point quotidien en deux sections : Immédiat (allergies "
             "sévères) et Avant la visite (valeurs hors norme, échéances)."],
            ["4. Consolider le briefing",
             "<b>Fait.</b> Briefing imprimable, brouillons de relance justifiés "
             "par un fait du dossier."],
            ["5. Valider et archiver",
             "<b>Fait.</b> Validation humaine obligatoire ; journal d'accès "
             "horodaté."],
        ],
        [52 * mm, 118 * mm], s,
    ))
    F.append(Spacer(1, 8))
    F.append(Paragraph(
        "Le workflow s'arrête à la porte de l'étape 2. L'application ne lit pas "
        "de document : on saisit, elle organise et signale. C'est une différence "
        "de nature avec ce que le mot « agent » suggère.",
        s["petit"],
    ))

    F.append(Spacer(1, 14))

    # ------------------------------------------------------------- page 2
    F.append(Paragraph("2. Forces", s["h2"]))
    F.append(Paragraph(
        "Ce qui tient, et pourquoi ce n'est pas une promesse mais une propriété "
        "du code.",
        s["corps"],
    ))
    F.append(Spacer(1, 4))

    forces = [
        ("La règle d'or est dans le code, pas dans une consigne.",
         "« Ne jamais deviner une donnée médicale » n'est pas un rappel : c'est "
         "une branche du programme. Une valeur sans borne complète, ou non "
         "chiffrée (« négatif », « traces »), sort en « à qualifier » — jamais "
         "en « normal ». Une seule borne ne suffit pas. Couvert par des tests."),
        ("Il n'envoie rien.",
         "Les relances sont des brouillons. L'écran le dit en haut, et un test "
         "échoue si un appel réseau apparaît dans le module. La validation "
         "humaine est une étape du workflow, pas une option."),
        ("Les accès sont fermés côté serveur.",
         "Le secrétariat qui saisit l'URL d'une fiche clinique reçoit un 403. "
         "Le lien n'est pas seulement masqué : la vue refuse. Testé, y compris "
         "pour garantir qu'aucune page clinique ne s'ouvre par inadvertance."),
        ("Deux bases séparées.",
         "Les patients fictifs vivent dans une base, les vrais dossiers dans une "
         "autre. Une erreur de manipulation sur la démonstration ne peut pas "
         "atteindre les données réelles, et les sauvegardes sont indépendantes."),
        ("Les fourchettes viennent du laboratoire, pas de normes génériques.",
         "13 paramètres chargés, versionnés. Un contrôle vérifie en plus que "
         "l'unité reste cohérente avec les bornes : c'est ce qui a détecté une "
         "glycémie étiquetée « 5,4 g/L — Normal » alors que la valeur était en "
         "mmol/L, donc dangereuse à lire."),
        ("Les relances sont justifiées par un fait vérifiable.",
         "« Dernier bilan du 26/08/2025 — 401 jours. » Un compte, pas une "
         "appréciation. Le soignant peut contester le fait affiché."),
        ("Le journal d'accès ne contient aucune donnée clinique.",
         "Qui, quand, quel rôle, quel dossier. Jamais une valeur de mesure, "
         "jamais un résultat. Un journal qui recopierait les données créerait "
         "un second dossier, non maîtrisé."),
    ]
    for titre, texte in forces:
        F.append(KeepTogether([
            Paragraph(f"<b>{titre}</b>", s["h3"]),
            Paragraph(texte, s["corps"]),
        ]))

    F.append(Spacer(1, 14))

    # ------------------------------------------------------------- page 3
    F.append(Paragraph("3. Faiblesses", s["h2"]))
    F.append(Paragraph(
        "Par ordre d'importance réelle pour un usage de soin. Les trois "
        "premières empêchent une mise en service sur de vrais dossiers.",
        s["corps"],
    ))
    F.append(Spacer(1, 4))
    F.append(tableau(
        ["#", "Faiblesse", "Conséquence concrète"],
        [
            ["1", "<b>Aucune autonomie.</b> Rien ne s'exécute sans qu'un humain "
                  "ouvre l'écran.",
             "Le « zéro oubli » de la spec repose sur la vigilance de quelqu'un. "
             "Si personne n'ouvre l'application, aucun oubli n'est évité."],
            ["2", "<b>La prophylaxie n'existe pas.</b> Aucun modèle, aucun écran.",
             "Le bloc vaccinal de la spec n'est pas commencé. Seule une analyse "
             "écrite existe, en attente des calendriers de l'établissement."],
            ["3", "<b>La couverture biologique est étroite.</b> 13 paramètres, "
                  "tous d'hématologie.",
             "Toute la biochimie — glycémie, créatinine, ferritine, lipides — "
             "ressort « à qualifier ». Honnête, mais la majorité d'un bilan "
             "courant n'est pas interprétée."],
            ["4", "<b>Les seuils de relance sont arbitraires.</b> 365 jours pour "
                  "un bilan ancien, 730 pour une absence.",
             "Ce sont des choix de développement, pas des règles validées par un "
             "soignant. Ils déclencheront des relances inutiles ou en manqueront."],
            ["5", "<b>Les sauvegardes ne se déclenchent pas seules.</b> Les "
                  "scripts existent, rien ne les planifie.",
             "Et la restauration n'a jamais été testée. Une sauvegarde jamais "
             "restaurée n'est pas une sauvegarde, seulement une copie."],
            ["6", "<b>Aucune notification.</b> Si un bilan devient anormal, "
                  "personne n'est prévenu.",
             "Cohérent avec « aucun envoi automatique », mais tout le poids "
             "repose sur la consultation de l'écran."],
            ["7", "<b>Un seul poste, une seule base SQLite.</b>",
             "L'accès distant par VPN n'est pas configuré. Aucun test à deux "
             "utilisateurs simultanés."],
            ["8", "<b>Mots de passe de démonstration identiques</b> pour tous "
                  "les comptes.",
             "Signalé depuis le début, jamais changé. À faire avant toute "
             "ouverture à un tiers."],
            ["9", "<b>L'anonymisation repose sur la discipline, pas sur du code.</b>",
             "La règle interdit que noms et données nominatives entrent en "
             "mémoire longue. Rien ne l'empêche techniquement."],
        ],
        [8 * mm, 62 * mm, 100 * mm], s,
    ))

    F.append(Spacer(1, 14))

    # ------------------------------------------------------------- page 4
    F.append(Paragraph("4. Verdict", s["h2"]))
    F.append(encadre(
        "Utilisable aujourd'hui",
        ["En pilote supervisé, sur données fictives, par une seule personne : "
         "enregistrer un patient, saisir un bilan, voir ce qui presse, rédiger "
         "une relance, l'imprimer. Les trois forces structurantes — règle d'or, "
         "aucun envoi, accès fermés — tiennent dans cet usage."],
        s, couleur=VERT, fond="#f0fdfa",
    ))
    F.append(Spacer(1, 8))
    F.append(encadre(
        "Pas utilisable en production réelle, en l'état",
        ["Trois blocages, dans cet ordre :<br/>"
         "<b>1.</b> Les mots de passe, identiques et publics dans le dépôt.<br/>"
         "<b>2.</b> Les fourchettes de biochimie, sans lesquelles la majorité des "
         "résultats reste « à qualifier ».<br/>"
         "<b>3.</b> Une sauvegarde dont la restauration n'a jamais été testée."],
        s, couleur=ROUGE, fond="#fef2f2",
    ))
    F.append(Spacer(1, 8))

    F.append(Paragraph("5. Ce qui reste à faire, par nature", s["h2"]))
    F.append(tableau(
        ["Chantier", "Nature", "Ce qu'il faut pour avancer"],
        [
            ["Module prophylaxie", "Développement",
             "Calendriers vaccinaux et protocoles de l'établissement"],
            ["Planification des tâches", "Développement",
             "Décision sur ce qui peut être automatisé sans validation"],
            ["Sources documentaires", "Développement",
             "Inventaire des protocoles et fiches types autorisés"],
            ["Fourchettes de biochimie", "Donnée",
             "Seconde feuille du laboratoire"],
            ["Durée de conservation", "Décision",
             "Règle de l'établissement, pas un choix technique"],
            ["Mots de passe, sauvegarde testée", "Exploitation",
             "Rien à concevoir : à exécuter"],
        ],
        [45 * mm, 30 * mm, 95 * mm], s,
    ))
    F.append(Spacer(1, 12))
    F.append(Paragraph(
        "Le code est prêt à accueillir ces éléments. Aucun des trois chantiers "
        "LAB 04 ne bute sur une difficulté technique : tous attendent une donnée "
        "ou une décision qui ne peut venir que de l'établissement. Aucun agent ne "
        "les inventerait — et c'est précisément la règle d'or qui l'interdit.",
        s["petit"],
    ))

    return F


if __name__ == "__main__":
    sortie = BASE / f"Etat-agent-infirmerie-{date.today():%Y-%m-%d}.pdf"
    doc = SimpleDocTemplate(
        str(sortie),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="Agent Infirmerie — état, forces, faiblesses",
        author="Projet Infirmerie",
    )
    doc.build(construire())
    print(f"PDF cree : {sortie.name}")
