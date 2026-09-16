"""gramide against tree-sitter on a corpus: fresh processes, one file per
call, the parse verdict (`check` vs `--check`) and the declaration listing
(`symbols` vs the ranges the C harness prints), in deterministic alternating
order, `--samples` runs per file, the minimum kept. Writes the evidence the
README cites.

    python3 bench/tree_sitter.py --gramide ./gramide_javascript --tree-sitter /tmp/ts-js \
        --root /path/to/node/lib --ext .js,.mjs,.cjs --out docs/evidence/tree-sitter-node-lib.json

Nothing here is an incremental-parse or editor-latency measurement; it is
the cost an agent pays for one call. tree-sitter's harness is
bench/tree_sitter_ranges.c, built against the pinned tree-sitter sources; it
lists functions, classes, methods, interfaces, enums and type aliases, while
gramide's `symbols` also lists fields, top-level bindings and namespaces and
names every method with its owner, so the two listings are not compared line
for line, only counted."""
from pathlib import Path
import argparse, hashlib, json, platform, subprocess, sys, time

ap = argparse.ArgumentParser()
ap.add_argument("--gramide", type=Path, required=True)
ap.add_argument("--tree-sitter", type=Path, required=True)
ap.add_argument("--root", type=Path, required=True)
ap.add_argument("--ext", default=".js,.mjs,.cjs")
ap.add_argument("--exclude", default="testdata")
ap.add_argument("--samples", type=int, default=3)
ap.add_argument("--out", type=Path, required=True)
args = ap.parse_args()
args.gramide = args.gramide.resolve(); args.tree_sitter = args.tree_sitter.resolve()
exts = tuple(args.ext.split(","))
files = sorted(p for p in args.root.resolve().rglob("*") if p.suffix in exts and args.exclude not in p.parts)

def timed(cmd):
    t = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True)
    return time.perf_counter() - t, p

def best(cmd):
    timed(cmd)
    runs = [timed(cmd) for _ in range(args.samples)]
    return min(r[0] for r in runs), runs[0][1]

rows = []
for p in files:
    g_check, gc = best([str(args.gramide), "check", str(p)])
    t_check, tc = best([str(args.tree_sitter), "--check", str(p)])
    g_syms, gs = best([str(args.gramide), "symbols", str(p)])
    t_syms, tsr = best([str(args.tree_sitter), str(p)])
    rows.append({"path": str(p.relative_to(args.root.resolve())), "bytes": p.stat().st_size,
                 "gramide_check_s": round(g_check, 5), "tree_sitter_check_s": round(t_check, 5),
                 "gramide_symbols_s": round(g_syms, 5), "tree_sitter_ranges_s": round(t_syms, 5),
                 "gramide_ok": gc.returncode == 0, "tree_sitter_ok": tc.returncode == 0,
                 "gramide_declarations": len(json.loads(gs.stdout)["symbols"]) if gs.returncode == 0 else None,
                 "tree_sitter_declarations": len(tsr.stdout.splitlines()) if tsr.returncode == 0 else None})

total_bytes = sum(r["bytes"] for r in rows)
def total(key): return round(sum(r[key] for r in rows), 3)
largest = max(rows, key=lambda r: r["bytes"])
summary = {"files": len(rows), "bytes": total_bytes, "samples": args.samples,
           "gramide_check_s": total("gramide_check_s"), "tree_sitter_check_s": total("tree_sitter_check_s"),
           "gramide_symbols_s": total("gramide_symbols_s"), "tree_sitter_ranges_s": total("tree_sitter_ranges_s"),
           "gramide_check_mb_s": round(total_bytes / 1e6 / total("gramide_check_s"), 1),
           "tree_sitter_check_mb_s": round(total_bytes / 1e6 / total("tree_sitter_check_s"), 1),
           "gramide_rejected": [r["path"] for r in rows if not r["gramide_ok"]],
           "tree_sitter_errors": [r["path"] for r in rows if not r["tree_sitter_ok"]],
           "gramide_declarations": sum(r["gramide_declarations"] or 0 for r in rows),
           "tree_sitter_declarations": sum(r["tree_sitter_declarations"] or 0 for r in rows),
           "largest": largest}
report = {"platform": platform.platform(), "root": str(args.root.resolve()), "ext": list(exts),
          "gramide_sha256": hashlib.sha256(args.gramide.read_bytes()).hexdigest(),
          "tree_sitter_harness_sha256": hashlib.sha256(args.tree_sitter.read_bytes()).hexdigest(),
          "summary": summary, "files_detail": rows}
try:
    report["reference_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.root, text=True, stderr=subprocess.DEVNULL).strip()
except subprocess.CalledProcessError:
    pass
args.out.parent.mkdir(parents=True, exist_ok=True)
args.out.write_text(json.dumps(report, indent=1) + "\n")
print(json.dumps({k: v for k, v in summary.items() if k != "largest"}))
print("largest", json.dumps(largest))
