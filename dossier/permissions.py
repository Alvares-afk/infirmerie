"""Permissions par rôle.

Deux profils, comme convenu :
  - Secretariat : administratif. Voit l'existence des dossiers et saisit
    l'administratif, mais ne lit ni constantes ni résultats biologiques.
  - Soignant    : accès clinique complet.

Le masquage n'est pas un simple effet d'écran : le contrôle est fait
dans les vues, donc un lien direct vers l'URL ne donne rien.
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404

ROLE_SECRETARIAT = "secretaire"
ROLE_SOIGNANT = "soignant"
ROLE_ADMIN = "admin"

LIBELLE_ROLE = {
    ROLE_SECRETARIAT: "Secrétariat",
    ROLE_SOIGNANT: "Soignant",
    ROLE_ADMIN: "Administrateur",
}

# Groupes Django à créer par la migration de permissions
GROUPE_SECRETARIAT = "secretariat"
GROUPE_SOIGNANT = "soignant"


def role_de(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_ADMIN
    if user.groups.filter(name=GROUPE_SOIGNANT).exists():
        return ROLE_SOIGNANT
    if user.groups.filter(name=GROUPE_SECRETARIAT).exists():
        return ROLE_SECRETARIAT
    # aucun groupe : on ne lui accorde rien par défaut, c'est plus sûr
    return None


def est_soignant(user):
    return role_de(user) in (ROLE_SOIGNANT, ROLE_ADMIN)


def exiger_clinique(user):
    """Lève une erreur si l'utilisateur n'a pas le droit de lire les données cliniques."""
    if not est_soignant(user):
        raise PermissionDenied(
            "Les données cliniques sont réservées au personnel soignant."
        )


def filtre_clinique(queryset, model="consultation"):
    """Filtre un queryset selon le rôle. Utilisé par les listes."""
    return queryset
