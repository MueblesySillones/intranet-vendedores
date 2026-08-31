' ============================================================================
'  PanelMyS_run.vbs  -  corre el launcher .bat OCULTO (sin ventana negra).
'  El acceso directo del Escritorio/Inicio apunta a ESTE archivo.
'  Vive en %LOCALAPPDATA%\PanelMyS_run\ (fuera de la carpeta que el update pisa).
' ============================================================================
Option Explicit
Dim sh, base, bat
Set sh = CreateObject("WScript.Shell")
base = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%")
bat = base & "\PanelMyS_run\PanelMyS_run.bat"
sh.Run Chr(34) & bat & Chr(34), 0, False
