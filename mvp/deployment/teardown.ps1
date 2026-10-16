# Removes what deploy.ps1 created (the two Cloud Run services and the images). It leaves the enabled APIs,
# the service account and the Artifact Registry repository alone; pass -Everything to remove those too.
param([switch]$Everything)
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\config.ps1"

foreach ($name in @($UiName, $BackendName)) {
  Write-Host "deleting Cloud Run service $name"
  gcloud run services delete $name --project $Project --region $Region --quiet
}
if ($Everything) {
  Write-Host "deleting the image repository $Repo"
  gcloud artifacts repositories delete $Repo --location $Region --project $Project --quiet
  Write-Host "deleting the service account $BackendSA"
  gcloud iam service-accounts delete "$BackendSA@$Project.iam.gserviceaccount.com" --project $Project --quiet
}
Write-Host "done"
