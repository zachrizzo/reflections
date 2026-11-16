@echo off
rem Reflections jam build: cook + stage Win64 Development into Saved\JamBuild\Windows.
rem Run AFTER building the editor and game targets together from the same source (see README.md, "How to package").
rem Announce a SAVE FREEZE first: content saved mid-cook gets dropped or breaks the cook.
rem Usage: PackageJamBuild.bat [--dry-run] [--with-npc-relay] [--allow-stale-people] [--no-build]
rem   By default UAT first builds the game target (reflections Win64 Development, -build) from the current source, so the
rem   staged exe matches the editor DLL the cook uses (B2). --no-build skips that, and is refused if reflections.exe is
rem   older than UnrealEditor-reflections.dll. If UBT reports another instance running, wait; never kill it.
rem   --build-editor first builds reflectionsEditor (Win64 Development) from the same source, because the cook commandlet
rem   loads the editor modules. Only with the editor closed: the script refuses while UnrealEditor.exe runs.
rem   --with-npc-relay  after staging, copy the NPC dialogue helper (Tools\RealtimeVoice\dist\NpcDialogueRelay, built by
rem                     Tools\RealtimeVoice\Build-NpcDialogueHelper.ps1) as loose files to
rem                     <stage>\reflections\Content\NpcDialogue\Relay. Off by default: shipping it is the user's decision.
setlocal
rem Capture the script folder before the argument loop: SHIFT also shifts %0.
set "HERE=%~dp0"
set "DRYRUN="
set "WITHRELAY="
set "ALLOWSTALE="
set "BUILDGAME=-build"
set "BUILDEDITOR="
set "EXTRASONLY="
:args
if "%~1"=="" goto argsdone
if /i "%~1"=="--dry-run" set "DRYRUN=1"
if /i "%~1"=="--with-npc-relay" set "WITHRELAY=1"
rem --allow-stale-people: measurement cooks only. Never use it for the build that gets uploaded.
if /i "%~1"=="--allow-stale-people" set "ALLOWSTALE=1"
if /i "%~1"=="--no-build" set "BUILDGAME="
if /i "%~1"=="--build-editor" set "BUILDEDITOR=1"
rem --extras-only: skip build, cook and stage; only (re)copy the notices and, with --with-npc-relay, the relay into an existing stage.
if /i "%~1"=="--extras-only" set "EXTRASONLY=1"
shift
goto args
:argsdone
for %%I in ("%HERE%..\..") do set "PROJ=%%~fI"
set "UAT=C:\Program Files\Epic Games\UE_5.9\Engine\Build\BatchFiles\RunUAT.bat"
set "STAGE=%PROJ%\Saved\JamBuild\Windows"
rem The dialogue session keeps the helper in Content\NpcDialogue\Relay (no NonUFS staging line, so only this flag ships it).
set "RELAYSRC=%PROJ%\Content\NpcDialogue\Relay"
if not exist "%RELAYSRC%\NpcDialogueRelay.exe" set "RELAYSRC=%PROJ%\Tools\RealtimeVoice\dist\NpcDialogueRelay"
set "RELAYDST=%STAGE%\reflections\Content\NpcDialogue\Relay"
rem The cooker splits its command line on spaces, so the never-cook list goes to a path without spaces.
set "NEVERCOOK=%TEMP%\ReflectionsJamNeverCook.txt"
copy /y "%HERE%NeverCookList.txt" "%NEVERCOOK%" >nul || (echo Could not copy NeverCookList.txt & exit /b 1)
if not exist "%PROJ%\Saved\JamBuild\Logs" mkdir "%PROJ%\Saved\JamBuild\Logs"
set ARGS=BuildCookRun -project="%PROJ%\reflections.uproject" -noP4 -platform=Win64 -clientconfig=Development -target=reflections -nocompileeditor %BUILDGAME% -cook -map=/Game/GrayLondon/Maps/MedievalLondon -stage -pak -iostore -compressed -nodebuginfo -stagingdirectory="%PROJ%\Saved\JamBuild" -unattended -utf8output -AdditionalCookerOptions=-NeverCookListFile=%NEVERCOOK%
if defined WITHRELAY (
  if not exist "%RELAYSRC%\NpcDialogueRelay.exe" (echo --with-npc-relay: NpcDialogueRelay.exe not found in Content\NpcDialogue\Relay or Tools\RealtimeVoice\dist. Build it first. & exit /b 1)
  rem Never ship API keys. A keys.json for local testing may sit next to the exe; it is excluded from the copy below
  rem and the staged folder is checked afterwards.
  if exist "%RELAYSRC%\keys.json" echo --with-npc-relay: note, %RELAYSRC%\keys.json exists locally and will NOT be staged.
)
rem The people book asset must be re-imported after every edit of people.json, or the build ships stale names.
set "PEOPLESTALE="
if exist "%PROJ%\Content\Lives\DA_PeopleBook.uasset" if exist "%PROJ%\ArtDirection\Story\people.json" (
  powershell -NoProfile -Command "if ((Get-Item -LiteralPath '%PROJ%\Content\Lives\DA_PeopleBook.uasset').LastWriteTime -lt (Get-Item -LiteralPath '%PROJ%\ArtDirection\Story\people.json').LastWriteTime) { exit 1 } else { exit 0 }"
  if errorlevel 1 set "PEOPLESTALE=1"
)
if defined PEOPLESTALE (
  echo ERROR: Content\Lives\DA_PeopleBook is older than ArtDirection\Story\people.json. Ask npc-lives to re-import it, then package.
  if defined ALLOWSTALE echo --allow-stale-people: continuing anyway. This package is for measuring only; don't upload it.
  if not defined DRYRUN if not defined ALLOWSTALE exit /b 1
)
rem With --no-build the staged exe is whatever is in Binaries; refuse one older than the editor DLL (a mismatched pair crashed before).
if not defined BUILDGAME (
  powershell -NoProfile -Command "$e = Get-Item -LiteralPath '%PROJ%\Binaries\Win64\reflections.exe' -ErrorAction SilentlyContinue; $d = Get-Item -LiteralPath '%PROJ%\Binaries\Win64\UnrealEditor-reflections.dll' -ErrorAction SilentlyContinue; if (-not $e -or ($d -and $e.LastWriteTime -lt $d.LastWriteTime.AddMinutes(-30))) { exit 1 } else { exit 0 }"
  if errorlevel 1 (
    echo ERROR: --no-build, but Binaries\Win64\reflections.exe is missing or older than UnrealEditor-reflections.dll. Drop --no-build so UAT builds the game target.
    if not defined DRYRUN exit /b 1
  )
)
rem Third-party notices (submission prep): CC BY 4.0, ODbL, MIT and OFL texts for the map's assets. They go next to
rem reflections.exe, so they sit in the zip's top folder. Open [CONFIRM] items only warn; they're the map owner's.
set "NOTICES=%PROJ%\ArtDirection\Submission\THIRD_PARTY_NOTICES.txt"
if not exist "%NOTICES%" echo WARNING: %NOTICES% not found; the zip will ship without third-party notices.
if exist "%NOTICES%" findstr /l /c:"[CONFIRM" "%NOTICES%" >nul && echo WARNING: THIRD_PARTY_NOTICES.txt still has [CONFIRM] items. Ask submission prep before the final upload.
set "BUILDBAT=C:\Program Files\Epic Games\UE_5.9\Engine\Build\BatchFiles\Build.bat"
if defined BUILDEDITOR (
  tasklist /FI "IMAGENAME eq UnrealEditor.exe" 2>nul | find /i "UnrealEditor.exe" >nul && (
    echo ERROR: --build-editor needs the editor closed ^(UnrealEditor.exe is running; its DLLs are loaded^).
    if not defined DRYRUN exit /b 1
  )
)
if defined DRYRUN (
  if defined BUILDEDITOR echo first: "%BUILDBAT%" reflectionsEditor Win64 Development -Project="%PROJ%\reflections.uproject" -WaitMutex
  echo "%UAT%" %ARGS%
  if exist "%NOTICES%" echo then: copy THIRD_PARTY_NOTICES.txt to "%STAGE%\"
  if defined WITHRELAY echo then: copy the relay allowlist ^(NpcDialogueRelay.exe, roster.json, keys.json.example, _internal\, seed\^) from "%RELAYSRC%" to "%RELAYDST%", then scan it for keys
  exit /b 0
)
rem Record what the package is built from: the commit, plus how many source/content/config files changed after it
rem (the working tree is packaged as it stands, committed or not). No git status: it runs LFS filters over Content.
if not defined EXTRASONLY powershell -NoProfile -Command "$p = '%PROJ%'; $h = (git -C $p log -1 --format='%%h %%cI %%s' 2>$null); $t = [datetime](git -C $p log -1 --format=%%cI 2>$null); $n = @(Get-ChildItem -LiteralPath (Join-Path $p 'Source'), (Join-Path $p 'Content'), (Join-Path $p 'Config') -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt $t }).Count; $line = '{0:yyyy-MM-dd HH:mm:ss} package from {1} plus the uncommitted working tree ({2} Source/Content/Config files newer than that commit)' -f (Get-Date), $h, $n; Add-Content -LiteralPath (Join-Path $p 'Saved\JamBuild\Logs\build_info.txt') -Value $line; $line"
if defined BUILDEDITOR (
  echo Building reflectionsEditor ... log: Saved\JamBuild\Logs\build_editor.log
  call "%BUILDBAT%" reflectionsEditor Win64 Development -Project="%PROJ%\reflections.uproject" -WaitMutex > "%PROJ%\Saved\JamBuild\Logs\build_editor.log" 2>&1
  if errorlevel 1 (echo reflectionsEditor build FAILED; see build_editor.log. Nothing was cooked. & exit /b 7)
  echo reflectionsEditor built.
)
if defined EXTRASONLY (
  if not exist "%STAGE%\reflections.exe" (echo --extras-only: no staged build at %STAGE%. Run without it first. & exit /b 1)
  echo --extras-only: no build or cook; refreshing the notices and, with --with-npc-relay, the relay in %STAGE%
  goto extras
)
echo Packaging %PROJ% ... log: Saved\JamBuild\Logs\uat_package.log
call "%UAT%" %ARGS% > "%PROJ%\Saved\JamBuild\Logs\uat_package.log" 2>&1
set RC=%ERRORLEVEL%
echo UAT exit code %RC% (0 = success). Output: %STAGE%
if not "%RC%"=="0" exit /b %RC%
:extras
if exist "%NOTICES%" (copy /y "%NOTICES%" "%STAGE%\" >nul || (echo Copying THIRD_PARTY_NOTICES.txt failed. & exit /b 8))
if defined WITHRELAY (
  call :stagerelay
  if errorlevel 9 exit /b 9
  if errorlevel 8 exit /b 8
)
exit /b 0

:stagerelay
rem ALLOWLIST copy: only these items ship. Anything else next to the exe (keys.json, "keys - Copy.json",
rem keys.json.txt, .env, notes) stays behind, whatever its name.
if exist "%RELAYDST%" rmdir /s /q "%RELAYDST%"
mkdir "%RELAYDST%"
copy /y "%RELAYSRC%\NpcDialogueRelay.exe" "%RELAYDST%\" >nul || (echo Copying NpcDialogueRelay.exe failed. & exit /b 8)
for %%F in (roster.json keys.json.example) do if exist "%RELAYSRC%\%%F" copy /y "%RELAYSRC%\%%F" "%RELAYDST%\" >nul
for %%D in (_internal seed) do if exist "%RELAYSRC%\%%D" (
  robocopy "%RELAYSRC%\%%D" "%RELAYDST%\%%D" /E /XF *key*.json *.env *.key /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 (echo Copying the NPC relay folder %%D failed. & exit /b 8)
)
rem Then refuse to report success if anything key-shaped reached the staged folder.
set "LEAK="
for /f "delims=" %%K in ('dir /s /b /a-d "%RELAYDST%\*key*" 2^>nul ^| findstr /v /i /e "keys.json.example"') do (echo LEAK: %%K & set "LEAK=1")
for /f "delims=" %%K in ('dir /s /b /a-d "%RELAYDST%\*.env" 2^>nul') do (echo LEAK: %%K & set "LEAK=1")
powershell -NoProfile -Command "$h = Get-ChildItem -LiteralPath '%RELAYDST%' -Recurse -File -Include *.json,*.txt,*.ini,*.cfg,*.yaml,*.yml,*.toml,*.env | Select-String -Pattern 'AIza[0-9A-Za-z_-]{30,}','sk-[A-Za-z0-9_-]{20,}' -List; if ($h) { $h | ForEach-Object { 'LEAK: key-shaped string in ' + $_.Path }; exit 1 } else { exit 0 }"
if errorlevel 1 set "LEAK=1"
if defined LEAK (rmdir /s /q "%RELAYDST%" & echo ERROR: key material reached the staged relay; it was removed. Fix the source folder and package again. & exit /b 9)
echo NPC relay staged loose at %RELAYDST% ^(allowlist, no keys found^). Without a keys.json next to it, NPCs use baked lines.
exit /b 0
