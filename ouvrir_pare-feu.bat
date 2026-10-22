@echo off
REM ==========================================================
REM  Infirmerie - OUVERTURE DU PARE-FEU (une seule fois)
REM  Autorise les tablettes et postes du reseau local a
REM  joindre l'application sur le port 8000.
REM
REM  Clic droit > "Executer en tant qu'administrateur".
REM  Regle limitee au sous-reseau local : pas d'ouverture
REM  vers Internet.
REM ==========================================================
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Ce fichier doit etre execute en tant qu'administrateur.
  echo   Clic droit sur le fichier ^> "Executer en tant qu'administrateur".
  echo.
  pause
  exit /b 1
)

echo.
echo   Ouverture du port 8000 pour le reseau local uniquement...
echo.

netsh advfirewall firewall delete rule name="Infirmerie 8000 (reseau local)" >nul 2>&1
netsh advfirewall firewall add rule ^
  name="Infirmerie 8000 (reseau local)" ^
  dir=in action=allow protocol=TCP localport=8000 ^
  remoteip=LocalSubnet profile=domain,private,public

echo.
echo   Regle installee. Verification :
echo.
netsh advfirewall firewall show rule name="Infirmerie 8000 (reseau local)"
echo.
pause
