@echo off
chcp 65001 >nul
title Installation de la sauvegarde automatique
cd /d "%~dp0"

rem ==========================================================
rem  Cree une tache Windows qui sauvegarde les dossiers reels
rem  chaque lundi a 12h30 (heure passable en premier argument).
rem
rem  Aucune pause dans la sauvegarde, aucun mot de passe stocke :
rem  la tache tourne sous votre session, uniquement quand vous
rem  etes connecte. C'est suffisant pour un poste de cabinet.
rem ==========================================================

set "HEURE=%~1"
if "%HEURE%"=="" set "HEURE=12:30"

set "NOM=Infirmerie - sauvegarde hebdomadaire"

echo.
echo   Creation de la tache planifiee...
echo   Nom    : %NOM%
echo   Quand  : chaque lundi a %HEURE%
echo   Quoi   : %~dp0sauvegarde_auto.bat
echo.

schtasks /Create /TN "%NOM%" /TR "\"%~dp0sauvegarde_auto.bat\"" /SC WEEKLY /D LUN /ST %HEURE% /F
if errorlevel 1 goto :echec

echo.
echo   Tache creee. Verification :
echo.
schtasks /Query /TN "%NOM%" /FO LIST | findstr /i "Nom NomTache TaskName Prochain Next Heure Start"
echo.
echo   Pour la supprimer plus tard :
echo     schtasks /Delete /TN "%NOM%" /F
echo.
echo   Pour verifier qu'elle a bien tourne :
echo     ouvrir sauvegardes\journal_sauvegarde.log
echo.
pause
exit /b 0

:echec
echo.
echo   La creation a echoue.
echo   Essayez en ouvrant ce fichier par clic droit puis
echo   "Executer en tant qu'administrateur".
echo.
pause
exit /b 1
