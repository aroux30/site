@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Resolve project root from this file's location.
rem Works both when this .bat lives in Desktop\site  AND when a copy lives on Desktop.
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"

set "ROOT="
if exist "%HERE%\backend\app\main.py" (
    set "ROOT=%HERE%"
) else if exist "%HERE%\site\backend\app\main.py" (
    set "ROOT=%HERE%\site"
)

rem Match a normal terminal PATH when launched by double-click.
set "PATH=%ProgramFiles%\nodejs;%ProgramFiles%\Python314;%ProgramFiles%\Python314\Scripts;%PATH%"

set "PY="
if exist "%ProgramFiles%\Python314\python.exe" set "PY=%ProgramFiles%\Python314\python.exe"
if not defined PY set "PY=py"

if /I "%~1"=="backend" goto run_backend
if /I "%~1"=="frontend" goto run_frontend

title Iranian E-Commerce - Local Launcher
color 0A

echo ============================================================
echo   Iranian E-Commerce - Local Development Launcher
echo ============================================================
echo.
echo   Root: %ROOT%
echo.

if not defined ROOT (
    echo   [FAIL] Could not find backend\app\main.py next to this file
    echo          or in .\site. Put this launcher in Desktop\site or on Desktop.
    goto fail
)
if not exist "%ROOT%\backend\app\main.py" (
    echo   [FAIL] backend\app\main.py not found under %ROOT%
    goto fail
)
if not exist "%ROOT%\frontend\package.json" (
    echo   [FAIL] frontend\package.json not found under %ROOT%
    goto fail
)

if not exist "%ROOT%\backend\.env" (
    if exist "%ROOT%\backend\.env.example" (
        copy /Y "%ROOT%\backend\.env.example" "%ROOT%\backend\.env" >nul
        echo       Created backend\.env from .env.example
    )
)
if not exist "%ROOT%\frontend\.env" (
    if exist "%ROOT%\frontend\.env.example" (
        copy /Y "%ROOT%\frontend\.env.example" "%ROOT%\frontend\.env" >nul
        echo       Created frontend\.env from .env.example
    )
)

echo [1/4] Cleaning ports 3000 and 8000...
call :kill_port 3000
call :kill_port 8000
timeout /t 2 /nobreak >nul
echo       Ports are free.

echo [2/4] Checking PostgreSQL and Redis...
call :port_listening 5432
if errorlevel 1 (
    echo       [FAIL] PostgreSQL is not listening on 5432.
    echo       Start Postgres, then run this launcher again.
    goto fail
)
echo       PostgreSQL :5432 OK
call :port_listening 6379
if errorlevel 1 (
    echo       [FAIL] Redis is not listening on 6379.
    echo       Backend will not boot without Redis.
    goto fail
)
echo       Redis      :6379 OK

echo [3/4] Database migrations + admin bootstrap...
cd /d "%ROOT%\backend"
"%PY%" -m alembic upgrade head
if errorlevel 1 (
    echo       [WARN] alembic upgrade head failed. Continuing so you can still develop.
) else (
    echo       Migrations applied.
)
if exist "%ROOT%\backend\scripts\ensure_admin.py" (
    "%PY%" scripts\ensure_admin.py
    if errorlevel 1 (
        echo       [WARN] ensure_admin reported an error. Continuing.
    ) else (
        echo       Admin bootstrap finished.
    )
) else (
    echo       [SKIP] scripts\ensure_admin.py not present.
)

echo [4/4] Starting backend and frontend in new windows...
start "Backend :8000" cmd /k call "%~f0" backend
timeout /t 4 /nobreak >nul
start "Frontend :3000" cmd /k call "%~f0" frontend

echo       Waiting for health checks...
set "BACKEND_OK=0"
set "FRONTEND_OK=0"
set /a TRIES=0

:wait_health
curl.exe -s -o nul -w "%%{http_code}" http://127.0.0.1:8000/healthz 2>nul | findstr /C:"200" >nul
if not errorlevel 1 set "BACKEND_OK=1"
curl.exe -s -o nul -w "%%{http_code}" http://127.0.0.1:3000/ 2>nul | findstr /C:"200" >nul
if not errorlevel 1 set "FRONTEND_OK=1"
if "%BACKEND_OK%"=="1" if "%FRONTEND_OK%"=="1" goto health_done
set /a TRIES+=1
if %TRIES% GEQ 40 goto health_done
timeout /t 1 /nobreak >nul
goto wait_health

:health_done
echo.
echo ============================================================
if "%BACKEND_OK%"=="1" (echo   [OK]   Backend  http://localhost:8000) else (echo   [FAIL] Backend  - look at the Backend :8000 window)
if "%FRONTEND_OK%"=="1" (echo   [OK]   Frontend http://localhost:3000) else (echo   [WAIT] Frontend still compiling - wait and refresh)
echo.
echo   Admin:    http://localhost:3000/admin/dashboard
echo   API docs: http://localhost:8000/docs
call :print_admin_phone
echo   Password comes from ADMIN_PASSWORD in backend\.env
echo   (it is not printed here)
echo ============================================================
echo.

if "%FRONTEND_OK%"=="1" (
    start "" http://localhost:3000
) else if "%BACKEND_OK%"=="1" (
    echo   Browser will open in 8 seconds...
    timeout /t 8 /nobreak >nul
    start "" http://localhost:3000
)

echo   Close this window whenever you like - servers keep running.
echo   Close the Backend / Frontend windows to stop them.
pause
exit /b 0

:fail
echo.
echo Launcher stopped.
pause
exit /b 1

:run_backend
title Backend :8000
color 0B
if not defined ROOT (
    set "HERE=%~dp0"
    if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
    if exist "%HERE%\backend\app\main.py" set "ROOT=%HERE%"
    if not defined ROOT if exist "%HERE%\site\backend\app\main.py" set "ROOT=%HERE%\site"
)
cd /d "%ROOT%\backend"
echo ============================================
echo   Backend - FastAPI / uvicorn :8000
echo   %ROOT%\backend
echo ============================================
echo.
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
echo.
echo Backend process exited.
pause
exit /b

:run_frontend
title Frontend :3000
color 0D
if not defined ROOT (
    set "HERE=%~dp0"
    if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
    if exist "%HERE%\backend\app\main.py" set "ROOT=%HERE%"
    if not defined ROOT if exist "%HERE%\site\backend\app\main.py" set "ROOT=%HERE%\site"
)
cd /d "%ROOT%\frontend"
echo ============================================
echo   Frontend - Next.js :3000
echo   %ROOT%\frontend
echo ============================================
echo.
call npm run dev
echo.
echo Frontend process exited.
pause
exit /b

:kill_port
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /C:":%~1 " ^| findstr /C:"LISTENING"') do (
    if not "%%P"=="0" if not "%%P"=="" taskkill /F /PID %%P >nul 2>&1
)
exit /b 0

:port_listening
netstat -ano 2>nul | findstr /C:":%~1 " | findstr /C:"LISTENING" >nul
exit /b %ERRORLEVEL%

:print_admin_phone
set "ADMIN_PHONE="
if exist "%ROOT%\backend\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /C:"ADMIN_PHONE=" "%ROOT%\backend\.env"`) do set "ADMIN_PHONE=%%B"
)
if defined ADMIN_PHONE (
    echo   Login:   %ADMIN_PHONE%
) else (
    echo   Login:   set ADMIN_PHONE in backend\.env
)
exit /b 0
