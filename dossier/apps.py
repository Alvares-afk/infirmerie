from django.apps import AppConfig


class DossierConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dossier"
    verbose_name = "Dossiers patients"

    def ready(self):
        # Branche les signaux de connexion / déconnexion / échec.
        # Sans cet import, aucun signal n'est enregistré.
        from . import signaux  # noqa: F401
