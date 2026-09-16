# Riati (رئتي) — Respiratory Health Research Platform

Riati is an Arabic-first respiratory health research platform. Participants record daily
symptoms, oxygen saturation, home breathing test results and step count; a published,
clinician-adjustable rule set classifies every reading so the care team sees who needs
attention before a crisis.

Live at [raitie.com](https://raitie.com).

## What's in this repository

| File | Purpose |
| --- | --- |
| `Riati.dc.html` | Landing page — bilingual AR/EN, problem/solution, action-plan zones, trends chart, roadmap, FAQs |
| `demo.html` | Live clinical demo — simulated patient, AI monitor, physician standing orders, scheduled reports |
| `support.js` | Design-canvas runtime for the landing page |
| `bar.md` | Design rules and round-by-round build log |
| `assets/` | Brand assets |

## The live clinical demo

`demo.html` is a self-contained page (no build step — open it in a browser) that
demonstrates the monitoring loop end to end:

1. **Vitals stream in** every simulated minute — SpO₂, heart rate, respiratory rate,
   blood pressure, temperature and Borg dyspnea score — from a simulated COPD patient.
2. **The AI monitor reads every reading** and acts only inside the physician's signed
   standing orders. Every threshold is editable live.
3. **Reports go to the physician** on a set interval (15 min to 2 h), with vitals ranges,
   trends, the zone classification, therapies given and a recommendation.
4. **Therapy response is verified.** Roughly 25 minutes after any therapy the AI checks
   whether it worked. Effective is logged; ineffective raises an alert, and a repeat
   failure raises an alarm with an immediate exception report.

In the default "routine day" scenario the patient is stable most of the time. Brief
episodes flare up, the AI treats them within the standing orders, and the patient
recovers — alarms are rare by design. The "severe" scenario shows the full escalation
chain when therapy fails.

### Cardiac and blood-pressure orders

The standing orders are grouped into **Respiratory** and **Cardiac & blood pressure**.
The cardiac group adds four physician-authorised actions, each guarded by a safety
interlock the AI checks against the live readings before acting:

| Trigger (default, editable) | Action | Interlock |
| --- | --- | --- |
| HR ≥ 115 for 30 min | Bisoprolol 2.5 mg (cardioselective β-blocker) | Withheld if salbutamol was given in the last 60 min (rate is SABA-driven), if systolic < 100, or if HR is already < 100 |
| Weight ≥ +2 kg above dry weight for 60 min | Furosemide 40 mg extra dose | Withheld if systolic < 100 |
| Systolic ≥ 180 for 15 min | Amlodipine 5 mg (intensify oral therapy) | Withheld if systolic already < 150 at dosing time |
| Systolic ≤ 95 for 10 min | Hold the next scheduled antihypertensive dose + notify | — |

A withheld order is explained in the log and re-evaluated after 15 minutes rather than
after the drug's full minimum interval. Every cardiac action gets a response check like
the respiratory ones (β-blocker at 60 min, diuretic at 6 h, amlodipine at 4 h). The
"Cardiac day" scenario exercises the whole set: a sustained tachycardia, fluid gain
through the day, a hypertensive spike and a later post-diuresis dip.

### Patient journal, keyword orders and voice

The patient has a journal: they type how they feel, or record a voice note (transcribed
with the browser's speech recognition), and the simulated patient also writes on its own
when something changes — "I am wheezing and can't catch my breath", "feeling weak and
shaky", "I feel better now".

Every entry is matched against the physician's **symptom keyword orders** (editable list,
Arabic and English words, loose matching that ignores diacritics and alef/ta-marbuta
variants). A match acts at once — the same interlocks and dose limits as any other order —
and sends the patient the physician's instruction, read aloud when speech is on. Defaults:

| Keywords | Action |
| --- | --- |
| dyspnea, short of breath, wheeze, ضيق نفس, صفير … | Salbutamol 2.5 mg neb + inhaler instruction |
| chest pain, ألم في الصدر … | Emergency alarm, physician alerted, sit down / call 997 if it persists |
| dizzy, shaky, sweating, دوخة, رجفة … | Check glucose now → 15-15 rule if under 70 mg/dL |
| fever, chills, حرارة, قشعريرة … | Notify physician, paracetamol and fluids instruction |
| better, improved, تحسنت … | Acknowledge, keep monitoring |

The physician can also record a voice note and send it to the journal.

### Blood glucose

Glucose is a fingerstick, not a continuous stream. The patient checks it **with each report
to the physician** (so every report carries a fresh reading), whenever symptoms suggest a
low, 15 minutes after treating one, and 2-hourly during a steroid course. Between checks
the tile shows the last reading and when the next is due, and the glucose orders act on
each new reading rather than every minute. Defaults follow the ADA Standards of Care: a
reading below 70 mg/dL → 15 g fast carbohydrate and recheck in 15 min (repeated if still
low); below 54 → emergency alarm; two consecutive readings above 300 → notify with the
sick-day plan (ketones, fluids, review steroid dose). The routine day includes one
mid-morning low that the hourly check can miss — the patient's "shaky" message is what
triggers the check, which is the point.

### Guideline basis

Default thresholds derive from published guidance, cited in the page footer:

- **[AARC Clinical Practice Guideline — Oxygen in the Acute Care Setting (2022)](https://www.aarc.org/wp-content/uploads/2022/10/cpg-clinical-mangement-adult-o2-acute-settings.pdf)** — SpO₂ target 88–92% for COPD, humidification above 4 L/min
- **[GOLD 2026 Report](https://www.guidelinecentral.com/guideline/2231686/)** — short-acting bronchodilator first line in exacerbation, systemic corticosteroid up to 5 days
- **Royal College of Physicians NEWS2** — score 5–6 urgent review, ≥7 emergency response; Scale 2 for hypercapnic patients
- **Cardioselective β-blockers in COPD** — safe and not to be withheld: [BICS trial](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9009490/), [CHEST 2024 review](https://journal.chestnet.org/article/S0012-3692(24)04927-4/fulltext)
- **ESC heart failure guidance** — weight gain > 2 kg in 3 days → increase diuretic per the patient's plan ([flexible diuretic regimens evidence check](https://aci.health.nsw.gov.au/__data/assets/pdf_file/0010/958483/ACI-Flexible-Diuretic-Regimens-Evidence-Check.pdf))
- **[2025 AHA/ACC hypertension guideline](https://www.jacc.org/doi/10.1016/j.jacc.2025.07.010)** — BP > 180/120 without organ damage → intensify oral therapy as an outpatient, no acute lowering
- **[ADA Standards of Care in Diabetes 2026, §6](https://diabetesjournals.org/care/article/49/Supplement_1/S132/163927/6-Glycemic-Goals-Hypoglycemia-and-Hyperglycemic)** — hypoglycaemia level 1 < 70 mg/dL, level 2 < 54 mg/dL; 15 g fast carbohydrate and recheck in 15 min; sick-day plan with ketone monitoring

NEWS2 is computed continuously in the background and surfaces only when it is elevated,
so the monitor shows vital signs rather than a score.

## Apple Watch simulator

`watch-sim.html` (served by the pilot at `/watch-sim.html`) stands in for a real Apple
Watch and its iPhone so the web side can be exercised before a watch is paired — and it
uses exactly the path a real device does: it creates a patient account, asks Riati for a
private upload key, optionally shares the record with a care-team code, and then posts
readings to `POST /api/readings` with `Authorization: Bearer <key>` and original
`measured_at` timestamps. Nothing on the server is special-cased for it.

- **The watch** generates a resting heart rate that follows the time of day with
  activity bursts, oxygen spot-checks every 30 minutes and hourly step counts. Scenarios:
  normal day, exacerbation (oxygen drifting to 88%, heart rate up), night. Stream every
  15 s to 5 min, send one reading, or backfill the last 6 hours (90 readings) at once.
- **The phone side** creates the simulated patient and key with one click (kept in that
  browser only), shares with the doctor's code, and can send check-ins ("more
  breathless", "wheezing"…) to the care record. Sharing and check-ins sign the simulated
  patient in and straight out again, so keep the doctor signed in on another browser or
  the phone.

Open it on the Mac at the pilot's secure address (`https://<mac-ip>:8750/watch-sim.html`)
so the readings land in the same records the real portal shows. To run it against a
scratch database instead: `python3 riati_server.py 8760 --data-dir work/sim-test` and open
`http://127.0.0.1:8760/watch-sim.html`.

## Accounts, care views and real Apple Watch testing

The approved action-explanation panel and patient/clinician views are implemented. The local account portal is at `/portal/`. Patient accounts control sharing; the care-team role requires a one-use invitation. Device uploads use revocable, account-specific keys, original measurement dates and duplicate detection. Real observations never enter the simulated medication engine.

**Start here:** double-click `Start Riati.command`, then follow **[WIFI-TEST.md](WIFI-TEST.md)** for the Mac account, iPhone certificate setup and Health Shortcut.

The pilot runs on the same Wi-Fi using local HTTPS. Remote internet access is not deployed. The former unauthenticated `/live` and `/ingest` endpoints return 410. They must not be used with real data.

New files: `riati_server.py` (accounts and scoped APIs), `riati_tls.py` (short-lived local HTTPS), `portal/` (patient and care-team UI), `demo-enhancements.js` / `.css` (simulated explanations and role previews). Private local data is stored under `.riati/`, excluded from Git and HTTP serving.

## Running locally

For the same-Wi-Fi pilot:

```bash
python3 watch_bridge.py 8750 --lan
```

For local-only development:

```bash
python3 watch_bridge.py 8740
```

Open the address printed by the server. `/` serves the landing page, `/portal/` serves accounts, and `/demo.html` remains the simulated clinical demo. A simple static file server cannot provide accounts or receive device readings.

Run isolated backend tests with `python3 -m unittest discover -s tests -v`.

## Status and scope

Research prototype with a fully simulated patient. **Not a medical device and not clinical
advice.** The physician remains responsible for every order; the AI executes and documents
within signed standing orders and never diagnoses. In an emergency in Saudi Arabia, call 997.

## Academic supervision

Dr Malik A. Althobiani — Assistant Professor, Respiratory Therapy, King Abdulaziz
University; PhD, UCL.

## Compare demo layouts

- `/demo.html`: the current redesigned patient and clinician workspace, unchanged.
- `/demo-previous.html`: the layout from before the redesign, restored from the saved snapshot with its own JavaScript and stylesheet. Both pages use the existing demo engine and local standing-order preferences; real observations remain in `/portal/`.
