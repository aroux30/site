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
rem Docker bin is included: the data stores (postgres/redis/elasticsearch)
rem run as compose containers since the native services were retired.
set "PATH=%ProgramFiles%\nodejs;%ProgramFiles%\Python314;%ProgramFiles%\Python314\Scripts;%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"

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

echo [1/5] Cleaning ports 3000 and 8000...
call :kill_port 3000
call :kill_port 8000
%SystemRoot%\System32\timeout.exe /t 2 /nobreak >nul
echo       Ports are free.

echo [2/5] Starting data stores in Docker ^(postgres, redis, elasticsearch^)...
call :ensure_docker
if errorlevel 1 (
    echo       [FAIL] Docker engine is not available.
    echo              Start Docker Desktop manually, then run this launcher again.
    goto fail
)
pushd "%ROOT%"
docker compose up -d postgres redis elasticsearch
if errorlevel 1 (
    popd
    echo       [FAIL] docker compose up failed - see the error above.
    goto fail
)
popd
call :wait_container_healthy ecommerce-postgres 100
if errorlevel 1 (
    echo       [FAIL] postgres container did not become healthy in time.
    goto fail
)
echo       postgres      :5432 OK
call :wait_container_healthy ecommerce-redis 50
if errorlevel 1 (
    echo       [WARN] redis container still starting - backend may error until it is up.
) else (
    echo       redis         :6379 OK
)
call :wait_container_healthy ecommerce-elasticsearch 100
if errorlevel 1 (
    echo       [WARN] elasticsearch still starting - search uses the SQL fallback until it is up.
) else (
    echo       elasticsearch :9200 OK
)

echo [3/5] Database migrations...
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
if exist "%ROOT%\backend\scripts\seed_pages.py" (
    "%PY%" scripts\seed_pages.py
    if errorlevel 1 (
        echo       [WARN] seed_pages reported an error. Continuing.
    ) else (
        echo       CMS pages bootstrap finished.
    )
) else (
    echo       [SKIP] scripts\seed_pages.py not present.
)

echo [4/5] Starting backend and frontend in new windows...
start "Backend :8000" cmd /k call "%~f0" backend
%SystemRoot%\System32\timeout.exe /t 4 /nobreak >nul
start "Frontend :3000" cmd /k call "%~f0" frontend

echo [5/5] Waiting for health checks...
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
%SystemRoot%\System32\timeout.exe /t 1 /nobreak >nul
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
    %SystemRoot%\System32\timeout.exe /t 8 /nobreak >nul
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

:ensure_docker
rem Ensure the Docker engine answers; launch Docker Desktop when needed.
where docker >nul 2>&1
if not errorlevel 1 goto docker_engine_check
if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
    goto docker_engine_check
)
echo       [FAIL] docker.exe not found - install Docker Desktop first.
exit /b 1

:docker_engine_check
docker info >nul 2>&1
if not errorlevel 1 exit /b 0
echo       Docker Desktop is not running - starting it ^(can take 1-2 minutes^)...
start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set /a DOCKER_TRIES=0

:docker_wait_loop
%SystemRoot%\System32\timeout.exe /t 5 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 exit /b 0
set /a DOCKER_TRIES+=1
if %DOCKER_TRIES% GEQ 36 (
    echo       Timed out after ~3 minutes waiting for the Docker engine.
    exit /b 1
)
echo       ...waiting for Docker engine ^(%DOCKER_TRIES%^)
goto docker_wait_loop

:wait_container_healthy
rem %1 = container name, %2 = tries (one per 3 seconds)
set "HC_STATUS="
set /a HC_TRIES=0

:hc_loop
for /f "usebackq delims=" %%H in (`docker inspect --format "{{.State.Health.Status}}" %~1 2^>nul`) do set "HC_STATUS=%%H"
if "%HC_STATUS%"=="healthy" exit /b 0
set /a HC_TRIES+=1
if %HC_TRIES% GEQ %~2 exit /b 1
%SystemRoot%\System32\timeout.exe /t 3 /nobreak >nul
goto hc_loop

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
