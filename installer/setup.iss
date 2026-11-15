#ifndef AppVersion
; Version is injected by CI (/DAppVersion=x.y.z from pyproject.toml);
; the 0.0.0 fallback keeps hand-run ISCC.exe builds working.
#define AppVersion "0.0.0"
#endif

[Setup]
AppId=Easy Math Lang
AppName=Easy Math Lang
AppVersion={#AppVersion}
PrivilegesRequired=admin
DefaultDirName={autopf}\EasyMathLang
DefaultGroupName=Easy Math Lang
OutputBaseFilename=EasyMathLang-Windows-x64-Setup
; Upgrade in place: every release up to 7.0.0 shipped without an
; explicit AppId, so Inno used AppName as the implicit AppId and the
; uninstall key "Easy Math Lang_is1". This AppId deliberately equals
; that implicit value (no braces) — exactly so installs made with those
; old installers are recognized and upgraded as the same application.
; (An earlier update-branch change declared a different AppId, which
; made the new installer not see existing installs.)
; PrivilegesRequired=admin means Windows shows the UAC
; prompt — that is the user's verification (silent updater runs use
; /SILENT and still elevate the setup process via UAC).
CloseApplications=yes
RestartApplications=yes
; Installer icon (also shown in Add/Remove Programs via
; UninstallDisplayIcon): the multi-size icons/ezmath.ico asset, whose
; path is relative to this script (installer\ -> repo root icons\).
SetupIconFile=..\icons\ezmath.ico
UninstallDisplayIcon=..\icons\ezmath.ico
Compression=lzma2/fast
SolidCompression=yes
; Windows 10 version 1809 (build 17763) is the minimum supported
; system; 64-bit only via ArchitecturesInstallIn64BitMode below.
MinVersion=10.0.17763
ArchitecturesInstallIn64BitMode=x64compatible
; Broadcast WM_SETTINGCHANGE at the end of install/uninstall so running
; programs pick up the optional user-PATH change from [Registry] below.
ChangesEnvironment=yes

[Files]
; Shared PyInstaller onedir bundle (one _internal with all heavy
; libraries): the compiler CLI, the language server and the desktop
; editor all live here, so the install carries a single copy of NumPy,
; Matplotlib, Typst, PySide6, … .
Source: "..\dist\easy-math-lang\easy-math-lang.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\dist\easy-math-lang\easy-math-lsp.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\dist\easy-math-lang\easy-math-editor.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\dist\easy-math-lang\ezmath.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\dist\easy-math-lang\_internal\*"; DestDir: "{app}\bin\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; MIT license plus third-party notices (CeTZ is LGPL-3.0-or-later,
; bundled for offline *draw): see docs/packaging.md.
Source: "..\THIRD_PARTY_LICENSES"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Easy Math Editor"; Filename: "{app}\bin\easy-math-editor.exe"
Name: "{autodesktop}\Easy Math Editor"; Filename: "{app}\bin\easy-math-editor.exe"; Tasks: desktopicon

; Launch the editor after an *update* install only. The updater passes
; /UPDATE=1 for silent self-updates; the Check function below then makes
; this entry run — after the files are replaced, before Setup exits —
; and the editor starts with the ORIGINAL user's (non-elevated)
; credentials. Interactive installs and any other silent run see no
; entry, so nothing is launched implicitly.
[Run]
Filename: "{app}\bin\easy-math-editor.exe"; Parameters: ""; WorkingDir: "{app}\bin"; Flags: nowait runasoriginaluser; Check: IsSilentUpdate

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
function IsSilentUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;

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
