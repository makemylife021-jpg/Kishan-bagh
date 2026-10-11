@echo off
title Kishan Bagh Call
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Install the LTS version from https://nodejs.org and try again.
  pause
  exit /b
)
if not exist node_modules (
  echo Installing, please wait. This needs internet only the first time...
  call npm install
)
echo.
call npm start
pause
