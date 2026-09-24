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
REM El lock evita dos updates a la vez. Pero si la maquina se apago en medio de
REM uno (o el antivirus mato el cmd), el archivo queda para siempre y a partir
REM de ahi CADA intento salia por aca: el panel ya se habia matado solo para
REM dejar reemplazar los archivos, asi que la persona se quedaba sin panel
REM abierto, sin update y sin ningun mensaje. En silencio, para siempre.
REM Ahora un lock de mas de 30 minutos se considera basura de un intento
REM muerto: se borra y se sigue. Y si el lock es reciente (hay otro update de
REM verdad corriendo) igual se relanza el panel, que es lo que la persona
REM necesita ver.
if exist "%UPD%\lock" (
  set "LOCKVIEJO="
  for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try{if(((Get-Date)-(Get-Item '%UPD%\lock').LastWriteTime).TotalMinutes -gt 30){'si'}}catch{'si'}" 2^>nul`) do set "LOCKVIEJO=%%A"
  if defined LOCKVIEJO (
    echo lock viejo de un intento muerto: lo borro y sigo >> "%LOG%"
    del /q "%UPD%\lock" 2>nul
  ) else (
    echo lock fresco: ya hay un update corriendo, relanzo el panel y salgo >> "%LOG%"
    if not defined PMYS_NORUN if exist "%INSTALL%\PanelMyS.exe" start "" /d "%INSTALL%" "%INSTALL%\PanelMyS.exe"
    exit /b 1
  )
)
type nul > "%UPD%\lock"
echo [%date% %time%] start pid=%PID% >> "%LOG%"

REM 1) esperar el cierre TOTAL del panel viejo (por PID, no por nombre) ~60s
REM    Si no se cierra solo, se lo cierra a la fuerza. Antes se hacia `goto
REM    fail` y listo: esa maquina no se actualizaba NUNCA MAS, en silencio,
REM    porque el panel viejo seguia ahi y cada intento terminaba igual. Un
REM    panel colgado no puede ser una condena permanente: ya guardo todo lo
REM    suyo antes de pedir la actualizacion.
set /a n=0
:wait
tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if not errorlevel 1 (
  set /a n+=1
  if !n! gtr 60 (
    echo no se cerro solo en 60s: lo cierro a la fuerza >> "%LOG%"
    taskkill /F /PID %PID% >> "%LOG%" 2>&1
    ping -n 4 127.0.0.1 >nul
    tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
    if not errorlevel 1 ( echo no pude cerrar el panel viejo >> "%LOG%" & goto fail )
    echo cerrado a la fuerza, sigo >> "%LOG%"
    goto listo
  )
  ping -n 2 127.0.0.1 >nul
  goto wait
)
:listo

REM 2) precondiciones: new completo (exe + marker de extraccion terminada)
if not exist "%NEW%\PanelMyS.exe" ( echo new sin exe >> "%LOG%" & goto fail )
if not exist "%NEW%\update_ok.marker" ( echo new sin marker >> "%LOG%" & goto fail )

REM 3) limpiar restos de updates anteriores (rollback viejo y fallidos)
if exist "%OLD%" rmdir /s /q "%OLD%"
if exist "%FAILED%" rmdir /s /q "%FAILED%"
REM barrer los old con sufijo que hayan quedado de updates anteriores (ver 3b)
for /d %%D in ("%ROOT%\PanelMyS_old_*") do rmdir /s /q "%%D" 2>nul

REM 3b) EL PASO QUE FALTABA.
REM     El rmdir de arriba falla mas seguido de lo que parece: al cerrar el
REM     panel, Windows sigue teniendo tomado un rato el runtime de C++
REM     (VCRUNTIME140.dll da "acceso denegado"). Si %OLD% sobrevive, el `move`
REM     del paso 4 NO renombra: mete la instalacion ADENTRO, como
REM     %OLD%\PanelMyS. De ahi no cierra nada -> el paso 6 no encuentra los
REM     archivos per-maquina, se va a ROLLBACK, y el rollback tampoco ve el exe
REM     porque quedo un nivel mas abajo: LA MAQUINA SE QUEDA SIN PROGRAMA.
REM     Paso de verdad en la central el 5-sep-2026 (v36 -> v37).
REM     No alcanza con frenar: si el DLL queda tomado siempre, la maquina
REM     nunca mas se actualizaria, en silencio. Se usa un nombre libre y el
REM     update sigue su curso; la carpeta trabada la barre el proximo update.
if exist "%OLD%" (
  echo old ocupado, uso uno con sufijo >> "%LOG%"
  set "OLD=%ROOT%\PanelMyS_old_%RANDOM%%RANDOM%"
)
if exist "!OLD!" ( echo no consigo una carpeta libre para el old >> "%LOG%" & goto fail )

