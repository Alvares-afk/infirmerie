@echo off
REM Sauvegarde de la base de DEMONSTRATION (patients fictifs)
REM Pour les vrais dossiers : sauvegarder_reel.bat
cd /d "%~dp0"
python sauvegarder.py
echo.
pause
