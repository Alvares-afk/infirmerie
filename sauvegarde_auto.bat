@echo off
chcp 65001 >nul
rem ==========================================================
rem  Sauvegarde automatique des vrais dossiers patients.
rem  Appelee par la tache planifiee Windows, pas par un humain :
rem  aucune pause, tout est ecrit dans un journal.
rem ==========================================================
cd /d "%~dp0"

if not exist "sauvegardes" mkdir "sauvegardes"
set "JOURNAL=sauvegardes\journal_sauvegarde.log"

".venv\Scripts\python.exe" sauvegarder.py --reel >> "%JOURNAL%" 2>&1

if errorlevel 1 (
    echo %DATE% %TIME%  ECHEC de la sauvegarde>> "%JOURNAL%"
    exit /b 1
)

echo %DATE% %TIME%  Sauvegarde effectuee>> "%JOURNAL%"
exit /b 0
