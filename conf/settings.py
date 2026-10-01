"""Configuration du projet.

Trois réglages de sécurité dépendent du contexte, et sont donc pilotés par
des variables d'environnement plutôt que codés en dur :

  INFIRMERIE_SECRET_KEY   signature des sessions. Absente en développement,
                           un secret temporaire est généré.
  INFIRMERIE_DEBUG         "1" pour tracer les erreurs en développement.
                           À laisser absent ou "0" en production.
  INFIRMERIE_ALLOWED_HOSTS  hôtes autorisés, séparés par des virgules.

En production :
  set INFIRMERIE_SECRET_KEY=<une valeur de 50 caracteres ou plus, aleatoire>
  set INFIRMERIE_DEBUG=0
  set INFIRMERIE_ALLOWED_HOSTS=127.0.0.1
"""

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool_environ(nom, defaut=False):
    """Lit un booleen depuis l'environnement.

    Une variable absente ou vide prend la valeur par defaut. Ce n'est pas le
    cas si on se contente de tester l'appartenance a un ensemble de
    valeurs vraies : une variable vide serait alors lue comme "faux".
    """
    valeur = os.environ.get(nom, "").strip().lower()
    if not valeur:
        return defaut
    if valeur in ("0", "false", "non", "no", "off"):
        return False
    return True


# --- SECRET_KEY ---------------------------------------------------------
# Cette clé signe les cookies de session : qui la possède peut forger une
# session administrateur. Elle ne doit jamais être écrite dans ce fichier.
_secret = os.environ.get("INFIRMERIE_SECRET_KEY", "").strip()
if not _secret:
    if _bool_environ("INFIRMERIE_DEBUG", True):
        # Développement : une clé éphémère suffit. Les sessions sont
        # réinitialisées à chaque redémarrage, ce qui est sans conséquence ici.
        _secret = "django-insecure-dev-" + secrets.token_urlsafe(32)
    else:
        raise RuntimeError(
            "INFIRMERIE_SECRET_KEY est obligatoire quand le mode debug est desactive.\n"
            "Generez-la avec : python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
SECRET_KEY = _secret

# --- DEBUG --------------------------------------------------------------
# En production, une trace d'erreur affiche le contexte interne et les
# variables : c'est une fuite d'information.
# Par défaut on est en développement (DEBUG actif) tant que la variable
# n'a pas été posée explicitement. Un poste qui démarre sans configuration
# doit rester utilisable.
DEBUG = _bool_environ("INFIRMERIE_DEBUG", True)

# Accès local uniquement. L'accès distant passe par le VPN, pas par une IP
# publique : il n'y a donc rien à ajouter ici par défaut.
_hosts = os.environ.get("INFIRMERIE_ALLOWED_HOSTS", "").strip()
ALLOWED_HOSTS = (
    [h.strip() for h in _hosts.split(",") if h.strip()]
    if _hosts
    else ["127.0.0.1", "localhost", "testserver"]
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dossier",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "dossier.middleware.JournalAccesMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "conf.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "conf.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Passage à PostgreSQL pour la mise en production.
# Prérequis : pip install "psycopg[binary]", puis créer la base et l'utilisateur.
#
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": "infirmerie",
#         "USER": "infirmerie",
#         "PASSWORD": "a-definir",
#         "HOST": "127.0.0.1",
#         "PORT": "5432",
#     }
# }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Poste d'infirmerie partagé : la session expire en fin de journée.
SESSION_COOKIE_AGE = 60 * 60 * 10
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

LOGIN_URL = "connexion"
LOGIN_REDIRECT_URL = "accueil"
LOGOUT_REDIRECT_URL = "connexion"

# --- Journal d'accès ----------------------------------------------------
# Voir dossier/audit.py. Désactivable sans toucher au code.
JOURNAL_ACTIF = _bool_environ("INFIRMERIE_JOURNAL", True)

# Conservation minimale du journal, en jours. Passé ce délai, la purge est
# faite a la main : une purge automatique risquerait de supprimer la trace
# d'un incident encore à instruire.
JOURNAL_CONSERVATION_JOURS = int(
    os.environ.get("INFIRMERIE_JOURNAL_JOURS", "3650") or 3650
)

# Si l'application est servie derrière un proxy (déploiement inverse),
# la protection CSRF exige que cet en-tête soit déclaré fiable.
# Laissé False en local, où aucun proxy n'est present.
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("INFIRMERIE_CSRF_TRUSTED", "").split(",")
    if o.strip()
]
