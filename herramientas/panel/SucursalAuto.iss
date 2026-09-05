; Instalador de SUCURSAL (colaborador) - Muebles y Sillones
; Un solo .exe que de un doble clic:
;   1) cierra el panel viejo si estaba abierto y BORRA la instalacion anterior
;      (con los restos de updates a medias), conservando la identidad
;   2) deja la carpeta del proyecto en Documentos
;   3) instala el panel limpio, como COLABORADOR, con la clave de publicacion
;
; Compilar:
;   ISCC.exe SucursalAuto.iss
;
; TAILSCALE: ya NO se instala. Se usaba para que la sucursal llegara a la
; central, pero desde que la publicacion va al cerebro de Cloudflare y las
; actualizaciones se bajan del sitio, todo pasa por internet comun y la central
; no hace falta. Ademas su clave se vencia cada 90 dias, y pedirla para cada
; rebuild era lo que dejaba a las sucursales atras con una version vieja.
; Si alguna vez hace falta de nuevo, se compila con:
;   ISCC.exe /DConTailscale=1 /DCentralIP=100.x.x.x /DAuthKey=tskey-xxx ...

#ifndef CentralIP
  #define CentralIP ""
#endif
#ifndef AuthKey
  #define AuthKey "PONER_AUTHKEY_DE_TAILSCALE"
#endif

; Clave de publicacion del equipo. Vive en clave-equipo.iss, que esta
; gitignoreado y NO viaja al repositorio.
; ⚠️ Esto FALTABA acá (PanelMyS.iss sí lo tenía): el instalador de sucursal se
; compilaba siempre con la clave vacía salvo que alguien se acordara de pasar
; /DPubKey, así que la sucursal tenía que pegarla a mano la primera vez que
; publicaba. Justo la fricción que este instalador venía a sacar.
; ORDEN IMPORTANTE: primero la linea de comandos (/DPubKey=...) y recien
; despues el archivo. Al reves, el archivo pisa el parametro y no se puede
; compilar un instalador con la clave de una sucursal puntual.
#ifndef PubKey
  #ifexist "clave-equipo.iss"
    #include "clave-equipo.iss"
  #endif
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
#ifdef ConTailscale
PrivilegesRequired=admin
#else
; el panel vive en {localappdata}: no hace falta el cartel de permisos de Windows
PrivilegesRequired=lowest
#endif
OutputDir=instalador
OutputBaseFilename=Instalar Sucursal
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
#ifdef ConTailscale
Source: "{#TsMsi}"; DestDir: "{tmp}"; DestName: "tailscale.msi"; Flags: deleteafterinstall
#endif
; Launcher ESTABLE del auto-update: vive FUERA de {app} (no se pisa cuando un update reemplaza la carpeta)
Source: "updater\PanelMyS_run.vbs"; DestDir: "{localappdata}\PanelMyS_run"; Flags: ignoreversion
Source: "updater\PanelMyS_run.bat"; DestDir: "{localappdata}\PanelMyS_run"; Flags: ignoreversion
Source: "panel.ico"; DestDir: "{localappdata}\PanelMyS_run"; Flags: ignoreversion

[Icons]
; los accesos directos apuntan al LAUNCHER (que auto-repara ante corte de luz y despues abre el panel)
Name: "{autoprograms}\{#AppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{localappdata}\PanelMyS_run\PanelMyS_run.vbs"""; IconFilename: "{localappdata}\PanelMyS_run\panel.ico"; WorkingDir: "{localappdata}\PanelMyS_run"
Name: "{autodesktop}\Panel Muebles y Sillones"; Filename: "{sys}\wscript.exe"; Parameters: """{localappdata}\PanelMyS_run\PanelMyS_run.vbs"""; IconFilename: "{localappdata}\PanelMyS_run\panel.ico"; WorkingDir: "{localappdata}\PanelMyS_run"

[Run]
#ifdef ConTailscale
; 1) instalar Tailscale (silencioso)
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\tailscale.msi"" /quiet /norestart"; StatusMsg: "Instalando la conexion segura (Tailscale)..."; Flags: waituntilterminated
; 2) esperar a que arranque el servicio de Tailscale
Filename: "{cmd}"; Parameters: "/c timeout /t 8 /nobreak"; Flags: runhidden waituntilterminated
; 3) conectarse a la red de la central con la clave (no pide login)
Filename: "{commonpf64}\Tailscale\tailscale.exe"; Parameters: "up --authkey={#AuthKey} --unattended --accept-routes --hostname={code:GetHost}"; StatusMsg: "Conectando con la central..."; Flags: runhidden waituntilterminated
#endif
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

