@echo off
chcp 65001 >nul
rem ==========================================================
rem  Point du jour : produit le PDF du matin dans sorties\.
rem  Appelee par la tache planifiee, ou a la main.
rem  Aucun envoi : le fichier reste sur le poste.
rem ==========================================================
cd /d "%~dp0"

if not exist "sorties" mkdir "sorties"
set "JOURNAL=sorties\journal_point_du_jour.log"

".venv\Scripts\python.exe" manage.py point_du_jour --pdf --enregistrer >> "%JOURNAL%" 2>&1

if errorlevel 1 (
    echo %DATE% %TIME%  ECHEC de la generation>> "%JOURNAL%"
    exit /b 1
)

echo %DATE% %TIME%  Point du jour genere>> "%JOURNAL%"
exit /b 0
