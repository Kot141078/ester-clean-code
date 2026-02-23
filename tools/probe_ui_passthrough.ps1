# Probes endpoints with HTML-fallback DISABLED to surface the real upstream status.
param(
  [string]$Base = "http://127.0.0.1:8080",
  [string[]]$Paths = @("/portal","/admin/messaging")
)

$ProgressPreference = "SilentlyContinue"

function Probe([string]$u){
  try{
    $r = Invoke-WebRequest -Uri $u -Headers @{"Accept"="text/html"; "X-Ester-UI-Debug"="passthrough"} -Method GET -TimeoutSec 20 -ErrorAction Stop
    return @{
      Url = $u
      Status = [int]$r.StatusCode
      ContentType = $r.Headers["Content-Type"]
      Length = $r.RawContentLength
      X_Ester_UI_Fallback = $r.Headers["X-Ester-UI-Fallback"]
    }
  } catch {
    if ($_.Exception.Response){
      $resp = $_.Exception.Response
      return @{
        Url = $u
        Status = [int]$resp.StatusCode.Value__
        ContentType = $resp.ContentType
        Length = 0
        X_Ester_UI_Fallback = $resp.Headers["X-Ester-UI-Fallback"]
      }
    } else {
      return @{
        Url = $u
        Status = "ERR"
        ContentType = ""
        Length = 0
        X_Ester_UI_Fallback = ""
        Error = $_.Exception.Message
      }
    }
  }
}

$rows = @()
foreach($p in $Paths){
  $u = "{0}{1}{2}" -f $Base, $p, ($p.Contains("?") ? "&ui_fallback=off" : "?ui_fallback=off")
  $rows += (Probe $u)
}

$rows | Format-Table Url, Status, ContentType, Length, X_Ester_UI_Fallback -AutoSize

# Also emit compact JSON for logs
$rows | ConvertTo-Json -Depth 5 | Out-File -Encoding UTF8 "probe_ui_passthrough.json"
Write-Host ("Saved JSON to: {0}" -f (Resolve-Path "probe_ui_passthrough.json"))
