"""Vues de l'infirmerie."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import (
    AllergieForm, BilanForm, ConsultationForm, MesureFormSet, PatientForm, SuiviForm,
)
from .audit import journaliser
from .journalisation import Action
from .models import Allergie, Bilan, Consultation, Mesure, Patient, Suivi
from .permissions import LIBELLE_ROLE, exiger_clinique, est_soignant, role_de


def _numero_dossier_libre():
    """Attribue le prochain numéro de dossier : INF-0001, INF-0002…"""
    dernier = (
        Patient.objects.filter(numero_dossier__startswith="INF-")
        .order_by("-numero_dossier")
        .first()
    )
    n = 1
    if dernier:
        try:
            n = int(str(dernier.numero_dossier).split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = Patient.objects.count() + 1
    return f"INF-{n:04d}"


# ------------------------------------------------------------------ Accueil


@login_required
def accueil(request):
    role = role_de(request.user)
    aujourdhui = timezone.localdate()

    patients = Patient.objects.filter(actif=True)

    contexte = {
        "role": role,
        "libelle_role": LIBELLE_ROLE.get(role, "Non attribué"),
        "now": timezone.localtime(),
        "nb_patients": patients.count(),
        "consultations_jour": Consultation.objects.filter(date=aujourdhui).count(),
        "suivis_en_retard": Suivi.objects.filter(fait=False, echeance__lt=aujourdhui).count(),
        "suivis_a_venir": Suivi.objects.filter(
            fait=False, echeance__gte=aujourdhui
        ).order_by("echeance")[:8],
        "patients_recents": patients.order_by("-cree_le")[:6],
    }

    # Les éléments cliniques ne sont annoncés qu'à un soignant
    if est_soignant(request.user):
        alertes = []
        for p in patients.prefetch_related("allergies"):
            b = p.dernier_bilan()
            if b and b.a_des_anomalies:
                alertes.append({"patient": p, "bilan": b, "nb": len(b.resume()["liste"])})
        # Bilan de plus de 12 mois : à renouveler
        for p in patients:
            b = p.dernier_bilan()
            if b and b.date < aujourdhui - timedelta(days=365):
                alertes.append({"patient": p, "bilan": b, "perime": True, "nb": 0})
        contexte["alertes"] = alertes[:8]
        contexte["nb_alertes"] = len(alertes)

    return render(request, "dossier/accueil.html", contexte)


# ----------------------------------------------------------------- Patients


@login_required
def liste_patients(request):
    q = request.GET.get("q", "").strip()
    patients = Patient.objects.all()
    if q:
        patients = patients.filter(
            Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(numero_dossier__icontains=q)
            | Q(telephone__icontains=q)
        )
    return render(
        request, "dossier/patients.html",
        {"patients": patients[:100], "q": q, "nb": patients.count(), "role": role_de(request.user)},
    )


@login_required
def patient_detail(request, pk):
    p = get_object_or_404(Patient, pk=pk)
    if not est_soignant(request.user):
        raise PermissionDenied("Le dossier clinique est réservé au personnel soignant.")

    journaliser(request, Action.LECTURE, patient=p, objet="dossier patient")
    return render(
        request, "dossier/patient_detail.html",
        {
            "patient": p,
            "consultations": p.consultations.select_related("soignant")[:20],
            "bilans": Bilan.objects.filter(consultation__patient=p)[:10],
            "allergies": p.allergies.all(),
            "suivis": p.suivis.all(),
            "suivi_form": SuiviForm(),
            "dernier_bilan": p.dernier_bilan(),
            "nb_consultations": p.consultations.count(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def patient_create(request):
    form = PatientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        p = form.save(commit=False)
        p.numero_dossier = p.numero_dossier or _numero_dossier_libre()
        p.save()
        journaliser(request, Action.CREATION, patient=p, objet="fiche patient")
        messages.success(request, f"Dossier {p.numero_dossier} créé pour {p}.")
        return redirect("patient_detail", pk=p.pk)
    return render(
        request, "dossier/patient_form.html",
        {"form": form, "titre": "Nouveau patient", "allergie_form": AllergieForm()},
    )


@login_required
@require_http_methods(["GET", "POST"])
def patient_edit(request, pk):
    p = get_object_or_404(Patient, pk=pk)
    form = PatientForm(request.POST or None, instance=p)
    if request.method == "POST" and form.is_valid():
        form.save()
        journaliser(request, Action.MODIFICATION, patient=p, objet="fiche patient")
        messages.success(request, "Fiche mise à jour.")
        return redirect("patient_detail", pk=p.pk)
    return render(
        request, "dossier/patient_form.html",
        {"form": form, "patient": p, "titre": f"Modifier {p}",
         "allergie_form": AllergieForm()},
    )


@login_required
@require_http_methods(["POST"])
def allergie_add(request, pk):
    p = get_object_or_404(Patient, pk=pk)
    form = AllergieForm(request.POST)
    if form.is_valid():
        a = form.save(commit=False)
        a.patient = p
        a.save()
        messages.success(request, f"Allergie enregistrée : {a.substance}.")
    else:
        messages.error(request, "Allergie non enregistrée : vérifiez les champs.")
    return redirect("patient_detail", pk=p.pk)


@login_required
@require_http_methods(["POST"])
def allergie_delete(request, pk, allergie_pk):
    a = Allergie.objects.filter(pk=allergie_pk, patient_id=pk).first()
    Allergie.objects.filter(pk=allergie_pk, patient_id=pk).delete()
    journaliser(request, Action.SUPPRESSION,
                patient=get_object_or_404(Patient, pk=pk),
                objet="allergie", details=(a.substance if a else ""))
    messages.info(request, "Allergie supprimée.")
    return redirect("patient_detail", pk=pk)


# ------------------------------------------------------------ Consultations


@login_required
@require_http_methods(["GET", "POST"])
def consultation_create(request, patient_pk):
    p = get_object_or_404(Patient, pk=patient_pk)
    exiger_clinique(request.user)
    form = ConsultationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.patient = p
        c.soignant = request.user
        c.save()
        journaliser(request, Action.CREATION, patient=p, objet="consultation",
                    details=f"date {c.date:%d/%m/%Y}")
        messages.success(request, "Consultation enregistrée.")
        return redirect("bilan_create", consultation_pk=c.pk)
    return render(
        request, "dossier/consultation_form.html",
        {"form": form, "patient": p,
         "alergies": p.allergies.all(), "titre": "Nouvelle consultation"},
    )


@login_required
def consultation_detail(request, pk):
    c = get_object_or_404(Consultation, pk=pk)
    exiger_clinique(request.user)
    return render(
        request, "dossier/consultation_detail.html",
        {
            "consultation": c,
            "patient": c.patient,
            "bilans": c.bilans.all(),
            "allergies": c.patient.allergies.all(),
            "imc": c.imc,
        },
    )


# ---------------------------------------------------------- Bilan de santé


@login_required
@require_http_methods(["GET", "POST"])
def bilan_create(request, consultation_pk):
    c = get_object_or_404(Consultation, pk=consultation_pk)
    exiger_clinique(request.user)
    form = BilanForm(request.POST or None)
    mesure_formset = MesureFormSet(request.POST or None, prefix="mesure")

    if request.method == "POST" and form.is_valid() and mesure_formset.is_valid():
        b = form.save(commit=False)
        b.consultation = c
        b.save()
        mesure_formset.instance = b
        mesure_formset.save()
        nb = b.nb_mesures
        journaliser(request, Action.CREATION, patient=c.patient, objet="bilan de sante",
                    details=f"{b.type_examen or 'bilan'} — {nb} mesure(s)")
        messages.success(request, f"Bilan enregistré : {nb} mesure{'s' if nb > 1 else ''}.")
        return redirect("bilan_detail", pk=b.pk)

    return render(
        request, "dossier/bilan_form.html",
        {"form": form, "mesure_formset": mesure_formset,
         "consultation": c, "patient": c.patient, "titre": "Nouveau bilan de santé"},
    )


@login_required
def bilan_detail(request, pk):
    b = get_object_or_404(Bilan, pk=pk)
    exiger_clinique(request.user)
    journaliser(request, Action.LECTURE, patient=b.consultation.patient,
                objet="bilan de sante", details=f"du {b.date:%d/%m/%Y}")
    resume = b.resume()
    return render(
        request, "dossier/bilan_detail.html",
        {
            "bilan": b,
            "mesures": b.mesures.all(),
            "resume": resume,
            "patient": b.consultation.patient,
            "consultation": b.consultation,
        },
    )


# ------------------------------------------------------------------ Suivis


@login_required
@require_http_methods(["POST"])
def suivi_add(request, patient_pk):
    p = get_object_or_404(Patient, pk=patient_pk)
    form = SuiviForm(request.POST)
    if form.is_valid():
        s = form.save(commit=False)
        s.patient = p
        s.save()
        messages.success(request, "Suivi ajouté.")
    return redirect("patient_detail", pk=p.pk)


@login_required
@require_http_methods(["POST"])
def suivi_toggle(request, pk):
    s = get_object_or_404(Suivi, pk=pk)
    s.fait = not s.fait
    s.save()
    return redirect("patient_detail", pk=s.patient_id)


# ------------------------------------------------- Export de synthèse PDF

@login_required
def synthese_patient(request, pk):
    """Synthèse imprimable. Sert au passage de relais vers un spécialiste."""
    p = get_object_or_404(Patient, pk=pk)
    exiger_clinique(request.user)
    journaliser(request, Action.LECTURE, patient=p, objet="synthese exportee",
                details="generation du document de synthese")

    consultations = list(p.consultations.select_related("soignant")[:10])
    bilans = list(Bilan.objects.filter(consultation__patient=p)[:5])

    html = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>Synthèse {p}</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; font-size: 11pt; color:#111; margin:2cm; }}
  h1 {{ font-size: 16pt; margin:0 0 2px; }}
  h2 {{ font-size: 12pt; margin:20px 0 6px; border-bottom:1px solid #999; padding-bottom:3px; }}
  .sous {{ color:#555; font-size:10pt; margin:0 0 14px; }}
  table {{ border-collapse: collapse; width:100%; margin-bottom:8px; }}
  th, td {{ border:1px solid #bbb; padding:5px 7px; text-align:left; font-size:10pt; }}
  th {{ background:#f0f0f0; }}
  .anormal {{ color:#b00020; font-weight:600; }}
  .alerte {{ border:2px solid #b00020; padding:8px 10px; margin-bottom:12px; background:#fff5f5; }}
  footer {{ margin-top:26px; font-size:9pt; color:#666; border-top:1px solid #ccc; padding-top:6px; }}
</style></head><body>
<h1>{p}</h1>
<p class="sous">Dossier {p.numero_dossier or "—"} · né(e) le {p.date_naissance.strftime("%d/%m/%Y")}
({p.age} ans) · médecin traitant : {p.medecin_traitant or "non renseigné"}</p>
"""

    if p.allergies.exists():
        liste = " ; ".join(
            f"{a.substance} ({a.get_gravite_display()})" for a in p.allergies.all()
        )
        html += f'<div class="alerte"><strong>⚠ ALLERGIES :</strong> {liste}</div>'

    html += "<h2>Dernières consultations</h2><table><tr><th>Date</th><th>Motif</th><th>Diagnostic</th><th>Prescription</th></tr>"
    for c in consultations:
        html += (
            f"<tr><td>{c.date.strftime('%d/%m/%Y')}</td><td>{c.motif or '—'}</td>"
            f"<td>{c.diagnostic or '—'}</td><td>{c.prescription or '—'}</td></tr>"
        )
    html += "</table>"

    html += "<h2>Bilans de santé</h2>"
    if not bilans:
        html += "<p>Aucun bilan enregistré.</p>"
    for b in bilans:
        r = b.resume()
        html += (
            f"<p><strong>{b.type_examen or 'Bilan'} — {b.date.strftime('%d/%m/%Y')}</strong>"
            + (f" · <span class='anormal'>{r['anomalies']} anomalie(s)</span>" if r["anomalies"] else "")
            + "</p><table><tr><th>Paramètre</th><th>Valeur</th><th>Norme</th><th>Interprétation</th></tr>"
        )
        for m in b.mesures.all():
            classe = ' class="anomal"' if m.est_anormal else ""
            norme = f"{m.norme_min} – {m.norme_max}".strip(" –") or m.reference or "—"
            html += (
                f"<tr><td>{m.parametre}</td><td>{m.valeur} {m.unite}</td>"
                f"<td>{norme}</td><td{classe}>{m.libelle_anomalie}</td></tr>"
            )
        html += "</table>"

    html += (
        f"<footer>Document généré le {timezone.localdate().strftime('%d/%m/%Y')} à "
        f"{timezone.localtime().strftime('%H:%M')} — usage interne, contient des données de santé.</footer>"
    )
    html += "</body></html>"

    response = HttpResponse(html)
    response["Content-Type"] = "text/html; charset=utf-8"
    return response
