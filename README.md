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

### Guideline basis

Default thresholds derive from published guidance, cited in the page footer:

- **[AARC Clinical Practice Guideline — Oxygen in the Acute Care Setting (2022)](https://www.aarc.org/wp-content/uploads/2022/10/cpg-clinical-mangement-adult-o2-acute-settings.pdf)** — SpO₂ target 88–92% for COPD, humidification above 4 L/min
- **[GOLD 2026 Report](https://www.guidelinecentral.com/guideline/2231686/)** — short-acting bronchodilator first line in exacerbation, systemic corticosteroid up to 5 days
- **Royal College of Physicians NEWS2** — score 5–6 urgent review, ≥7 emergency response; Scale 2 for hypercapnic patients
- **Cardioselective β-blockers in COPD** — safe and not to be withheld: [BICS trial](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9009490/), [CHEST 2024 review](https://journal.chestnet.org/article/S0012-3692(24)04927-4/fulltext)
- **ESC heart failure guidance** — weight gain > 2 kg in 3 days → increase diuretic per the patient's plan ([flexible diuretic regimens evidence check](https://aci.health.nsw.gov.au/__data/assets/pdf_file/0010/958483/ACI-Flexible-Diuretic-Regimens-Evidence-Check.pdf))
- **[2025 AHA/ACC hypertension guideline](https://www.jacc.org/doi/10.1016/j.jacc.2025.07.010)** — BP > 180/120 without organ damage → intensify oral therapy as an outpatient, no acute lowering

NEWS2 is computed continuously in the background and surfaces only when it is elevated,
so the monitor shows vital signs rather than a score.

## Testing with a real Apple Watch

The demo can take live readings instead of simulated ones. Nothing is installed on the
watch: readings already flow Watch → iPhone Health app. A Shortcut on the iPhone sends
them to a small bridge on your Mac, and the demo page picks them up from there.

1. **Start the bridge** (it also serves the site):
   ```bash
   python3 watch_bridge.py
   ```
   It prints your Mac's address, e.g. `http://192.168.1.20:8734`. Click *Allow* if macOS
   asks about incoming connections. The iPhone and the Mac must be on the same Wi-Fi.
2. **Open the demo through it** — `http://<that address>/demo.html`, on the Mac or on
   the iPhone itself — and press **Connect Apple Watch** in the header. The AI panel now
   shows the exact ingest URL it is waiting on; the clock switches to real time.
3. **Sanity-check without the phone first**: open
   `http://<address>/ingest?hr=128&spo2=94` in any browser tab. Within a few seconds the
   heart-rate tile reads 128 with an *Apple Watch* source label, and the standing orders
   treat it like any other reading (set a rule's "for N min" to 1 to see it fire quickly).
4. **Build the Shortcut on the iPhone** — Shortcuts app → **+** → name it *Riati Sync*:
   1. *Find Health Samples* — Type: **Heart Rate** · Sort by: Start Date · Order: Latest First · Limit: 1
   2. *Get Details of Health Sample* — **Value** (of the samples above)
   3. *Find Health Samples* — Type: **Blood Oxygen Saturation** · Latest First · Limit: 1
   4. *Get Details of Health Sample* — **Value**
   5. *Text* — `http://<address>/ingest?hr=` *(first Value)* `&spo2=` *(second Value)*
   6. *Get Contents of URL* — the Text above (GET is fine)

   Allow Health access when prompted, then run it. The tiles update on the next poll.
5. **Stream during a demo**: wrap steps 1–6 in *Repeat 30 times* with *Wait 60 seconds*
   at the end. Start a workout (Other) on the watch: it then records heart rate every
   few seconds instead of every few minutes, so each run sends a fresh value.

Accepted fields: `hr`, `spo2`, `rr`, `sbp`, `dbp`, `temp`, `wt` (kg — absolute, or as a
change from the 78 kg dry weight), `borg`, `steps`. A Bluetooth cuff and a smart scale
that write to Apple Health can be sent the same way (`sbp`, `dbp`, `wt`). Each field
stays valid for a clinically sensible window (heart rate 15 min, SpO₂ 2 h, blood
pressure and weight 24 h); after that the simulation resumes for that field.

`POST /ingest` with a JSON body does the same — that is what an aggregator service
(Terra, Thryve, Validic) or a native HealthKit companion app would call.

## Running locally

Both pages are static. `demo.html` opens directly in a browser; the landing page needs to
be served over HTTP for its runtime to load:

```bash
python3 -m http.server 8734
```

Then open <http://localhost:8734/Riati.dc.html>.

## Status and scope

Research prototype with a fully simulated patient. **Not a medical device and not clinical
advice.** The physician remains responsible for every order; the AI executes and documents
within signed standing orders and never diagnoses. In an emergency in Saudi Arabia, call 997.

## Academic supervision

Dr Malik A. Althobiani — Assistant Professor, Respiratory Therapy, King Abdulaziz
University; PhD, UCL.
