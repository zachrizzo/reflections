"""Summarise the DIGSPIKE lines of rendered measurement logs into the figures ArtDirection/Digging/SpikeResults.md shows.

Usage: python summarize_spike_log.py <log> [<log> ...]
Prints one column per log. A figure whose line or field is missing from a log prints n/a.
Standard library only.
"""

import os
import re
import sys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

NA = "n/a"
TIMESTAMP = re.compile(r"^\[(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2}):(\d{3})\]")
FIELD = re.compile(r'([A-Za-z0-9_.]+)=("[^"]*"|\S+)')


class SpikeLog:
    """The DIGSPIKE lines of one log, by tag, with their key=value fields; plus the run's start, end and test results."""

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.lines = {}
        self.first_time = None
        self.last_time = None
        self.command_line = None
        self.cef_loaded = False
        self.cef_started = False
        self.tests_ran = 0
        self.tests_passed = 0
        with open(path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.rstrip("\n")
                stamp = TIMESTAMP.match(line)
                if stamp:
                    when = datetime(*(int(part) for part in stamp.groups()[:6]), int(stamp.group(7)) * 1000)
                    if self.first_time is None:
                        self.first_time = when
                    self.last_time = when
                if self.command_line is None and "LogInit: Command Line:" in line:
                    self.command_line = line
                if "LogWebBrowser: Loaded CEF3" in line:
                    self.cef_loaded = True
                if "LogCEFBrowser:" in line:
                    self.cef_started = True
                if "Test Completed. Result={" in line:
                    self.tests_ran += 1
                    self.tests_passed += 1 if "Result={Success}" in line else 0
                at = line.find("DIGSPIKE ")
                if at < 0:
                    continue
                rest = line[at + len("DIGSPIKE "):]
                tag, _, text = rest.partition(" ")
                fields = {key: value.strip('"') for key, value in FIELD.findall(text)}
                self.lines.setdefault(tag, []).append(fields)

    def all(self, tag):
        return self.lines.get(tag, [])

    def get(self, tag, field, where=None):
        """The field's value as a float from the first line of tag (matching where, a dict of field values), or None."""
        for fields in self.all(tag):
            if where and any(fields.get(key) != value for key, value in where.items()):
                continue
            if field in fields:
                try:
                    return float(fields[field])
                except ValueError:
                    return None
            return None
        return None

    def run_seconds(self):
        if self.first_time is None or self.last_time is None:
            return None
        return (self.last_time - self.first_time).total_seconds()


def fmt(value, decimals=1, thousands=False):
    """Rounded half up from the value as logged (88.550 gives 88.6), as the results page rounds."""
    if value is None:
        return NA
    rounded = Decimal(repr(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    return f"{rounded:,.{decimals}f}" if thousands else f"{rounded:.{decimals}f}"


def total(*values):
    return None if any(value is None for value in values) else sum(values)


def minus(a, b):
    return None if a is None or b is None else a - b


SPIKE_TAGS = ("digs", "commits", "cooks_finished", "nav_updates", "gc", "previous_frame_dig_related")
SPIKE_MS = 16.0


def frame_tags(log, spike_tag, raw_ms):
    """
    The frame number and tags of the frame whose raw game-thread time is raw_ms, from the window's spike lines (the
    test logs a frame there only when it is over 16 ms, and at most 20 per window).
    """
    if raw_ms is None:
        return NA
    for fields in log.all(spike_tag):
        try:
            if abs(float(fields.get("game_ms", "nan")) - raw_ms) <= 0.011:
                return f"frame={fields.get('frame', '?')} " + " ".join(f"{key}={fields.get(key, '?')}" for key in SPIKE_TAGS)
        except ValueError:
            continue
    return "not logged (16 ms or under)" if raw_ms <= SPIKE_MS else "not among the logged spike lines (first 20 only)"


def worst_frame_rows(tag):
    """The tags of a window's worst frame and of its worst dig-related frame, from its _WINDOW_SPIKE lines."""
    spike_tag = tag[: -len("_WHOLE")] + "_WINDOW_SPIKE"

    def dig_related_raw(log):
        above = log.get(tag, "dig_related_max_ms")
        median = log.get(tag, "idle_median_ms")
        return None if above is None or median is None else above + median

    return [
        ("worst frame: tags", lambda log: frame_tags(log, spike_tag, log.get(tag, "raw_max_ms"))),
        ("worst dig-related frame: tags", lambda log: frame_tags(log, spike_tag, dig_related_raw(log))),
    ]


def whole_rows(tag):
    """The rows of one *_WHOLE line: the whole-window table of its test."""
    def worst(log):
        above = log.get(tag, "above_max_ms")
        raw = log.get(tag, "raw_max_ms")
        if above is None:
            return NA
        note = " (a)" if log.get(tag, "max_is_collection") == 1 else ""
        return f"{fmt(above)} ms ({fmt(raw)}){note}"

    return [
        ("average / middle frame", lambda log: f"{fmt(log.get(tag, 'above_mean_ms'), 2)} / {fmt(log.get(tag, 'above_median_ms'), 2)} ms"),
        ("99 in 100 at or under", lambda log: f"{fmt(log.get(tag, 'above_p99_ms'))} ms"),
        ("worst frame (raw), (a) = a collection", worst),
        ("worst dig-related frame", lambda log: f"{fmt(log.get(tag, 'dig_related_max_ms'))} ms"),
        ("worst dig-related = worst frame", lambda log: NA if log.get(tag, "above_max_ms") is None
            else ("yes" if log.get(tag, "dig_related_max_ms") == log.get(tag, "above_max_ms") else "no")),
        ("cost per dig", lambda log: f"{fmt(log.get(tag, 'cost_per_dig_ms'))} ms"),
        ("frames / digs", lambda log: f"{fmt(log.get(tag, 'frames'), 0)} / {fmt(log.get(tag, 'digs'), 0)}"),
        ("idle median (raw)", lambda log: f"{fmt(log.get(tag, 'idle_median_ms'), 2)} ms"),
        ("background max / in idle", lambda log: f"{fmt(log.get(tag, 'background_max_ms'))} / {fmt(log.get(tag, 'idle_background_max_ms'))} ms"),
        ("collections window / idle", lambda log: f"{fmt(log.get(tag, 'collections_window'), 0)} / {fmt(log.get(tag, 'collections_idle'), 0)}"),
        ("commits / cooks finished / nav updates", lambda log: f"{fmt(log.get(tag, 'commits'), 0)} / {fmt(log.get(tag, 'cooks_finished'), 0)} / {fmt(log.get(tag, 'nav_updates'), 0)}"),
        ("game_thread_cooks", lambda log: fmt(log.get(tag, "game_thread_cooks"), 0)),
    ] + worst_frame_rows(tag)


def split_rows(test, corner):
    """The rows of the split table for one SPLIT line (test=BUSY or test=CORNER), totals over the window in whole ms."""
    where = {"test": test}

    def value(log, field):
        return log.get("SPLIT", field, where)

    def pair(log, a, b):
        return f"{fmt(value(log, a), 0, True)} / {fmt(value(log, b), 0, True)} ms"

    rows = [
        ("whole window, extra main-thread time", lambda log: f"{fmt(value(log, 'window_above_idle_ms_total'), 0, True)} ms"),
        ("... chunk updates / swap check", lambda log: pair(log, "commit_ms_total", "swap_ms_total")),
        ("... collision finishing / navigation", lambda log: pair(log, "cook_finish_ms_total", "nav_after_cook_ms_total")),
    ]
    if corner:
        rows += [
            ("... rest, in the frames with a chunk update", lambda log: f"{fmt(value(log, 'rest_commit_ms'), 0, True)} ms"),
            ("... rest, in the frame right after", lambda log: f"{fmt(value(log, 'rest_after_commit_ms'), 0, True)} ms"),
            ("... rest, all other frames", lambda log: f"{fmt(total(value(log, 'rest_cook_ms'), value(log, 'rest_other_ms')), 0, True)} ms"),
        ]
    else:
        rows += [
            ("... rest, in the frame right after a chunk update", lambda log: f"{fmt(value(log, 'rest_after_commit_ms'), 0, True)} ms"),
            ("... rest, all other frames", lambda log: f"{fmt(total(value(log, 'rest_commit_ms'), value(log, 'rest_cook_ms'), value(log, 'rest_other_ms')), 0, True)} ms"),
        ]
    rows += [
        ("parts named, share of the whole", lambda log: NA if value(log, "parts_ms_total") is None or not value(log, "window_above_idle_ms_total")
            else f"{fmt(100.0 * value(log, 'parts_ms_total') / value(log, 'window_above_idle_ms_total'), 0)}%"),
        ("pieces / vertices per chunk update", lambda log: f"{fmt(value(log, 'pieces_per_commit'), 2)} / {fmt(value(log, 'vertices_per_commit'), 0, True)}"),
    ]
    return rows


def gpu_rows():
    """Average graphics-card time over every *_IDLE and *_WINDOW line, and the most a window added to its idle."""
    def means(log):
        return [float(fields["gpu_mean"]) for tag, lines in log.lines.items() if tag.endswith(("_IDLE", "_WINDOW"))
                for fields in lines if "gpu_mean" in fields]

    def added(log):
        best = None
        for tag in log.lines:
            if tag.endswith("_WINDOW"):
                window = log.get(tag, "gpu_mean")
                idle = log.get(tag[: -len("_WINDOW")] + "_IDLE", "gpu_mean")
                if window is not None and idle is not None:
                    best = window - idle if best is None else max(best, window - idle)
        return best

    return [
        ("average per frame, lowest to highest window", lambda log: f"{fmt(min(means(log)), 2)} to {fmt(max(means(log)), 2)} ms" if means(log) else NA),
        ("most a window added to its idle", lambda log: f"{fmt(added(log), 2)} ms"),
    ]


def shot_rows():
    names = ["tunnel_hwrt_on", "tunnel_hwrt_off", "tunnel_wall_hwrt_on", "tunnel_wall_hwrt_off", "pit_hwrt_on", "pit_hwrt_off",
             "tunnel_fixed_exposure_hwrt_on", "tunnel_fixed_exposure_hwrt_off"]
    return [(name, lambda log, name=name: NA if log.get("SHOT", "mean_luma", {"name": name}) is None
             else f"{fmt(log.get('SHOT', 'mean_luma', {'name': name}))} (hwrt {fmt(log.get('SHOT', 'hwrt_active', {'name': name}), 0)})")
            for name in names]


def sections():
    run = [
        ("tests completed / passed", lambda log: f"{log.tests_ran} / {log.tests_passed}"),
        ("run length, first to last log line", lambda log: f"{fmt(log.run_seconds(), 0)} s"),
        ("-nocef on the command line", lambda log: NA if log.command_line is None else ("yes" if "-nocef" in log.command_line.lower() else "no")),
        ("'LogWebBrowser: Loaded CEF3' line (library loaded)", lambda log: "yes" if log.cef_loaded else "no"),
        ("any 'LogCEFBrowser:' line (browser started)", lambda log: "yes" if log.cef_started else "no"),
    ]

    def pass_row(tag):
        def row(log):
            p99 = log.get(tag, "above_p99_ms")
            above = log.get(tag, "above_max_ms")
            if p99 is None or above is None:
                return NA
            note = " (a)" if log.get(tag, "max_is_collection") == 1 else ""
            return f"{fmt(p99)} / {fmt(above)} ms{note}"
        return row

    def met(tag):
        def row(log):
            p99 = log.get(tag, "above_p99_ms")
            above = log.get(tag, "above_max_ms")
            if p99 is None or above is None:
                return NA
            return f"{'met' if p99 <= 4.0 else 'NOT'} / {'met' if above <= 4.0 else 'NOT'}"
        return row

    pass_marks = []
    for label, tag in (("busy chunk", "BUSY_WHOLE"), ("eight-chunk corner", "CORNER_WHOLE"), ("open ground", "DIG_WHOLE"), ("streaming", "STREAM_WHOLE")):
        pass_marks.append((f"{label}: 99 in 100 / worst frame", pass_row(tag)))
        pass_marks.append((f"{label}: 4 ms mark met", met(tag)))

    noise = [
        ("background max, open ground / streaming", lambda log: f"{fmt(log.get('DIG_WHOLE', 'background_max_ms'))} / {fmt(log.get('STREAM_WHOLE', 'background_max_ms'))} ms"),
        ("idle background max, open ground / streaming", lambda log: f"{fmt(log.get('DIG_WHOLE', 'idle_background_max_ms'))} / {fmt(log.get('STREAM_WHOLE', 'idle_background_max_ms'))} ms"),
        ("idle background max, corner / busy", lambda log: f"{fmt(log.get('CORNER_WHOLE', 'idle_background_max_ms'))} / {fmt(log.get('BUSY_WHOLE', 'idle_background_max_ms'))} ms"),
        ("raw idle max, open ground / streaming", lambda log: f"{fmt(log.get('DIG_IDLE', 'game_max'))} / {fmt(log.get('STREAM_IDLE', 'game_max'))} ms"),
    ]
    open_ground = [
        ("digs changing the ground", lambda log: fmt(log.get("DIG", "digs"), 0)),
        ("reached the bottom after", lambda log: f"{fmt(log.get('DIG_EXTRA', 'bottom_at_s'), 2)} s"),
        ("feet went down by", lambda log: f"{fmt(None if log.get('DIG_EXTRA', 'feet_end') is None else (log.get('DIG_EXTRA', 'feet_start') - log.get('DIG_EXTRA', 'feet_end')) / 100.0, 2)} m"),
    ]
    busy = [
        ("riddle stamps that changed the grid", lambda log: fmt(log.get("BUSY_RIDDLE", "stamps_changed"), 0)),
        ("before: pieces / vertices / largest piece", lambda log: f"{fmt(log.get('BUSY_BEFORE', 'pieces'), 0)} / {fmt(log.get('BUSY_BEFORE', 'vertices'), 0, True)} / {fmt(log.get('BUSY_BEFORE', 'largest_piece_vertices'), 0, True)}"),
        ("frames a second while digging", lambda log: fmt(None if log.get("BUSY_WHOLE", "frames") is None else log.get("BUSY_WHOLE", "frames") / 10.0, 0)),
    ]
    streaming = [
        ("chunks dropped / rebuilt", lambda log: f"{fmt(log.get('STREAM', 'chunks_released'), 0)} / {fmt(log.get('STREAM', 'chunks_restored'), 0)}"),
        ("time spent dropping chunks", lambda log: f"{fmt(log.get('STREAM_WHOLE', 'release_ms_total'))} ms"),
    ]
    nav = [
        ("dig to walkable floor", lambda log: f"{fmt(log.get('NAV', 'FROM_DIG_SECONDS'), 3)} s"),
        ("collision ready after / walkable after that", lambda log: f"{fmt(log.get('NAV_EXTRA', 'collision_ready_after_dig_seconds'), 3)} / {fmt(log.get('NAV_EXTRA', 'from_collision_ready_seconds'), 3)} s"),
        ("worst frame while it rebuilt, above idle (raw)", lambda log: f"{fmt(log.get('NAV_EXTRA', 'worst_frame_above_idle_ms'))} ms ({fmt(log.get('NAV_EXTRA', 'raw_worst_ms'))})"),
        ("worst frame: tags", lambda log: frame_tags(log, "NAV_WINDOW_SPIKE", log.get("NAV_EXTRA", "raw_worst_ms"))),
    ]
    collision = [
        ("largest collision mesh (COLLISION)", lambda log: f"{fmt(log.get('COLLISION', 'largest_vertices'), 0, True)} vertices"),
        ("largest collision mesh (BUSY_AFTER)", lambda log: f"{fmt(log.get('BUSY_AFTER', 'largest_collision_vertices'), 0, True)} vertices"),
    ]
    seams = [("missed / traces", lambda log: f"{fmt(log.get('SEAMS', 'misses'), 0)} / {fmt(log.get('SEAMS', 'traces'), 0)}")]
    shadows = [
        ("render thread, digging (idle)", lambda log: f"{fmt(log.get('SHADOW_EXTRA', 'render_mean_ms'))} ({fmt(log.get('SHADOW_EXTRA', 'render_idle_mean_ms'))}) ms"),
        ("graphics card, digging (idle)", lambda log: f"{fmt(log.get('SHADOW_WINDOW', 'gpu_mean'), 2)} ({fmt(log.get('SHADOW_IDLE', 'gpu_mean'), 2)}) ms"),
        ("render / graphics card change", lambda log: f"{fmt(minus(log.get('SHADOW_EXTRA', 'render_mean_ms'), log.get('SHADOW_EXTRA', 'render_idle_mean_ms')), 2)} / {fmt(minus(log.get('SHADOW_WINDOW', 'gpu_mean'), log.get('SHADOW_IDLE', 'gpu_mean')), 2)} ms"),
        ("game thread: worst frame minus worst idle frame", lambda log: f"{fmt(minus(log.get('SHADOW', 'max_ms'), log.get('SHADOW', 'idle_max_ms')))} ms"),
        ("game thread: worst frame / worst idle frame (raw)", lambda log: f"{fmt(log.get('SHADOW', 'max_ms'))} / {fmt(log.get('SHADOW', 'idle_max_ms'))} ms"),
        ("worst frame: tags", lambda log: frame_tags(log, "SHADOW_WINDOW_SPIKE", log.get("SHADOW", "max_ms"))),
    ]
    return [
        ("Run", run),
        ("Pass marks (above idle; (a) = the worst frame was a collection)", pass_marks),
        ("Open ground (DIG_WHOLE)", whole_rows("DIG_WHOLE") + open_ground),
        ("Eight-chunk corner (CORNER_WHOLE)", whole_rows("CORNER_WHOLE")),
        ("Busy chunk (BUSY_WHOLE)", whole_rows("BUSY_WHOLE") + busy),
        ("Streaming (STREAM_WHOLE)", whole_rows("STREAM_WHOLE") + streaming),
        ("Split: busy chunk (SPLIT test=BUSY)", split_rows("BUSY", corner=False)),
        ("Split: corner (SPLIT test=CORNER)", split_rows("CORNER", corner=True)),
        ("Noise level", noise),
        ("Navmesh (NAV, NAV_EXTRA)", nav),
        ("Collision size", collision),
        ("Seams", seams),
        ("Shadows (SHADOW, SHADOW_EXTRA, SHADOW_IDLE, SHADOW_WINDOW)", shadows),
        ("Graphics card (every _IDLE and _WINDOW line)", gpu_rows()),
        ("Screenshot brightness (mean luma of 255)", shot_rows()),
    ]


def main(paths):
    if not paths:
        print(__doc__.strip().splitlines()[2])
        return 2
    logs = [SpikeLog(path) for path in paths]
    label_width = 56
    column_width = max(24, *(len(log.name) + 2 for log in logs))
    print(f"{'':<{label_width}}" + "".join(f"{log.name:<{column_width}}" for log in logs))
    for title, rows in sections():
        print()
        print(title)
        for label, figure in rows:
            cells = []
            for log in logs:
                try:
                    cells.append(figure(log))
                except (TypeError, ValueError, ZeroDivisionError):
                    cells.append(NA)
            if any(len(cell) >= column_width for cell in cells):
                # Too wide for a column (the frame tags): one line per log.
                print(f"  {label}")
                for log, cell in zip(logs, cells):
                    print(f"      {log.name}: {cell}")
            else:
                print(f"  {label:<{label_width - 2}}" + "".join(f"{cell:<{column_width}}" for cell in cells))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
