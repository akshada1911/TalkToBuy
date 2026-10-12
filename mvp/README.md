# TalkToBuy MVP

> An embeddable, Hindi-speaking shopping assistant: a live avatar that listens, looks, plans and
> fills the cart, then checks out after one fingerprint approval in the shop's own payment step.

Spec, plan and tasks: [`specs/001-talktobuy-assistant/`](../specs/001-talktobuy-assistant/).
Constitution: [`.specify/memory/constitution.md`](../.specify/memory/constitution.md).

## Layout

```text
mvp/
├── contracts/            JSON Schemas: single source of truth for tools, domain and widget messages
├── prompts/              Provider-neutral system instruction and rule files (*.md)
├── services/
│   ├── session-server/   Python 3.12 / FastAPI: Live session proxy, nine tools, guards, safety
│   └── demo-store/       Python 3.12 / FastAPI: UCP 2026-08-25 store, AP2 test-mode checkout
├── packages/
│   └── assistant-widget/ TypeScript / Lit: the <talktobuy-assistant> web component
├── apps/
│   └── shop/             TypeScript / React: plain demo shop that embeds the widget
├── infra/                Dockerfiles, Cloud Run service YAML, deploy scripts, Firebase config
└── scripts/              gen_types.py and tasks.ps1 (Windows task runner)
```

## Quick start

```bash
cd mvp
cp .env.example .env            # set GCP_PROJECT to the TalkToBuy project (never the gcloud default)
uv sync --all-packages          # or: python -m uv sync --all-packages
npm install
make test                       # Windows: ./scripts/tasks.ps1 test
make dev                        # Windows: ./scripts/tasks.ps1 dev
```

See [`quickstart.md`](../specs/001-talktobuy-assistant/quickstart.md) for the full run and
rehearsal guide.
