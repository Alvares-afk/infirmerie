"""Journalisation des connexions et déconnexions.

Branché sur les signaux Django, donc actif partout sans que les vues aient
à s'en préoccuper. Un compte qui tente une connexion échouée est également
noté : plusieurs échecs d'affilée méritent d'être vus.
"""

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .audit import journaliser
from .journalisation import Action


@receiver(user_logged_in)
def sur_connexion(sender, request, user, **kwargs):
    journaliser(request, Action.LECTURE, objet="connexion",
                details="session ouverte",
                identifiant_fourni=user.get_username())


@receiver(user_logged_out)
def sur_deconnexion(sender, request, user, **kwargs):
    journaliser(request, Action.LECTURE, objet="deconnexion",
                details="session fermee",
                identifiant_fourni=(user.get_username() if user else ""))


@receiver(user_login_failed)
def sur_echec_connexion(sender, credentials, request=None, **kwargs):
    identifiant = (credentials or {}).get("username", "") if credentials else ""
    journaliser(
        request,
        Action.ACCES_REFUSE,
        objet="connexion",
        details=f"echec - identifiant '{identifiant}'",
    )
