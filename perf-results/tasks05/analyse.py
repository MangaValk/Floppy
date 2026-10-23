"""Produce raw per-operation readings and comparable-condition deltas."""
import json
import math
import pstats
import re
import statistics
from collections import defaultdict
from pathlib import Path

root = Path(__file__).resolve().parent

def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values)*fraction)-1)] if values else None

def cpu(cgroup):
    return int(dict(line.split() for line in cgroup["cpu.stat"].splitlines())["usage_usec"])/1e6

def metrics(row):
    tasks = row["tasks"]
    syncs = [t for t in tasks if t["name"] == "app.tasks.statistics_sync_task"]
    hooks = [t for t in tasks if t["name"] == "Process media server webhook"]
    waits = [t["queue_wait_s"] for t in tasks]
    hook_waits = [t["queue_wait_s"] for t in hooks]
    redis_cpu = sum(row["redis_cpu_after"][name]-row["redis_cpu_before"][name]
                    for name in ("used_cpu_sys", "used_cpu_user"))
    return {"task_executions": len(tasks), "sync_executions": len(syncs),
        "task_enqueues": len(row["enqueues"]),
        "sync_enqueues": sum(t["name"] == "app.tasks.statistics_sync_task" for t in row["enqueues"]),
        "background_publications": len(row["background_publications_not_consumed"]),
        "unproductive_syncs": sum(not s["published"] for s in row["syncs"]),
        "busy_syncs": sum(s["status"] == "busy" for s in row["syncs"]),
        "wall_s": row["wall_s"], "queue_wait_p50_s": statistics.median(waits) if waits else None,
        "queue_wait_empirical_p95_s": percentile(waits, .95), "queue_wait_raw_s": waits,
        "task_runtime_raw_s": [t["wall_s"] for t in tasks],
        "sync_runtime_total_s": sum(t["wall_s"] for t in syncs),
        "worker_cpu_s": sum(t["cpu_s"] for t in tasks),
        "sync_cpu_s": sum(t["cpu_s"] for t in syncs), "parent_cpu_s": row["parent_cpu_s"],
        "container_cpu_s": cpu(row["cgroup_after"])-cpu(row["cgroup_before"]),
        "redis_server_cpu_s": redis_cpu,
        "db_write_statements": row["parent_sql"].get("writes", 0)+sum(t["writes"] for t in tasks),
        "db_query_statements": row["parent_sql"].get("queries", 0)+sum(t["queries"] for t in tasks),
        "redis_commands_parent_and_task_bodies": row["parent_redis_commands"]+sum(t["redis_commands"] for t in tasks),
        "redis_operations_including_instrumentation": row["redis_operations_including_instrumentation"],
        "peak_pss_bytes": row["peak_sampled_process_bytes"].get("pss"),
        "peak_uss_bytes": row["peak_sampled_process_bytes"].get("uss"),
        "container_memory_peak_cumulative_bytes": int(row["cgroup_after"]["memory.peak"]),
        "webhook_delay_raw_s": hook_waits,
        "webhook_completion_raw_s": [t["queue_wait_s"]+t["wall_s"] for t in hooks],
        "webhook_delay_p50_s": statistics.median(hook_waits) if hook_waits else None,
        "webhook_delay_empirical_p95_s": percentile(hook_waits, .95),
        "max_queue_depth": max((sum(v["llen"] or v["zcard"] or 0 for v in s["keys"].values())
                                for s in row["queue_samples"]), default=0),
        "executions_per_hour_observed_rate": len(tasks)*3600/row["wall_s"],
        "enqueues_per_hour_observed_rate": len(row["enqueues"])*3600/row["wall_s"]}

summary = {}
for phase in ("baseline", "after"):
    path = root/f"{phase}.jsonl"
    if not path.exists():
        continue
    raw = [json.loads(line) for line in path.read_text().splitlines()]
    grouped = defaultdict(list)
    rows = []
    for row in raw:
        reading = {"label": row["label"], **metrics(row)}
        rows.append(reading)
        if re.search(r"-(?:quiet|playback)-0$|^reconcile-backlog-0$", row["label"]) or row["label"].startswith("warmup"):
            continue
        group = re.sub(r"-\d+$", "", row["label"]) if re.search(r"-(?:quiet|playback)-\d+$|^reconcile-backlog-\d+$", row["label"]) else row["label"]
        grouped[group].append(reading)
    summary[phase] = {"readings": rows, "groups": {}}
    for group, readings in grouped.items():
        names = [name for name, value in readings[0].items()
                 if isinstance(value, (int, float)) and name != "label"]
        summary[phase]["groups"][group] = {"n": len(readings),
            "raw": {name: [r.get(name) for r in readings] for name in names},
            "median": {name: statistics.median(r[name] for r in readings if r.get(name) is not None) for name in names}}
    for kind in ("reconcile", "duplicate"):
        path = root/f"{phase}-{kind}.prof"
        if path.exists():
            with (root/f"{phase}-{kind}-profile.txt").open("w") as stream:
                pstats.Stats(str(path), stream=stream).sort_stats("cumulative").print_stats(30)

