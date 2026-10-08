[Setup]
AppName=Easy Math Lang
AppVersion=4.0.0
PrivilegesRequired=admin
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
function RemoveBackslash(S: string): string;
var
  T: string;
begin
  T := S;
  while (Length(T) > 0) and (T[Length(T)] = '\') do
    Delete(T, Length(T), 1);
  Result := T;
end;

function NeedsAddPath(Param: string): boolean;
var
  OrigPath, Hay, Needle, NeedleSlash: string;
begin
  // Must read the same hive the [Registry] entry writes (HKCU user PATH).
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  // Case-insensitive, trailing-backslash tolerant: Windows paths are
  // case-insensitive, so 'C:\X\Bin' must match 'c:\x\bin\'.
  Hay := ';' + LowerCase(OrigPath) + ';';
  // Normalize '\;' (trailing slash before separator) to ';' for matching.
  StringChangeEx(Hay, '\;', ';', True);
  Needle := ';' + LowerCase(RemoveBackslash(Param)) + ';';
  NeedleSlash := ';' + LowerCase(RemoveBackslash(Param)) + '\;';
  Result := (Pos(Needle, Hay) = 0) and (Pos(NeedleSlash, Hay) = 0);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  OrigPath, Cleaned, Entry: string;
begin
  // Strip the '{app}\bin' entry we appended, so uninstall does not leave
  // a stale dead dir on the user's PATH.
  if CurUninstallStep = usUninstall then
  begin
    if RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath) then
    begin
      Entry := ExpandConstant('{app}\bin');
      Cleaned := OrigPath;
      StringChangeEx(Cleaned, ';' + Entry, '', True);
      StringChangeEx(Cleaned, Entry + ';', '', True);
      StringChangeEx(Cleaned, Entry, '', True);
      // Collapse accidental ';;' leftovers.
      while Pos(';;', Cleaned) > 0 do
        StringChangeEx(Cleaned, ';;', ';', True);
      if Cleaned <> OrigPath then
        RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Cleaned);
    end;
  end;
end;
