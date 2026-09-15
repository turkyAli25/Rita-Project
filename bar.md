# Bar — Riati (raitie.com) rebuilt from the investor brief

Reference: raitie.com (theme #4F2D57, logo) + Riati_Investor_Brief_AR.pdf + Riati project.docx.
Live page is JS-rendered and not fetchable, so mechanisms derive from the brief and the brand assets.

## Mechanisms (checkable by looking)
1. Two type sizes per block: one serif display (Newsreader / Amiri) at 3–5x body, one sans body (IBM Plex Sans Arabic). No third size except 12–13px kickers.
2. Palette locked to brand: aubergine #4F2D57 / #2E1834, cream #FAF7F3, lilac #EDE6F2, one gold accent #B8892E. Clinical zones use exactly green #1F6F5B, amber #C9822B, red #A8323E and appear nowhere else.
3. Gold accent appears at most twice per screen (kicker + one glyph).
4. Every section is fully mirrored in Arabic (dir="rtl", Arabic numerals in AR copy, Amiri for Arabic display). Language toggle is one tap, top right.
5. Motion resolves in one direction (up / draw left-to-right); nothing under 400ms; charts draw their line, never fade in.
6. Every chart shows the participant's threshold line and flags the readings that cross it. No chart without a threshold.
7. Nothing decorative: no emoji, no icon grids, no stock illustration. The only imagery is the official logo.

## Pieces in the loop
A. Hero + nav (AR/EN)  B. Trends chart  C. Action-plan zones  D. Account + progress dashboard

## Round log
- Round 1: build in progress.
- Round 2 (2026-09-15): repaired drifted kickers (33/43px → 13px), hero title fixed w/h → fluid clamp, restored hero stats + card note. Built demo.html — standalone live clinical demo: simulated COPD patient (vitals per sim-minute), AI monitor executing editable physician standing orders (O₂ titration per AARC 2022 88–92%, salbutamol per GOLD 2026, NEWS2 escalation per RCP), scheduled + exception reports to physician, therapy-response checks with ineffectiveness alarms, three adjustable scenarios, full AR/EN mirror. Landing page links to it (nav + hero primary CTA).
- Round 3 (2026-09-15): removed the "My progress" dashboard, guest check-in flow, and auth modal from the landing page — superseded by demo.html. Nav "Try the demo" button and hero CTAs now point to demo.html; dead JS (auth/entries/zoneFor) stripped. Pieces in the loop are now: A. Hero + nav (AR/EN)  B. Trends chart  C. Action-plan zones  D. Live clinical demo page.
- Round 4 (2026-09-15): demo.html — NEWS2 tile removed from the live monitor (6 vital tiles only). NEWS2 still computed every minute in the background (rules, reports, escalation unchanged); it surfaces as a pulsing chip on the patient card only when ≥5 / single-param-3 (amber, urgent review) or ≥7 (red, emergency response).
- Round 5 (2026-09-15): demo.html default scenario rebuilt as "routine day": stable baseline (severity ~2) with brief random episodes (~every 3–6 sim-hours, first ~08:40) that the AI treats per standing orders; treatment shortens the episode (fall time scales with responsiveness slider) and the patient recovers to baseline. Alarms/NEWS2 chip now rare by design; escalation chain lives in the severe scenario. Verified 7+ sim-hours: two episodes, both treated effectively, zero alarms, green hourly reports.
- Round 6 (2026-09-15): cardiac & BP standing orders in demo.html. New vitals: BP shown systolic/diastolic, weight vs dry weight. New actions with interlocks: bisoprolol (HR≥115/30 min; withheld ≤60 min after salbutamol, SBP<100, HR<100 — BICS/CHEST), furosemide extra dose (weight ≥+2 kg/60 min; withheld SBP<100 — ESC HF), amlodipine intensify (SBP≥180/15 min; withheld SBP<150 — AHA/ACC 2025), hold next antihypertensive (SBP≤95/10 min). Orders grouped Respiratory / Cardiac & BP; withheld orders re-evaluate in 15 min. New "Cardiac day" scenario. Bug fixed in two places: "never fired" sentinels of −999 (drugLast init and the rule-cooldown fallback in aiTick) blocked any order with a ≥1000-min cooldown until minute 441; both now −99999.
- Round 7 (2026-09-15): real-device path. watch_bridge.py (stdlib, serves the folder + GET/POST /ingest + GET /live, no-store caching). demo.html "Connect Apple Watch" mode: polls /live every 3 s, fresh readings override the simulated fields (hr 15 min, spo2 2 h, BP/weight 24 h), clock switches to real time, speed locked ×1, scenario forced stable, tiles show "Apple Watch · HH:MM" source. README: step-by-step iPhone Shortcut recipe. Bug fixed: end_headers override read self.path before it existed, so any malformed request (an https:// probe from Safari) crashed the handler and the phone saw a dead connection — now getattr with default; verified 0 tracebacks under the same probe. Orders storage key bumped to v3.
