@echo off
REM ============================================================
REM  SODEXAM - Suivi transmissions
REM  Double-cliquez sur ce fichier pour installer et lancer.
REM  (Placez-le dans le meme dossier que serveur.py)
REM ============================================================
title Serveur SODEXAM - Suivi transmissions
cd /d "%~dp0"

echo ============================================================
echo   SODEXAM - Demarrage du serveur de suivi
echo ============================================================
echo.

REM --- 1) Reperer Python (py ou python) ---
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY ( where python >nul 2>nul && set "PY=python" )

if not defined PY (
  echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
  echo Installez-le depuis https://www.python.org/downloads/
  echo en cochant "Add Python to PATH", puis relancez ce fichier.
  echo.
  pause
  exit /b 1
)
echo Python detecte : %PY%
echo.

REM --- 2) Verifier que serveur.py est present ---
if not exist "serveur.py" (
  echo [ERREUR] Fichier serveur.py introuvable dans ce dossier :
  echo   %cd%
  echo Placez ce .bat dans le meme dossier que serveur.py et app.html.
  echo.
  pause
  exit /b 1
)

REM --- 3) Installer / mettre a jour les dependances ---
echo Installation des dependances (Flask)...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERREUR] L'installation des dependances a echoue.
  echo Verifiez votre connexion Internet puis relancez.
  echo.
  pause
  exit /b 1
)
echo.

REM --- 4) Ouvrir le navigateur automatiquement apres 4 s ---
REM    (PowerShell : methode fiable, sans probleme de guillemets)
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://localhost:5000/'"

REM --- 5) Lancer le serveur (laissez cette fenetre ouverte) ---
echo ============================================================
echo   Serveur en cours d'execution.
echo   Si le navigateur ne s'ouvre pas tout seul, ouvrez :
echo       http://localhost:5000/
echo.
echo   - Sur ce poste        : http://localhost:5000/
echo   - Depuis les stations : http://IP_DU_SERVEUR:5000/
echo     (commande "ipconfig" pour connaitre l'IP, ligne IPv4)
echo.
echo   NE FERMEZ PAS cette fenetre tant que l'application
echo   doit rester accessible. Fermez-la pour arreter le serveur.
echo ============================================================
echo.
%PY% serveur.py

echo.
echo Le serveur s'est arrete.
pause
