# Deploy TalkToBuy from Windows (T106). Usage, from mvp/:
#   $env:GCP_PROJECT = '<talktobuy-project>'; $env:SHOP_ORIGIN = 'https://<site>.web.app'; ./infra/deploy.ps1
# Same gates as deploy.sh: explicit project only (never the gcloud default), tests + SAFETY SUITE +
# generated-types check must pass before anything is deployed.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$project = $env:GCP_PROJECT
$region = if ($env:GCP_LOCATION) { $env:GCP_LOCATION } else { 'us-central1' }
$forbidden = @('zeroqueue-503710')
if (-not $project -or $project.StartsWith('REPLACE_') -or $forbidden -contains $project) {
  throw 'Refusing to deploy: set GCP_PROJECT to the dedicated TalkToBuy project.'
}
if (-not $env:SHOP_ORIGIN) { throw 'Set SHOP_ORIGIN to the Firebase Hosting origin, e.g. https://<site>.web.app' }
$shopOrigin = $env:SHOP_ORIGIN
$rpId = $shopOrigin -replace '^https://', ''

function Check { param([scriptblock]$Cmd) & $Cmd; if ($LASTEXITCODE) { throw "Gate failed: $Cmd" } }
Write-Host '== Gate: tests, safety suite, generated types =='
Check { python -m uv run pytest -m 'not safety and not live' }
Check { python -m uv run pytest -m safety }
Check { python -m uv run python scripts/gen_types.py --check }
Check { npm test }

$repo = "$region-docker.pkg.dev/$project/talktobuy"
$tag = (git rev-parse --short HEAD 2>$null); if (-not $tag) { $tag = [int][double]::Parse((Get-Date -UFormat %s)) }
foreach ($svc in 'session-server', 'demo-store') {
  Check { docker build -f "infra/$svc.Dockerfile" -t "$repo/${svc}:$tag" . }
  Check { docker push "$repo/${svc}:$tag" }
}

function Deploy-Service { param([string]$Yaml, [hashtable]$Vars)
  $text = Get-Content $Yaml -Raw
  foreach ($k in $Vars.Keys) { $text = $text.Replace('${' + $k + '}', [string]$Vars[$k]) }
  $out = Join-Path $env:TEMP (Split-Path $Yaml -Leaf); Set-Content $out $text
  Check { gcloud run services replace $out --project $project --region $region }
}
function Get-Url { param([string]$Name)
  gcloud run services describe $Name --project $project --region $region --format 'value(status.url)' 2>$null
}

$common = @{ PROJECT_ID = $project; REGION = $region; SHOP_ORIGIN = $shopOrigin; RP_ID = $rpId }
Deploy-Service 'infra/demo-store.service.yaml' ($common + @{ IMAGE = "$repo/demo-store:$tag" })
$storeUrl = Get-Url 'talktobuy-demo-store'
$sessionUrl = Get-Url 'talktobuy-session-server'
Deploy-Service 'infra/session-server.service.yaml' ($common + @{ IMAGE = "$repo/session-server:$tag"; STORE_URL = $storeUrl; SESSION_URL = $sessionUrl })
$sessionUrl = Get-Url 'talktobuy-session-server'

Write-Host '== Shop =='
$env:VITE_PUBLIC_SESSION_SERVER_URL = $sessionUrl
Check { npm run build }
Push-Location infra; try { Check { firebase deploy --only hosting --project $project } } finally { Pop-Location }
Write-Host "Deployed. Session server: $sessionUrl  Store: $storeUrl  Shop: $shopOrigin"
