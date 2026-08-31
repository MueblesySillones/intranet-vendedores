; Instalador AUTOMATICO de SUCURSAL (colaborador) - Muebles y Sillones
; Un solo .exe que hace TODO de un doble clic:
;   1) instala Tailscale (silencioso)
;   2) se conecta a la red privada con la clave de la central (authkey)
;   3) deja la carpeta del proyecto en Documentos
;   4) instala el panel como COLABORADOR y lo configura apuntando a la central
;
; Compilar (los 2 valores se pasan por linea de comando en el build final):
;   ISCC.exe /DCentralIP=100.x.x.x /DAuthKey=tskey-xxxx SucursalAuto.iss
; Si no se pasan, quedan placeholders (compila igual, pero no conecta).

#ifndef CentralIP
  #define CentralIP "PONER_IP_TAILSCALE_DE_LA_CENTRAL"
#endif
#ifndef AuthKey
  #define AuthKey "PONER_AUTHKEY_DE_TAILSCALE"
#endif

#ifndef PubKey
  #define PubKey ""
#endif
#define AppName   "Panel Sucursal - Muebles y Sillones"
#define AppShort  "PanelMyS"
#define AppExe    "PanelMyS.exe"
#define SrcDir    "dist\PanelMyS"
#define ProyDir   "paquete\Proyecto MyS"
#define TsMsi     "paquete\tailscale.msi"

[Setup]
AppId={{C9F1D3B2-77A4-4E10-9C55-2B7E6D0A9F31}
AppName={#AppName}
AppVersion=1.17.0
AppPublisher=Muebles y Sillones
DefaultDirName={localappdata}\{#AppShort}
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
DisableWelcomePage=no
PrivilegesRequired=admin
OutputDir=instalador
OutputBaseFilename=Instalar Sucursal (automatico)
SetupIconFile=panel.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UsedUserAreasWarning=no
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Excludes: "proyecto.txt,panel_config.json,aprobaciones\*"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#ProyDir}\*"; DestDir: "{userdocs}\Proyecto MyS"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#TsMsi}"; DestDir: "{tmp}"; DestName: "tailscale.msi"; Flags: deleteafterinstall
; Launcher ESTABLE del auto-update: vive FUERA de {app} (no se pisa cuando un update reemplaza la carpeta)
Source: "updater\PanelMyS_run.vbs"; DestDir: "{localappdata}\PanelMyS_run"; Flags: ignoreversion
Source: "updater\PanelMyS_run.bat"; DestDir: "{localappdata}\PanelMyS_run"; Flags: ignoreversion
Source: "panel.ico"; DestDir: "{localappdata}\PanelMyS_run"; Flags: ignoreversion

[Icons]
; los accesos directos apuntan al LAUNCHER (que auto-repara ante corte de luz y despues abre el panel)
Name: "{autoprograms}\{#AppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{localappdata}\PanelMyS_run\PanelMyS_run.vbs"""; IconFilename: "{localappdata}\PanelMyS_run\panel.ico"; WorkingDir: "{localappdata}\PanelMyS_run"
Name: "{autodesktop}\Panel Muebles y Sillones"; Filename: "{sys}\wscript.exe"; Parameters: """{localappdata}\PanelMyS_run\PanelMyS_run.vbs"""; IconFilename: "{localappdata}\PanelMyS_run\panel.ico"; WorkingDir: "{localappdata}\PanelMyS_run"

[Run]
; 1) instalar Tailscale (silencioso)
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\tailscale.msi"" /quiet /norestart"; StatusMsg: "Instalando la conexion segura (Tailscale)..."; Flags: waituntilterminated
; 2) esperar a que arranque el servicio de Tailscale
Filename: "{cmd}"; Parameters: "/c timeout /t 8 /nobreak"; Flags: runhidden waituntilterminated
; 3) conectarse a la red de la central con la clave (no pide login)
Filename: "{commonpf64}\Tailscale\tailscale.exe"; Parameters: "up --authkey={#AuthKey} --unattended --accept-routes --hostname={code:GetHost}"; StatusMsg: "Conectando con la central..."; Flags: runhidden waituntilterminated
; 4) abrir el panel al terminar (via el launcher)
Filename: "{sys}\wscript.exe"; Parameters: """{localappdata}\PanelMyS_run\PanelMyS_run.vbs"""; Description: "Abrir el panel ahora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\panel_config.json"
Type: files; Name: "{app}\proyecto.txt"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_run"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_update"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_old"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_state"

[Code]
function GetHost(Param: String): String;
var s: String; i: Integer; c: Char;
begin
  { hostname para Tailscale: sucursal-<nombrepc>, solo letras/numeros/guion }
  s := '';
  for i := 1 to Length(GetComputerNameString) do
  begin
    c := GetComputerNameString[i];
    if ((c >= 'a') and (c <= 'z')) or ((c >= 'A') and (c <= 'Z')) or
       ((c >= '0') and (c <= '9')) then s := s + c
    else s := s + '-';
  end;
  Result := 'sucursal-' + s;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var cfg, proy: String;
begin
  if CurStep = ssPostInstall then
  begin
    { la carpeta del proyecto quedo en Documentos\Proyecto MyS }
    proy := ExpandConstant('{userdocs}\Proyecto MyS');
    SaveStringToFile(ExpandConstant('{app}\proyecto.txt'), proy, False);

    { configuracion del panel: COLABORADOR apuntando a la central por Tailscale }
    cfg := '{' + #13#10 +
           '  "rol": "colaborador",' + #13#10 +
           '  "usuario": "' + GetComputerNameString + '",' + #13#10 +
           '  "central_url": "http://{#CentralIP}:8125",' + #13#10 +
           { la clave de publicacion viaja en el instalador A PEDIDO DEL DUEnO:
             cero friccion para el equipo. Quien tenga este exe puede publicar
             al sitio; si eso preocupa algun dia, se rota la clave "equipo" en
             el cerebro y se recompila. Vacia => el panel la pide como antes. }
           '  "publish_token": "{#PubKey}",' + #13#10 +
           '  "receptor_port": 8125' + #13#10 +
           '}' + #13#10;
    SaveStringToFile(ExpandConstant('{app}\panel_config.json'), cfg, False);
  end;
end;
