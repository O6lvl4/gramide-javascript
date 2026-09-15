"""Exercise the package's own binary; no network, no model, no oracle."""
from pathlib import Path
import json, subprocess, tempfile

BIN = Path(__file__).resolve().parents[1] / "gramide_javascript"

def run(*args, code=0):
    p = subprocess.run([str(BIN), *map(str, args)], capture_output=True, text=True, timeout=30)
    assert p.returncode == code, (args, p.returncode, p.stdout, p.stderr)
    return p.stdout

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    for ext in ["js", "mjs", "cjs"]:
        source = root / ("valid." + ext)
        source.write_text("export class Box {\n  read() { return /re/.test(this.x) ? 1 : 2 }\n}\nconst f = (a) => a\n")
        run("check", source)
        out = run("outline", source)
        assert "Box.read" in out and "function f" in out, out
        doc = json.loads(run("symbols", source))
        assert doc["lang"] == "javascript" and doc["complete"] is True and doc["symbols"][0]["start_byte"] == 0, doc
        broken = root / ("broken." + ext)
        broken.write_text("export class Box {\n  read() { return 1 }\n  broken( {\n  also() { return 2 }\n}\nfunction f() {}\n")
        run("check", broken, code=1)
        # a reader still answers: the members around the damage, and the function after it
        recovered = run("outline", broken)
        assert "Box.read" in recovered and "Box.also" in recovered and "function f" in recovered, recovered
    assert run("version").splitlines()[0].startswith("gramide_javascript ")
print("CLI smoke passed: .js .mjs .cjs check, outline, symbols and recovered outline")
