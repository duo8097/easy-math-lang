[Setup]
AppName=Easy Math Lang
AppVersion=1.1.0
DefaultDirName={autopf}\EasyMathLang
DefaultGroupName=Easy Math Lang
OutputBaseFilename=EasyMathLangSetup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
; Broadcast WM_SETTINGCHANGE at the end of install/uninstall so running
; programs pick up the optional user-PATH change from [Registry] below.
ChangesEnvironment=yes

[Files]
Source: "..\dist\easy-math-lang.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\dist\ezmath.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\dist\easy-math-lsp.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\dist\easy-math-editor\*"; DestDir: "{app}\editor"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Easy Math Editor"; Filename: "{app}\editor\easy-math-editor.exe"
Name: "{autodesktop}\Easy Math Editor"; Filename: "{app}\editor\easy-math-editor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional options:"; Flags: unchecked
Name: "addtopath"; Description: "Add compiler/LSP to PATH (to use easy-math-lang from the terminal)"; GroupDescription: "Additional options:"; Flags: unchecked

[Registry]
; Per-user PATH (HKCU\Environment is where Windows reads the user PATH from).
; Never write PATH to HKLM\Environment: that key is not a real environment
; location, and creating keys directly under HKLM fails on some machines
; ("RegCreateKeyEx failed; code 87").
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}\bin"; Tasks: addtopath; Check: NeedsAddPath('{app}\bin')

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  // Must read the same hive the [Registry] entry writes (HKCU user PATH).
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;
