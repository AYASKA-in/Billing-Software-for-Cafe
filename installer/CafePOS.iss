#define MyAppName "Cafe POS"
#define MyAppPublisher "Cafe POS"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#ifndef SourceDir
  #error "SourceDir define is required"
#endif

#ifndef OutputDir
  #define OutputDir "."
#endif

#ifndef OutputBaseFilename
  #define OutputBaseFilename "CafePOS-setup"
#endif

[Setup]
AppId={{8D4B4E91-2CB0-437C-B7C5-C729127A6015}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CafePOS
DefaultGroupName=CafePOS
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Cafe POS"; Filename: "{app}\CafePOS.exe"
Name: "{autodesktop}\Cafe POS"; Filename: "{app}\CafePOS.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CafePOS.exe"; Description: "Launch Cafe POS"; Flags: nowait postinstall skipifsilent
