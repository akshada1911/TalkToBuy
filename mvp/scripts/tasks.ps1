# TalkToBuy MVP task runner for Windows (same targets as the Makefile).
# Usage: ./scripts/tasks.ps1 <install|dev|test|test-safety|gen-types|check-generated|lint>
param([Parameter(Mandatory = $true)][ValidateSet('install', 'dev', 'test', 'test-safety', 'gen-types', 'check-generated', 'lint')][string]$Target)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$uv = if (Get-Command uv -ErrorAction SilentlyContinue) { @('uv') } else { @('python', '-m', 'uv') }
function Invoke-Uv {
  param([string[]]$UvArgs)
  $prefix = @($uv | Select-Object -Skip 1)
  & $uv[0] @($prefix + $UvArgs)
  if ($LASTEXITCODE) { exit $LASTEXITCODE }
}

switch ($Target) {
  'install' { Invoke-Uv @('sync', '--all-packages'); npm install; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
  'dev' {
    Write-Host 'Starting store :3000, session server :8080, shop :5173 in new windows'
    Start-Process pwsh -ArgumentList '-NoExit', '-Command', "$($uv -join ' ') run --package demo-store uvicorn demo_store.main:app --port 3000 --reload"
    Start-Process pwsh -ArgumentList '-NoExit', '-Command', "$($uv -join ' ') run --package session-server uvicorn session_server.main:app --port 8080 --reload"
    npm run -w apps/shop dev
  }
  'test' { Invoke-Uv @('run', 'pytest', '-m', 'not safety and not live'); npm test; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
  'test-safety' { Invoke-Uv @('run', 'pytest', '-m', 'safety') }
  'gen-types' { Invoke-Uv @('run', 'python', 'scripts/gen_types.py') }
  'check-generated' { Invoke-Uv @('run', 'python', 'scripts/gen_types.py', '--check') }
  'lint' { Invoke-Uv @('run', 'ruff', 'check', 'services', 'scripts'); Invoke-Uv @('run', 'ruff', 'format', '--check', 'services', 'scripts') }
}
