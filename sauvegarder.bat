@echo off
REM Sauvegarde de la base de l'infirmerie
cd /d "%~dp0"
python sauvegarder.py
echo.
pause
