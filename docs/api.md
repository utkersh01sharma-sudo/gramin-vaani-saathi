# API Contract (v1)

Frozen on Day 1. The PWA is built against this on Day 6, so shapes here should not
change without updating both sides. Live interactive docs: `/api/docs/`.

**Safety:** every banking and UPI endpoint operates on a simulated ledger in this
project's own database. No real bank, PSP, or payment network is contacted, and no
real account number, card number, Aadhaar number, or bank PIN is ever accepted. No
OTP belonging to a real bank or payment app is ever requested: the one-time codes
below are this project's own, issued and verified locally, and no SMS gateway or
email provider is integrated -- see `POST /api/accounts/otp/request/`.

Auth: `Authorization: Token <token>` on everything except `/api/accounts/otp/*`,
`/api/accounts/register/` and `/api/accounts/login/`.

---

## accounts

Signing up is three calls: request a code, verify it, then register with the
signed token the verification returned. The server keeps no half-signed-up
session -- the token is the whole state, so any replica can serve any of the
three requests.

### `POST /api/accounts/otp/request/`
```json
{"channel": "phone", "destination": "+91 98765 00001"}
```
`channel` is `phone` or `email`. `destination` is normalised server-side (a `+91`
or leading `0` is stripped; email is lowercased).

→ `201 {"challenge_id": "uuid", "channel": "phone", "destination_masked": "******0001",
       "expires_in": 300, "code_length": 6, "resend_in": 30, "delivery": "console",
       "dev_code": "418302"}`

`dev_code` is present only when `OTP_ECHO_IN_RESPONSE` is on, which `dev.py` ties to
DEBUG. **No SMS gateway or email provider is integrated in this project**: the code
is written to the server log, and the email channel additionally goes through
Django's console email backend. Everything else about the flow is real -- codes are
hashed at rest, expire after `OTP_TTL_SECONDS`, are single-use, lock after
`OTP_MAX_ATTEMPTS` wrong guesses, and are rate limited per destination by both a
resend cooldown and an hourly cap.

→ `409 {"error": "already_registered"}` if that contact already has an account
  (checked *before* a code is sent).
→ `429 {"error": "cooldown", "retry_after": 23}` or `{"error": "too_many"}`
→ `400 {"error": "bad_phone" | "bad_email"}`

### `POST /api/accounts/otp/verify/`
```json
{"challenge_id": "uuid", "code": "418302"}
```
→ `200 {"verification_token": "...", "channel": "phone",
       "destination_masked": "******0001", "expires_in": 900}`
→ `400 {"error": "wrong_code", "attempts_remaining": 3}`
→ `400 {"error": "expired" | "locked" | "already_used" | "not_found"}`

### `POST /api/accounts/register/`
```json
{"verification_token": "...", "display_name": "Kamla Devi", "password": "...",
 "language": "hi", "literacy_level": "none"}
```
Phone and email are **not** accepted here; they are read out of the signed token, so
a client cannot verify one number and register a different one. `username` is
optional and derived when omitted (from the name, else the email local part, else
the phone number) because it also becomes the sandbox VPA.

→ `201 {"token": "...", "user": {...}, "profile": {...},
       "account": {"vpa": "kamladevi@sandbox", "balance": "2000.00"}}`
→ `409 {"error": "already_registered"}`
→ `400 {"error": "verification_expired" | "verification_invalid"}`

### `POST /api/accounts/login/`
```json
{"username": "sita", "password": "..."}
```
→ `200 {"token": "...", "user": {...}, "profile": {...}}`

### `GET /api/accounts/me/`
→ `200 {"user": {...}, "profile": {...}, "account": {...}, "contacts": [...]}`

### `PATCH /api/accounts/profile/`
Any subset of the profile fields. These double as scheme-eligibility inputs.
```json
{"language": "ta", "literacy_level": "none", "age": 47, "occupation": "farmer",
 "annual_income": 84000, "land_holding_acres": 1.5, "state": "Tamil Nadu", "is_bpl": true}
```
→ `200 {"profile": {...}}`

