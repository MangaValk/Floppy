"""Host launcher; never connects to the application's normal DB or Redis."""
import json
import subprocess
import sys
from pathlib import Path

out = Path(__file__).resolve().parent
mode = sys.argv[1]
assert mode in ("baseline", "after", "smoke")
source = Path("/tmp/floppy-tasks05-source")
if mode == "after":
    source = Path("/tmp/floppy-tasks05-after")

def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()

assert not run(["docker", "ps", "--filter", "name=^tasks05-(smoke|baseline|after)$", "--format", "{{.Names}}"]), "another TASKS-05 run is active"
run(["docker", "exec", "tasks05-redis", "redis-cli", "FLUSHALL"])
sha = run(["git", "rev-parse", "HEAD"])
command = ["docker", "run", "-d", "--name", f"tasks05-{mode}", "--network", "tasks05-net",
    "--cpus", "2", "--memory", "2g", "--memory-swap", "2g", "--pids-limit", "256",
    "--ulimit", "nofile=4096:4096", "--entrypoint", "python", "-e", f"TASKS05_SHA={sha}",
    "-v", f"{source}/src:/source:ro", "-v", f"{out}:/results", "floppy:start01-baseline",
    "/results/bench.py", mode, sys.argv[2] if len(sys.argv)>2 else "1800"]
(out/f"{mode}-launch.json").write_text(json.dumps({"command": command, "git_sha": sha,
    "host": run(["uname", "-a"]), "host_cpu_memory": run(["sysctl", "-n", "machdep.cpu.brand_string", "hw.memsize"]),
    "docker": json.loads(run(["docker", "info", "--format", "{{json .}}"])),
    "source_diff": run(["git", "diff", "--", "src/app/statistics_sync.py"]),
    "other_containers": run(["docker", "ps", "--format", "{{.Names}} {{.Image}} {{.Status}}"]),
    "image": json.loads(run(["docker", "image", "inspect", "floppy:start01-baseline"]))}, indent=2))
print(run(command))
