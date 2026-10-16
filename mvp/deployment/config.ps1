# Settings shared by the deployment scripts. No secrets here.
$Project       = "talktobuy"
$Region        = "us-central1"
$ProjectNumber = "949496778375"          # gcloud projects describe talktobuy
$Repo          = "talktobuy"             # Artifact Registry repository
$BackendName   = "talktobuy-backend"     # Cloud Run service 1: session server + demo store (one container)
$UiName        = "talktobuy-ui"          # Cloud Run service 2: the shop app (nginx), proxies API calls to the backend
$BackendSA     = "talktobuy-backend"     # service account the backend runs as

# Cost and abuse limits for a public demo link.
$MaxConcurrentSessions = 5
$DailySessionQuota     = 300

$Registry = "$Region-docker.pkg.dev/$Project/$Repo"
# Cloud Run URLs are predictable, so the backend can be configured with the UI's address before the UI exists
# (the fingerprint login is tied to the UI's domain).
$UiUrlGuess = "https://$UiName-$ProjectNumber.$Region.run.app"