---

## voice — the orchestrator

> **Contract change, Day 2.** The Day 1 draft threaded multi-turn state through a
> `session_id`. It does not any more. The pending action is handed back to the
> client and sent up again on the next turn, which keeps every web worker
> stateless — you scale by adding replicas, not by adding sticky sessions. The
> field is `pending`, and it is opaque to the client: echo it back unmodified.

### `POST /api/voice/query/` (multipart)
| field | type | notes |
|---|---|---|
| `audio` | file | webm/ogg/opus/wav/m4a/mp4/mp3/flac from `MediaRecorder`; ≤ 8 MB |
| `language` | string | `hi` \| `en` \| `ta` \| `te`; defaults to the profile language |
| `pending` | string | optional; the previous response's `pending` object, JSON-encoded |

Two response shapes, and the client handles both:

* **with a broker** (`CELERY_TASK_ALWAYS_EAGER=false`) →
  `202 {"status": "queued", "task_id": "...", "poll_url": "/api/voice/result/<id>/"}`
* **without one** (laptop demo, no Redis) the task runs inline →
  `200 <VoiceResult>` with `"status": "done"`

Read `status`, not the HTTP code, to decide whether to poll.

The uploaded recording is deleted as soon as it has been transcribed. Audio of
someone saying a payee's name and an amount is personal data with no further use
once the text exists.

### `POST /api/voice/text/`
Same pipeline, skipping ASR. Used by the text fallback, by the browser's own
speech recognition where it exists, and by tests.
```json
{"text": "मेरा बैलेंस क्या है", "language": "hi", "pending": null}
```
→ `200 <VoiceResult>`

### `POST /api/voice/confirm/`
Explicit tap-to-confirm for users who would rather press the green tick than say
the word. Same code path and same idempotency key as answering "हाँ".
```json
{"pending": {"action": "send_money", "amount": "500", "payee_vpa": "...",
             "idempotency_key": "..."}, "language": "hi"}
```
→ `201 <VoiceResult>`

### `GET /api/voice/result/<task_id>/`
→ `202 {"status": "pending"}` · `200 <VoiceResult>` · `200 {"status": "failed", ...}`

Only meaningful when a broker is configured; in eager mode the result was already
returned by `/api/voice/query/` and is not stored anywhere.

### `VoiceResult`
```json
{
  "status": "done",
  "task_id": "8f1c...",
  "transcript": "मेरा बैलेंस क्या है",
  "language": "hi",
  "intent": "check_balance",
  "confidence": 0.97,
  "asr_confidence": 0.91,
  "audio_seconds": 2.4,
  "slots": {},
  "reply_text": "आपके खाते में 4,250 रुपये हैं।",
  "reply_audio_url": "/media/tts/9f3c....mp3",
  "icon": "wallet",
  "screen": "balance",
  "action_taken": "balance_read",
  "needs_confirmation": false,
  "pending": null,
  "nlu_backend": "muril_intent",
  "low_confidence": false,
  "timings": {"asr_ms": 1180, "nlu_ms": 24, "tts_ms": 310, "total_ms": 1514}
}
```

`reply_audio_url` is `null` when synthesis was unavailable — offline, or the TTS
host unreachable. That is a supported outcome, not an error: the client speaks
`reply_text` with the browser's own voice. The user hears the sentence either
way; only the voice changes.

`nlu_backend` names the implementation that actually answered (`muril_intent` or
`keyword_baseline`), so a demo can never silently report baseline numbers as
model numbers.

`timings` is reported rather than reduced to a pass/fail against the 4 s budget.
A number you cannot see is a number you cannot defend.

`needs_confirmation: true` means the intent moves money. The client speaks
`reply_text` — which is the confirmation question — and sends the user's yes/no
back to `/api/voice/text/` (or `/api/voice/query/`) along with `pending`
unchanged. Nothing is executed on the first utterance.

