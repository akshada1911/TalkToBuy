# Deploying TalkToBuy on Google Cloud Run

Two Cloud Run services in project `talktobuy`, region `us-central1`:

| Service | What runs in it |
|---|---|
| **talktobuy-ui** | nginx serving the built shop app. It proxies `/v1` (voice socket, ticket), `/demo`, `/payment`, `/static` to the backend, so the browser sees one address (needed for the microphone, the voice socket and the fingerprint login). |
| **talktobuy-backend** | One container with the **session server** (Gemini Live, tools, dish planner) and the **demo store** (catalogue, cart, payment), behind a small nginx that sends `/v1/*` to the session server and everything else to the store. |

Gemini (Live voice, Flash, Flash-Lite, embeddings, the recorded greeting) is called from the backend with the
service account `talktobuy-backend@talktobuy.iam.gserviceaccount.com` (role `aiplatform.user`). No keys exist anywhere.

**Live address:** https://talktobuy-ui-949496778375.us-central1.run.app
(the service's other address, `...-3o5mbytdmq-uc.a.run.app`, redirects to it)

## Deploy (or redeploy after a code change)

From anywhere, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File mvp\deployment\deploy.ps1
```

It enables the APIs, creates the image repository and the service account, builds both images in Cloud Build
(no local Docker needed, about 1 to 2 minutes), deploys both services, and runs a smoke test on the live address.

Options: `-SkipTests` (the Python tests run first by default), `-SkipBuild -Tag <tag>` (reuse built images),
`-SkipVerify`.

## What the smoke test checks (`smoke_test.py`)
Shop page, catalogue, product images, delivery slots, voice ticket, the greeting (by name, first audio within
seconds), the dish flow (asks how many people, the list appears), adding to the cart after a yes, and clearing
the cart by voice. Run it alone any time: `.venv\Scripts\python.exe mvp\deployment\smoke_test.py <ui-url>`.

## Settings (`config.ps1`)
Project, region, service names, and the limits for a public link: 5 concurrent voice sessions, 300 sessions a day.

## Things to know
- **One instance of each.** The store keeps carts and orders in its own database, and the session server keeps
  sessions in memory, so the backend runs as exactly one instance (always on, CPU always allocated).
  Restarting it (a redeploy) resets carts, orders and the registered fingerprint. That is fine for a demo.
- **Secrets** (ticket signing key, admin key) are generated on the first deploy into `deployment/.generated/`
  (git-ignored) and set as environment variables. For production, move them to Secret Manager.
- **Greeting recordings** are made when the backend starts (a few seconds) and kept in the container's disk;
  until they are ready the live model says the greeting itself.
- **The first fingerprint** a person uses is registered in the store; the next one is checked against it. After a
  redeploy it registers again.
- **Cost:** two always-on instances (about 2 vCPU + 2 GiB and 1 vCPU + 256 MiB) plus about $0.01 to $0.04 per
  voice session. To stop paying, run `teardown.ps1`.
- **Logs:** `gcloud run services logs read talktobuy-backend --project talktobuy --region us-central1 --limit 100`

## Files
| File | Purpose |
|---|---|
| `deploy.ps1` | The whole deployment, step by step. Safe to run again. |
| `config.ps1` | Names, project, region, limits. |
| `backend.Dockerfile`, `start-backend.sh`, `nginx-backend.conf` | The backend container. |
| `ui.Dockerfile`, `nginx-ui.conf.template` | The UI container. |
| `cloudbuild.yaml`, `.gcloudignore` | Builds both images in Cloud Build and keeps junk out of the upload. |
| `smoke_test.py` | Checks a deployed copy end to end. |
| `teardown.ps1` | Deletes the two services (`-Everything` also removes the repository and service account). |

## Not done here (on purpose)
The dish planner and the safety check still run inside the backend, calling Gemini directly. Moving them to
Agent Engine would be a separate step (see the earlier plan).
