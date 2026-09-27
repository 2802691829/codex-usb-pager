$cfg = 'C:\Users\28026\.codex\config.toml'
$notify = 'notify = [ "python", "C:\\Users\\28026\\.codex\\hooks\\codex_notify_pager.py" ]'
$deadline = (Get-Date).AddMinutes(3)

while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $cfg) {
        $text = Get-Content -LiteralPath $cfg -Raw
        if ($text -match '(?m)^notify\s*=') {
            $text = [regex]::Replace($text, '(?m)^notify\s*=.*$', $notify)
        } else {
            $text = $notify + "`r`n" + $text
        }
        Set-Content -LiteralPath $cfg -Value $text -Encoding UTF8
    }
    Start-Sleep -Seconds 2
}
