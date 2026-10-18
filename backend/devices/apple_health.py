"""Apple Health / Apple Watch data -> daily HRV, nights of sleep and workouts.

Two inputs, one result (`HealthBatch`):
  - the "Export All Health Data" file from the iPhone Health app (export.zip / export.xml),
    parsed as a stream with defusedxml (no entity expansion, no external entities)
  - a JSON payload from an iPhone Shortcut (or a future native app), see `HealthPayload`

Apple Watch measures HRV as SDNN (ms), not RMSSD. We store ln(SDNN) as metric "sdnn" and
the readiness score only compares it with the player's own SDNN baseline.
"""

from __future__ import annotations

import math
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import IO

from defusedxml.ElementTree import iterparse
from pydantic import BaseModel, Field

HRV = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
SLEEP = "HKCategoryTypeIdentifierSleepAnalysis"
HEART_RATE = "HKQuantityTypeIdentifierHeartRate"
MORNING_END_HOUR = 10  # HRV samples before 10:00 describe last night's recovery best
NIGHT_CUTOFF_HOUR = 18  # sleep ending before 18:00 belongs to that morning's "night of"
MAX_UNCOMPRESSED = 3 * 1024**3  # export.xml larger than this is refused (zip bomb guard)
WORKOUT_DEFAULT_RPE = {"soccer": 6, "running": 5, "functionalstrengthtraining": 6, "traditionalstrengthtraining": 6,
                       "highintensityintervaltraining": 7, "cycling": 5, "walking": 2, "yoga": 2}  # fmt: skip


class ExportError(ValueError):
    pass


# --------------------------------------------------------------------------- normalised batch


@dataclass
class Workout:
    id: str
    start: datetime
    minutes: float
    kind: str
    avg_hr: float | None = None


@dataclass
class HealthBatch:
    hrv_sdnn: dict[date, float] = field(default_factory=dict)  # daily SDNN in ms
    sleep_hours: dict[date, float] = field(default_factory=dict)  # by "night of" (the morning)
    workouts: list[Workout] = field(default_factory=list)


def _dt(s: str) -> datetime:
    """Apple's export format '2026-10-18 07:12:03 +0200', or ISO 8601 from Shortcuts."""
    s = s.strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))


def night_of(end: datetime) -> date:
    return end.date() if end.hour < NIGHT_CUTOFF_HOUR else end.date() + timedelta(days=1)


def merge_hours(intervals: list[tuple[datetime, datetime]]) -> float:
    """Total hours covered, counting overlaps once (iPhone and Watch both record sleep)."""
    total, cur_s, cur_e = 0.0, None, None
    for s, e in sorted(intervals):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += (cur_e - cur_s).total_seconds()
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += (cur_e - cur_s).total_seconds()
    return total / 3600


def daily_hrv(samples: list[tuple[datetime, float]]) -> dict[date, float]:
    """Mean of the morning samples (before 10:00) per day, else the day's mean."""
    by_day: dict[date, list[tuple[datetime, float]]] = defaultdict(list)
    for t, v in samples:
        if v > 0:
            by_day[t.date()].append((t, v))
    out = {}
    for d, vals in by_day.items():
        morning = [v for t, v in vals if t.hour < MORNING_END_HOUR]
        use = morning or [v for _, v in vals]
        out[d] = sum(use) / len(use)
    return out


# --------------------------------------------------------------------------- Health app export