REM 4) install -> old  (retry para absorber locks residuales de handles/AV)
set /a n=0
:mv1
move "%INSTALL%" "%OLD%" >> "%LOG%" 2>&1
if errorlevel 1 (
  set /a n+=1
  if !n! gtr 20 ( echo no pude mover install a old: copio encima >> "%LOG%" & goto copiar )
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

:copiar
REM 23-sep-2026. EL CIRCULO "actualizo y me vuelve a pedir actualizar":
REM cuando algo tiene tomada la carpeta del programa (antivirus, el navegador,
REM otro programa parado adentro), Windows no deja MOVERLA. Antes se hacia
REM `goto fail`: se reabria la version VIEJA sin decir nada, el panel veia que
REM seguia habiendo una version nueva y pedia actualizar otra vez, para siempre.
REM Copiar ENCIMA si se puede aunque la carpeta este tomada (es lo mismo que
REM hace ACTUALIZAR PANEL MyS.bat). Antes, un respaldo; si la copia falla, se
REM restaura el respaldo y recien ahi se da por fallido.
robocopy "%INSTALL%" "%OLD%" /MIR /R:2 /W:1 /NFL /NDL /NJH /NJS /NP >nul 2>&1
if errorlevel 8 ( echo no pude respaldar para copiar encima >> "%LOG%" & goto fail )
robocopy "%NEW%" "%INSTALL%" /MIR /XF panel_config.json proyecto.txt identity.json update_ok.marker /XD aprobaciones /R:15 /W:2 /NFL /NDL /NJH /NJS /NP >> "%LOG%" 2>&1
if errorlevel 8 (
  echo la copia encima fallo: restauro el respaldo >> "%LOG%"
  robocopy "%OLD%" "%INSTALL%" /MIR /R:5 /W:2 /NFL /NDL /NJH /NJS /NP >nul 2>&1
  goto fail
)
if not exist "%INSTALL%\PanelMyS.exe" ( echo install sin exe tras copiar >> "%LOG%" & robocopy "%OLD%" "%INSTALL%" /MIR /R:5 /W:2 /NFL /NDL /NJH /NJS /NP >nul 2>&1 & goto fail )
echo swap OK (copiado encima) >> "%LOG%"
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
REM Red de seguridad para las maquinas que YA quedaron con la copia anidada
REM por el bug de arriba: sin esto el rollback no encuentra el programa y la
REM instalacion se queda vacia. Salir de aca sin panel no es una opcion.
if not exist "%INSTALL%\PanelMyS.exe" (
  if exist "%OLD%\PanelMyS\PanelMyS.exe" move "%OLD%\PanelMyS" "%INSTALL%" >> "%LOG%" 2>&1
)
if not exist "%INSTALL%\PanelMyS.exe" echo ROLLBACK INCOMPLETO: no encontre el programa >> "%LOG%"
goto relaunch

:fail
echo FAIL_NOCHANGE (install intacto) >> "%LOG%"
goto relaunch

:relaunch
REM Se relanza con el directorio de trabajo FUERA de la instalacion. Con
REM /d "%INSTALL%" el panel quedaba parado adentro de su propia carpeta y el
REM navegador que abre despues heredaba ese directorio; como el navegador
REM sobrevive al panel, la carpeta quedaba tomada y el update siguiente no
REM podia reemplazarla (FAIL_NOCHANGE, "utilizado por otro proceso").
if not defined PMYS_NORUN if exist "%INSTALL%\PanelMyS.exe" start "" /d "%SystemRoot%" "%INSTALL%\PanelMyS.exe"
del "%UPD%\lock" 2>nul
del /q "%UPD%\bundle.zip" 2>nul
if exist "%NEW%" rmdir /s /q "%NEW%" 2>nul
REM PanelMyS_old se CONSERVA para rollback; lo limpia el proximo update (paso 3)
(goto) 2>nul & del "%~f0"
