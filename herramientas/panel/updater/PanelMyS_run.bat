@echo off
REM ============================================================================
REM  PanelMyS_run.bat  -  launcher ESTABLE del panel (Muebles y Sillones)
REM  El acceso directo apunta ACA (via el .vbs), NO al exe. Vive fuera de la
REM  carpeta que el update reemplaza, asi que nunca se pisa. Auto-repara si un
REM  corte de luz dejo el swap a medias: si falta la instalacion, restaura la
REM  version vieja (o completa el swap) y recien ahi lanza el panel.
REM  Hooks de test:  PMYS_ROOT (raiz alternativa)  PMYS_NORUN (no relanzar exe)
REM ============================================================================
setlocal EnableExtensions
if defined PMYS_ROOT (set "ROOT=%PMYS_ROOT%") else (set "ROOT=%LOCALAPPDATA%")
set "INSTALL=%ROOT%\PanelMyS"
set "OLD=%ROOT%\PanelMyS_old"
set "NEW=%ROOT%\PanelMyS_update\new"
cd /d "%SystemRoot%"

REM auto-reparacion: preferimos la version vieja (tiene la config), si no el new completo
if not exist "%INSTALL%\PanelMyS.exe" (
  if exist "%OLD%\PanelMyS.exe" move "%OLD%" "%INSTALL%" >nul 2>&1
)
if not exist "%INSTALL%\PanelMyS.exe" (
  if exist "%NEW%\update_ok.marker" move "%NEW%" "%INSTALL%" >nul 2>&1
)

REM El directorio de trabajo va FUERA de la instalacion. Con /d "%INSTALL%" el
REM panel quedaba parado adentro de su propia carpeta, y el navegador que abre
REM despues heredaba ese directorio. El navegador sobrevive al panel, asi que
REM la carpeta quedaba tomada por Windows y el update siguiente no podia
REM reemplazarla: "utilizado por otro proceso" -> FAIL_NOCHANGE. Solo pasaba
REM cuando el navegador NO estaba abierto de antes, por eso parecia al azar.
if not defined PMYS_NORUN if exist "%INSTALL%\PanelMyS.exe" start "" /d "%SystemRoot%" "%INSTALL%\PanelMyS.exe"
endlocal
