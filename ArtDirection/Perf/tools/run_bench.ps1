# Drive a packaged Reflections build with a timed console-command schedule.
# Usage: powershell -File run_bench.ps1 -Exe <reflections.exe> -Schedule <file> -Tag <name> [-ExtraArgs "..."]
# Schedule lines: "<seconds> <console command>"  (# comments allowed). Commands are typed into the
# in-game console via window messages (PostMessage), so the game window does not need focus.
param(
  [Parameter(Mandatory)] [string]$Exe,
  [Parameter(Mandatory)] [string]$Schedule,
  [Parameter(Mandatory)] [string]$Tag,
  [string]$ExtraArgs = "",
  [string]$ExecCmds = "",
  [int]$ResX = 1920, [int]$ResY = 1080,
  [int]$TimeoutSec = 900
)
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class W {
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte sc, uint f, UIntPtr e);
  [DllImport("user32.dll")] public static extern short VkKeyScan(char c);
  public static void Tap(byte vk) { byte sc=(byte)MapVirtualKey(vk,0); keybd_event(vk,sc,0,UIntPtr.Zero); System.Threading.Thread.Sleep(25); keybd_event(vk,sc,2,UIntPtr.Zero); System.Threading.Thread.Sleep(12); }
  public static void Type(string s) { foreach (char c in s) { short v = VkKeyScan(c); bool sh = (v & 0x100)!=0; if (sh) keybd_event(0x10,0,0,UIntPtr.Zero); Tap((byte)(v & 0xff)); if (sh) keybd_event(0x10,0,2,UIntPtr.Zero); } }
  public static void Focus(IntPtr h) {
    IntPtr fg = GetForegroundWindow(); uint ft = GetWindowThreadProcessId(fg, IntPtr.Zero); uint me = GetCurrentThreadId();
    AttachThreadInput(me, ft, true); BringWindowToTop(h); SetForegroundWindow(h); AttachThreadInput(me, ft, false);
  }
}
"@
function Send-Key([IntPtr]$h, [int]$vk) {
  $sc = [W]::MapVirtualKey([uint32]$vk, 0)
  [W]::PostMessage($h, 0x0100, [IntPtr]$vk, [IntPtr](1 -bor ($sc -shl 16))) | Out-Null   # WM_KEYDOWN
  Start-Sleep -Milliseconds 30
  [W]::PostMessage($h, 0x0101, [IntPtr]$vk, [IntPtr]([int64]0xC0000001 -bor ($sc -shl 16))) | Out-Null # WM_KEYUP
}
function Send-Console([IntPtr]$h, [string]$cmd) {
  # UE only routes keys while its window is foreground: take focus briefly, type, then hand it back.
  # "key:<chars>" taps game keys instead of typing a console command.
  $prev = [W]::GetForegroundWindow()
  [W]::Focus($h)
  Start-Sleep -Milliseconds 150
  if ($cmd.StartsWith("key:")) { [W]::Type($cmd.Substring(4)) }
  else { [W]::Tap(0xC0); Start-Sleep -Milliseconds 120; [W]::Type($cmd); Start-Sleep -Milliseconds 40; [W]::Tap(0x0D) }
  Start-Sleep -Milliseconds 120
  if ($prev -ne [IntPtr]::Zero -and $prev -ne $h) { [W]::Focus($prev) }
}
$exec = "r.GPUCsvStatsEnabled 1,csvprofile start"
if ($ExecCmds) { $exec = "$exec,$ExecCmds" }
$argline = "-windowed -ResX=$ResX -ResY=$ResY -WinX=2600 -WinY=40 -nosplash -unattended -csvGpuStats -ExecCmds=`"$exec`" $ExtraArgs"
Write-Host "[$Tag] launching: $argline"
$p = Start-Process -FilePath $Exe -ArgumentList $argline -PassThru
$t0 = Get-Date
$h = [IntPtr]::Zero
while ($h -eq [IntPtr]::Zero -and ((Get-Date) - $t0).TotalSeconds -lt 180) { Start-Sleep 1; $p.Refresh(); $h = $p.MainWindowHandle }
Write-Host "[$Tag] window after $([int]((Get-Date)-$t0).TotalSeconds)s"
$lines = Get-Content $Schedule | Where-Object { $_ -match '^\s*\d' }
$tw = Get-Date
foreach ($ln in $lines) {
  $sp = $ln.Trim() -split '\s+', 2
  $at = [double]$sp[0]; $cmd = $sp[1]
  while (((Get-Date) - $tw).TotalSeconds -lt $at) { if ($p.HasExited) { break }; Start-Sleep -Milliseconds 100 }
  if ($p.HasExited) { Write-Host "[$Tag] game exited early (code $($p.ExitCode)) at $([int]((Get-Date)-$tw).TotalSeconds)s"; break }
  $p.Refresh(); $h = $p.MainWindowHandle
  Write-Host ("[{0}] t={1,6:N1}s  {2}" -f $Tag, ((Get-Date)-$tw).TotalSeconds, $cmd)
  Send-Console $h $cmd
}
if (-not $p.WaitForExit($TimeoutSec * 1000)) { Write-Host "[$Tag] timeout, killing"; $p.Kill() }
Write-Host "[$Tag] exit code $($p.ExitCode) after $([int]((Get-Date)-$t0).TotalSeconds)s"
