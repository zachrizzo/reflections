@echo off
rem Reflections jam build: cook + stage Win64 Development into Saved\JamBuild\Windows.
rem Run AFTER building the editor and game targets together from the same source (see README.md, "The command").
rem Announce a SAVE FREEZE first: content saved mid-cook gets dropped or breaks the cook.
rem Usage: PackageJamBuild.bat [--dry-run]
setlocal
for %%I in ("%~dp0..\..") do set "PROJ=%%~fI"
set "UAT=C:\Program Files\Epic Games\UE_5.9\Engine\Build\BatchFiles\RunUAT.bat"
rem The cooker splits its command line on spaces, so the never-cook list goes to a path without spaces.
set "NEVERCOOK=%TEMP%\ReflectionsJamNeverCook.txt"
copy /y "%~dp0NeverCookList.txt" "%NEVERCOOK%" >nul || (echo Could not copy NeverCookList.txt & exit /b 1)
if not exist "%PROJ%\Saved\JamBuild\Logs" mkdir "%PROJ%\Saved\JamBuild\Logs"
set ARGS=BuildCookRun -project="%PROJ%\reflections.uproject" -noP4 -platform=Win64 -clientconfig=Development -target=reflections -nocompileeditor -cook -map=/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd -stage -pak -iostore -compressed -nodebuginfo -stagingdirectory="%PROJ%\Saved\JamBuild" -unattended -utf8output -AdditionalCookerOptions=-NeverCookListFile=%NEVERCOOK%
if /i "%~1"=="--dry-run" (
  echo "%UAT%" %ARGS%
  exit /b 0
)
echo Packaging %PROJ% ... log: Saved\JamBuild\Logs\uat_package.log
call "%UAT%" %ARGS% > "%PROJ%\Saved\JamBuild\Logs\uat_package.log" 2>&1
set RC=%ERRORLEVEL%
echo UAT exit code %RC% (0 = success). Output: %PROJ%\Saved\JamBuild\Windows
exit /b %RC%
