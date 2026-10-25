"""Compare TASKS-04A prefork worker memory before and after the freeze change."""

# ruff: noqa: INP001, D103 -- standalone experiment

import argparse
import json
import statistics
from pathlib import Path

MIB = 1024 * 1024


def load(path):
    return json.loads(Path(path).read_text())


def measured(report, label):
    return [row for row in report["samples"] if row["label"] == label and not row["warmup"]]


def run_summary(report):
    idle = measured(report, "idle")
    loaded = measured(report, "loaded")
    footprint = report.get("idle", {}).get("footprint", {})
    parents = [row["parent"]["rss"] for row in footprint.values()]
    return {
        "idle": {
            "child_uss": statistics.median(row["uss"] for row in idle) / MIB,
            "child_rss": statistics.median(row["rss"] for row in idle) / MIB,
            "parent_rss": statistics.median(parents) / MIB if parents else None,
            "workers": len(parents),
        },
        "loaded": {
            "max_child_uss": max(row["uss"] for row in loaded) / MIB,
            "max_child_rss": max(row["rss"] for row in loaded) / MIB,
        },
        "load_result": (
            {
                "peak_rss": report["load_result"]["peak_bytes"]["rss"] / MIB,
                "peak_uss": report["load_result"]["peak_bytes"]["uss"] / MIB,
            }
            if report.get("load_result")
            else None
        ),
    }


def median_summaries(reports):
    summaries = [run_summary(report) for report in reports]
    return {
        "runs": len(summaries),
        "idle_child_uss_mib": statistics.median(row["idle"]["child_uss"] for row in summaries),
        "idle_child_rss_mib": statistics.median(row["idle"]["child_rss"] for row in summaries),
        "idle_parent_rss_mib": statistics.median(row["idle"]["parent_rss"] for row in summaries),
        "idle_total_private_mib": statistics.median(
            row["idle"]["workers"] * row["idle"]["child_uss"]
            + row["idle"]["workers"] * row["idle"]["parent_rss"]
            for row in summaries
        ),
        "loaded_max_child_uss_mib": statistics.median(
            row["loaded"]["max_child_uss"] for row in summaries
        ),
        "loaded_max_child_rss_mib": statistics.median(
            row["loaded"]["max_child_rss"] for row in summaries
        ),
        "per_run": summaries,
    }


def pct(before, after):
    return (after - before) / before * 100 if before else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()

    def reports(pattern):
        return [load(path) for path in sorted(args.dir.glob(pattern))]

    baseline = median_summaries(reports("baseline-separate*.json"))
    after = median_summaries(reports("after-separate*.json"))
    merged = median_summaries(reports("after-merged*.json"))
    def peak(pattern):
        rows = [
            load(path)["load_result"]["peak_bytes"]
            for path in sorted(args.dir.glob(pattern))
        ]
        return {
            "runs": len(rows),
            "rss": statistics.median(row["rss"] for row in rows),
            "uss": statistics.median(row["uss"] for row in rows),
            "pss": None,
        }

    baseline_peak = peak("baseline-peak*.json")
    after_peak = peak("after-peak*.json")
    output = {
        "baseline_separate": baseline,
        "after_separate": after,
        "after_merged": merged,
        "peak_sync": {
            "baseline": baseline_peak,
            "after": after_peak,
        },
        "deltas": {
            "idle_child_uss_percent": pct(
                baseline["idle_child_uss_mib"], after["idle_child_uss_mib"]
            ),
            "idle_child_rss_percent": pct(
                baseline["idle_child_rss_mib"], after["idle_child_rss_mib"]
            ),
            "idle_total_private_percent": pct(
                baseline["idle_total_private_mib"], after["idle_total_private_mib"]
            ),
            "merged_vs_separate_total_percent": pct(
                after["idle_total_private_mib"], merged["idle_total_private_mib"]
            ),
        },
    }
    args.json.write_text(json.dumps(output, indent=2) + "\n")
    lines = [
        "# TASKS-04A — prefork child private memory",
        "",
        "Separate variants are the median of five independent worker starts; the",
        "merged control is two. Idle is measured in the child that runs the sync",
        "body; PSS is unavailable on macOS. Total private memory is the sum of",
        "each child's USS and its parent's RSS (parent USS unavailable).",
        "",
        "| Variant | Idle child USS MiB | Idle child RSS MiB | Idle parent RSS MiB | Total private MiB |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, row in (
        ("baseline separate", baseline),
        ("after separate", after),
        ("after merged", merged),
    ):
        lines.append(
            f"| {name} | {row['idle_child_uss_mib']:.1f} | "
            f"{row['idle_child_rss_mib']:.1f} | {row['idle_parent_rss_mib']:.1f} | "
            f"{row['idle_total_private_mib']:.1f} |"
        )
    lines.extend(
        [
            "",
            "After vs baseline, separate: child USS "
            f"{output['deltas']['idle_child_uss_percent']:+.1f}%, child RSS "
            f"{output['deltas']['idle_child_rss_percent']:+.1f}%, total private "
            f"{output['deltas']['idle_total_private_percent']:+.1f}%.",
            "",
            "Peak during a full sync (median of "
            f"{baseline_peak['runs']}/{after_peak['runs']} runs): USS "
            f"{baseline_peak['uss'] / MIB:.1f} -> "
            f"{after_peak['uss'] / MIB:.1f} MiB "
            f"({pct(baseline_peak['uss'], after_peak['uss']):+.1f}%); RSS "
            f"{baseline_peak['rss'] / MIB:.1f} -> "
            f"{after_peak['rss'] / MIB:.1f} MiB "
            f"({pct(baseline_peak['rss'], after_peak['rss']):+.1f}%).",
        ]
    )
    args.markdown.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
