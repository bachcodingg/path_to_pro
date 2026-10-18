# Apple Watch and Apple Health

Apple Health has no web API: health data stays on the iPhone unless something on the
phone sends it. PathToPro supports two ways today and documents a third.

| Route | How | Needs |
| --- | --- | --- |
| **1. iPhone Shortcut** (daily, automatic) | A personal automation sends last night's HRV and sleep (and optionally workouts) to `POST /api/ingest/apple-health` every morning | iPhone + Shortcuts app (built in) |
| **2. Health export upload** | Health app → Export All Health Data → upload the zip on the "Apple Watch" screen | Nothing |
| **3. Native iOS/watchOS app** (roadmap) | HealthKit background delivery, no setup for the player | Mac + Xcode, Apple Developer Program, App Store review |

## What is used

| Apple Health data | PathToPro use |
| --- | --- |
| Heart-rate variability (SDNN, ms) | Readiness battery, HRV component. Daily value = mean of the morning samples (before 10:00), else the day's mean |
| Sleep analysis (asleep stages) | Sleep hours for the night, overlapping iPhone and Watch records counted once; "in bed" and "awake" not counted |
| Workouts (duration, average heart rate) | Training load = estimated effort x minutes. Effort from average HR as a share of estimated max HR (208 - 0.7 x age) |

**SDNN vs RMSSD.** Apple Watch reports SDNN; chest straps and most HRV apps report RMSSD.
The readiness score uses a z-score against the player's own 7-day baseline, so each
record stores its metric and the baseline only uses records of the same metric. A
player switching from a strap to a watch starts a new baseline (7 days).

**No double counting.** Workouts on days that already have a club, coach or manual load
(training log, match diary) are skipped, and each workout is stored once (re-imports and
repeated Shortcut runs are safe). The watch's sleep replaces a typed-in sleep estimate
for the same night.

## Security and privacy

- **Device codes** (`ptp_...`) are write-only: they can send data to one player's
  account and nothing else (no reading, no login). Only a SHA-256 hash is stored; the
  code is shown once. Players can disconnect a device at any time (max 5 per player).
- **Consent** applies per data type: for players under 16 nothing is stored until a
  parent has agreed to HRV, sleep or training data respectively. Skipped types are
  reported back.
- **Export uploads** are parsed as a stream with `defusedxml` (no entity expansion, no
  external entities), limited to 400 MB uploaded and 3 GB unzipped, read for the last
  60 days only, and deleted right after reading.
- Every import is written to the audit log.

## Setting up the Shortcut

The "Apple Watch" screen (watch icon at the top of the player app) creates the device
code and shows the steps. Payload format:

```json
POST /api/ingest/apple-health
Authorization: Bearer ptp_...

{
  "days": [{"date": "2026-10-18", "hrv_sdnn_ms": 48.5, "sleep_hours": 7.6}],
  "workouts": [{"id": "optional-unique-id", "start": "2026-10-17T17:00:00+02:00",
                "minutes": 88, "type": "soccer", "avg_hr": 156}]
}
```

The Shortcut steps were written from Apple's Shortcuts actions (Find Health Samples,
Calculate Statistics, Get Contents of URL) but have **not been tested on an iPhone yet**:
action names and units can differ between iOS versions (e.g. sleep duration in seconds
or minutes). Test with "Run" once and check "Last sync" on the Apple Watch screen.

## Native app (next step)

A small SwiftUI app with HealthKit would remove the setup: request read access to
`heartRateVariabilitySDNN`, `sleepAnalysis`, `workoutType()` and `heartRate`, register
`enableBackgroundDelivery` for HRV and sleep, and post the same payload with the device
code (stored in the Keychain). A watchOS companion could also start a "Football session"
workout and ask for the session RPE on the wrist. This needs a Mac with Xcode, the Apple
Developer Program and App Store review (health data apps need a privacy policy and a
clear purpose string).
