"""Genere la procedure d'installation a remettre sur le poste client.

Usage  : python generer_installation_pdf.py
Sortie : Installation-Infirmerie-<date>.pdf

Destine a la personne qui installe, pas a l'utilisatrice : commandes
exactes, resultats attendus, et une liste de points de controle qui se
coche.
"""

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from generer_resume_pdf import (
    BORD,
    CLAIR,
    GRIS,
    ORANGE,
    ROUGE,
    VERT,
    encadre,
    styles,
    tableau,
)

BASE = Path(__file__).resolve().parent
LARGEUR = 170 * mm


def bloc_code(texte, s):
    """Commande en chasse fixe sur fond gris : rien à confondre avec du texte."""
    style = ParagraphStyle(
        "code", parent=s["corps"], fontName="Courier", fontSize=8.5,
        leading=11, textColor=colors.HexColor("#0f172a"),
    )
    # Un Paragraph écrase les retours à la ligne et les espaces multiples :
    # sans cette conversion, trois commandes se retrouvent collées sur une
    # seule ligne et deviennent impossibles à recopier.
    sur = (
        texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("\n", "<br/>")
        .replace("  ", "&nbsp;&nbsp;")
    )
    t = Table([[Paragraph(sur, style)]], colWidths=[LARGEUR])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.6, BORD),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, VERT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def etape(numero, titre, s):
    return Paragraph(f"{numero}. {titre}", s["h3"])


