; Instalador del Panel de administracion - Muebles y Sillones
; Compilar:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" PanelMyS.iss
; Genera:    instalador\Instalar Panel MyS.exe  (un solo archivo, sin admin)

#define AppName    "Panel Muebles y Sillones"
#define AppShort   "PanelMyS"
#define AppVer     "1.25.1"
; Clave de publicacion del equipo. VIVE EN UN ARCHIVO APARTE (clave-equipo.iss)
; que esta gitignoreado: NO viaja al repositorio. Si el archivo no esta, el
; instalador compila igual pero SIN la clave baked (habria que pegarla a mano).
; Para bakearla: crear clave-equipo.iss con  #define PubKey "LA_CLAVE"
; ORDEN IMPORTANTE: primero se mira si la clave vino por linea de comandos
; (/DPubKey=...) y recien despues se lee el archivo. Al reves, el archivo pisaba
; el parametro y era IMPOSIBLE compilar un instalador con la clave de una
; sucursal puntual: salian todos con la misma. Probado con /DPubKey.
#ifndef PubKey
  #ifexist "clave-equipo.iss"
    #include "clave-equipo.iss"
  #endif
#endif
#ifndef PubKey
  #define PubKey ""
#endif
#define AppExe     "PanelMyS.exe"
#define SrcDir     "dist\PanelMyS"

