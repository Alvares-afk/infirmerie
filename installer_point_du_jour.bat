@echo off
chcp 65001 >nul
title Installation du point du jour
cd /d "%~dp0"

rem ==========================================================
rem  Cree une tache Windows qui produit le PDF du point du jour
rem  chaque matin, dans sorties\.
rem
rem  Heure par defaut : 07h30, pas 6h : un poste eteint a 6h ne
rem  produit rien, et Windows ne rattrape pas une execution
rem  manquee. 7h30 correspond a l'ouverture du cabinet.
rem  Heure passable en premier argument : installer_point_du_jour.bat 08:00
rem ==========================================================

set "HEURE=%~1"
if "%HEURE%"=="" set "HEURE=07:30"

set "NOM=Infirmerie - point du jour"

echo.
echo   Creation de la tache planifiee...
echo   Nom   : %NOM%
echo   Quand : chaque jour a %HEURE%
echo   Quoi  : %~dp0point_du_jour_local.bat
echo.

schtasks /Create /TN "%NOM%" /TR "\"%~dp0point_du_jour_local.bat\"" /SC DAILY /ST %HEURE% /F
if errorlevel 1 goto :echec

echo.
echo   Tache creee. Verification :
echo.
schtasks /Query /TN "%NOM%" /FO LIST | findstr /i "Nom NomTache TaskName Prochaine Next"
echo.
echo   Le PDF du jour est ecrit dans : sorties\
echo   Journal d'execution           : sorties\journal_point_du_jour.log
echo.
echo   Si le poste est eteint a cette heure-la, la tache ne tourne
echo   pas. Le PDF peut toujours etre produit a la main en
echo   double-cliquant sur point_du_jour_local.bat.
echo.
pause
exit /b 0

:echec
echo.
echo   La creation a echoue.
echo   Essayez par clic droit puis "Executer en tant qu'administrateur".
echo.
pause
exit /b 1
