#!/usr/bin/env python3
"""Cron_Decode — parse, validate, and explain cron expressions in plain English.

Cron_Decode takes standard 5-field cron expressions (minute, hour,
day-of-month, month, day-of-week) and translates them into human-readable
English.  Also validates cron syntax and lists upcoming execution times.

Zero dependencies — pure Python stdlib.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta

# ── Named day-of-week mapping ──────────────────────────────────────────
DAY_NAMES: dict[str, int] = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3,
    "thu": 4, "fri": 5, "sat": 6,
}
DAY_NUM_NAMES: list[str] = [
    "Sunday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday",
]
MONTH_NAMES: list[str] = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

# ── Cron field definition ──────────────────────────────────────────────
FIELDS = [
    ("minute",       0,  59),
    ("hour",         0,  23),
    ("day of month", 1,  31),
    ("month",        1,  12),
    ("day of week",  0,   7),   # 0 & 7 both Sunday
]


def _parse_field(raw: str, mini: int, maxi: int, field_name: str) -> set[int]:
    """Parse one cron field into a set of integer values.

    Handles *, */N, N-M, N,M,K, and named days (mon, tue, …).
    """
    result: set[int] = set()
    # Expand named days
    expanded = raw.lower()
    for name, val in DAY_NAMES.items():
        expanded = re.sub(rf"\b{name}\b", str(val), expanded)
    # Split on commas
    parts = [p.strip() for p in expanded.split(",") if p.strip()]
    for part in parts:
        if part == "*":
            result.update(range(mini, maxi + 1))
        elif "/" in part:
            base, _, step_str = part.partition("/")
            if not step_str.isdigit() or int(step_str) < 1:
                raise ValueError(f"invalid step in '{part}' for {field_name}")
            step = int(step_str)
            if base == "*":
                start, end = mini, maxi
            elif "-" in base:
                start, end = _parse_range(base, mini, maxi, field_name)
            elif base.isdigit():
                start = int(base)
                if not (mini <= start <= maxi):
                    raise ValueError(
                        f"{start} out of range [{mini},{maxi}] for {field_name}"
                    )
                end = maxi
            else:
                raise ValueError(f"invalid field part '{part}' for {field_name}")
            result.update(range(start, end + 1, step))
        elif "-" in part:
            start, end = _parse_range(part, mini, maxi, field_name)
            result.update(range(start, end + 1))
        elif part.isdigit():
            val = int(part)
            if not (mini <= val <= maxi):
                raise ValueError(
                    f"{val} out of range [{mini},{maxi}] for {field_name}"
                )
            result.add(val)
        else:
            raise ValueError(f"unrecognized token '{part}' in {field_name}")
    # Day-of-week special: 7 should be treated as 0 (Sunday)
    if field_name == "day of week" and 7 in result:
        result.discard(7)
        result.add(0)
    return result


def _parse_range(part: str, mini: int, maxi: int, field_name: str) -> tuple[int, int]:
    a_str, _, b_str = part.partition("-")
    if not a_str.isdigit() or not b_str.isdigit():
        raise ValueError(f"invalid range '{part}' for {field_name}")
    a, b = int(a_str), int(b_str)
    if not (mini <= a <= maxi and mini <= b <= maxi):
        raise ValueError(
            f"range [{a},{b}] out of bounds [{mini},{maxi}] for {field_name}"
        )
    if a > b:
        raise ValueError(f"range start {a} > end {b} for {field_name}")
    return a, b


def parse_cron(raw: str) -> tuple[list[set[int]], str | None]:
    """Parse a 5-field cron expression.

    Returns (fields_list, error_string).  error_string is None on success.
    """
    parts = raw.strip().split()
    if len(parts) != 5:
        return [], (
            f"expected 5 fields, got {len(parts)}. "
            "Standard cron: minute hour dom month dow"
        )
    fields: list[set[int]] = []
    for (fname, mini, maxi), part in zip(FIELDS, parts):
        try:
            fields.append(_parse_field(part, mini, maxi, fname))
        except ValueError as e:
            return [], str(e)
    return fields, None


# ── English explainers ─────────────────────────────────────────────────

def _describe_field(values: set[int], field_name: str, mini: int, maxi: int) -> str:
    """Turn a set of values into a concise English phrase."""
    sorted_vals = sorted(values)
    if len(sorted_vals) == maxi - mini + 1:
        return f"every {field_name}"

    # Detect */N pattern (only when starting at the beginning of the range)
    if len(sorted_vals) >= 2:
        step = sorted_vals[1] - sorted_vals[0]
        if step > 1 and all(
            sorted_vals[i] - sorted_vals[i - 1] == step
            for i in range(1, len(sorted_vals))
        ):
            # For day-of-week, a large step (e.g. 6 for Sat+Sun) isn't a real pattern
            if field_name != "day of week" or step <= 2:
                # Check if it really is every-N from mini
                if sorted_vals[0] == mini:
                    expected = set(range(mini, maxi + 1, step))
                    if values == expected:
                        return f"every {step} {field_name}s"
            # If it doesn't start at mini nor fill the range cleanly, fall through to list

    # Build range / list description
    parts: list[str] = []
    i = 0
    while i < len(sorted_vals):
        j = i
        while j + 1 < len(sorted_vals) and sorted_vals[j + 1] == sorted_vals[j] + 1:
            j += 1
        if j > i:
            parts.append(f"{_label(sorted_vals[i], field_name)} through {_label(sorted_vals[j], field_name)}")
            i = j + 1
        else:
            parts.append(_label(sorted_vals[i], field_name))
            i += 1
    return ", ".join(parts)


def _label(value: int, field_name: str) -> str:
    """Label a value with its natural name where applicable."""
    if field_name == "month":
        return MONTH_NAMES[value - 1]
    if field_name == "day of week":
        return DAY_NUM_NAMES[value]
    return str(value)


def explain_cron(raw: str) -> dict:
    """Return a dict with 'valid', 'raw', 'fields', 'english', 'error'."""
    fields, error = parse_cron(raw)
    if error:
        return {"valid": False, "raw": raw, "error": error}

    minute_set, hour_set, dom_set, month_set, dow_set = fields

    # Check if everything is wildcard (* * * * *)
    # Dow is special: range is 0-7 but 0 and 7 both mean Sunday, so wildcard = 7 values
    all_wild = (
        len(minute_set) == 60
        and len(hour_set) == 24
        and len(dom_set) == 31
        and len(month_set) == 12
        and len(dow_set) == 7
    )
    if all_wild:
        return {
            "valid": True,
            "raw": raw,
            "fields": [sorted(list(v)) for v in fields],
            "english": "Every minute.",
        }

    # Check if only minute is specific (e.g., */5 * * * *)
    only_minute = (
        len(minute_set) != 60
        and len(hour_set) == 24
        and len(dom_set) == 31
        and len(month_set) == 12
        and len(dow_set) == 7
    )

    parts: list[str] = []

    # --- Minute part ---
    if only_minute:
        if len(minute_set) == 1:
            parts.append(f"At minute {_label(list(minute_set)[0], 'minute')} of every hour")
        else:
            # Check for every-N pattern
            sorted_m = sorted(minute_set)
            if len(sorted_m) >= 2:
                step = sorted_m[1] - sorted_m[0]
                if all(sorted_m[i] - sorted_m[i - 1] == step for i in range(1, len(sorted_m))):
                    if sorted_m[0] == 0 and set(range(0, 60, step)) == minute_set:
                        parts.append(f"Every {step} minutes" if step > 1 else "Every minute")
                    else:
                        parts.append(f"Every {step} minutes starting at {_label(sorted_m[0], 'minute')}")
            if not parts:
                parts.append(f"At minutes {_describe_field(minute_set, 'minute', 0, 59)} of every hour")
    else:
        # Combined minute + hour
        time_part = _build_time_part(minute_set, hour_set)
        parts.append(time_part)

    # --- Day-of-week restrictions ---
    if len(dow_set) < 7:
        parts.append(_describe_field(dow_set, "day of week", 0, 6))

    # --- Day-of-month restrictions (only if dow is wildcard, otherwise dow takes precedence) ---
    if len(dow_set) == 7 and len(dom_set) < 31:
        parts.append(f"on {_describe_field(dom_set, 'day of month', 1, 31)}")

    # --- Month restrictions ---
    if len(month_set) < 12:
        parts.append(f"in {_describe_field(month_set, 'month', 1, 12)}")

    english = ", ".join(parts) + "."
    english = english[0].upper() + english[1:]
    return {
        "valid": True,
        "raw": raw,
        "fields": [sorted(list(v)) for v in fields],
        "english": english,
    }


def _build_time_part(minute_set: set[int], hour_set: set[int]) -> str:
    """Build the time-of-day portion of the cron explanation."""

    def _fmt_hour(h: int) -> str:
        if h == 0:
            return "12 AM"
        elif h < 12:
            return f"{h} AM"
        elif h == 12:
            return "12 PM"
        else:
            return f"{h - 12} PM"

    def _fmt_time(h: int, m: int) -> str:
        # Combine an hour + minute into a single 12-hour clock time, e.g. "9:30 AM".
        num, ampm = _fmt_hour(h).split()
        return f"{num}:{m:02d} {ampm}"

    sorted_h = sorted(hour_set)

    # Check for every-N pattern in hours (*/N)
    is_every_n_hours = False
    if len(sorted_h) >= 2 and sorted_h[0] == 0:
        step = sorted_h[1] - sorted_h[0]
        if step > 1 and all(
            sorted_h[i] - sorted_h[i - 1] == step
            for i in range(1, len(sorted_h))
        ) and set(range(0, 24, step)) == hour_set:
            is_every_n_hours = True

    # Case: single minute + single hour → "At 9:30 AM"
    if len(minute_set) == 1 and len(hour_set) == 1:
        m = list(minute_set)[0]
        h = list(hour_set)[0]
        h_label = _fmt_hour(h)
        # Split "12 AM" → "12" + "AM"
        parts_h = h_label.split()
        return f"At {parts_h[0]}:{m:02d} {parts_h[1]}"

    # Case: every-N hours with single minute → "At minute 0, every 6 hours"
    if len(minute_set) == 1 and is_every_n_hours:
        step = sorted_h[1] - sorted_h[0]
        return f"At minute {list(minute_set)[0]}, every {step} hours"

    # Case: every-N hours, all minutes (hour-only pattern) → "Every 6 hours"
    if is_every_n_hours and len(minute_set) == 60:
        step = sorted_h[1] - sorted_h[0]
        return f"Every {step} hours"

    # Case: all hours wildcard, just minute → skip hour description
    if len(hour_set) == 24:
        return _describe_field(minute_set, "minute", 0, 59)

    # Case: hour range (e.g., 9-17) with single minute → "9 AM through 5 PM"
    if len(hour_set) > 1 and not is_every_n_hours:
        # Check if it's a contiguous range
        if sorted_h[-1] - sorted_h[0] + 1 == len(sorted_h):
            hdesc = f"{_fmt_hour(sorted_h[0])} through {_fmt_hour(sorted_h[-1])}"
            if len(minute_set) == 1:
                m = list(minute_set)[0]
                return f"At minute {m}, {hdesc}"
            elif len(minute_set) == 60:
                return hdesc
            else:
                return f"{_describe_field(minute_set, 'minute', 0, 59)} of {hdesc}"
        else:
            # Non-contiguous hours — list each full clock time so the hour
            # values can't be misread as minutes.
            if len(minute_set) == 1:
                m = list(minute_set)[0]
                times = ", ".join(_fmt_time(h, m) for h in sorted_h)
                return f"At {times}"
            hdesc = _describe_field(hour_set, "hour", 0, 23)
            mdesc = _describe_field(minute_set, "minute", 0, 59)
            return f"At minutes {mdesc} past hours {hdesc}"

    # Case: single hour, multiple minutes → "At 9 AM, 0 through 30"
    if len(hour_set) == 1:
        h = list(hour_set)[0]
        return f"At {_fmt_hour(h)}, {_describe_field(minute_set, 'minute', 0, 59)}"

    # Fallback
    return (f"At {_describe_field(minute_set, 'minute', 0, 59)} "
            f"of {_describe_field(hour_set, 'hour', 0, 23)}")


# ── Next execution times ───────────────────────────────────────────────

def _next_executions(raw: str, count: int = 5) -> list[str]:
    """Return next *count* execution datetimes for a valid cron expression."""
    fields, error = parse_cron(raw)
    if error:
        return [f"Error: {error}"]

    minute_set, hour_set, dom_set, month_set, dow_set = fields

    # Cron day-of-week is Sun=0..Sat=6 (7→Sun), but datetime.weekday() is
    # Mon=0..Sun=6. Convert so comparisons match the correct day.
    dow_py = {(d + 6) % 7 for d in dow_set}

    now = datetime.now().replace(second=0, microsecond=0)
    results: list[str] = []
    cursor = now

    # Step one minute at a time, but search a full year ahead so sparse
    # schedules (daily/weekly/monthly/yearly) are still found. Worst case is
    # ~526k iterations, which is well under a second in pure Python.
    max_steps = 60 * 24 * 367
    for _ in range(max_steps):
        cursor += timedelta(minutes=1)
        if (
            cursor.minute in minute_set
            and cursor.hour in hour_set
            and cursor.day in dom_set
            and cursor.month in month_set
            and cursor.weekday() in dow_py
        ):
            results.append(cursor.strftime("%Y-%m-%d %H:%M:%S %A"))
            if len(results) >= count:
                break

    return results


# ── Subcommand handlers ────────────────────────────────────────────────

def cmd_explain(args: argparse.Namespace) -> int:
    """Explain a cron expression in plain English."""
    result = explain_cron(args.expression)
    if args.format == "json":
        print(json.dumps(result, indent=2))
        return 0 if result["valid"] else 1
    if not result["valid"]:
        print(f"❌ Invalid: {result['error']}", file=sys.stderr)
        return 1
    print(result["english"])
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a cron expression."""
    fields, error = parse_cron(args.expression)
    result = {
        "valid": error is None,
        "raw": args.expression,
        "error": error,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2))
        return 0 if result["valid"] else 1
    if error:
        print(f"❌ {error}")
        return 1
    print("✅ Valid cron expression")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List upcoming execution times."""
    times = _next_executions(args.expression, args.count)
    if args.format == "json":
        err = None
        if times and times[0].startswith("Error:"):
            err = times[0]
            times = []
        print(json.dumps({"expression": args.expression, "upcoming": times, "error": err}, indent=2))
        return 1 if err else 0
    for t in times:
        if t.startswith("Error:"):
            print(t, file=sys.stderr)
            return 1
        print(t)
    return 0


# ── Parser ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cron_decode",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text)")

    sub = p.add_subparsers(dest="cmd", required=True)

    s_explain = sub.add_parser("explain", parents=[common],
                               help="Explain a cron expression in plain English")
    s_explain.add_argument("expression", help="5-field cron expression (e.g., '0 */6 * * 1-5')")
    s_explain.set_defaults(func=cmd_explain)

    s_validate = sub.add_parser("validate", parents=[common],
                                help="Check if a cron expression is valid")
    s_validate.add_argument("expression", help="5-field cron expression")
    s_validate.set_defaults(func=cmd_validate)

    s_list = sub.add_parser("list", parents=[common],
                            help="Show upcoming execution times")
    s_list.add_argument("expression", help="5-field cron expression")
    s_list.add_argument("-n", "--count", type=int, default=5,
                        help="Number of upcoming times to show (default: 5)")
    s_list.set_defaults(func=cmd_list)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