Low confidence (`asr_confidence < ASR_MIN_CONFIDENCE` or
`confidence < INTENT_MIN_CONFIDENCE`) returns `intent: "unknown"` and
`low_confidence: true` with a reply asking the user to repeat or tap an icon. The
system declines to guess rather than misrouting a payment.

---

## banking

### `GET /api/banking/account/`
→ `200 {"vpa": "sita@sandbox", "masked_account_number": "XXXX0001", "balance": "4250.00", "bank_name": "...", "spent_today": "500.00", "daily_limit": "10000.00"}`

### `POST /api/banking/transfer/`
```json
{"to_vpa": "ramesh@sandbox", "amount": "500.00",
 "idempotency_key": "c1f2...", "note": "", "by_voice": true}
```
→ `201 {"transaction": {...}, "replayed": false}`

`idempotency_key` is generated by the **client** before queueing. Replaying the same
key returns the original transaction with `"replayed": true` and does not move money
again. This is what makes the offline queue safe.

Failures return `201` with `transaction.status = "failed"` and a
`failure_reason` of `insufficient_funds` or `unknown_payee` — a declined transfer is
a recorded ledger event, not an HTTP error.

### `GET /api/banking/transactions/?limit=20`
→ `200 {"results": [{...}]}`

---

## schemes

