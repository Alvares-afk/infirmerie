@echo off
REM ==========================================================
REM  Infirmerie - lancement en local
REM  Double-clic sur ce fichier.
REM ==========================================================
cd /d "%~dp0"

echo.
echo   Demarrage de l'application Infirmerie...
echo.

if not exist ".venv\Scripts\python.exe" (
  echo   Environnement absent. Creation en cours, cela peut prendre 2 minutes.
  python -m venv .venv
)

".venv\Scripts\python.exe" -m pip install --quiet django
".venv\Scripts\python.exe" manage.py migrate --noinput

echo.
echo   Application disponible sur :  http://127.0.0.1:8000
echo.
echo   Comptes de demonstration :
echo     soignant    : dr.benali      / Infirmerie2026!
echo     secretariat : secretariat    / Infirmerie2026!
echo     administration : admin       / Infirmerie2026!
echo.
echo   Laissez cette fenetre ouverte. Ctrl+C pour arreter.
echo.

".venv\Scripts\python.exe" manage.py runserver 8000
pause
