$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Docker could not start the studio. Open Docker Desktop and read the error above.' }
Start-Process 'http://localhost:8787'
