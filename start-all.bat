@echo off
chcp 65001 >nul
cd /d %~dp0
title MiaoSha Demo - Launcher

echo ============================================================
echo   MiaoSha Demo Launcher  (real Redis + MySQL + Node)
echo ============================================================
echo.

where node >nul 2>nul
if errorlevel 1 goto NONODE

rem ---- 1. Redis ----
netstat -ano | findstr ":6379" | findstr "LISTENING" >nul
if errorlevel 1 (
  start "Redis-6379" /MIN bin\redis\redis-server.exe bin\redis-demo.conf
  echo [1/3] Redis starting on 127.0.0.1:6379
) else (
  echo [1/3] Redis already running - skip
)

rem ---- 2. MySQL ----
if not exist "bin\mysql\data" (
  echo [2/3] First run: initializing MySQL data dir, about 10 seconds ...
  bin\mysql\bin\mysqld.exe --initialize-insecure --basedir=%cd%\bin\mysql --datadir=%cd%\bin\mysql\data
)
netstat -ano | findstr ":3306" | findstr "LISTENING" >nul
if errorlevel 1 (
  start "MySQL-3306" /MIN bin\mysql\bin\mysqld.exe --defaults-file=mysql-init.ini --console
  echo       MySQL starting on 127.0.0.1:3306
) else (
  echo [2/3] MySQL already running - skip
)

rem ---- 3. Web app ----
netstat -ano | findstr ":4000" | findstr "LISTENING" >nul
if errorlevel 1 (
  echo [3/3] Starting web app on http://localhost:4000 ...
  echo       waiting for Redis/MySQL to be ready, about 5 seconds ...
  timeout /t 5 >nul
  start "" http://localhost:4000/
  node server.js
  echo.
  echo [INFO] Web app exited. If it failed, please screenshot the message above.
) else (
  echo [3/3] Web app already running - opening browser
  start "" http://localhost:4000/
)

echo.
echo NOTE: closing this window does NOT stop Redis/MySQL.
echo       To stop everything, close the Redis-6379 and MySQL-3306 windows.
echo.
pause
exit /b 0

:NONODE
echo [ERROR] Node.js not found. Please install Node.js first.
echo         Download: https://nodejs.org/
echo.
pause
exit /b 1