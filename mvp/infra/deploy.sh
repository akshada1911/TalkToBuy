#!/usr/bin/env bash
# Deploy TalkToBuy (T106). Usage, from mvp/:  GCP_PROJECT=<talktobuy-project> ./infra/deploy.sh
#
# Never uses the gcloud default project: GCP_PROJECT must be explicit, and placeholders and
# known-forbidden projects are refused. Tests, the SAFETY SUITE (Constitution II) and the
# generated-types check must pass first, or nothing is deployed.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="${GCP_PROJECT:-}"
REGION="${GCP_LOCATION:-us-central1}"
FORBIDDEN="zeroqueue-503710"
if [[ -z "$PROJECT" || "$PROJECT" == REPLACE_* || " $FORBIDDEN " == *" $PROJECT "* ]]; then
  echo "Refusing to deploy: set GCP_PROJECT to the dedicated TalkToBuy project." >&2; exit 1
fi
UV="uv"; command -v uv >/dev/null || UV="python -m uv"

echo "== Gate: tests, safety suite, generated types =="
$UV run pytest -m "not safety and not live"
$UV run pytest -m safety
$UV run python scripts/gen_types.py --check
npm test

REPO="$REGION-docker.pkg.dev/$PROJECT/talktobuy"
TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%s)"
for svc in session-server demo-store; do
  docker build -f "infra/$svc.Dockerfile" -t "$REPO/$svc:$TAG" .
  docker push "$REPO/$svc:$TAG"
done

SHOP_ORIGIN="${SHOP_ORIGIN:?set SHOP_ORIGIN to the Firebase Hosting origin, e.g. https://<site>.web.app}"
RP_ID="${SHOP_ORIGIN#https://}"

deploy() {  # $1 = service yaml, $2 = image
  IMAGE="$2" PROJECT_ID="$PROJECT" REGION="$REGION" SHOP_ORIGIN="$SHOP_ORIGIN" RP_ID="$RP_ID" \
  STORE_URL="${STORE_URL:-}" SESSION_URL="${SESSION_URL:-}" envsubst < "$1" > "/tmp/$(basename "$1")"
  gcloud run services replace "/tmp/$(basename "$1")" --project "$PROJECT" --region "$REGION"
}
deploy infra/demo-store.service.yaml "$REPO/demo-store:$TAG"
STORE_URL="$(gcloud run services describe talktobuy-demo-store --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"
SESSION_URL="$(gcloud run services describe talktobuy-session-server --project "$PROJECT" --region "$REGION" --format 'value(status.url)' 2>/dev/null || true)"
STORE_URL="$STORE_URL" SESSION_URL="$SESSION_URL" deploy infra/session-server.service.yaml "$REPO/session-server:$TAG"
SESSION_URL="$(gcloud run services describe talktobuy-session-server --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"

echo "== Shop =="
VITE_PUBLIC_SESSION_SERVER_URL="$SESSION_URL" npm run build
(cd infra && firebase deploy --only hosting --project "$PROJECT")
echo "Deployed. Session server: $SESSION_URL  Store: $STORE_URL  Shop: $SHOP_ORIGIN"
