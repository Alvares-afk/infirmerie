"""Genere le resume PDF de l'etat du projet.

Usage : python generer_resume_pdf.py
Sortie : Resume-infirmerie-<date>.pdf
"""

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

BASE = Path(__file__).resolve().parent

VERT = colors.HexColor("#0f766e")
ROUGE = colors.HexColor("#b00020")
ORANGE = colors.HexColor("#b45309")
GRIS = colors.HexColor("#64748b")
CLAIR = colors.HexColor("#f1f5f9")
BORD = colors.HexColor("#e2e8f0")


def styles():
    base = getSampleStyleSheet()
    s = {}
    s["titre"] = ParagraphStyle(
        "titre", parent=base["Title"], fontSize=22, textColor=VERT,
        spaceAfter=2, alignment=TA_LEFT,
    )
    s["sous_titre"] = ParagraphStyle(
        "sous_titre", parent=base["Normal"], fontSize=10, textColor=GRIS, spaceAfter=14,
    )
    s["h2"] = ParagraphStyle(
        "h2", parent=base["Heading2"], fontSize=13, textColor=VERT,
        spaceBefore=14, spaceAfter=6,
    )
    s["h3"] = ParagraphStyle(
        "h3", parent=base["Heading3"], fontSize=11, textColor=colors.HexColor("#0f172a"),
        spaceBefore=8, spaceAfter=4,
    )
    s["corps"] = ParagraphStyle(
        "corps", parent=base["Normal"], fontSize=9.5, leading=13.5, spaceAfter=5,
    )
    s["petit"] = ParagraphStyle(
        "petit", parent=base["Normal"], fontSize=8.5, leading=12, textColor=GRIS,
    )
    s["puce"] = ParagraphStyle(
        "puce", parent=base["Normal"], fontSize=9.5, leading=13,
        leftIndent=10, bulletIndent=2, spaceAfter=3,
    )
    s["alerte"] = ParagraphStyle(
        "alerte", parent=base["Normal"], fontSize=9.5, leading=13.5,
        textColor=colors.HexColor("#7f1d1d"), spaceAfter=4,
    )
    return s


def tableau(entetes, lignes, largeurs, s, couleurs_etat=None):
    """Tableau à en-tête vert. `couleurs_etat` : colonne 0 -> couleur du texte."""
    # Le texte de l'en-tête a sa propre couleur : sans cela, le style du
    # paragraphe (gris) l'emporte sur le TEXTCOLOR blanc du tableau, et
    # l'en-tête devient gris sur vert — illisible.
    style_entete = ParagraphStyle(
        "entete", parent=s["petit"], textColor=colors.white,
        fontName="Helvetica-Bold", fontSize=8.5,
    )
    donnees = [[Paragraph(str(h), style_entete) for h in entetes]]
    for lg in lignes:
        donnees.append([Paragraph(str(c), s["corps"]) for c in lg])

    t = Table(donnees, colWidths=largeurs, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), VERT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, BORD),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(donnees)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), CLAIR))
    if couleurs_etat:
        for i, lg in enumerate(lignes, start=1):
            c = couleurs_etat.get(str(lg[0]))
            if c:
                style.append(("TEXTCOLOR", (0, i), (0, i), c))
    t.setStyle(TableStyle(style))
    return t


def encadre(titre, lignes, s, couleur=ORANGE, fond="#fffbeb"):
    """Encadré d'alerte : titre en couleur, texte dessous."""
    contenu = [[Paragraph(f"<b>{titre}</b>", ParagraphStyle(
        "e", parent=s["corps"], textColor=couleur))]]
    for lg in lignes:
        contenu.append([Paragraph(lg, s["corps"])])
    t = Table(contenu, colWidths=[170 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fond)),
        ("BOX", (0, 0), (-1, -1), 1.2, couleur),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ]))
    # L'enveloppe empêche l'encadré d'être coupé entre deux pages : sans elle,
    # le titre reste seul en bas de page et le texte reprend au suivant.
    return KeepTogether(t)


