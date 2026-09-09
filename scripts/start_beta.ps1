# Phase 25 — Start controlled-beta stack (Windows PowerShell)
# Does NOT invent packages/writers. Does NOT claim success without Docker.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "BLOCK: Docker CLI not found. Move to a Docker-capable beta host."
  exit 2
}
if (-not $env:POSTGRES_PASSWORD -or -not $env:AUTH_SECRET) {
  Write-Host "BLOCK: set POSTGRES_PASSWORD and AUTH_SECRET (see .env.example)"
  exit 2
}
if (-not $env:AUTH_REQUIRED) { $env:AUTH_REQUIRED = "true" }

Write-Host "Starting docker compose beta stack..."
docker compose -f docker-compose.beta.yml up -d --build

$api = if ($env:API_PORT) { $env:API_PORT } else { "8000" }
Write-Host "Waiting for health..."
$ok = $false
for ($i = 1; $i -le 60; $i++) {
  try {
    Invoke-RestMethod "http://127.0.0.1:$api/api/health" | Out-Null
    Write-Host "health OK"
    $ok = $true
    break
  } catch {
    Start-Sleep -Seconds 2
  }
}
if (-not $ok) {
  Write-Host "BLOCK: health timeout"
  exit 2
}
try { Invoke-RestMethod "http://127.0.0.1:$api/api/ready" | ConvertTo-Json -Compress } catch {}
try { Invoke-RestMethod "http://127.0.0.1:$api/api/version" | ConvertTo-Json -Compress } catch {}
Write-Host "Stack started. Migrations run on backend start. Next: python scripts/beta_smoke_test.py"
