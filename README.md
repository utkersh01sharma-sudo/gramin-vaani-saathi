# Gramin Vaani Saathi — AI-Powered Voice Financial Companion for Rural Communities

A voice-first financial assistant for users who may not read, may not have a stable
network, and are disproportionately targeted by financial fraud. Speak in Hindi,
English, Tamil, or Telugu; navigate by icon; get answers spoken back.

> ### ⚠️ This is a simulation
> Every banking and UPI operation runs against a **sandbox ledger inside this
> project's own database**. No real bank, payment service provider, or payment
> network is contacted. The app never asks for and never stores real account
> numbers, card numbers, Aadhaar numbers, PINs, or OTPs. Financial literacy content
> is **educational only** and is not personalised investment or financial advice.

---

## What it does

| Feature | How |
|---|---|
| Voice-first interface | `faster-whisper` ASR → intent model → action → spoken reply |
| Local language support | Hindi, English, Tamil, Telugu, including code-mixed and transliterated speech |
| UPI & banking assistance | Simulated balance, transfers, and history, with spoken confirmation before any money moves |
| Government scheme recommendations | Declarative eligibility rules + semantic search over a curated scheme catalog |
| Financial literacy coaching | Short audio lessons with voice quizzes |
| Scam detection | Custom-trained classifier + explainable rule layer over SMS/call text |
| Offline / low-network mode | Cached app shell, cached reads, and an idempotent action queue that replays on reconnect |
| Icon-based navigation | Large icon tiles with audio labels; no free text on the primary path |

## Models

Three models trained for this project, plus off-the-shelf speech components.

| Model | Base | Task | Metric |
|---|---|---|---|
| **IntentNet** | `google/muril-base-cased` | 14-way intent classification, 4 languages | _pending Day 3_ |
| **ScamNet** | `google/muril-base-cased` + rule features | safe / suspicious / scam | _pending Day 4_ |
| **NoteNet** | MobileNetV3-Small | currency denomination, 7 classes | _pending Day 5_ |
| ASR | `faster-whisper` small/medium | speech → text | _WER pending Day 7_ |

Metrics are reported on a **hand-written** test set
(`ml/data/intent_test_handwritten.jsonl`), not on generated data. Full results:
[`docs/RESULTS.md`](docs/RESULTS.md) _(generated on Day 7)_.

## Architecture

```
PWA (no-build ES modules, service worker, offline action queue)
        │  REST
Django 5 + DRF  ──  Celery workers  ──  Redis
        │                  │
   PostgreSQL         ai/ adapter layer
                   (local in-process  |  remote model server)
```

Models sit behind the adapter interfaces in [`backend/ai/base.py`](backend/ai/base.py),
never imported directly into views. Setting `AI_BACKEND=remote` routes the identical
calls to a separate model server, so scaling out is a config change rather than a
rewrite. Heavy work (ASR, vision) runs in Celery so web workers never block.

## Setup

Requires Python 3.11+ and Node 20+. A CUDA GPU is optional — CPU works, more slowly.

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Linux/macOS: .venv/bin/pip
cp .env.example .env
python backend/manage.py migrate
python backend/manage.py seed_demo
python backend/manage.py runserver
```

Then open <http://localhost:8000/> — Django serves the PWA and the API from the
same origin, so there is no second dev server and no CORS setup. API docs are at
<http://localhost:8000/api/docs/>.

`seed_demo` creates four sandbox identities — **sita**, **ramesh**, **lakshmi**,
and the shop **ramkirana** — all with the password `demo1234`. They hold play
money in your local database. The sign-in screen offers them as one-tap buttons
so a demo does not open on a signup form.

### Trying it without a microphone

Chrome's speech recognition needs a mic and a network. The `☰` button beside the
mic opens a text box that runs the typed sentence through the **same** NLU and
dialog path, which is also the documented fallback for Tamil and Telugu if
server-side ASR proves weak on them. Try:

```
मेरा बैलेंस बताओ
रमेश को पांच सौ रुपये भेज दो
నా బ్యాలెన్స్ చెప్పు
```

### Frontend

`frontend/` is plain HTML, CSS, and ES modules with **no build step** — Django
serves the files directly. The service worker needs origin-root scope and the
project's real complexity is in the model and ledger layers, so a bundler would
add a compile between an edit and a reload without buying anything yet.

Docker (added Day 7):

```bash
docker compose up
```

## Repository layout

```
backend/    Django project: config/, apps/ (8 apps), ai/ (adapter layer)
ml/         dataset generators, training scripts, evaluation
frontend/   PWA: no-build HTML/CSS/ES modules, service worker, icon-first UI
docs/       api.md, RESULTS.md, SDG_MAPPING.md, DEMO.md
```

## SDG alignment

- **SDG 1 (No Poverty)** — surfaces welfare schemes people are entitled to but unaware of
- **SDG 8 (Decent Work)** — credit and micro-enterprise scheme discovery
- **SDG 10 (Reduced Inequalities)** — voice and icon access for non-literate users in their own language
- **SDG 16 (Peace, Justice, Strong Institutions)** — explainable fraud detection and a path to report it

Detail: [`docs/SDG_MAPPING.md`](docs/SDG_MAPPING.md).

## License

Academic project. See [`docs/api.md`](docs/api.md) for the API contract.
