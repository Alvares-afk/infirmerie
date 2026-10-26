@echo off
chcp 65001 >nul
title Installation de l'infirmerie
cd /d "%~dp0"

rem ------------------------------------------------------------------
rem  Point d'entree de l'installation : un double-clic sur ce fichier.
rem  Il ne fait qu'une chose : trouver Python, puis lui passer la main.
rem  Tout le reste est dans installer.py, plus lisible qu'un script .bat.
rem ------------------------------------------------------------------

set "PY="

py -3 --version >nul 2>nul
if not errorlevel 1 set "PY=py -3"

if not defined PY (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY=python"
)

if not defined PY goto :absent

echo.
echo Python trouve. Lancement de l'installation...
echo.
%PY% installer.py
goto :fin

:absent
echo.
echo ==============================================================
echo   PYTHON N'EST PAS INSTALLE SUR CE POSTE
echo ==============================================================
echo.
echo   L'application en a besoin pour fonctionner.
echo.
echo   1. La page de telechargement va s'ouvrir.
echo   2. Cliquez sur le gros bouton jaune "Download Python".
echo   3. Lancez le fichier telecharge.
echo   4. IMPORTANT : cochez la case
echo         "Add python.exe to PATH"
echo      en bas de la premiere fenetre, avant de cliquer sur
echo      "Install Now".
echo   5. Quand c'est fini, revenez ici et double-cliquez de nouveau
echo      sur installer.bat.
echo.
start "" "https://www.python.org/downloads/"
echo.
pause
exit /b 1

:fin
echo.
pause
