#ifndef PayloadDir
  #error PayloadDir must be passed to the compiler
#endif
#ifndef ReleaseDir
  #error ReleaseDir must be passed to the compiler
#endif

[Setup]
AppId={{C70952BE-94C0-4A13-88F7-47FBD1771B22}
AppName=YouTube Saver
AppVersion=1.0.0
AppVerName=YouTube Saver 1.0.0
DefaultDirName={localappdata}\Programs\YouTube Saver
DefaultGroupName=YouTube Saver
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=YouTube-Saver-1.0.0-Setup
SetupIconFile=..\assets\desktop.ico
UninstallDisplayIcon={app}\YouTube Saver.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
WizardImageFile=..\assets\installer-banner.png
WizardSmallImageFile=..\assets\logo.png
WizardImageBackColor=$FAF7F4
WizardSmallImageBackColor=clWhite
WizardImageStretch=yes
CloseApplications=yes
RestartApplications=no
DisableWelcomePage=no
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\YouTube Saver"; Filename: "{app}\YouTube Saver.exe"; AppUserModelID: "YouTubeSaver.Desktop"
Name: "{autodesktop}\YouTube Saver"; Filename: "{app}\YouTube Saver.exe"; Tasks: desktopicon; AppUserModelID: "YouTubeSaver.Desktop"

[Run]
Filename: "{app}\YouTube Saver.exe"; Description: "Open YouTube Saver"; Flags: nowait postinstall skipifsilent