[Setup]
AppId={{B7E4C2A1-9D3F-4E6B-8A21-6F0C5D8E1A44}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=Muebles y Sillones
DefaultDirName={localappdata}\{#AppShort}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=instalador
OutputBaseFilename=Instalar Panel MyS
SetupIconFile=panel.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Excludes: "proyecto.txt,panel_config.json,aprobaciones\*"; Flags: recursesubdirs createallsubdirs ignoreversion
; Launcher ESTABLE del auto-update (fuera de {app}, no se pisa en un swap)
Source: "updater\PanelMyS_run.vbs"; DestDir: "{localappdata}\PanelMyS_run"; Flags: ignoreversion
Source: "updater\PanelMyS_run.bat"; DestDir: "{localappdata}\PanelMyS_run"; Flags: ignoreversion
Source: "panel.ico"; DestDir: "{localappdata}\PanelMyS_run"; Flags: ignoreversion

[InstallDelete]
; Instalar = dejar el programa LIMPIO: fuera el codigo de la version anterior y
; los restos de updates. La config/clave/aprobaciones de la maquina NO se tocan.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\PanelMyS.exe"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_update"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_old"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_failed"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{localappdata}\PanelMyS_run\PanelMyS_run.vbs"""; IconFilename: "{localappdata}\PanelMyS_run\panel.ico"; WorkingDir: "{localappdata}\PanelMyS_run"
Name: "{autodesktop}\{#AppName}";  Filename: "{sys}\wscript.exe"; Parameters: """{localappdata}\PanelMyS_run\PanelMyS_run.vbs"""; IconFilename: "{localappdata}\PanelMyS_run\panel.ico"; WorkingDir: "{localappdata}\PanelMyS_run"
; Solo la CENTRAL: arranca el receptor (oculto) al iniciar sesion, asi recibe
; propuestas aunque el panel no este abierto.
Name: "{userstartup}\Receptor Panel MyS"; Filename: "{app}\iniciar_receptor.vbs"; WorkingDir: "{app}"; Check: EsCentral

[UninstallDelete]
Type: files; Name: "{app}\iniciar_receptor.vbs"
Type: files; Name: "{app}\panel_config.json"
Type: files; Name: "{app}\proyecto.txt"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_run"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_update"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_old"
Type: filesandordirs; Name: "{localappdata}\PanelMyS_state"

[Run]
Filename: "{sys}\wscript.exe"; Parameters: """{localappdata}\PanelMyS_run\PanelMyS_run.vbs"""; Description: "Abrir el panel ahora"; Flags: nowait postinstall skipifsilent

[Code]
{ SIN PREGUNTAS y CON LA CLAVE INCLUIDA. La central es una sola y ya esta
  configurada (se detecta sola y no se toca). Toda otra PC queda como
  COLABORADOR con la clave del equipo YA cargada: puede editar y publicar sin
  que se le pida nada. Si la maquina ya tenia un nombre de usuario, se conserva. }

function EsCentral: Boolean;
var
  sa: AnsiString;
  t: String;
begin
  { es central TODO lo que no diga "colaborador" (la config de la central puede
    no tener la clave "rol" escrita). AnsiString -> String explicito. }
  Result := False;
  if LoadStringFromFile(ExpandConstant('{app}\panel_config.json'), sa) then
  begin
    t := String(sa);
    Result := (Trim(t) <> '') and (Pos('"colaborador"', t) = 0);
  end;
end;

function UsuarioActual: String;
var
  sa: AnsiString;
  t, marca: String;
  i, j: Integer;
begin
  { conservar el "usuario" de una config existente; si no, el nombre de Windows }
  Result := '';
  if LoadStringFromFile(ExpandConstant('{app}\panel_config.json'), sa) then
  begin
    t := String(sa);
    marca := '"usuario"';
    i := Pos(marca, t);
    if i > 0 then
    begin
      i := i + Length(marca);
      while (i <= Length(t)) and (t[i] <> ':') do i := i + 1;
      while (i <= Length(t)) and (t[i] <> '"') do i := i + 1;
      i := i + 1;
      j := i;
      while (j <= Length(t)) and (t[j] <> '"') do j := j + 1;
      if j > i then Result := Copy(t, i, j - i);
    end;
  end;
  if Trim(Result) = '' then Result := Trim(GetUserNameString);
  if Trim(Result) = '' then Result := 'Equipo MyS';
end;

procedure EscribirLanzadorReceptor;
var
  vbs: String;
begin
  vbs :=
    'Set fso = CreateObject("Scripting.FileSystemObject")' + #13#10 +
    'carpeta = fso.GetParentFolderName(WScript.ScriptFullName)' + #13#10 +
    'q = Chr(34)' + #13#10 +
    'Set sh = CreateObject("WScript.Shell")' + #13#10 +
    'sh.Run q & carpeta & "\PanelMyS.exe" & q & " --receptor", 0, False' + #13#10;
  SaveStringToFile(ExpandConstant('{app}\iniciar_receptor.vbs'), vbs, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  cfg, usuario, proy: String;
begin
  if CurStep = ssPostInstall then
  begin
    if EsCentral then
    begin
      { la central se respeta tal cual; solo su autoarranque del receptor }
      EscribirLanzadorReceptor;
    end
    else
    begin
      { colaborador (nuevo o existente): clave del equipo YA cargada -> publica
        sin que se le pida nada. Se conserva el nombre si ya lo tenia. }
      usuario := UsuarioActual;
      StringChangeEx(usuario, '\', '\', True);
      StringChangeEx(usuario, '"', '\"', True);
      cfg := '{' + #13#10 +
             '  "rol": "colaborador",' + #13#10 +
             '  "usuario": "' + usuario + '",' + #13#10 +
             '  "publish_token": "{#PubKey}"' + #13#10 +
             '}' + #13#10;
      SaveStringToFile(ExpandConstant('{app}\panel_config.json'), cfg, False);
    end;
    { PC nueva: carpeta de proyecto lista (se llena con "Traer ultima version") }
    if not FileExists(ExpandConstant('{app}\proyecto.txt')) then
    begin
      proy := ExpandConstant('{userdocs}\Proyecto MyS');
      ForceDirectories(proy + '\intranet');
      ForceDirectories(proy + '\herramientas');
      SaveStringToFile(ExpandConstant('{app}\proyecto.txt'), proy, False);
    end;
  end;
end;
