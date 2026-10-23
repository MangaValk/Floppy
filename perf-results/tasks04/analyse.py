"""Compare TASKS-04 baseline and changed-commit lane measurements."""

# ruff: noqa: INP001, D103, PERF401, PLR2004 -- standalone experiment

import argparse
import json
import statistics
from pathlib import Path


def percentile(values, fraction):
    """Return a linearly interpolated percentile, or None for no samples."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarise_cell(samples):
    probes = [
        task["queue_wait_s"]
        for sample in samples
        for task in sample["tasks"]
        if task["kind"] == "playback_probe"
    ]
    sync = [
        task for sample in samples for task in sample["tasks"] if task["kind"] == "sync"
    ]
    return {
        "runs": len(samples),
        "operation_wall_s": {
            "mean": statistics.mean(sample["wall_s"] for sample in samples),
            "values": [sample["wall_s"] for sample in samples],
        },
        "enqueues_per_operation": statistics.mean(
            len(sample["tasks"]) for sample in samples
        ),
        "probe_wait_s": {
            "count": len(probes),
            "p50": percentile(probes, 0.5),
            "p95": percentile(probes, 0.95),
            "values": probes,
        },
        "sync_wait_s": {
            "count": len(sync),
            "p50": percentile([task["queue_wait_s"] for task in sync], 0.5),
            "p95": percentile([task["queue_wait_s"] for task in sync], 0.95),
        },
        "sync_wall_s": {
            "mean": statistics.mean(task["wall_s"] for task in sync),
            "total": sum(task["wall_s"] for task in sync),
        },
        "sync_cpu_s": {
            "mean": statistics.mean(task["cpu_s"] for task in sync),
            "total": sum(task["cpu_s"] for task in sync),
        },
        "db_write_statements": sum(task["db_write_statements"] for task in sync),
        "redis_commands": sum(task["redis_commands"] for task in sync),
        "peak_rss_bytes": max(
            (task["peak_bytes"].get("rss") or 0) for task in sync
        ),
        "peak_uss_bytes": max(
            (task["peak_bytes"].get("uss") or 0) for task in sync
        ),
        "invariants": samples[0]["invariants"],
    }


def summarise(report):
    cells = {}
    for sample in report["samples"]:
        if sample["warmup"]:
            continue
        key = (
            f"{sample['records']}-"
            f"{'cold' if sample['cold'] else 'warm'}-"
            f"{'loaded' if sample['loaded'] else 'idle'}"
        )
        cells.setdefault(key, []).append(sample)
    idle = report.get("idle") or []
    idle_summary = report.get("idle_summary") or {}
    steady = [row for row in idle if row["elapsed_s"] >= 300]
    steady_base = steady[0] if steady else None
    steady_seconds = (
        steady[-1]["elapsed_s"] - steady_base["elapsed_s"] if len(steady) > 1 else 0
    )
    steady_state = {
        "window_s": steady_seconds,
        "executions": (
            steady[-1]["executions"] - steady_base["executions"] if steady else None
        ),
        "enqueues": sum(row["queued"] for row in steady) if steady else None,
        "executions_per_hour": (
            (steady[-1]["executions"] - steady_base["executions"]) * 3600
            / steady_seconds
            if steady_seconds
            else None
        ),
        "enqueues_per_hour": (
            sum(row["queued"] for row in steady) * 3600 / steady_seconds
            if steady_seconds
            else None
        ),
    }
    return {
        "cells": {key: summarise_cell(value) for key, value in cells.items()},
        "idle": {
            "wall_s": idle_summary.get("wall_s"),
            "executions": idle_summary.get("executions"),
            "enqueues_per_hour": (
                idle_summary.get("enqueues", 0) * 3600 / idle_summary["wall_s"]
                if idle_summary.get("wall_s")
                else None
            ),
            "executions_per_hour": (
                idle_summary.get("executions", 0) * 3600 / idle_summary["wall_s"]
                if idle_summary.get("wall_s")
                else None
            ),
            "cpu_s": idle_summary.get("cpu_s"),
            "samples": len(idle),
            "steady_state_after_300s": steady_state,
        },
    }


def delta(before, after):
    if before in (None, 0) or after is None:
        return None
    return (after - before) / before * 100


def main():
    """Write machine-readable and Markdown comparisons."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()

    baseline = summarise(json.loads(args.baseline.read_text()))
    after = summarise(json.loads(args.after.read_text()))
    output = {"baseline": baseline, "after": after, "deltas": {}}
    for key, before_cell in baseline["cells"].items():
        after_cell = after["cells"].get(key)
        if after_cell is None:
            continue
        output["deltas"][key] = {
            "probe_p95_s": {
                "before": before_cell["probe_wait_s"]["p95"],
                "after": after_cell["probe_wait_s"]["p95"],
                "percent": delta(
                    before_cell["probe_wait_s"]["p95"],
                    after_cell["probe_wait_s"]["p95"],
                ),
            },
            "operation_wall_s": {
                "before": before_cell["operation_wall_s"]["mean"],
                "after": after_cell["operation_wall_s"]["mean"],
                "percent": delta(
                    before_cell["operation_wall_s"]["mean"],
                    after_cell["operation_wall_s"]["mean"],
                ),
            },
            "sync_cpu_s": {
                "before": before_cell["sync_cpu_s"]["total"],
                "after": after_cell["sync_cpu_s"]["total"],
                "percent": delta(
                    before_cell["sync_cpu_s"]["total"],
                    after_cell["sync_cpu_s"]["total"],
                ),
            },
            "db_write_statements": {
                "before": before_cell["db_write_statements"],
                "after": after_cell["db_write_statements"],
                "percent": delta(
                    before_cell["db_write_statements"],
                    after_cell["db_write_statements"],
                ),
            },
            "redis_commands": {
                "before": before_cell["redis_commands"],
                "after": after_cell["redis_commands"],
                "percent": delta(
                    before_cell["redis_commands"], after_cell["redis_commands"]
                ),
            },
        }
    args.json.write_text(json.dumps(output, indent=2) + "\n")

    lines = [
        "# TASKS-04 baseline and after comparison",
        "",
        "Lower is better for every column except the correctness invariants.",
        "",
        "| Cell | Probe wait p95 s | Op wall mean s | Sync CPU total s | DB writes | Redis ops |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in baseline["cells"]:
        before = baseline["cells"][key]
        changed = after["cells"].get(key)
        if changed is None:
            continue
        lines.append(
            "| {key} | {bp:.3f} -> {ap:.3f} | {bw:.2f} -> {aw:.2f} | "
            "{bc:.2f} -> {ac:.2f} | {bd} -> {ad} | {br} -> {ar} |".format(
                key=key,
                bp=before["probe_wait_s"]["p95"] or 0,
                ap=changed["probe_wait_s"]["p95"] or 0,
                bw=before["operation_wall_s"]["mean"],
                aw=changed["operation_wall_s"]["mean"],
                bc=before["sync_cpu_s"]["total"],
                ac=changed["sync_cpu_s"]["total"],
                bd=before["db_write_statements"],
                ad=changed["db_write_statements"],
                br=before["redis_commands"],
                ar=changed["redis_commands"],
            )
        )
    lines.extend(
        [
            "",
            "## Idle window",
            "",
            "| Metric | Baseline | After |",
            "| --- | ---: | ---: |",
        ]
    )
    for name in ("executions", "cpu_s"):
        lines.append(
            f"| {name} | {baseline['idle'].get(name)} | {after['idle'].get(name)} |"
        )
    for name in ("executions_per_hour", "enqueues_per_hour"):
        lines.append(
            f"| {name} (after 300 s) | "
            f"{baseline['idle']['steady_state_after_300s'].get(name)} | "
            f"{after['idle']['steady_state_after_300s'].get(name)} |"
        )
    args.markdown.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
