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

### Guideline basis

Default thresholds derive from published guidance, cited in the page footer:

- **[AARC Clinical Practice Guideline — Oxygen in the Acute Care Setting (2022)](https://www.aarc.org/wp-content/uploads/2022/10/cpg-clinical-mangement-adult-o2-acute-settings.pdf)** — SpO₂ target 88–92% for COPD, humidification above 4 L/min
- **[GOLD 2026 Report](https://www.guidelinecentral.com/guideline/2231686/)** — short-acting bronchodilator first line in exacerbation, systemic corticosteroid up to 5 days
- **Royal College of Physicians NEWS2** — score 5–6 urgent review, ≥7 emergency response; Scale 2 for hypercapnic patients

NEWS2 is computed continuously in the background and surfaces only when it is elevated,
so the monitor shows vital signs rather than a score.

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