def pied(page, total):
    return Paragraph(
        f"Application Infirmerie — résumé d'état · page {page} / {total}",
        ParagraphStyle("pied", fontSize=7.5, textColor=GRIS, alignment=1),
    )


def construire():
    s = styles()
    aujourdhui = date.today().strftime("%d/%m/%Y")
    F = []

    # ---------------------------------------------------------- titre
    F.append(Paragraph("Application Infirmerie", s["titre"]))
    F.append(Paragraph(
        "Gestion des dossiers patients et des bilans de santé — résumé d'état",
        s["sous_titre"],
    ))

    F.append(tableau(
        ["Champ", "Valeur"],
        [
            ["Projet", f"<b>{BASE}</b>"],
            ["Dépôt", "github.com/Alvares-afk/infirmerie (public)"],
            ["Pile", "Django 6.1.1 · SQLite · Python 3.14 · Windows"],
            ["Date du document", aujourdhui],
            ["État", '<b><font color="#b00020">Application en service, à configurer avant usage réel</font></b>'],
        ],
        [35 * mm, 135 * mm], s,
    ))
    F.append(Spacer(1, 10))

    # --------------------------------------------------- ce qui est fait
    F.append(Paragraph("1. Ce qui est en place", s["h2"]))
    F.append(tableau(
        ["Module", "État", "Contenu"],
        [
            ["Fiches patients", "✅", "Identité, allergies, médecin traitant, n° de dossier automatique"],
            ["Consultations", "✅", "Datées, motif, diagnostic, prescription, constantes, IMC calculé"],
            ["Bilans de santé", "✅", "Rattachés à la consultation, interprétation selon les normes"],
            ["Fourchettes de référence", "✅", "<b>Paramétrables par laboratoire</b>, signées et versionnées"],
            ["Suivis", "✅", "Échéances, détection de retard"],
            ["Synthèse imprimable", "✅", "Avec bandeau d'allergies"],
            ["Point quotidien", "✅", "Priorisé : immédiat / avant visite / à planifier"],
            ["Relances", "✅", "Brouillons — <b>aucun envoi automatique</b>"],
            ["Journal d'accès", "✅", "Lecture seule, <b>sans donnée clinique</b>"],
            ["Deux rôles", "✅", "Secrétariat / soignant, contrôle côté serveur"],
        ],
        [32 * mm, 12 * mm, 126 * mm], s,
    ))
    F.append(Spacer(1, 8))

    # -------------------------------------------------------- sécurité
    F.append(Paragraph("2. Sécurité — vérifié, pas supposé", s["h2"]))
    for lg in [
        "• Contrôle des accès <b>côté serveur</b> : un compte secrétariat obtient 403 sur une URL de dossier clinique. Un lien direct ne donne rien.",
        "• <code>SECRET_KEY</code> hors du fichier de configuration, lue depuis l'environnement. L'application <b>refuse de démarrer</b> en production sans elle.",
        "• Mode debug piloté par variable d'environnement.",
        "• L'administration Django n'est accessible qu'au compte <code>admin</code> : le soignant reçoit 403.",
        "• Aucune donnée clinique dans le journal d'accès ni dans les URL — les logs du serveur ne contiennent que des identifiants numériques.",
        "• Une panne du journal <b>ne bloque pas</b> l'accès au dossier : le soignant garde la main.",
    ]:
        F.append(Paragraph(lg, s["puce"], bulletText=""))

    F.append(Spacer(1, 6))
    F.append(encadre(
        "Règle d'or appliquée",
        ["« Normal » n'est prononcé que si le laboratoire a borné le côté qui compte. "
         "Trois cas donnent « à qualifier » : mention qualitative "
         "(« négatif », « traces »), ou aucune borne. Une borne haute seule suffit "
         "à conclure (enzymes), une borne basse seule non. "
         "Sans cette règle, un résultat dont on ignore la norme s'afficherait "
         "comme rassurant — le risque le plus grave possible ici."],
        s,
    ))
    F.append(Spacer(1, 10))

    # ------------------------------------------------------- deux bases
    F.append(Paragraph("3. Deux bases séparées", s["h2"]))
    F.append(Paragraph(
        "Les patients fictifs et les vrais dossiers ne partagent rien : une erreur sur "
        "la démonstration ne peut pas atteindre une donnée réelle.", s["corps"]))
    F.append(tableau(
        ["Lanceur", "Base", "Contenu"],
        [
            ["<b>demarrer_reel.bat</b>", "db_reelle.sqlite3", "<b>Vrais dossiers patients</b> — vide, prête"],
            ["demarrer_demo.bat", "db.sqlite3", "6 patients fictifs, pour essayer"],
        ],
        [42 * mm, 40 * mm, 88 * mm], s,
    ))
    F.append(Spacer(1, 6))
    for lg in [
        "Un <b>bandeau rouge permanent</b> en haut de chaque page indique la base ouverte.",
        "Les sauvegardes sont séparées (<code>sauvegarder_reel.bat</code> / <code>sauvegarder.bat</code>).",
        "Une restauration <b>refuse de franchir les deux bases</b> : restaurer une sauvegarde de démonstration sur les vrais dossiers est bloqué.",
    ]:
        F.append(Paragraph(lg, s["puce"], bulletText=""))
    F.append(Spacer(1, 10))

    # ------------------------------------------------------------ tests
    F.append(Paragraph("4. Vérifications", s["h2"]))
    F.append(tableau(
        ["Contrôle", "Résultat"],
        [
            ["Tests automatisés", "<b>132 passent</b> (parcours, permissions, journal, briefing, relances, références, unités)"],
            ["Rendu des écrans", "12 écrans vérifiés pour les deux rôles"],
            ["Isolation des bases", "Vérifiée"],
            ["Sauvegarde / restauration", "Testées, y compris le refus de confusion"],
        ],
        [45 * mm, 125 * mm], s,
    ))
    F.append(Spacer(1, 6))
    F.append(Paragraph(
        "Neuf bugs réels ont été trouvés et corrigés, dont trois lors des derniers "
                "travaux : une valeur sans norme complète était classée <b>« normal »</b> "
                "(donc rassurante), une borne basse seule permettait de conclure à tort sur un "
                "résultat élevé, et des valeurs issues d'un compte rendu réel s'étaient "
                "retrouvées dans les tests versionnés.", s["petit"]))

    F.append(PageBreak())

    # --------------------------------------------------------- à faire
    F.append(Paragraph("5. À faire avant un usage réel", s["h2"]))
    F.append(encadre(
        "✓ Fait — les fourchettes de référence du laboratoire",
        ["Les normes ne sont plus des repères usuels : ce sont les bornes de votre "
         "laboratoire, chargées et vérifiées. <b>Le risque le plus sérieux de "
         "l'application est levé.</b> Il reste à compléter si votre laboratoire "
         "analyse d'autres paramètres sur une autre feuille (glycémie, créatinine, "
         "ferritine, lipides) : tant qu'ils ne sont pas dans la table, ils "
         "restent « à qualifier » — ce qui est le comportement voulu."],
        s, couleur=VERT, fond="#f0fdfa",
    ))
    F.append(Spacer(1, 6))
    F.append(encadre(
        "1. Changer les mots de passe des trois comptes  — À FAIRE",
        ["Ils sont identiques pour l'instant. Un fichier <code>secret.env.txt</code> "
         "contenant un mot de passe en clair a été trouvé à la racine du projet ; il n'a "
         "pas été versionné, mais ce mot de passe est à considérer comme compromis."],
        s, couleur=ROUGE, fond="#fef2f2",
    ))
    F.append(Spacer(1, 6))
    F.append(encadre(
        "2. Saisir un patient de bout en bout",
        ["Fiche, consultation, bilan, synthèse imprimée. Les vrais manques n'apparaissent "
         "qu'à l'usage — un champ inutile, une saisie qui fait trois allers-retours."],
        s,
    ))
    F.append(Spacer(1, 10))
    # ---------------------------------------------------------- ouverture
    F.append(Paragraph("6. État du déploiement en ligne", s["h2"]))
    F.append(Paragraph(
        "L'application <b>tourne en local</b> : http://127.0.0.1:8000 — c'est là que la "
        "saisie de vrais dossiers se fait.", s["corps"]))
    F.append(tableau(
        ["Point", "État"],
        [
            ["Erreur de build Vercel", '<font color="#166534"><b>Corrigée</b></font> — runtime Python inventé dans <code>vercel.json</code>, supprimé au profit d\'un <code>.python-version</code>'],
            ["Accès public", '<font color="#b45309"><b>Bloqué</b></font> — protection d\'équipe Vercel, réglage d\'organisation'],
            ["Supabase", "Base de démonstration connectée, jamais de données réelles"],
            ["Compte Vercel", "Projet rattaché à l'équipe <b>win-team5</b> — à confirmer"],
        ],
        [38 * mm, 132 * mm], s,
    ))
    F.append(Spacer(1, 6))
    F.append(encadre(
        "Pourquoi les données réelles restent en local",
        ["Supabase n'est <b>pas certifié HDS</b>. Héberger des dossiers patients chez eux "
         "poserait un problème légal français. L'hébergement local, avec accès par VPN et "
         "aucun port ouvert, reste la bonne voie pour un usage réel."],
        s,
    ))
    F.append(Spacer(1, 10))

    # ------------------------------------------------------------- suite
    F.append(Paragraph("7. Points ouverts", s["h2"]))
    F.append(tableau(
        ["Sujet", "Nature"],
        [
            ["Durée de conservation des dossiers", "Décision d'établissement"],
            ["Sort du dossier au départ d'un patient", "Décision d'établissement"],
            ["Politique de purge du journal d'accès", "Décision d'établissement"],
            ["Module prophylaxie (spéc. LAB 04)", "Modèle conçu — attend les calendriers et protocoles de l'établissement"],
            ["Planification automatique (spéc. LAB 04)", "Conçue — 4 tâches à automatiser sur 4 à proscrire"],
                        ["Sources documentaires (protocoles, fiches types)", "Conçue — attend l'inventaire des documents"],
        ],
        [70 * mm, 100 * mm], s,
    ))
    F.append(Spacer(1, 6))
    F.append(Paragraph(
        "Sur les six écarts entre la spécification LAB 04 et l'application, trois sont "
        "comblés : dossiers et bilans, point quotidien, relances.", s["petit"]))

    F.append(Spacer(1, 14))
    F.append(encadre(
        "Commandes utiles",
        [
            "<b>Lancer les vrais dossiers</b> : double-clic sur <code>demarrer_reel.bat</code><br/>"
            "<b>Lancer la démonstration</b> : <code>demarrer_demo.bat</code><br/>"
            "<b>Sauvegarder les vrais dossiers</b> : <code>sauvegarder_reel.bat</code><br/>"
            "<b>Vérifier l'application</b> : <code>manage.py test dossier</code> (132 tests)",
        ],
        s, couleur=VERT, fond="#f0fdfa",
    ))
    return F


if __name__ == "__main__":
    sortie = BASE / f"Resume-infirmerie-{date.today():%Y-%m-%d}.pdf"
    doc = SimpleDocTemplate(
        str(sortie), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Application Infirmerie — résumé d'état",
        author="Projet Infirmerie",
    )
    doc.build(construire(), onFirstPage=lambda c, d: None,
              onLaterPages=lambda c, d: None)
    print(f"PDF cree : {sortie.name}")
