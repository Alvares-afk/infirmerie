"""Middleware de journalisation.

Journalise deux événements qu'aucune vue ne peut voir venir :

  1. les refus d'accès (PermissionDenied) — un compte secrétariat qui tente
     d'atteindre un dossier clinique laisse une trace. C'est ce qui permet
     de détecter une-curiosité ou une tentative.
  2. les connexions et déconnexions.

Les ouvertures de dossier, elles, sont journalisées par les vues via
audit.journaliser(), car il faut y connaître le patient concerné.
"""

import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class JournalAccesMiddleware:
    """Journalise les refus d'accès.

    Django appelle process_exception avant de construire la réponse 403 :
    c'est le seul endroit où l'on voit une tentative échouée sans que la vue
    ait eu à s'en préoccuper.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Intercepte PermissionDenied avant que Django ne renvoie la 403."""
        if not getattr(settings, "JOURNAL_ACTIF", True):
            return None
        if not isinstance(exception, PermissionDenied):
            return None

        from .audit import journaliser
        from .journalisation import Action

        try:
            # On ne note que la page visée, jamais le contenu du dossier refusé.
            journaliser(
                request,
                Action.ACCES_REFUSE,
                objet=request.path,
                details=str(exception)[:200] or "acces non autorise",
            )
            logger.warning(
                "Accès refusé : %s sur %s", getattr(request.user, "username", "?"), request.path
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Échec journalisation du refus : %s", exc)
        return None
