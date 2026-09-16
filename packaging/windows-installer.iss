; ============================================================================
;  🜲 NyxRecover — Instalador para Windows (Inno Setup 6)
;  Compilar:  ISCC.exe /DAppVersion=1.0.1 packaging\windows-installer.iss
;  Requiere:  dist\NyxRecover.exe ya compilado
;  Produce:   dist\NyxRecover-<ver>-windows-x64-setup.exe
;
;  Todo se instala en UNA única carpeta ({autopf}\NyxRecover) y el
;  desinstalador borra exe, accesos directos y clave de registro —
;  cero residuos. Los datos forenses del usuario (recuperaciones e
;  informes) se conservan SIEMPRE: nunca se borran sin permiso.
; ============================================================================

#define MyAppName "NyxRecover"
#define MyAppPublisher "D1se0"
#define MyAppURL "https://d1se0.github.io/nyxrecover/"
#define MyAppExeName "NyxRecover.exe"

#ifndef AppVersion
#define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{7E3F2A61-9C44-4B8E-A2D1-5A2B7C9D0E13}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} v{#AppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL=https://github.com/D1se0/nyxrecover/issues
DefaultDirName={autopf}\NyxRecover
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
InfoBeforeFile=aviso-instalacion.rtf
OutputDir=..\dist
OutputBaseFilename=NyxRecover-{#AppVersion}-windows-x64-setup
SetupIconFile=..\assets\nyx.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=no

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el &escritorio"; \
    GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\NyxRecover.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\NyxRecover-cli.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    Comment: "Recuperacion forense de datos borrados y borrado seguro"
Name: "{group}\{#MyAppName} (consola CLI)"; Filename: "{app}\NyxRecover-cli.exe"; \
    Comment: "NyxRecover en modo linea de comandos"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--cli devices"; \
    Description: "Verificar la instalación (inventario de discos)"; \
    Flags: postinstall skipifsilent runasoriginaluser

[UninstallDelete]
; Limpieza total de lo generado dentro de la carpeta de la app:
Type: filesandordirs; Name: "{app}\docs"
Type: filesandordirs; Name: "{app}\logs"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // en modo silencioso no molestar con diálogos
    if (Pos('/SILENT', Uppercase(GetCmdTail)) = 0) then
      MsgBox(
        'NyxRecover se ha desinstalado por completo.' #13#10 #13#10 +
        'Tus datos forenses (carpetas "nyx_recuperados" y "nyx_informes" en tu perfil de usuario) ' +
        'se han CONSERVADO a propósito: son tuyos. Bórralos tú si ya no los necesitas.',
        mbInformation, MB_OK);
  end
end;