[Setup]
AppName=Easy Math Lang
AppVersion=0.1.0
DefaultDirName={autopf}\EasyMathLang
DefaultGroupName=Easy Math Lang
OutputBaseFilename=EasyMathLangSetup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "dist\easy-math-lang.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "dist\easy-math-lsp.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "dist\easy-math-editor\*"; DestDir: "{app}\editor"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Easy Math Editor"; Filename: "{app}\editor\easy-math-editor.exe"
Name: "{autodesktop}\Easy Math Editor"; Filename: "{app}\editor\easy-math-editor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional options:"; Flags: unchecked
Name: "addtopath"; Description: "Add compiler/LSP to PATH (to use easy-math-lang from the terminal)"; GroupDescription: "Additional options:"; Flags: unchecked

[Registry]
Root: HKA
Subkey: "Environment"
ValueType: expandsz
ValueName: "Path"
ValueData: "{olddata};{app}\bin"
Tasks: addtopath
Check: NeedsAddPath('{app}\bin')

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKA, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;

  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;