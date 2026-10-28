# SDG mapping

Each feature is mapped to the specific **target** it serves, not just the goal,
together with the part of the code that does the work and how the claim is
measured. Where a claim is not yet measured in the field, this says so.

| Feature | SDG target | What it changes for the user | Where | Evidence |
|---|---|---|---|---|
| Scheme discovery with per-rule reasons | **1.3** — social protection systems for all, incl. the poor and vulnerable | Finds welfare schemes a person is entitled to but may not know of, and says *why* they qualify or what is missing | `apps/schemes/engine.py`, `fixtures/schemes.json` | Search hit@1 0.875 on 48 hand-written queries ([RESULTS §3](RESULTS.md)) |
| Simulated UPI with spoken confirmation | **1.4** — equal access to financial services, incl. microfinance | Lets someone who cannot read a banking app check a balance and send money by voice, with a mandatory yes/no before money moves | `apps/voice/dialog.py`, `apps/banking/models.py` | p50 0.55 s end-to-end on GPU ([RESULTS §5](RESULTS.md)); idempotency proven by tests |
| MUDRA, PM-SVANidhi, Stand-Up India, PM Vishwakarma in the catalogue | **8.3** — growth of micro and small enterprises, incl. access to financial services | Street vendors, artisans and small shopkeepers find collateral-free credit routes | `fixtures/schemes.json` | Rule coverage; hand-written queries such as "I sell vegetables on a cart and need a small loan" |
| Financial-literacy lessons with graded quizzes | **8.10** — expand access to banking, insurance and financial services for all | Eight one-minute spoken lessons (UPI, OTP safety, interest, saving, passbook, scams, borrowing, insurance) | `apps/literacy/` | Progress tracked per user; quizzes graded server-side |
| Four languages, voice-first, icon + word + audio on every control | **10.2** — social and economic inclusion of all, irrespective of … ethnicity, origin, … or other status | Usable without reading English, or without reading at all | `frontend/`, `ai/local/intent.py` | IntentNet 82.8–87.8% per language on hand-written tests ([RESULTS §1](RESULTS.md)) |
| ScamNet with explained verdicts | **16.4** — significantly reduce illicit financial flows | Stops money leaving before it is stolen: "this message asks for your OTP; no bank ever does" | `ai/local/scam.py`, `ai/local/scam_rules.py` | 0 missed scams on 83 hand-written messages; 7.1% false alarms on genuine ones ([RESULTS §2](RESULTS.md)) |
| Report flow leading with the 1930 helpline | **16.3** — equal access to justice for all | Gives the next three steps in order, fastest-acting first, in the user's language | `apps/fraud/views.py` (`NEXT_STEPS`) | Behavioural; not measured in the field |
| QR verification and sticker detection | **16.4** | Warns before paying a fraudster's QR pasted over a shop's | `ai/local/vision.py` | AUC 0.92 on synthetic posters; field photos still needed ([RESULTS §4](RESULTS.md)) |
| Women-specific schemes (Ujjwala, Sukanya Samriddhi, Matru Vandana, widow pension) surfaced by eligibility | **5.a** — women's equal rights to economic resources and financial services | A woman's profile surfaces schemes in her own name | `fixtures/schemes.json` | Rule coverage |
| Offline queue with exactly-once replay | **9.c** — access to ICT in least-developed areas (supporting) | A transfer confirmed in a dead zone is sent once when signal returns, never twice | `frontend/db.js`, `apps/sync/views.py` | `test_offline_queue_replay_is_idempotent` |

## What this project does not claim

- **No real money moves.** Every transaction is against a sandbox ledger; the
  SDG claims are about the design being ready for a real rail, not about
  impact achieved.
- **Eligibility is a guide, not a decision.** The rules are a simplified,
  teaching-grade model of each scheme. The app says "you appear to qualify",
  never "you qualify", and points to a bank or Common Service Centre.
- **The literacy content is general education**, not personalised financial
  advice.
- **Field validation is missing.** Every model number is on hand-written test
  data, which is honest but is not the same as rural users on cheap phones.
  The next step would be a small usability study with real users in each
  language.
