@echo off
REM ==========================================================
REM  Infirmerie - VRAIS DOSSIERS PATIENTS
REM  Ce lanceur utilise la base de donnee des dossiers reels.
REM  La demonstration (patients fictifs) est dans une autre base.
REM ==========================================================
cd /d "%~dp0"

echo.
echo   ================================================
echo    INFIRMERIE - DOSSIERS REELS
echo   ================================================
echo.
echo   Cette instance contient de VRAIS dossiers patients.
echo   Les patients fictifs de demonstration sont dans
echo   une base separee (demarrer_demo.bat).
echo.
echo   Sauvegarde : sauvegarder_reel.bat
echo.

if not exist ".venv\Scripts\python.exe" (
  echo   Environnement absent. Creation en cours...
  python -m venv .venv
)

set INFIRMERIE_BASE=reelle

".venv\Scripts\python.exe" manage.py migrate --noinput

echo.
echo   Application : http://127.0.0.1:8000
echo.
echo     soignant       : dr.benali      / Infirmerie2026!
echo     secretariat    : secretariat    / Infirmerie2026!
echo     administration : admin         / Infirmerie2026!
echo.
echo   Laissez cette fenetre ouverte. Ctrl+C pour arreter.
echo.

".venv\Scripts\python.exe" manage.py runserver 8000
pause
