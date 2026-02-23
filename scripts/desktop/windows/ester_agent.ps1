# scripts\desktop\windows\ester_agent.ps1
# Naznachenie: lokalnyy RPA-agent dlya seansa "ester".
# HTTP API: 127.0.0.1:8732
#   GET  /health
#   GET  /screen                        -> { ok, png_b64 }
#   POST /open {"app":"chrome"|...}
#   POST /click {"x":int,"y":int}
#   POST /type {"text":"..."}
#   POST /ocr_click {"needle":"...", "lang":"eng+rus"}  -> klikaet po naydennomu tekstu (Tesseract tsv)
#   POST /slot {"slot":"A"|"B"}        -> pereklyuchit A/B-slot (avto-perezapusk snaruzhi)
#
# Zavisimosti (OCR):
#   - (optsionalno) C:\Program Files\Tesseract-OCR\tesseract.exe
#     Esli ne ustanovlen — /ocr_click vernet error: "tesseract_not_found"
#
# MOSTY:
#   Yavnyy: (Zrenie ↔ Deystvie) ekran→OCR→klik.
#   Skrytyy #1: (Infoteoriya ↔ Bezopasnost) whitelist deystviy ogranichivaet entropiyu.
#   Skrytyy #2: (Kibernetika ↔ Arkhitektura) heartbeat/sloty zamykayut ustoychivuyu petlyu kontrolya.
#
# ZEMNOY ABZATs:
#   Skrinshot cherez .NET CopyFromScreen, OCR cherez Tesseract TSV daet koordinaty; klik — v tsentr boksa.
#   Nikakogo oblaka: vse lokalno. Sloty A/B menyayutsya zapisyu fayla active.slot.
#
# c=a+b

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = "Continue"

function Write-Log($msg) {
  $ts = (Get-Date).ToString("s")
  $line = @{ts=$ts; level="info"; msg=$msg} | ConvertTo-Json -Compress
  Add-Content -LiteralPath "C:\Ester\logs\rpa.jsonl" -Value $line
}

function Heartbeat {
  $ts = [int][double]::Parse((Get-Date -UFormat %s))
  $hb = @{ts=$ts; agent="ester_agent"; ok=$true} | ConvertTo-Json -Compress
  Add-Content -LiteralPath "C:\Ester\logs\health.jsonl" -Value $hb
}

# Slot management
$ActiveSlotPath = "C:\Ester\releases\active.slot"
if (-not (Test-Path $ActiveSlotPath)) { Set-Content $ActiveSlotPath "A" -Encoding ASCII }
$ActiveSlot = (Get-Content $ActiveSlotPath -Encoding ASCII).Trim()

Write-Log "agent_start slot=$ActiveSlot"

# Low-level mouse
Add-Type -MemberDefinition @"
using System;
using System.Runtime.InteropServices;
public class W32Mouse {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint cButtons, uint dwExtraInfo);
  public const uint MOUSEEVENTF_LEFTDOWN=0x0002;
  public const uint MOUSEEVENTF_LEFTUP=0x0004;
}
"@ -Name "W32Mouse" -Namespace "Native"

function Click-At([int]$x,[int]$y) {
  [Native.W32Mouse]::SetCursorPos($x,$y) | Out-Null
  Start-Sleep -Milliseconds 30
  [Native.W32Mouse]::mouse_event([Native.W32Mouse]::MOUSEEVENTF_LEFTDOWN,0,0,0,0)
  Start-Sleep -Milliseconds 30
  [Native.W32Mouse]::mouse_event([Native.W32Mouse]::MOUSEEVENTF_LEFTUP,0,0,0,0)
}

function Type-Text([string]$text) {
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.SendKeys]::SendWait($text)
}

function Take-ScreenshotPngBase64 {
  $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
  $ms = New-Object System.IO.MemoryStream
  $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
  $bytes = $ms.ToArray()
  $ms.Dispose(); $g.Dispose(); $bmp.Dispose()
  return [Convert]::ToBase64String($bytes)
}