def construire():
    s = styles()
    aujourd_hui = date.today().strftime("%d/%m/%Y")
    F = []

    # ------------------------------------------------------------ page 1
    F.append(Paragraph("Installer l'application Infirmerie", s["titre"]))
    F.append(Paragraph(
        f"Procédure d'installation sur le poste du client · version du {aujourd_hui}",
        s["sous_titre"],
    ))

    F.append(encadre(
        "À lire avant de commencer",
        ["Ce document s'adresse à la personne qui installe le poste, pas à "
         "l'utilisatrice. Compter <b>vingt minutes</b>.<br/><br/>"
         "Trois points décident de la réussite de l'installation :<br/>"
         "<b>1.</b> Python doit être installé en cochant « Add python.exe to PATH ».<br/>"
         "<b>2.</b> Le dossier ne doit pas être dans OneDrive, Dropbox ni sur le Bureau.<br/>"
         "<b>3.</b> Les mots de passe ne sont pas fournis : ils se créent à l'étape 4."],
        s, couleur=VERT, fond="#f0fdfa",
    ))
    F.append(Spacer(1, 12))

    F.append(Paragraph("1. Ce qu'il faut", s["h2"]))
    F.append(tableau(
        ["Élément", "Détail"],
        [
            ["Windows", "10 ou 11"],
            ["Python", "3.12 ou plus récent — python.org/downloads/windows"],
            ["Espace disque", "300 Mo environ"],
            ["Connexion Internet", "Nécessaire à l'installation seulement "
                                   "(téléchargement des dépendances)"],
            ["Accès administrateur", "Non requis, sauf pour le nom d'hôte (étape 6)"],
        ],
        [45 * mm, 125 * mm], s,
    ))

    F.append(Paragraph("2. Installation, étape par étape", s["h2"]))
    F.append(Paragraph(
        "Toutes les commandes se lancent dans une invite de commandes ouverte "
        "<b>dans le dossier de l'application</b> :",
        s["corps"],
    ))
    F.append(bloc_code("cd C:\\Infirmerie", s))
    F.append(Spacer(1, 8))

    F.append(etape(1, "Copier les fichiers", s))
    F.append(Paragraph(
        "Copier le dossier de l'application à son emplacement définitif, par "
        "exemple <font face='Courier'>C:\\Infirmerie</font>. Éviter le Bureau et "
        "les dossiers synchronisés : une base de données déplacée pendant une "
        "écriture se corrompt.",
        s["corps"],
    ))

    F.append(etape(2, "Créer l'environnement Python", s))
    F.append(bloc_code(
        "python -m venv .venv\n"
        ".venv\\Scripts\\python.exe -m pip install --upgrade pip\n"
        ".venv\\Scripts\\python.exe -m pip install -r requirements.txt",
        s,
    ))
    F.append(Paragraph(
        "La dernière commande télécharge Django et ses dépendances : quelques "
        "minutes selon la connexion.",
        s["petit"],
    ))
    F.append(Spacer(1, 8))

    F.append(etape(3, "Créer la base de données", s))
    F.append(bloc_code(".venv\\Scripts\\python.exe manage.py migrate", s))
    F.append(Paragraph(
        "La base est créée vide. Elle ne contient aucun dossier patient.",
        s["petit"],
    ))
    F.append(Spacer(1, 8))

    F.append(etape(4, "Créer les comptes et définir les mots de passe", s))
    F.append(bloc_code(
        ".venv\\Scripts\\python.exe manage.py creer_comptes\n"
        ".venv\\Scripts\\python.exe manage.py renouveler_mots_de_passe",
        s,
    ))
    F.append(Paragraph(
        "La première commande crée les trois comptes <b>sans mot de passe "
        "utilisable</b> : personne ne peut se connecter entre les deux étapes, "
        "et c'est voulu. La seconde génère un mot de passe par compte et les "
        "écrit une seule fois dans <font face='Courier'>acces-comptes.txt</font>.",
        s["corps"],
    ))
    F.append(Paragraph(
        "<b>Noter ces mots de passe, puis supprimer le fichier.</b>",
        s["alerte"],
    ))

    F.append(Spacer(1, 12))

    # ------------------------------------------------------------ page 2
    F.append(etape(5, "Charger les fourchettes de référence", s))
    F.append(bloc_code(
        ".venv\\Scripts\\python.exe manage.py charger_references\n"
        ".venv\\Scripts\\python.exe manage.py importer_fourchettes fourchettes-biochimie.csv",
        s,
    ))
    F.append(Paragraph(
        "La première commande installe les treize paramètres d'hématologie, la "
        "seconde les vingt-huit de biochimie. <b>Sans elles, toutes les valeurs "
        "ressortiront « à qualifier »</b> : l'application ne signalera aucune "
        "anomalie. Le fichier CSV est fourni à la racine du paquet.",
        s["corps"],
    ))
    F.append(Spacer(1, 8))

    F.append(etape(6, "Vérifier que les trois comptes se connectent", s))
    F.append(bloc_code(
        ".venv\\Scripts\\python.exe manage.py verifier_connexion\n"
        ".venv\\Scripts\\python.exe manage.py check",
        s,
    ))
    F.append(Paragraph(
        "Le résultat attendu est exactement celui-ci : trois lignes « ok », puis "
        "« Tous les comptes se connectent. » et « System check identified no issues ».",
        s["corps"],
    ))
    F.append(Spacer(1, 8))

    F.append(etape(7, "Lancer l'application", s))
    F.append(Paragraph(
        "Double-cliquer sur <font face='Courier'>lancer.py</font>. Le navigateur "
        "s'ouvre sur l'application. Pour un raccourci sur le Bureau : clic droit "
        "sur <font face='Courier'>lancer.py</font> → <i>Envoyer vers</i> → "
        "<i>Bureau (créer un raccourci)</i>.",
        s["corps"],
    ))
    F.append(Paragraph(
        "Optionnel — adresse sans numéro de port : exécuter "
        "<font face='Courier'>installer_nom.bat</font> en administrateur, une "
        "seule fois. L'application répond alors sur "
        "<font face='Courier'>http://infirmerie</font>.",
        s["petit"],
    ))

    F.append(Paragraph("3. Points de contrôle", s["h2"]))
    F.append(Paragraph(
        "À vérifier avant de déclarer l'installation terminée. Si une ligne ne "
        "donne pas le résultat attendu, ne pas continuer : voir la section 6.",
        s["corps"],
    ))
    F.append(Spacer(1, 5))
    F.append(tableau(
        ["Après l'étape", "Résultat attendu"],
        [
            ["2 — dépendances", "Aucun message d'erreur. "
                                 "<font face='Courier'>pip list</font> affiche Django."],
            ["3 — migration", "Une série de « Applying … OK », sans erreur."],
            ["4 — comptes", "« 3 compte(s) créé(s) : dr.benali, secretariat, admin »"],
            ["4 — mots de passe", "Le fichier <font face='Courier'>acces-comptes.txt</font> "
                                  "existe et contient trois lignes."],
            ["5 — fourchettes", "« Aucune incohérence détectée » (verifier_unites)"],
            ["6 — connexions", "Trois lignes « ok », puis « Tous les comptes se connectent. »"],
            ["6 — check", "« System check identified no issues »"],
            ["7 — lancement", "La page de connexion s'affiche dans le navigateur."],
            ["7 — connexion réelle", "Se connecter avec dr.benali : l'accueil "
                                     "s'affiche, sans erreur."],
        ],
        [42 * mm, 128 * mm], s,
    ))

    F.append(Spacer(1, 12))

    # ------------------------------------------------------------ page 3
    F.append(Paragraph("4. Sauvegardes — à ne pas remettre à plus tard", s["h2"]))
    F.append(Paragraph(
        "Une installation sans sauvegarde planifiée n'est pas une installation "
        "terminée. C'est le seul point de cette procédure qui, s'il est oublié, "
        "ne se voit qu'au moment où l'on en a besoin.",
        s["corps"],
    ))
    F.append(bloc_code(
        ".venv\\Scripts\\python.exe manage.py verifier_restauration",
        s,
    ))
    F.append(Paragraph(
        "Cette commande teste le cycle complet sur une copie : sauvegarde, "
        "modification, restauration, comparaison. Elle ne touche jamais aux "
        "vraies données. Résultat attendu : « Restauration vérifiée. »",
        s["corps"],
    ))
    F.append(Spacer(1, 4))
    F.append(Paragraph(
        "Planifier ensuite <font face='Courier'>sauvegarder_reel.bat</font> dans "
        "le Planificateur de tâches Windows, une fois par jour, à une heure où "
        "le poste est allumé.",
        s["corps"],
    ))
    F.append(encadre(
        "Une sauvegarde sur le même disque ne protège pas d'une panne de disque",
        ["Copier régulièrement le contenu du dossier <font face='Courier'>sauvegardes/"
         "</font> sur une clé USB, et vérifier que la copie s'ouvre. Une sauvegarde "
         "jamais relue n'est qu'une promesse."],
        s, couleur=ORANGE, fond="#fffbeb",
    ))

    F.append(Paragraph("5. Ce que le paquet ne contient pas", s["h2"]))
    F.append(tableau(
        ["Absent", "Conséquence"],
        [
            ["Aucune donnée patient", "La base est vide à l'installation. "
                                      "Normal : les dossiers se saisissent ici."],
            ["Aucun mot de passe", "Ils se créent à l'étape 4 et ne circulent "
                                   "par aucun autre canal."],
            ["Aucun message automatique de 6 h",
             "Le point du jour s'affiche dans la console "
             "(<font face='Courier'>manage.py point_du_jour</font>) mais n'est "
             "envoyé nulle part. L'envoi demande un ordonnanceur, non inclus."],
            ["Fourchettes de biochimie",
             "13 paramètres d'hématologie sont fournis. Les autres resteront "
             "« à qualifier » tant que le laboratoire n'aura pas fourni ses bornes."],
        ],
        [45 * mm, 125 * mm], s,
    ))

    F.append(Paragraph("6. En cas de problème", s["h2"]))
    F.append(tableau(
        ["Symptôme", "Cause probable et solution"],
        [
            ["« python n'est pas reconnu »",
             "La case « Add python.exe to PATH » n'était pas cochée. "
             "Réinstaller Python en la cochant."],
            ["« pip n'est pas reconnu »",
             "Utiliser <font face='Courier'>.venv\\Scripts\\python.exe -m pip</font> "
             "plutôt que <font face='Courier'>pip</font> seul."],
            ["Page blanche, ou erreur 400",
             "L'adresse utilisée n'est pas celle affichée par le lanceur. "
             "Recopier l'adresse exacte."],
            ["« Identifiant ou mot de passe incorrect »",
             "Vérifier qu'on est bien sur <b>ce</b> poste et pas une autre copie "
             "de l'application installée ailleurs."],
            ["« Le port est déjà pris »",
             "Une autre fenêtre de l'application est restée ouverte. "
             "La fermer, puis relancer."],
            ["Les trois comptes échouent à l'étape 5",
             "Les mots de passe ont été régénérés après avoir été notés. "
             "Relancer <font face='Courier'>renouveler_mots_de_passe</font>."],
        ],
        [55 * mm, 115 * mm], s,
    ))

    F.append(Spacer(1, 8))
    F.append(Paragraph("7. Avant la mise en service réelle", s["h2"]))
    F.append(Paragraph(
        "Ces points ne relèvent pas de l'installation technique mais conditionnent "
        "l'usage réel. Ils sont à valider avec l'établissement.",
        s["corps"],
    ))
    for ligne in [
        "Les trois comptes se connectent, et les mots de passe sont notés.",
        "Le fichier acces-comptes.txt a été supprimé.",
        "La sauvegarde est planifiée, et une restauration a été testée.",
        "Les fourchettes de biochimie sont chargées, ou l'absence est assumée.",
        "La durée de conservation des dossiers est définie avec l'établissement.",
        "L'établissement sait qui utilise quel compte, et pourquoi.",
    ]:
        # Pas de caractère ☐ : absent de Helvetica, il sort en carré plein et
        # laisse croire que tout est déjà coché.
        F.append(Paragraph(
            f"<font face='Courier'>[&nbsp;&nbsp;]</font>&nbsp;&nbsp;{ligne}", s["puce"]
        ))

    F.append(Spacer(1, 10))
    F.append(Paragraph(
        "Document généré par <font face='Courier'>generer_installation_pdf.py</font>. "
        "Il décrit l'état du logiciel à sa date de génération : "
        "régénérer le document après toute modification de l'installation.",
        s["petit"],
    ))

    return F


def pied(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GRIS)
    canvas.drawCentredString(
        A4[0] / 2, 12 * mm,
        f"Installation de l'application Infirmerie — page {doc.page}",
    )
    canvas.restoreState()


if __name__ == "__main__":
    sortie = BASE / f"Installation-Infirmerie-{date.today():%Y-%m-%d}.pdf"
    doc = SimpleDocTemplate(
        str(sortie),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="Installer l'application Infirmerie",
        author="Projet Infirmerie",
        subject="Procédure d'installation sur le poste client",
    )
    doc.build(construire(), onFirstPage=pied, onLaterPages=pied)
    print(f"PDF cree : {sortie.name}")
