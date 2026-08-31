@echo off
REM ============================================================================
REM  aplicar.bat  -  swap seguro del auto-update (Muebles y Sillones)
REM  Lo copia el panel a %LOCALAPPDATA%\PanelMyS_update\ y lo lanza DETACHED
REM  pasando el PID del panel viejo como %1. Reemplaza la carpeta del programa
REM  por rename/move (casi-atomico), restaura los archivos per-maquina y
REM  hace ROLLBACK si algo sale mal (la instalacion SIEMPRE queda usable).
REM  Hooks de test:  PMYS_ROOT (raiz alternativa)  PMYS_NORUN (no relanzar exe)
REM ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
set "PID=%~1"
if defined PMYS_ROOT (set "ROOT=%PMYS_ROOT%") else (set "ROOT=%LOCALAPPDATA%")
set "INSTALL=%ROOT%\PanelMyS"
set "NEW=%ROOT%\PanelMyS_update\new"
set "OLD=%ROOT%\PanelMyS_old"
set "UPD=%ROOT%\PanelMyS_update"
set "FAILED=%ROOT%\PanelMyS_failed"
set "LOG=%UPD%\aplicar.log"
cd /d "%SystemRoot%"

if not exist "%UPD%" mkdir "%UPD%"
if exist "%UPD%\lock" exit /b 1
type nul > "%UPD%\lock"
echo [%date% %time%] start pid=%PID% >> "%LOG%"

REM 1) esperar el cierre TOTAL del panel viejo (por PID, no por nombre) ~60s
set /a n=0
:wait
tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if not errorlevel 1 (
  set /a n+=1
  if !n! gtr 60 ( echo timeout esperando PID >> "%LOG%" & goto fail )
  ping -n 2 127.0.0.1 >nul
  goto wait
)

REM 2) precondiciones: new completo (exe + marker de extraccion terminada)
if not exist "%NEW%\PanelMyS.exe" ( echo new sin exe >> "%LOG%" & goto fail )
if not exist "%NEW%\update_ok.marker" ( echo new sin marker >> "%LOG%" & goto fail )

REM 3) limpiar restos de updates anteriores (rollback viejo y fallidos)
if exist "%OLD%" rmdir /s /q "%OLD%"
if exist "%FAILED%" rmdir /s /q "%FAILED%"

REM 4) install -> old  (retry para absorber locks residuales de handles/AV)
set /a n=0
:mv1
move "%INSTALL%" "%OLD%" >> "%LOG%" 2>&1
if errorlevel 1 (
  set /a n+=1
  if !n! gtr 20 ( echo no pude mover install a old >> "%LOG%" & goto fail )
  ping -n 2 127.0.0.1 >nul
  goto mv1
)

REM 5) new -> install  (retry; si no entra, ROLLBACK)
set /a n=0
:mv2
move "%NEW%" "%INSTALL%" >> "%LOG%" 2>&1
if errorlevel 1 (
  set /a n+=1
  if !n! gtr 20 ( echo no pude mover new a install >> "%LOG%" & goto rollback )
  ping -n 2 127.0.0.1 >nul
  goto mv2
)
if not exist "%INSTALL%\PanelMyS.exe" ( echo install sin exe tras swap >> "%LOG%" & goto rollback )

REM 6) restaurar archivos PER-MAQUINA desde OLD (el bundle NO los trae)
if exist "%OLD%\proyecto.txt" copy /y "%OLD%\proyecto.txt" "%INSTALL%\" >> "%LOG%" 2>&1
if exist "%OLD%\panel_config.json" copy /y "%OLD%\panel_config.json" "%INSTALL%\" >> "%LOG%" 2>&1
if exist "%OLD%\aprobaciones" robocopy "%OLD%\aprobaciones" "%INSTALL%\aprobaciones" /E /R:2 /W:1 /NFL /NDL /NJH /NJS >nul 2>&1

REM 7) verificar IDENTIDAD (o rollback): jamas quedar sin config tras el swap.
REM    Desde v27 la central TAMBIEN se auto-actualiza, asi que se acepta
REM    cualquier rol conocido (central o colaborador), no solo colaborador.
if not exist "%INSTALL%\panel_config.json" ( echo falta panel_config tras restaurar >> "%LOG%" & goto rollback )
findstr /i "colaborador central" "%INSTALL%\panel_config.json" >nul || ( echo config sin rol conocido >> "%LOG%" & goto rollback )
echo swap OK >> "%LOG%"
goto relaunch

:rollback
echo ROLLBACK >> "%LOG%"
if exist "%INSTALL%\PanelMyS.exe" (
  if exist "%FAILED%" rmdir /s /q "%FAILED%"
  move "%INSTALL%" "%FAILED%" >> "%LOG%" 2>&1
)
if not exist "%INSTALL%\PanelMyS.exe" (
  if exist "%OLD%\PanelMyS.exe" move "%OLD%" "%INSTALL%" >> "%LOG%" 2>&1
)
goto relaunch

:fail
echo FAIL_NOCHANGE (install intacto) >> "%LOG%"
goto relaunch

:relaunch
if not defined PMYS_NORUN if exist "%INSTALL%\PanelMyS.exe" start "" /d "%INSTALL%" "%INSTALL%\PanelMyS.exe"
del "%UPD%\lock" 2>nul
del /q "%UPD%\bundle.zip" 2>nul
if exist "%NEW%" rmdir /s /q "%NEW%" 2>nul
REM PanelMyS_old se CONSERVA para rollback; lo limpia el proximo update (paso 3)
(goto) 2>nul & del "%~f0"
