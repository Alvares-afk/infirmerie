@echo off
REM ==========================================================
REM  Infirmerie - DEMONSTRATION (patients fictifs)
REM  Base separee, aucun vrai dossier patient ici.
REM ==========================================================
cd /d "%~dp0"

echo.
echo   ================================================
echo    INFIRMERIE - DEMONSTRATION
echo   ================================================
echo.
echo   Cette instance contient uniquement des patients
echo   FICTIFS. Pour vos vrais dossiers, utilisez
echo   demarrer_reel.bat
echo.

if not exist ".venv\Scripts\python.exe" (
  echo   Environnement absent. Creation en cours...
  python -m venv .venv
)

set INFIRMERIE_BASE=

".venv\Scripts\python.exe" manage.py migrate --noinput

echo.
echo   Application : http://127.0.0.1:8000
echo.
echo     soignant       : dr.benali
echo     secretariat    : secretariat
echo     administration : admin
echo.
echo   Mot de passe : celui defini a l'installation.
echo   Pour en definir un : manage.py renouveler_mots_de_passe
echo.
echo   Laissez cette fenetre ouverte. Ctrl+C pour arreter.
echo.

".venv\Scripts\python.exe" manage.py runserver 8000
pause
