@echo off
REM ==========================================================
REM  Infirmerie - Enregistrer le nom simple "infirmerie"
REM  A executer UNE SEULE FOIS. Windows demandera l'autorisation
REM  administrateur : repondez Oui.
REM ==========================================================
cd /d "%~dp0"

set ACTION=ajouter
if /i "%~1"=="retirer" set ACTION=retirer

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo   Autorisation administrateur necessaire...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%ACTION%' -Verb RunAs"
  exit /b
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0nom.ps1" -action %ACTION%

if /i "%ACTION%"=="ajouter" (
  echo.
  echo   Terminé. Relancez demarrer_reel.bat : l'application
  echo   s'ouvrira sur http://infirmerie
) else (
  echo.
  echo   Le nom simple a ete retire. L'application s'ouvrira
  echo   a nouveau sur http://127.0.0.1:8000
)
echo.
pause
