# Demo script — 8 minutes

Rehearse three times on the demo laptop. Record one clean run as a screen
capture: it is the fallback if anything on the day fails.

## Before you start (5 minutes, not on the clock)

```bash
python backend/manage.py seed_demo          # resets nothing; creates demo users if missing
python backend/manage.py runserver 127.0.0.1:8000 --noreload
```

- Open <http://localhost:8000>, pick **English**, sign in as **Sita**.
- Ask one throwaway question ("what is my balance") so every model is loaded
  before the audience is watching — the first request pays ~12 s of loading.
- Browser zoom 100%, window at least 1366×768 so every view fits on screen.
- Have the Swagger page open in a second tab: <http://localhost:8000/api/docs/>.
- Volume up: answers are spoken.

## The run

| Time | Do | Say | They should see |
|---|---|---|---|
| 0:00 | Overview, no clicks | "Rural users may not read, may not have signal, and are the main target of UPI fraud. This is one screen for all of it." | Sidebar: every function with a one-line description. Bento: balance, quick send, fraud check, activity, schemes, lessons, scan. |
| 0:45 | Type **"what is my balance"** in the command bar (or press the mic) | "Voice or typing, four languages, same model." | Spoken + written answer; the app moves to Money & history. |
| 1:15 | Type **"send 50 rupees to Ramesh"** | "Nothing that moves money happens on the first sentence." | Confirmation dialog. Press **No** first: "Cancelled. No money was sent." Then repeat and press **Yes**. |
| 2:15 | Sidebar → Languages: **हिं**. Type **"मुझे खेती के लिए पैसा चाहिए"** | "Hindi, no scheme name mentioned." | Schemes view with PM-KISAN, KCC, crop insurance, each with a verdict and the reason for every rule. |
| 3:15 | Schemes → filter **Not for you** → open one | "Every no comes with the rule that failed." | The exact failing rule, e.g. an age limit. (A brand-new account instead shows most schemes as *need more info*: a missing fact is a question, not a no.) |
| 3:45 | **My details** → change the fact that failed → Save → back to Schemes | "The profile is the only input; nothing is hard-coded per person." | That scheme's verdict changes. Change it back afterwards. |
| 4:15 | Fraud safety. Paste **exactly**: **"मम्मी यह मेरा नया नंबर है, पुराना फ़ोन खराब हो गया। अभी 8000 रुपये इस UPI पर भेज दो, बहुत ज़रूरी है"** | "This scam type was never in training." | Scam, with the reason and "report on 1930". |
| 4:50 | Paste: **"482913 is your OTP. Do not share it with anyone. -SBI"** | "The hard case: a real bank message mentions an OTP too." | Safe, with the reason: it tells you not to share. |
| 5:10 | Codes & notes → **Try a sample: Pasted sticker** | "A fraudster pastes their QR over the shop's." | Danger: payee not in the registry, sticker likely; the claimed shop name is shown as a claim, not a fact. Then **Genuine shop**: "Pay this shop". |
| 6:00 | Learn → "What is UPI?" → answer the quiz | "Graded on the server, explained after every answer." | Score and explanations; progress ring on the overview moves. |
| 6:40 | Show `docs/RESULTS.md` | "Every number is on hand-written test data, including the bad ones." | IntentNet 85.8% vs 71.0% baseline; ScamNet ablation; the Telugu ASR miss. |
| 7:20 | Swagger tab | "Models sit behind an adapter. AI_BACKEND=remote moves them to their own server with no code change." | 25 documented endpoints. |
| 7:45 | Close | SDG 1.3, 1.4, 8.10, 10.2, 16.4 — one line each (see SDG_MAPPING.md). | — |

## Do not improvise the fraud examples

Use the messages above word for word. They are verified. ScamNet is sensitive
to phrasing on scam types it never saw in training: a *shortened* version of
the "new number" message ("मम्मी यह मेरा नया नंबर है, अभी 8000 रुपये भेज दो,
बहुत ज़रूरी है") is scored **safe**. If an examiner asks, that is the honest
answer and a good one — it is listed under Limitations in the README, and the
fix is more varied training data, not a different threshold.

## If something fails

| Symptom | Recovery |
|---|---|
| Mic does nothing | Type instead — same NLU path. Say so; it is the designed fallback. |
| "I did not catch that" | The confidence gate refused. Rephrase, or use the sidebar. Point out that refusing is the safe failure. |
| First answer is slow | Models were not warmed. Say it is the one-time load and carry on. |
| Network down | Toggle offline, confirm a transfer: it is queued. Reconnect: sent exactly once. Turn it into the offline demo. |
| Anything else | Play the recorded run. |