def parse_export(source: IO[bytes], since: date) -> HealthBatch:
    """Stream-parse export.xml, keeping only data from `since` on."""
    hrv: list[tuple[datetime, float]] = []
    sleep: dict[date, list[tuple[datetime, datetime]]] = defaultdict(list)
    workouts: list[Workout] = []
    in_workout: Workout | None = None
    for event, el in iterparse(source, events=("start", "end")):
        tag = el.tag
        if event == "start":
            if tag == "Workout":
                start = _dt(el.get("startDate", ""))
                if start.date() >= since:
                    minutes = float(el.get("duration") or 0)
                    if (el.get("durationUnit") or "min") == "s":
                        minutes /= 60
                    kind = (el.get("workoutActivityType") or "").replace("HKWorkoutActivityType", "").lower()
                    in_workout = Workout(id=f"{el.get('sourceName', '')}|{el.get('startDate')}", start=start, minutes=minutes, kind=kind)
            continue
        if tag == "Record":
            rtype = el.get("type")
            if rtype in (HRV, SLEEP):
                start = _dt(el.get("startDate", ""))
                if start.date() >= since - timedelta(days=1):
                    if rtype == HRV:
                        hrv.append((start, float(el.get("value") or 0)))
                    elif "Asleep" in (el.get("value") or ""):
                        end = _dt(el.get("endDate", ""))
                        sleep[night_of(end)].append((start, end))
        elif tag == "WorkoutStatistics" and in_workout is not None and el.get("type") == HEART_RATE:
            avg = el.get("average")
            in_workout.avg_hr = float(avg) if avg else None
        elif tag == "Workout":
            if in_workout is not None:
                workouts.append(in_workout)
            in_workout = None
        if tag in ("Record", "Workout", "ActivitySummary"):
            el.clear()  # keep memory flat on multi-GB exports
    return HealthBatch(
        hrv_sdnn={d: v for d, v in daily_hrv(hrv).items() if d >= since},
        sleep_hours={d: round(merge_hours(iv), 2) for d, iv in sleep.items() if d >= since},
        workouts=workouts,
    )


@contextmanager
def open_export(path: Path) -> Iterator[IO[bytes]]:
    """export.zip (as the Health app shares it) or a bare export.xml; closes everything after."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = [i for i in z.infolist() if i.filename.endswith("export.xml") and not i.filename.endswith("_cda.xml")]
            if not names:
                raise ExportError("No export.xml in this zip: share 'Export All Health Data' from the Health app")
            if names[0].file_size > MAX_UNCOMPRESSED:
                raise ExportError("This export is too large to import")
            with z.open(names[0]) as member:
                yield member
        return
    with path.open("rb") as f:
        head = f.read(512)
        if b"<HealthData" not in head and b"<?xml" not in head:
            raise ExportError("Not an Apple Health export")
        f.seek(0)
        yield f


# --------------------------------------------------------------------------- Shortcut / app JSON


class DaySummary(BaseModel):
    date: date
    hrv_sdnn_ms: float | None = Field(default=None, gt=0, lt=400)
    sleep_hours: float | None = Field(default=None, ge=0, le=16)


class WorkoutIn(BaseModel):
    id: str | None = Field(default=None, max_length=100)
    start: str
    minutes: float = Field(ge=1, le=600)
    type: str = Field(default="other", max_length=60)
    avg_hr: float | None = Field(default=None, gt=30, lt=240)


class HealthPayload(BaseModel):
    """What an iPhone Shortcut (or a future native app) sends: daily summaries and workouts."""

    days: list[DaySummary] = Field(default_factory=list, max_length=90)
    workouts: list[WorkoutIn] = Field(default_factory=list, max_length=300)

    def to_batch(self) -> HealthBatch:
        b = HealthBatch()
        for d in self.days:
            if d.hrv_sdnn_ms is not None:
                b.hrv_sdnn[d.date] = d.hrv_sdnn_ms
            if d.sleep_hours is not None:
                b.sleep_hours[d.date] = d.sleep_hours
        for w in self.workouts:
            start = _dt(w.start)
            kind = w.type.replace("HKWorkoutActivityType", "").replace(" ", "").lower()
            b.workouts.append(Workout(id=w.id or f"shortcut|{w.start}", start=start, minutes=w.minutes, kind=kind, avg_hr=w.avg_hr))
        return b


# --------------------------------------------------------------------------- effort estimate


def estimate_rpe(w: Workout, age: float) -> int:
    """Session effort (RPE 1-10) from average heart rate as a share of the estimated max
    (Tanaka: 208 - 0.7 x age); without heart rate, a default for the activity type."""
    if w.avg_hr:
        share = w.avg_hr / (208 - 0.7 * age)
        return max(1, min(10, round((share - 0.5) * 20)))
    return WORKOUT_DEFAULT_RPE.get(w.kind, 4)


def ln(x: float) -> float:
    return math.log(x)
