from django.contrib import admin
from django.utils.html import format_html

from .journalisation import JournalAcces
from .models import Allergie, Bilan, Consultation, Mesure, Patient, Suivi


class MesureInline(admin.TabularInline):
    model = Mesure
    extra = 1


class AllergieInline(admin.TabularInline):
    model = Allergie
    extra = 0


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("numero_dossier", "nom", "prenom", "date_naissance", "telephone", "actif")
    search_fields = ("nom", "prenom", "numero_dossier", "telephone")
    list_filter = ("actif", "sexe")
    inlines = [AllergieInline]
    date_hierarchy = "date_naissance"


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ("patient", "date", "soignant", "statut")
    list_filter = ("date", "statut")
    search_fields = ("patient__nom", "patient__prenom", "diagnostic")


@admin.register(Bilan)
class BilanAdmin(admin.ModelAdmin):
    list_display = ("consultation", "date", "type_examen", "nb_mesures")
    search_fields = ("type_examen", "consultation__patient__nom")
    inlines = [MesureInline]


@admin.register(Mesure)
class MesureAdmin(admin.ModelAdmin):
    list_display = ("parametre", "valeur", "unite", "norme_min", "norme_max", "interpretation")

    @admin.display(description="interprétation")
    def interpretation(self, obj):
        if obj.est_anormal:
            return format_html("<b style='color:#b00020'>{}</b>", obj.libelle_anomalie)
        return obj.libelle_anomalie

    search_fields = ("parametre",)


@admin.register(Suivi)
class SuiviAdmin(admin.ModelAdmin):
    list_display = ("patient", "description", "echeance", "fait")
    list_filter = ("fait",)


admin.site.register(Allergie)


@admin.register(JournalAcces)
class JournalAccesAdmin(admin.ModelAdmin):
    """Consultation du journal d'accès.

    Strictement en lecture seule : un journal d'audit qui se peut modifier
    soi-même ne vaut plus rien comme preuve. La suppression et la
    modification sont donc bloquées.
    """

    list_display = (
        "horodatage", "identifiant_utilisateur", "role",
        "action", "numero_dossier", "objet", "adresse_ip",
    )
    list_filter = ("action", "role")
    search_fields = ("identifiant_utilisateur", "numero_dossier", "objet", "details")
    date_hierarchy = "horodatage"
    readonly_fields = [f.name for f in JournalAcces._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # La purge se fait par la commande de management, pas à la main :
        # elle est ainsi datée et explicite.
        return False
