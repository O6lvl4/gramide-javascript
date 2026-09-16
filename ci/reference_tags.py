"""Every file of a corpus through `tags` and through the TypeScript compiler's
parser, and the references compared: every `ref call` and `ref type` line,
as a sorted list per file. The definitions are the symbols oracle's
(reference_corpus.py) and are not compared again. Writes the evidence the
README cites.

    python3 ci/reference_tags.py <root> <out.json> [--ext .js,.mjs,.cjs] [--exclude testdata]

Needs node and the `typescript` package resolvable from ci/ (`npm ci` in ci/)."""
from pathlib import Path
import hashlib, json, platform, subprocess, sys

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
exts = tuple(".js,.mjs,.cjs".split(","))
excluded = []
for i, arg in enumerate(sys.argv):
    if arg == "--ext": exts = tuple(sys.argv[i + 1].split(","))
    if arg == "--exclude": excluded = sys.argv[i + 1].split(",")
here = Path(__file__).resolve().parent
binary = here.parent / ("gramide_" + here.parent.name.split("-", 1)[1])
oracle = here / "reference_tags.mjs"

files = sorted(p for p in root.rglob("*") if p.suffix in exts and not any(x in p.parts for x in excluded))
reference = {}
ref = subprocess.run(["node", str(oracle), *map(str, files)], capture_output=True, text=True, cwd=here, check=True)
for line in ref.stdout.splitlines():
    row = json.loads(line); reference[row["path"]] = row

results = {"platform": platform.platform(), "node": subprocess.check_output(["node", "--version"], text=True).strip(),
           "typescript": subprocess.check_output(["node", "-e", "console.log(require('typescript').version)"], text=True, cwd=here).strip(),
           "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "root": str(root), "ext": list(exts), "excluded": excluded,
           "files": len(files), "bytes": sum(p.stat().st_size for p in files),
           "reference_rejected": [], "gramide_rejected": [], "reference_mismatch": [], "passed": 0, "references": 0}
for p in files:
    key = str(p); rel = str(p.relative_to(root)); r = reference[key]
    if not r["accepted"]:
        results["reference_rejected"].append(rel); continue
    got = subprocess.run([str(binary), "tags", key], capture_output=True, text=True)
    if got.returncode:
        results["gramide_rejected"].append({"path": rel, "error": got.stderr.strip()}); continue
    actual = sorted(l for l in got.stdout.splitlines() if l.startswith("ref "))
    expected = sorted(r["refs"])
    if actual != expected:
        missing = sorted(set(expected) - set(actual))[:3]; extra = sorted(set(actual) - set(expected))[:3]
        results["reference_mismatch"].append({"path": rel, "expected_count": len(expected), "actual_count": len(actual), "missing": missing, "extra": extra})
    else:
        results["passed"] += 1; results["references"] += len(expected)
try:
    results["reference_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
except subprocess.CalledProcessError:
    pass
results["input_sha256"] = hashlib.sha256(b"".join(hashlib.sha256(p.read_bytes()).digest() for p in files)).hexdigest()
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2) + "\n")
print({k: (len(v) if isinstance(v, list) else v) for k, v in results.items() if k not in ("input_sha256", "ext", "excluded", "root", "binary_sha256", "platform")})
for row in results["gramide_rejected"][:10]: print("gramide rejected", row)
for row in results["reference_mismatch"][:10]: print("mismatch", row)
sys.exit(1 if results["gramide_rejected"] or results["reference_mismatch"] else 0)