{ Lo que se rescata de la instalacion vieja antes de borrarla. Son las dos
  cosas que NO vienen en el paquete y que son de ESA computadora: quien es
  (nombre de la sucursal + clave de publicacion) y donde tiene el proyecto. }
{ AnsiString y no String: LoadStringFromFile los recibe por referencia y exige
  ese tipo exacto (con String da "Type mismatch" al compilar). }
var CfgViejo, ProyViejo: AnsiString;

procedure BorrarSiEsta(carpeta: String);
begin
  if DirExists(carpeta) then DelTree(carpeta, True, True, True);
end;

{ Limpia la instalacion anterior ANTES de copiar la nueva.
  Por que instalar limpio y no encima: una instalacion vieja arrastra archivos
  de versiones anteriores que ya no se usan, y sobre todo las carpetas que deja
  un update a medias (PanelMyS_old, _failed, _update). Justamente esas carpetas
  son las que en las versiones anteriores a la v38 podian dejar la maquina sin
  panel. Se van todas y se arranca de cero.
  Lo que NO se toca: PanelMyS_state (la identidad durable y el manifiesto de
  publicacion) y la carpeta del proyecto en Documentos. }
procedure LimpiarInstalacionVieja();
var app, base: String; rc: Integer; fr: TFindRec;
begin
  app := ExpandConstant('{app}');
  base := ExpandConstant('{localappdata}');

  { 1) rescatar la identidad antes de borrar nada }
  CfgViejo := '';
  ProyViejo := '';
  if FileExists(app + '\panel_config.json') then
    LoadStringFromFile(app + '\panel_config.json', CfgViejo);
  if FileExists(app + '\proyecto.txt') then
    LoadStringFromFile(app + '\proyecto.txt', ProyViejo);

  { 2) cerrar el panel: con el programa abierto los archivos estan tomados y
       la copia falla a la mitad. Se le da un momento para que muera. }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExe}', '',
       SW_HIDE, ewWaitUntilTerminated, rc);
  Sleep(1500);

  { 3) borrar la instalacion anterior y los restos de updates a medias }
  BorrarSiEsta(app);
  BorrarSiEsta(base + '\PanelMyS_old');
  BorrarSiEsta(base + '\PanelMyS_failed');
  BorrarSiEsta(base + '\PanelMyS_update');
  { los PanelMyS_old_<numero> que deja el updater nuevo cuando el anterior
    quedo tomado por Windows }
  if FindFirst(base + '\PanelMyS_old_*', fr) then
  begin
    try
      repeat
        if (fr.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          BorrarSiEsta(base + '\' + fr.Name);
      until not FindNext(fr);
    finally
      FindClose(fr);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var cfg, central: String;
begin
  if CurStep = ssInstall then
    LimpiarInstalacionVieja();

  if CurStep = ssPostInstall then
  begin
    { la ruta del proyecto: si la maquina ya tenia una, se respeta (pudieron
      haber movido la carpeta y reescribirla la dejaria apuntando a otro lado) }
    if ProyViejo <> '' then
      SaveStringToFile(ExpandConstant('{app}\proyecto.txt'), ProyViejo, False)
    else
      SaveStringToFile(ExpandConstant('{app}\proyecto.txt'),
                       ExpandConstant('{userdocs}\Proyecto MyS'), False);

    { la identidad: si esta computadora ya estaba instalada, ese archivo dice
      el nombre que eligieron para la sucursal y la clave que pudieron haber
      cargado a mano. Reinstalar para actualizar no tiene por que borrarla. }
    if CfgViejo <> '' then
    begin
      SaveStringToFile(ExpandConstant('{app}\panel_config.json'), CfgViejo, False);
      exit;
    end;

    { instalacion nueva. Sin Tailscale no hay central a la que llegar, y una
      direccion que no responde solo sirve para que el panel muestre un boton
      que da error: mejor vacia. }
#ifdef ConTailscale
    central := 'http://{#CentralIP}:8125';
#else
    central := '';
#endif
    cfg := '{' + #13#10 +
           '  "rol": "colaborador",' + #13#10 +
           '  "usuario": "' + GetComputerNameString + '",' + #13#10 +
           '  "central_url": "' + central + '",' + #13#10 +
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