function OCR-FindAndClick([string]$needle, [string]$lang) {
  $tess = "C:\Program Files\Tesseract-OCR\tesseract.exe"
  if (-not (Test-Path $tess)) { return @{ ok=$false; error="tesseract_not_found" } }

  $tmpDir = "$env:TEMP\ester_rpa"; New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
  $png = Join-Path $tmpDir "shot.png"
  # Sokhranyaem tekuschiy skrin
  $b64 = Take-ScreenshotPngBase64
  [IO.File]::WriteAllBytes($png, [Convert]::FromBase64String($b64))

  $lang = if ([string]::IsNullOrWhiteSpace($lang)) { "eng+rus" } else { $lang }
  # TSV c bbox: level,page_num,block_num,par_num,line_num,word_num,left,top,width,height,conf,text
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $tess
  $psi.Arguments = "`"$png`" stdout -l $lang tsv"
  $psi.RedirectStandardOutput = $true
  $psi.UseShellExecute = $false
  $p = [System.Diagnostics.Process]::Start($psi)
  $tsv = $p.StandardOutput.ReadToEnd()
  $p.WaitForExit()

  $lines = $tsv -split "`r?`n"
  $best = $null
  foreach ($ln in $lines) {
    if ($ln -match "^\d+\t") {
      $cols = $ln -split "`t"
      if ($cols.Length -ge 12) {
        $text = $cols[11]
        if ($text -and $text.ToLower().Contains($needle.ToLower())) {
          $left = [int]$cols[6]; $top = [int]$cols[7]; $w = [int]$cols[8]; $h = [int]$cols[9]
          $cx = $left + [int]($w/2); $cy = $top + [int]($h/2)
          $best = @{ x=$cx; y=$cy; box=@{left=$left;top=$top;width=$w;height=$h}; text=$text }
          break
        }
      }
    }
  }
  if ($null -eq $best) { return @{ ok=$false; error="text_not_found" } }
  Click-At $best.x $best.y
  return @{ ok=$true; hit=$best }
}

# HTTP listener
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://127.0.0.1:8732/")
$listener.Start()
Write-Log "agent_listen addr=127.0.0.1:8732"

# heartbeat timer
$hbTimer = New-Object System.Timers.Timer
$hbTimer.Interval = 3000
$hbTimer.AutoReset = $true
$hbTimer.add_Elapsed({ Heartbeat })
$hbTimer.Start()

function Respond($ctx, [hashtable]$obj) {
  $msg = ($obj | ConvertTo-Json -Compress)
  $buf = [Text.Encoding]::UTF8.GetBytes($msg)
  $ctx.Response.ContentType = "application/json"
  $ctx.Response.ContentEncoding = [Text.Encoding]::UTF8
  $ctx.Response.OutputStream.Write($buf,0,$buf.Length)
  $ctx.Response.Close()
}

# Whitelist prilozheniy
$apps = @{
  "notepad"    = "notepad.exe";
  "explorer"   = "explorer.exe";
  "cmd"        = "C:\Windows\System32\cmd.exe";
  "powershell" = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe";
  "chrome"     = "C:\Program Files\Google\Chrome\Application\chrome.exe"
}

while ($listener.IsListening) {
  $ctx = $listener.GetContext()
  $req = $ctx.Request
  try {
    if ($req.HttpMethod -eq "GET" -and $req.Url.AbsolutePath -eq "/health") {
      Respond $ctx @{ ok=$true; agent="ester"; slot=$ActiveSlot }; continue
    }
    if ($req.HttpMethod -eq "GET" -and $req.Url.AbsolutePath -eq "/screen") {
      $b64 = Take-ScreenshotPngBase64
      Respond $ctx @{ ok=$true; png_b64=$b64 }; continue
    }

    $raw = New-Object IO.StreamReader $req.InputStream, $req.ContentEncoding
    $body = $raw.ReadToEnd(); $raw.Close()
    if (-not $body) { $body = "{}" }
    $o = ConvertFrom-Json $body

    switch ($req.Url.AbsolutePath) {
      "/open" {
        $app = ($o.app).ToLower()
        if (-not $apps.ContainsKey($app)) { Respond $ctx @{ok=$false; error="app_not_allowed"}; break }
        Start-Process $apps[$app] | Out-Null
        Write-Log "open app=$app"
        Respond $ctx @{ ok=$true }
      }
      "/click" {
        Click-At ([int]$o.x) ([int]$o.y)
        Write-Log ("click x={0} y={1}" -f $o.x, $o.y)
        Respond $ctx @{ ok=$true }
      }
      "/type" {
        $text = [string]$o.text
        if (-not $text) { Respond $ctx @{ ok=$false; error="text_required" }; break }
        Type-Text $text
        Write-Log "type len=$($text.Length)"
        Respond $ctx @{ ok=$true }
      }
      "/ocr_click" {
        $needle = [string]$o.needle
        if (-not $needle) { Respond $ctx @{ ok=$false; error="needle_required" }; break }
        $lang = if ($o.lang) { [string]$o.lang } else { "eng+rus" }
        $res = OCR-FindAndClick -needle $needle -lang $lang
        Respond $ctx $res
      }
      "/slot" {
        $slot = ([string]$o.slot).ToUpper()
        if ($slot -notin @("A","B")) { Respond $ctx @{ ok=$false; error="slot_invalid"}; break }
        Set-Content $ActiveSlotPath $slot -Encoding ASCII
        $ActiveSlot = $slot
        Respond $ctx @{ ok=$true; slot=$slot }
      }
      default {
        Respond $ctx @{ ok=$false; error="unknown_endpoint" }
      }
    }
  } catch {
    Write-Log ("error msg=""{0}""" -f $_.Exception.Message.Replace('"','\"'))
    Respond $ctx @{ ok=$false; error="exception" }
  }
}
