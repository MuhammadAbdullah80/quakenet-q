# Starts the QuakeNet-Q API on this machine only (127.0.0.1:8000).
# The tunnel agent forwards to this address; the API is never bound to 0.0.0.0.
#
#   powershell -ExecutionPolicy Bypass -File scripts\start_server.ps1
#
# Reads KEY=VALUE lines from .env in the repo root if the file exists (values are not printed).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        $line = $line.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { continue }
        $i = $line.IndexOf("=")
        if ($i -lt 1) { continue }
        $name = $line.Substring(0, $i).Trim()
        $value = $line.Substring($i + 1).Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

if (-not $env:QUAKENET_TOKEN -or $env:QUAKENET_TOKEN.Length -lt 32) {
    Write-Error "QUAKENET_TOKEN is missing or shorter than 32 characters. Copy .env.example to .env and set it."
    exit 1
}

python -m uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