Every response is already in the requested language (`?lang=hi|en|ta|te`,
default: the profile's language) and already explained.

### `GET /api/schemes/`
All 20 schemes, each with this user's verdict, best first.
→
```json
{"language": "en",
 "summary": {"eligible": 11, "maybe": 0, "total": 20, "ask_next": ["age"]},
 "results": [{"scheme_id": "pm-kisan", "name": "PM-KISAN", "summary": "...", "benefit": "...",
              "category": "farming", "icon": "sprout", "tone": "var(--tone-scheme)",
              "verdict": "eligible|maybe|not_eligible",
              "reasons_met": ["..."], "reasons_unmet": ["..."], "reasons_unknown": ["..."],
              "missing_fields": ["land_holding_acres"]}]}
```

### `GET /api/schemes/search/?q=<what the user said>&lang=hi&k=3`
Multilingual semantic search (multilingual-e5-small + fixture keywords).
→ `200 {"query": "...", "backend": "embedding+keyword|keyword", "results": [<as above> + "score"]}`

### `POST /api/schemes/check/`
What-if check without saving the profile.
```json
{"scheme_id": "nsap-old-age", "facts": {"age": 65}, "lang": "en"}
```
→ `200 {"result": {...}}`, or all schemes when `scheme_id` is omitted.

---

## literacy

### `GET /api/literacy/lessons/?lang=hi`
→ `200 {"completed": 1, "total": 8, "results": [{"id": "upi", "title": "...", "steps": ["...", "...", "..."],
"quiz": [{"q": "...", "options": ["...", "..."]}], "minutes": 1, "icon": "upi",
"progress": {"attempts": 1, "best_score": 3, "total": 3, "completed": true}}]}`

Answers are **not** included; they are graded server-side.

### `POST /api/literacy/lessons/<id>/quiz/`
```json
{"answers": [1, 0, 0], "language": "hi"}
```
→ `200 {"score": 3, "total": 3, "passed": true, "results": [{"correct": true, "answer": 1, "explain": "..."}], "progress": {...}}`

Passing is two thirds right; progress keeps the best score.

---

## fraud

### `POST /api/fraud/check/`
```json
{"text": "Dear customer your KYC is expired, update at bit.ly/xy", "language": "en"}
```
→
```json
{"label": "safe|suspicious|scam", "score": 0.98,
 "headline": "This is a scam",
 "reasons": ["It threatens that your account will be blocked...", "The link is shortened..."],
 "advice": "Do not reply, do not open the link, do not pay anything. Report fraud on 1930.",
 "model_score": 0.99, "rule_score": 0.93, "backend": "scamnet_blend", "language": "en"}
```
`reasons` is never empty for a non-`safe` verdict. Every check is logged.

### `GET /api/fraud/history/` → the caller's last 20 checks.

### `POST /api/fraud/report/`
```json
{"kind": "money_lost|shared_details|message_only", "amount_lost": "5000.00", "language": "hi"}
```
→ `201 {"id": 1, "helpline": "1930", "portal": "https://cybercrime.gov.in", "next_steps": ["...", "...", "..."]}`

The app does not file a complaint and never says it has.

### `POST /api/fraud/ask/`
Search over reviewed fraud-safety answers (fixtures/knowledge.json). Nothing is generated; questions are not stored.
```json
{"text": "क्या बैंक वाले को OTP बताना चाहिए", "language": "hi"}
```
→ `200 {"answered": true, "backend": "embedding+keyword",
"best": {"id": "share-otp", "question": "...", "answer": "...", "icon": "lock", "links": [{"label": "1930", "href": "tel:1930"}], "score": 0.87},
"related": [<same shape>]}`

Below the no-answer threshold: `"answered": false, "best": null`, and `related` holds the near misses.

### `GET /api/fraud/questions/?lang=hi` → suggested questions to show before anything is typed.

---

## vision

The uploaded image is deleted before the response is sent.

### `POST /api/vision/qr/` (multipart: `image`, `language`)
→
```json
{"level": "ok|caution|danger",
 "payee_vpa": "ramkirana@sandbox",
 "payee_name_in_code": "Ram Kirana Store",
 "payee_name_registered": "Ram Kirana Store",
 "amount": null, "is_valid_upi": true, "tamper_score": 0.0,
 "warnings": ["possible_sticker", "unknown_payee", "amount_prefilled", "embedded_url",
              "multiple_qr", "name_mismatch", "malformed_upi", "not_upi", "no_qr_found"],
 "reply_text": "This code belongs to Ram Kirana Store.",
 "can_pay": true}
```
A name inside a QR is whatever its printer chose; when the VPA is not in the
registry, `reply_text` reports it as a claim ("This code says it is for …").

### `POST /api/vision/note/` (multipart: `image`, `language`)
→ `200 {"denomination": 500, "confidence": 0.55, "is_note": true, "confident": false,
"backend": "notenet|colour_heuristic", "reply_text": "..."}`

Below 0.75 confidence the reply tells the user to check the note themselves.

---

## sync — offline queue

### `POST /api/sync/replay/`
Everything confirmed while offline, in one request. The same batch may be sent
any number of times.
```json
{"items": [{"pending": {"action": "send_money", "amount": "500", "payee_vpa": "ramesh@sandbox",
            "payee_name": "Ramesh", "idempotency_key": "tap-…"},
            "language": "hi", "queued_at": 1767225600000}]}
```
→ `200 {"executed": 1, "replayed": 0, "failed": 0,
"results": [{"idempotency_key": "tap-…", "status": "executed|replayed|failed", "detail": "...", "reply_text": "...", "transaction_id": "..."}]}`

---

## Changes from the Day 1 contract

Recorded rather than silently edited, because the frontend was built against both.

| Was | Now | Why |
|---|---|---|
| `GET /schemes/recommend/` + `GET /schemes/` | one `GET /schemes/` with verdicts | Every scheme screen needs the verdict; two calls bought nothing |
| `POST /schemes/search/` | `GET /schemes/search/?q=` | A search is a read; GET is cacheable offline |
| Scheme names as `{"hi": …, "en": …}` | one language per response | The client never needs the other three; it re-fetches on a language change |
| `GET /literacy/.../quiz/` | questions inside the lesson list | One request for the whole screen |
| Reasons as `{code, text: {lang: …}}` | plain strings in the request language | Same reason as above |
| `reply_audio_url` on fraud/vision | not returned | Spoken in the browser; server TTS is used by the voice endpoints only |
| `sync/replay` with generic `actions` | `items` of confirmed `pending` objects | Only transfers are ever queued; quiz answers need the network anyway |
| `GET /sync/snapshot/` | not built | The client caches `me`, `transactions`, `schemes` and `lessons` per language from the normal endpoints |
