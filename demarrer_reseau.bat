@echo off
REM ==========================================================
REM  Infirmerie - ACCES RESEAU LOCAL
REM  Ouvre l'application aux tablettes et postes du meme reseau.
REM  Le serveur n'ecoute que sur la carte reseau du poste.
REM ==========================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo   Environnement absent. Creation en cours...
  python -m venv .venv
)

".venv\Scripts\python.exe" manage.py migrate --noinput

".venv\Scripts\python.exe" demarrer_reseau.py
pause
