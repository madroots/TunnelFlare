; Inno Setup 6 script for TunnelFlare. Compiled by packaging/build.py:
;   ISCC.exe /DAppVersion=<v> /DSourceDir=<dist\TunnelFlare> /DOutputDir=<dist\release>
;            /DIconFile=<build\icons\tunnelflare.ico> packaging\windows\tunnelflare.iss

#ifndef AppVersion
  #error AppVersion must be defined (/DAppVersion=x.y.z)
#endif
#ifndef SourceDir
  #error SourceDir must be defined (/DSourceDir=path to the PyInstaller onedir output)
#endif
#ifndef OutputDir
  #error OutputDir must be defined (/DOutputDir=path)
#endif
#ifndef IconFile
  #error IconFile must be defined (/DIconFile=path to tunnelflare.ico)
#endif

#define AppName "TunnelFlare"
#define AppExe "TunnelFlare.exe"

[Setup]
AppId={{6F0D8B2A-3C41-4E7B-9A55-2D8C1F4B7E90}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=madroots
AppPublisherURL=https://github.com/madroots/TunnelFlare
AppSupportURL=https://github.com/madroots/TunnelFlare/issues
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename={#AppName}-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Drop the previous version's runtime so stale libraries never mix with new ones.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
