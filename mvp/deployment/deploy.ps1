# Deploys TalkToBuy to Google Cloud Run: ONE service for the UI and ONE service for the backend.
#
#   talktobuy-ui       nginx + the built shop app; proxies /v1 /demo /payment /static to the backend
#   talktobuy-backend  the session server (voice + tools) and the demo store, in one container
#
# Run from anywhere:   powershell -ExecutionPolicy Bypass -File mvp\deployment\deploy.ps1
# Options:  -SkipTests  -SkipBuild (reuse the last built images with -Tag)  -SkipVerify  -Tag <tag>
param(
  [switch]$SkipTests,
  [switch]$SkipBuild,
  [switch]$SkipVerify,
  [string]$Tag = ""
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\config.ps1"
$Mvp = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Mvp

function Run {
  param([scriptblock]$Command, [string]$What)
  # gcloud prints progress on stderr; Windows PowerShell would treat that as an error, so judge by the exit code only.
  $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  & $Command
  $code = $LASTEXITCODE
  $ErrorActionPreference = $old
  if ($code -ne 0) { throw "Failed: $What" }
}
function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Exists {  # true if the command succeeds (used for "does it already exist?")
  param([scriptblock]$Command)
  $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  & $Command *> $null
  $ok = ($LASTEXITCODE -eq 0)
  $ErrorActionPreference = $old
  return $ok
}
function New-Secret {
  $b = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
  return (([BitConverter]::ToString($b)) -replace "-", "").ToLower()
}
function Describe-Url($name) {
  $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  $url = (gcloud run services describe $name --project $Project --region $Region --format "value(status.url)" 2>$null)
  $ErrorActionPreference = $old
  return "$url".Trim()
}

# ---------------------------------------------------------------- 1. preflight
Step "1. Preflight (project $Project, region $Region)"
Run { gcloud config set account $Account --quiet } "switch to $Account"
Run { gcloud config set project $Project --quiet } "set project"
$account = "$(gcloud config get-value account 2>$null)".Trim()
Write-Host "gcloud account: $account"
$billing = "$(gcloud billing projects describe $Project --format 'value(billingEnabled)' 2>$null)".Trim()
if ($billing -ne "True") { throw "Billing is not enabled on $Project." }
Write-Host "billing: enabled"

# ---------------------------------------------------------------- 2. tests
if (-not $SkipTests) {
  Step "2. Tests (the deploy stops if any fail)"
  $py = Join-Path $Mvp ".venv\Scripts\python.exe"
  if (Test-Path $py) {
    Run { & $py -m pytest services/session-server/tests -q } "session server tests"
    Run { & $py -m pytest services/demo-store -q } "demo store tests"
  } else {
    Write-Host "no .venv found; skipping the Python tests" -ForegroundColor Yellow
  }
} else { Step "2. Tests skipped" }

# ---------------------------------------------------------------- 3. APIs
Step "3. Enable the Google Cloud APIs"
Run { gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com aiplatform.googleapis.com texttospeech.googleapis.com iam.googleapis.com logging.googleapis.com --project $Project } "enable APIs"

# ---------------------------------------------------------------- 4. image registry
Step "4. Artifact Registry repository '$Repo'"
if (-not (Exists { gcloud artifacts repositories describe $Repo --location $Region --project $Project })) {
  Run { gcloud artifacts repositories create $Repo --repository-format docker --location $Region --project $Project --description "TalkToBuy images" } "create repository"
} else { Write-Host "already exists" }

# ---------------------------------------------------------------- 5. identity
Step "5. Service account for the backend, and build permissions"
$backendSaEmail = "$BackendSA@$Project.iam.gserviceaccount.com"
if (-not (Exists { gcloud iam service-accounts describe $backendSaEmail --project $Project })) {
  Run { gcloud iam service-accounts create $BackendSA --display-name "TalkToBuy backend" --project $Project } "create service account"
  Start-Sleep -Seconds 8
} else { Write-Host "service account exists" }
# Gemini (voice, planner, embeddings, speech) is called with this account's identity: no keys anywhere.
foreach ($role in @("roles/aiplatform.user", "roles/logging.logWriter")) {
  Run { gcloud projects add-iam-policy-binding $Project --member "serviceAccount:$backendSaEmail" --role $role --condition None --quiet *> $null } "grant $role"
}
# Cloud Build (new projects build as the default compute account).
$buildSa = "$ProjectNumber-compute@developer.gserviceaccount.com"
foreach ($role in @("roles/cloudbuild.builds.builder", "roles/artifactregistry.writer", "roles/logging.logWriter", "roles/storage.objectViewer")) {
  Run { gcloud projects add-iam-policy-binding $Project --member "serviceAccount:$buildSa" --role $role --condition None --quiet *> $null } "grant $role to the build account"
}

# ---------------------------------------------------------------- 6. secrets (generated once, kept locally)
Step "6. Secrets for tickets and the admin key (generated once)"
$genDir = Join-Path $PSScriptRoot ".generated"
New-Item -ItemType Directory -Force $genDir | Out-Null
$secretFile = Join-Path $genDir "secrets.json"
if (Test-Path $secretFile) {
  $secrets = Get-Content $secretFile -Raw | ConvertFrom-Json
  Write-Host "reusing $secretFile"
} else {
  $secrets = [pscustomobject]@{ ticket = (New-Secret); admin = (New-Secret) }
  $secrets | ConvertTo-Json | Set-Content -Encoding ascii $secretFile
  Write-Host "created $secretFile (git-ignored)"
}

# ---------------------------------------------------------------- 7. build
if (-not $Tag) { $Tag = (Get-Date -Format "yyyyMMdd-HHmmss") }
if (-not $SkipBuild) {
  Step "7. Build both images in Cloud Build (tag $Tag), about 4 to 8 minutes"
  Run { gcloud builds submit . --project $Project --config deployment/cloudbuild.yaml --ignore-file deployment/.gcloudignore --substitutions "_REGISTRY=$Registry,_TAG=$Tag" } "cloud build"
} else { Step "7. Build skipped (using tag $Tag)" }

# ---------------------------------------------------------------- 8. backend
Step "8. Deploy the backend ($BackendName)"
$uiHostGuess = $UiUrlGuess -replace "^https://", ""
$backendEnv = @(
  "GCP_PROJECT=$Project", "GCP_LOCATION=$Region",
  "STORE_BASE_URL=http://127.0.0.1:3000",
  "SESSION_SERVER_URL=$UiUrlGuess", "SHOP_ORIGIN=$UiUrlGuess", "WEBAUTHN_RP_ID=$uiHostGuess",
  "MEDIA_MODE_DEFAULT=audio_only", "STATE_BACKEND=memory", "SEARCH_MODE=live",
  "DEMO_TICKETS_ENABLED=true", "MAX_CONCURRENT_SESSIONS=$MaxConcurrentSessions", "DAILY_SESSION_QUOTA=$DailySessionQuota",
  "TICKET_SIGNING_SECRET=$($secrets.ticket)", "DEMO_ADMIN_KEY=$($secrets.admin)",
  "GREETING_CACHE_DIR=/tmp/greetings"
) -join "@"
# One instance: the store keeps carts in its own database and the session server keeps sessions in memory.
Run {
  gcloud run deploy $BackendName --project $Project --region $Region `
    --image "$Registry/backend:$Tag" --service-account $backendSaEmail `
    --allow-unauthenticated --port 8080 --cpu 2 --memory 2Gi --no-cpu-throttling `
    --min-instances 1 --max-instances 1 --concurrency 40 --timeout 3600 --session-affinity `
    --set-env-vars "^@^$backendEnv" --quiet
} "deploy backend"
$backendUrl = Describe-Url $BackendName
$backendHost = $backendUrl -replace "^https://", ""
Write-Host "backend: $backendUrl"

# ---------------------------------------------------------------- 9. UI
Step "9. Deploy the UI ($UiName)"
Run {
  gcloud run deploy $UiName --project $Project --region $Region `
    --image "$Registry/ui:$Tag" --allow-unauthenticated --port 8080 --cpu 1 --memory 256Mi `
    --min-instances 1 --max-instances 1 --concurrency 80 --timeout 3600 `
    --set-env-vars "BACKEND_HOST=$backendHost,CANONICAL_HOST=$uiHostGuess" --quiet
} "deploy ui"
# The address people use. The service's other address redirects here, so the fingerprint login always matches.
$uiUrl = $UiUrlGuess
Write-Host "ui: $uiUrl"

# ---------------------------------------------------------------- 10. verify
if (-not $SkipVerify) {
  Step "10. Smoke test on the live URL (about 1 to 2 minutes, uses a little Gemini)"
  $py = Join-Path $Mvp ".venv\Scripts\python.exe"
  if (-not (Test-Path $py)) { $py = "python" }
  Start-Sleep -Seconds 20   # let the backend finish starting and record the greeting
  Run { & $py (Join-Path $PSScriptRoot "smoke_test.py") $uiUrl } "smoke test"
}

Write-Host ""
Write-Host "DEPLOYED" -ForegroundColor Green
Write-Host "  Open this:  $uiUrl"
Write-Host "  Backend:    $backendUrl"
Write-Host "  Logs:       gcloud run services logs read $BackendName --project $Project --region $Region --limit 100"
