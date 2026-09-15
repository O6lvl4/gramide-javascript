"""Every file of a corpus through gramide and through the TypeScript compiler's
parser, and the two answers compared: acceptance both ways, then declaration
names, owners, line and byte ranges. Writes the evidence the README cites.

    python3 ci/reference_corpus.py <root> <out.json> [--ext .js,.mjs,.cjs] [--exclude testdata]

Needs node and the `typescript` package resolvable from ci/ (`npm ci` in ci/)."""
from pathlib import Path
import hashlib, json, platform, subprocess, sys, time

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
exts = tuple(".js,.mjs,.cjs".split(","))
excluded = []
for i, arg in enumerate(sys.argv):
    if arg == "--ext": exts = tuple(sys.argv[i + 1].split(","))
    if arg == "--exclude": excluded = sys.argv[i + 1].split(",")
here = Path(__file__).resolve().parent
binary = here.parent / "gramide_javascript"
oracle = here / "reference_ranges.mjs"
COMPARED = ["kind", "name", "owner", "start", "end", "start_byte", "end_byte"]

files = sorted(p for p in root.rglob("*") if p.suffix in exts and not any(x in p.parts for x in excluded))
total_bytes = sum(p.stat().st_size for p in files)

# gramide: one batched check, then symbols per file (the oracle compares per file)
started = time.perf_counter()
check = subprocess.run([str(binary), "check", *map(str, files)], capture_output=True, text=True)
check_seconds = time.perf_counter() - started
rejected = {}
for line in check.stdout.splitlines() + check.stderr.splitlines():
    if line.endswith(": ok") or not line.strip(): continue
    path, _, message = line.partition(": ")
    rejected[path] = message

# the oracle: one node process over every file
reference = {}
ref = subprocess.run(["node", str(oracle), *map(str, files)], capture_output=True, text=True, cwd=here, check=True)
for line in ref.stdout.splitlines():
    row = json.loads(line); reference[row["path"]] = row

results = {"platform": platform.platform(), "node": subprocess.check_output(["node", "--version"], text=True).strip(),
           "typescript": subprocess.check_output(["node", "-e", "console.log(require('typescript').version)"], text=True, cwd=here).strip(),
           "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "root": str(root), "ext": list(exts), "excluded": excluded,
           "files": len(files), "bytes": total_bytes, "check_seconds": round(check_seconds, 3),
           "megabytes_per_second": round(total_bytes / 1e6 / check_seconds, 1) if check_seconds else None,
           "reference_rejected": [], "gramide_rejected": [], "range_mismatch": [], "passed": 0, "symbols": 0}
for p in files:
    key = str(p); rel = str(p.relative_to(root)); r = reference[key]
    if not r["accepted"]:
        results["reference_rejected"].append({"path": rel, "gramide": rejected.get(key, "ok")}); continue
    if key in rejected:
        results["gramide_rejected"].append({"path": rel, "error": rejected[key]}); continue
    got = subprocess.run([str(binary), "symbols", key], capture_output=True, text=True)
    if got.returncode:
        results["gramide_rejected"].append({"path": rel, "error": got.stderr.strip()}); continue
    actual = [{k: s[k] for k in COMPARED} for s in json.loads(got.stdout)["symbols"]]
    expected = [{k: s[k] for k in COMPARED} for s in r["symbols"]]
    if actual != expected:
        first = next(((a, b) for a, b in zip(actual, expected) if a != b), (actual[len(expected):][:1], expected[len(actual):][:1]))
        results["range_mismatch"].append({"path": rel, "expected_count": len(expected), "actual_count": len(actual), "first_difference": {"actual": first[0], "expected": first[1]}})
    else:
        results["passed"] += 1; results["symbols"] += len(expected)
try:
    results["reference_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
except subprocess.CalledProcessError:
    pass
results["input_sha256"] = hashlib.sha256(b"".join(hashlib.sha256(p.read_bytes()).digest() for p in files)).hexdigest()
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2) + "\n")
print({k: (len(v) if isinstance(v, list) else v) for k, v in results.items() if k not in ("input_sha256", "ext", "excluded", "root", "binary_sha256", "platform")})
for row in results["gramide_rejected"][:10]: print("gramide rejected", row)
for row in results["range_mismatch"][:10]: print("mismatch", row)
sys.exit(1 if results["gramide_rejected"] or results["range_mismatch"] else 0)
