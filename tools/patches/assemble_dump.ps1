# Sobiraet damp v fayly
$parts = @("Ester_dump_part_0001.txt", "Ester_dump_part_0002.txt", "Ester_dump_part_0003.txt")
foreach ($part in $parts) {
    Get-Content $part | ForEach-Object {
        if ($_ -match "----- BEGIN FILE: (.*)  \(size=\d+ B, type=text\) -----") {
            $file = $matches[1]
            $dir = Split-Path $file -Parent
            if ($dir) { New-Item -ItemType Directory -Force -Path $dir }
            Out-File -FilePath $file -Encoding utf8 -InputObject ""
        } elseif ($_ -match "----- END FILE: .* -----") {
            # Konets fayla
        } else {
            Add-Content -Path $file -Encoding utf8 -Value $_
        }
    }
}
Write-Host "Damp sobran!"