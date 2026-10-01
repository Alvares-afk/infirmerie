@echo off
REM ==========================================================
REM  Sauvegarde des VRAIS DOSSIERS PATIENTS
REM  Les sauvegardes de demonstration sont dans un autre fichier.
REM ==========================================================
cd /d "%~dp0"
echo.
echo   Sauvegarde des dossiers patients reels.
echo.
python sauvegarder.py --reel
echo.
pause
