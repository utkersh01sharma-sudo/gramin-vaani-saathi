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

### `POST /api/voice/query/` (multipart)
| field | type | notes |
|---|---|---|
| `audio` | file | webm/ogg/wav from `MediaRecorder` |
| `language` | string | `hi` \| `en` \| `ta` \| `te`; defaults to the profile language |
| `session_id` | string | optional; carries multi-turn confirmation state |

→ `202 {"task_id": "..."}`

### `POST /api/voice/text/`
Same pipeline, skipping ASR. Used by the text fallback and by tests.
```json
{"text": "मेरा बैलेंस क्या है", "language": "hi", "session_id": "..."}
```
→ `200 <VoiceResult>`

### `GET /api/voice/result/<task_id>/`
→ `200 {"status": "pending"}` or `200 <VoiceResult>`

### `VoiceResult`
```json
{
  "status": "done",
  "transcript": "मेरा बैलेंस क्या है",
  "language": "hi",
  "asr_confidence": 0.91,
  "intent": "check_balance",
  "intent_confidence": 0.97,
  "slots": {"amount": null, "person": null},
  "needs_confirmation": false,
  "confirmation_prompt": null,
  "action_taken": "balance_read",
  "reply_text": "आपके खाते में 4,250 रुपये हैं।",
  "reply_audio_url": "/media/tts/9f3c...mp3",
  "icon": "wallet",
  "data": {"balance": "4250.00"},
  "latency_ms": 2840
}
```

`needs_confirmation: true` means the intent moves money. The client must speak
`confirmation_prompt` and send the user's yes/no back on `/api/voice/text/` with the
same `session_id`. Nothing is executed on the first utterance.

Low confidence (`asr_confidence < 0.45` or `intent_confidence < 0.55`) returns
`intent: "unknown"` with a reply asking the user to repeat or tap an icon. The
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

### `GET /api/schemes/`
→ `200 {"results": [{"code": "pm_kisan", "name": {"hi": "...", "en": "..."}, "category": "...", "benefit_summary": {...}}]}`

### `GET /api/schemes/recommend/`
Runs the eligibility rules against the caller's profile.
→ `200 {"results": [{"scheme": {...}, "verdict": "eligible|maybe|not_eligible", "reasons": [{"rule": "age >= 18", "passed": true, "explanation": {"hi": "...", "en": "..."}}], "score": 0.92}]}`

### `POST /api/schemes/search/`
Semantic search, so a natural sentence finds the right scheme.
```json
{"query": "मुझे खेती के लिए पैसा चाहिए", "language": "hi", "top_k": 5}
```
→ `200 {"results": [{"scheme": {...}, "similarity": 0.71, "verdict": "eligible"}]}`

---

## literacy

### `GET /api/literacy/lessons/?language=hi`
→ `200 {"results": [{"code": "what_is_upi", "title": "...", "body": "...", "audio_url": "...", "duration_s": 48, "completed": false}]}`

### `GET /api/literacy/lessons/<code>/quiz/`
→ `200 {"questions": [{"id": 1, "prompt": "...", "options": [{"id": "a", "text": "...", "icon": "..."}]}]}`

### `POST /api/literacy/lessons/<code>/quiz/`
```json
{"answers": {"1": "a", "2": "c", "3": "b"}}
```
→ `200 {"score": 2, "total": 3, "passed": true, "feedback": [...]}`

---

## fraud

### `POST /api/fraud/check/`
```json
{"text": "Dear customer your KYC is expired click http://bit.ly/xy to update",
 "language": "en", "source": "sms"}
```
→
```json
{
  "label": "scam",
  "score": 0.96,
  "model_score": 0.97,
  "rule_score": 0.93,
  "reasons": [
    {"code": "asks_for_link", "text": {"hi": "यह संदेश एक अनजान लिंक खोलने को कहता है।", "en": "This message asks you to open an unknown link."}},
    {"code": "url_shortener", "text": {"hi": "लिंक छोटा किया गया है ताकि असली पता छिपे।", "en": "The link is shortened to hide its real address."}}
  ],
  "advice": {"hi": "इस लिंक को न खोलें...", "en": "Do not open this link..."},
  "reply_audio_url": "/media/tts/....mp3"
}
```

`reasons` is mandatory, never empty for a non-`safe` verdict: a non-literate user
cannot audit a score, so the verdict has to be explainable in one spoken sentence.

### `POST /api/fraud/report/`
```json
{"description": "...", "amount_lost": "5000.00", "channel": "call"}
```
→ `201 {"report_id": "...", "next_steps": [...], "helpline": "1930"}`

---

## vision

### `POST /api/vision/qr/` (multipart: `image`)
→
```json
{
  "decoded": true,
  "payee_vpa": "ramkirana@sandbox",
  "payee_name": "Ram Kirana Store",
  "amount": 250.0,
  "is_valid_upi": true,
  "is_known_payee": true,
  "tamper_score": 0.08,
  "warnings": [],
  "reply_text": "यह QR राम किराना स्टोर का है, 250 रुपये।",
  "reply_audio_url": "/media/tts/....mp3"
}
```
`tamper_score > 0.5` adds a `qr_possibly_overlaid` warning — the sticker-over-sticker
scam seen at rural shop counters.

### `POST /api/vision/note/` (multipart: `image`)
→ `200 {"is_note": true, "denomination": 500, "confidence": 0.97, "reply_text": "यह पांच सौ रुपये का नोट है।", "reply_audio_url": "..."}`

Below the confidence floor: `{"is_note": false, "denomination": null, "reply_text": "मुझे नोट साफ नहीं दिखा, फिर से दिखाइए।"}`. Guessing a
denomination for someone who cannot read one is worse than admitting uncertainty.

---

## sync — offline queue

### `POST /api/sync/replay/`
Batch replay of everything queued while offline. Idempotency keys make it safe to
send the same batch more than once.
```json
{"actions": [
  {"kind": "transfer", "idempotency_key": "c1f2...", "payload": {"to_vpa": "...", "amount": "500.00"}},
  {"kind": "quiz_submit", "idempotency_key": "a7b1...", "payload": {...}}
]}
```
→ `200 {"results": [{"idempotency_key": "c1f2...", "status": "applied|replayed|failed", "detail": {...}}]}`

### `GET /api/sync/snapshot/`
One call that fills the offline cache: profile, balance, recent transactions,
schemes, and lessons.
→ `200 {"generated_at": "...", "profile": {...}, "account": {...}, "transactions": [...], "schemes": [...], "lessons": [...]}`
