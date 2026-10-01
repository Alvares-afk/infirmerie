"""Écriture du journal d'accès.

Une seule porte d'entrée : `journaliser()`. Les vues l'appellent
explicitement, ce qui évite qu'un oubli passe inaperçu.

Règle : on journalise la RÉFÉRENCE (quel dossier, quel patient), jamais le
contenu clinique. Un journal qui contient les valeurs biologiques serait
lui-même un fichier de données de santé, avec le même niveau de protection.
"""

from .journalisation import Action, JournalAcces


def _ip(request):
    if request is None:
        return None
    # X-Forwarded-For n'est lu que si un proxy de confiance est devant ;
    # ici l'application est locale, donc l'adresse socket suffit.
    adresse = request.META.get("REMOTE_ADDR")
    return adresse or None


def journaliser(request, action, *, patient=None, objet="", details="", numero_dossier="",
               identifiant_fourni=""):
    """Enregistre une entrée d'audit. Ne doit jamais interrompre la requête.

    Si l'écriture échoue, l'accès ne doit pas être bloqué : on journalise
    l'incident sur la console et on laisse la requête se poursuivre. Un
    dossier inaccessible vaut mieux qu'une application qui plante, mais la
    panne de journal doit être visible.
    """
    from .permissions import role_de

    try:
        utilisateur = getattr(request, "user", None)
        connecte = bool(utilisateur and utilisateur.is_authenticated)

        # Le signal user_logged_in est émis au moment où Django remplace
        # request.user : selon l'ordre, on lit l'ancien ou le nouvel
        # utilisateur. On accepte donc un identifiant explicite.
        if connecte:
            identifiant = utilisateur.get_username()
        else:
            identifiant = identifiant_fourni or ""

        if numero_dossier == "" and patient is not None:
            numero_dossier = patient.numero_dossier or ""

        JournalAcces.objects.create(
            utilisateur=utilisateur if connecte else None,
            identifiant_utilisateur=(identifiant or "anonyme")[:150],
            role=(role_de(utilisateur) or "") if connecte else "",
            patient=patient,
            numero_dossier=numero_dossier[:20],
            objet=objet[:120],
            action=action,
            details=details[:200],
            adresse_ip=_ip(request),
        )
    except Exception as exc:  # pragma: no cover - ne doit pas casser l'application
        print(f"[JOURNAL] échec d'écriture : {exc}")
