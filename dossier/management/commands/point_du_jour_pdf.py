"""Point du jour au format PDF, pour l'envoi du matin.

Le texte reste disponible (`manage.py point_du_jour`) ; celui-ci produit un
document imprimable et archivable.

Deux choix à connaître :

  - **fond clair**, contrairement à l'interface. Un PDF destiné à l'impression
    en fond sombre vide les cartouches et sort souvent illisible.
  - **aucun nom de patient** : uniquement le numéro de dossier. Le document
    quitte le poste, la règle ne change pas.

Usage :
    python manage.py point_du_jour_pdf              # écrit le PDF, affiche son chemin
    python manage.py point_du_jour_pdf --enregistrer
"""

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .point_du_jour import elements_du_jour

BASE = Path(__file__).resolve().parents[3]
SORTIES = BASE / "sorties"

CUIVRE = colors.HexColor("#a8672f")
CREME = colors.HexColor("#faf7f2")
GRIS = colors.HexColor("#6b5b4d")
ROUGE = colors.HexColor("#a3231c")
BORD = colors.HexColor("#e5ddd2")


def styles():
    base = getSampleStyleSheet()
    return {
        "titre": ParagraphStyle(
            "titre", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=20, textColor=CUIVRE, alignment=0, spaceAfter=2,
        ),
        "sous": ParagraphStyle(
            "sous", parent=base["Normal"], fontSize=9.5, textColor=GRIS, spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "section", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=11, textColor=CUIVRE, spaceBefore=14, spaceAfter=6,
        ),
        "ligne": ParagraphStyle(
            "ligne", parent=base["Normal"], fontSize=9.5, leading=13.5,
            spaceAfter=4, leftIndent=8,
        ),
        "petit": ParagraphStyle(
            "petit", parent=base["Normal"], fontSize=7.5, textColor=GRIS, leading=10,
        ),
    }


def _ligne(texte, gras=False):
    return Paragraph(texte, styles()["ligne"])


class Command(BaseCommand):
    help = "Génère le point du jour en PDF et affiche son chemin."

    def add_arguments(self, parser):
        parser.add_argument(
            "--enregistrer", action="store_true",
            help="Marque les points comme vus (pour la mention « nouveau »).",
        )
        parser.add_argument(
            "--dossier", default=str(SORTIES),
            help="Répertoire de sortie (sorties/ par défaut).",
        )

    def handle(self, *args, **options):
        data, elements = elements_du_jour()

        if not elements:
            # Rien à signaler : aucun fichier, aucune sortie. Le script
            # d'envoi n'aura rien à transmettre.
            return

        s = styles()
        dossier = Path(options["dossier"])
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / f"point-du-jour-{data['date']:%Y-%m-%d}.pdf"

        doc = SimpleDocTemplate(
            str(chemin), pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=16 * mm, bottomMargin=16 * mm,
            title=f"Point du jour — {data['date']:%d/%m/%Y}",
            author="Infirmerie",
        )

        flux = [Paragraph("Point du jour", s["titre"])]
        resume = (
            f"{data['date']:%d/%m/%Y} · {data['nb_patients_concernes']} patient(s) "
            f"concerné(s) · {data['nb_lignes']} point(s)"
        )
        if data["consultations_du_jour"]:
            resume += f" · {data['consultations_du_jour']} consultation(s) aujourd'hui"
        flux.append(Paragraph(resume, s["sous"]))

        nouveaux = [e for e in elements if e["nouveau"]]
        connus = [e for e in elements if not e["nouveau"]]

        for titre, groupe in (("Nouveau depuis le dernier envoi", nouveaux),
                              ("Déjà signalé", connus)):
            if not groupe:
                continue
            flux.append(Paragraph(f"{titre} — {len(groupe)}", s["section"]))
            donnees = [[
                Paragraph("<b>Dossier</b>", s["petit"]),
                Paragraph("<b>Point d'attention</b>", s["petit"]),
                Paragraph("<b>Détail</b>", s["petit"]),
            ]]
            for e in groupe:
                donnees.append([
                    Paragraph(e["patient"] or "—", s["ligne"]),
                    Paragraph(e["titre"], s["ligne"]),
                    Paragraph(e["detail"] or "—", s["petit"]),
                ])
            tableau = Table(donnees, colWidths=[26 * mm, 78 * mm, 70 * mm], repeatRows=1)
            tableau.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), CREME),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORD),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]))
            flux.append(tableau)

        flux.append(Spacer(1, 14))
        flux.append(Paragraph(
            "Document produit automatiquement. Il ne contient aucun nom de patient : "
            "seul le numéro de dossier permet de retrouver la fiche dans l'application. "
            "Aucune conclusion clinique n'y figure — les valeurs signalées le sont "
            "par rapport aux bornes du laboratoire, sans interprétation.<br/>"
            "En cas de doute sur une donnée, vérifier dans l'application avant d'agir.",
            s["petit"],
        ))

        doc.build(flux)

        if options["enregistrer"]:
            from .point_du_jour import Command as CommandeTexte

            CommandeTexte()._enregistrer(elements)

        self.stdout.write(str(chemin))
