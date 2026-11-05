"""Tests de l'agenda des rendez-vous.

L'agenda contient des données nominatives mais aucune donnée clinique : il
est accessible au secrétariat, contrairement au dossier patient. Ces tests
verrouillent cette frontière, et le fait qu'un rendez-vous ne crée jamais de
consultation tout seul.
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dossier.models import Consultation, Patient, RendezVous, StatutRdv


class AgendaDesRendezVous(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            nom="Martin", prenom="Claire", date_naissance="1985-04-02",
            numero_dossier="INF-9200",
        )
        self.soignant = User.objects.create_user("soignant_test", password="Mot-De-Passe-2026")
        self.secretariat = User.objects.create_user("secretariat_test", password="Mot-De-Passe-2026")

    def _rdv(self, jours=0, heure="09:30", statut=StatutRdv.PREVU, motif="Pansement"):
        return RendezVous.objects.create(
            patient=self.patient,
            date=timezone.localdate() + timedelta(days=jours),
            heure=heure,
            statut=statut,
            motif=motif,
        )

    # ---------------------------------------------------------- acces
    def test_le_secretariat_voit_l_agenda(self):
        self.client.force_login(self.secretariat)
        reponse = self.client.get(reverse("liste_rendez_vous"))
        self.assertEqual(reponse.status_code, 200)

    def test_l_agenda_n_exige_pas_de_role_clinique(self):
        """Un rendez-vous n'est pas un dossier : le secrétariat le gère."""
        self.client.force_login(self.secretariat)
        reponse = self.client.post(reverse("rendez_vous_create"), {
            "patient": self.patient.pk,
            "date": (timezone.localdate() + timedelta(days=3)).isoformat(),
            "heure": "14:00",
            "motif": "Contrôle tension",
            "notes": "",
        })
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(RendezVous.objects.count(), 1)

    def test_connexion_obligatoire(self):
        reponse = self.client.get(reverse("liste_rendez_vous"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/connexion/", reponse.url)

    # ---------------------------------------------------------- affichage
    def test_un_rendez_vous_passe_non_traite_apparait_en_retard(self):
        self._rdv(jours=-4)
        self.client.force_login(self.soignant)
        reponse = self.client.get(reverse("liste_rendez_vous"))
        self.assertEqual(len(reponse.context["en_retard"]), 1)
        self.assertContains(reponse, "En retard")

    def test_un_rendez_vous_annule_ne_traîne_pas_en_retard(self):
        self._rdv(jours=-4, statut=StatutRdv.ANNULE)
        self.client.force_login(self.soignant)
        reponse = self.client.get(reverse("liste_rendez_vous"))
        self.assertEqual(len(reponse.context["en_retard"]), 0)

    def test_le_jour_meme_est_isole(self):
        self._rdv(jours=0)
        self._rdv(jours=2, heure="15:00")
        self.client.force_login(self.soignant)
        reponse = self.client.get(reverse("liste_rendez_vous"))
        self.assertEqual(len(reponse.context["du_jour"]), 1)
        self.assertEqual(len(reponse.context["a_venir"]), 1)

    # ---------------------------------------------------------- statuts
    def test_marquer_honore_change_le_statut(self):
        rdv = self._rdv()
        self.client.force_login(self.soignant)
        self.client.post(reverse("rendez_vous_statut", args=[rdv.pk]), {"statut": "honore"})
        rdv.refresh_from_db()
        self.assertEqual(rdv.statut, StatutRdv.HONORE)

    def test_un_rendez_vous_honore_ne_cree_pas_de_consultation(self):
        """Le soignant décide de ce qu'il note en séance, pas le calendrier."""
        rdv = self._rdv()
        self.client.force_login(self.soignant)
        self.client.post(reverse("rendez_vous_statut", args=[rdv.pk]), {"statut": "honore"})
        self.assertEqual(Consultation.objects.filter(patient=self.patient).count(), 0)

    def test_statut_inconnu_refuse(self):
        rdv = self._rdv()
        self.client.force_login(self.soignant)
        reponse = self.client.post(reverse("rendez_vous_statut", args=[rdv.pk]), {"statut": "peut-etre"})
        self.assertEqual(reponse.status_code, 403)
        rdv.refresh_from_db()
        self.assertEqual(rdv.statut, StatutRdv.PREVU)

    # ---------------------------------------------------------- doublons
    def test_deux_rendez_vous_a_la_meme_heure_sont_refuses(self):
        self._rdv(heure="10:00")
        self.client.force_login(self.soignant)
        reponse = self.client.post(reverse("rendez_vous_create"), {
            "patient": self.patient.pk,
            "date": timezone.localdate().isoformat(),
            "heure": "10:00",
            "motif": "Autre motif",
            "notes": "",
        })
        self.assertEqual(reponse.status_code, 200, "le formulaire doit rester affiché")
        self.assertEqual(RendezVous.objects.count(), 1)

    def test_heure_facultative(self):
        self.client.force_login(self.soignant)
        self.client.post(reverse("rendez_vous_create"), {
            "patient": self.patient.pk,
            "date": timezone.localdate().isoformat(),
            "heure": "",
            "motif": "Sans heure fixée",
            "notes": "",
        })
        self.assertEqual(RendezVous.objects.count(), 1)
