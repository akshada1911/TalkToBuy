# Settings shared by the deployment scripts. No secrets here.
# The Google Cloud project and the Google account that owns it. Override with $env:TTB_PROJECT / $env:TTB_ACCOUNT.
$Project       = if ($env:TTB_PROJECT) { $env:TTB_PROJECT } else { "project-e4c9b387-60c8-4c1f-901" }
$Account       = if ($env:TTB_ACCOUNT) { $env:TTB_ACCOUNT } else { "akshada.agivant@gmail.com" }
$Region        = "us-central1"
# Looked up from Google (it is part of every Cloud Run address); needs `gcloud auth login` as $Account first.
$ProjectNumber = "$(gcloud projects describe $Project --account $Account --format 'value(projectNumber)' 2>$null)".Trim()
if (-not $ProjectNumber) {
  throw "Cannot read project $Project as $Account. Log in first:  gcloud auth login --account=$Account"
}
$Repo          = "talktobuy"             # Artifact Registry repository
# Optional: set $env:TTB_SUFFIX (e.g. "-v2") to deploy a separate pair of services next to the existing ones.
$Suffix        = "$env:TTB_SUFFIX"
$BackendName   = "talktobuy-backend$Suffix"     # Cloud Run service 1: session server + demo store (one container)
$UiName        = "talktobuy-ui$Suffix"          # Cloud Run service 2: the shop app (nginx), proxies API calls to the backend
$BackendSA     = "talktobuy-backend"     # service account the backend runs as

# Cost and abuse limits for a public demo link.
$MaxConcurrentSessions = 5
$DailySessionQuota     = 300

$Registry = "$Region-docker.pkg.dev/$Project/$Repo"
# Cloud Run URLs are predictable, so the backend can be configured with the UI's address before the UI exists
# (the fingerprint login is tied to the UI's domain).
$UiUrlGuess = "https://$UiName-$ProjectNumber.$Region.run.app"
