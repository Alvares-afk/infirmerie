"""Routes du projet."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from dossier import views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("connexion/", auth_views.LoginView.as_view(
        template_name="dossier/login.html", redirect_authenticated_user=True
    ), name="connexion"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),

    path("", views.accueil, name="accueil"),
    path("briefing/", views.briefing, name="briefing"),

    path("relances/", views.liste_relances, name="liste_relances"),
    path("relances/generer/", views.relance_generer, name="relance_generer"),
    path("relances/<int:pk>/valider/", views.relance_valider, name="relance_valider"),
    path("relances/<int:pk>/abandonner/", views.relance_abandonner, name="relance_abandonner"),

    path("patients/", views.liste_patients, name="liste_patients"),
    path("patients/nouveau/", views.patient_create, name="patient_create"),
    path("patients/<int:pk>/", views.patient_detail, name="patient_detail"),
    path("patients/<int:pk>/modifier/", views.patient_edit, name="patient_edit"),
    path("patients/<int:pk>/synthese/", views.synthese_patient, name="synthese_patient"),

    path("patients/<int:pk>/allergie/ajouter/", views.allergie_add, name="allergie_add"),
    path("patients/<int:pk>/allergie/<int:allergie_pk>/supprimer/",
         views.allergie_delete, name="allergie_delete"),

    path("patients/<int:patient_pk>/consultation/nouvelle/",
         views.consultation_create, name="consultation_create"),
    path("consultations/<int:pk>/", views.consultation_detail, name="consultation_detail"),

    path("consultations/<int:consultation_pk>/bilan/nouveau/",
         views.bilan_create, name="bilan_create"),
    path("bilans/<int:pk>/", views.bilan_detail, name="bilan_detail"),

    path("patients/<int:patient_pk>/suivi/ajouter/", views.suivi_add, name="suivi_add"),
    path("suivis/<int:pk>/basculer/", views.suivi_toggle, name="suivi_toggle"),
]