comparison = {}
if "after" in summary:
    for name, before in summary["baseline"]["groups"].items():
        if name not in summary["after"]["groups"]:
            continue
        after = summary["after"]["groups"][name]
        comparison[name] = {key: {"baseline": value, "after": after["median"][key],
            "absolute_delta": after["median"][key]-value,
            "percent_delta": (after["median"][key]-value)*100/value if value else None}
            for key, value in before["median"].items() if key in after["median"]}
    # Iteration zero is normally treated as warmup, but backlog zero is the only
    # replication with real 60-second tick spacing, so keep its raw comparison.
    before_row = next((r for r in summary["baseline"]["readings"] if r["label"] == "reconcile-backlog-0"), None)
    after_row = next((r for r in summary["after"]["readings"] if r["label"] == "reconcile-backlog-0"), None)
    if before_row and after_row:
        comparison["reconcile-backlog-first-tick"] = {
            key: {"baseline": value, "after": after_row[key],
                  "absolute_delta": after_row[key]-value,
                  "percent_delta": (after_row[key]-value)*100/value if value else None}
            for key, value in before_row.items()
            if isinstance(value, (int, float)) and isinstance(after_row.get(key), (int, float))}

result = {"notes": ["Iteration zero is warmup and excluded from comparable groups, except reconcile-backlog-0, which is retained separately because it is the only replication using real 60-second tick spacing.",
    "Backlog zero uses actual 60-second tick spacing; other backlog samples replay the resulting three-message burst.",
    "Empirical p95 for small groups is an observation, not a stable tail estimate; raw waits are retained.",
    "Per-hour rates are extrapolations from observed duration; only idle spans a continuous 30-minute window.",
    "Redis raw total includes monitoring. Parent+task-body commands exclude monitoring and worker-main broker commands.",
    "DB writes count SQL statements, not physical storage writes. Container peak is cumulative; PSS/USS peaks are per-operation samples."],
    "phases": summary, "comparison_of_medians": comparison}
(root/"measurements.json").write_text(json.dumps(result, indent=2))
lines = ["# TASKS-05 measurements", "", "All deltas are after minus baseline; lower is better for work, CPU, delay and memory.",
         "Warmup excluded unless noted. Raw observations and metric definitions are in `measurements.json` and `*.jsonl`.",
         "Wall, CPU and latency deltas on ordinary sync trials are not attributable to this change: the two phases ran at different points on a shared host and identical-work trials moved by tens of percent. The deterministic enqueue, execution, statement and Redis-command counts are the evidence; the backlog phase is the target workload.", ""]
for condition, values in comparison.items():
    lines += [f"## {condition}", "", "| Metric | Baseline median | After median | Absolute delta | Change |",
              "|---|---:|---:|---:|---:|"]
    for key in ("sync_enqueues", "task_executions", "unproductive_syncs", "wall_s", "sync_runtime_total_s",
                "worker_cpu_s", "container_cpu_s", "db_write_statements", "redis_commands_parent_and_task_bodies",
                "queue_wait_p50_s", "queue_wait_empirical_p95_s", "webhook_delay_p50_s", "webhook_delay_empirical_p95_s",
                "peak_pss_bytes", "peak_uss_bytes", "container_memory_peak_cumulative_bytes"):
        if key not in values:
            continue
        item = values[key]
        pct = f"{item['percent_delta']:+.2f}%" if item["percent_delta"] is not None else "undefined (zero baseline)"
        lines.append(f"| {key} | {item['baseline']:.6g} | {item['after']:.6g} | {item['absolute_delta']:+.6g} | {pct} |")
    lines += [""]
(root/"comparison.md").write_text("\n".join(lines))
print(json.dumps({phase: len(data["readings"]) for phase, data in summary.items()}))
