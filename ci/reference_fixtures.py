"""Structured ranges against the TypeScript compiler's parser, on fixtures;
no model calls. The corpus-wide run is ci/reference_corpus.py."""
from pathlib import Path
import json, subprocess, tempfile
HERE = Path(__file__).resolve().parent
BIN = HERE.parent / "gramide_javascript"
COMPARED = ["kind", "name", "owner", "start", "end", "start_byte", "end_byte"]

def oracle(paths):
    p = subprocess.run(["node", str(HERE / "reference_ranges.mjs"), *map(str, paths)], capture_output=True, text=True, cwd=HERE, check=True)
    return {json.loads(l)["path"]: json.loads(l) for l in p.stdout.splitlines()}

def symbols(path):
    p = subprocess.run([str(BIN), "symbols", str(path)], capture_output=True, text=True, check=True)
    d = json.loads(p.stdout); assert d["schema_version"] == 1 and d["complete"] is True
    return [{k: s[k] for k in COMPARED} for s in d["symbols"]]

FIXTURE = '''// 日本語 before declarations tests UTF-8 byte offsets.
import { x } from "./x.js"
export const VERSION = "1", limit = 3;
let count = 0
var legacy = function () {}
@decorate("class")
export default class Widget extends Base {
  static #registry = new Map();
  #size = 0
  static { Widget.#registry.clear() }
  constructor(name, ...rest) { super(name) }
  get size() { return this.#size }
  set size(v) { this.#size = v }
  async *items() { yield* this.list }
  static of(...xs) { return new Widget(xs[0]) }
  ["computed" + 1]() {}
}
export function render(widget, { depth = 1 } = {}) {
  const local = 1
  function inner() {
    const text = `}
function phantom() {}`
    return text
  }
  return inner()
}
export const helper = async (a, b = 2) => a ** b
const handlers = { onClick() {}, get value() { return 1 }, nested: { deep() {} } }
const Anon = class { method() {} }
using resource = acquire()
'''

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    fixture = root / "ranges.js"; fixture.write_text(FIXTURE)
    expected = oracle([fixture])[str(fixture)]
    assert expected["accepted"], "the fixture must parse for the oracle"
    actual = symbols(fixture)
    want = [{k: s[k] for k in COMPARED} for s in expected["symbols"]]
    assert actual == want, "\n".join(f"{a}\n{b}" for a, b in zip(actual, want) if a != b) or (actual, want)
    raw = fixture.read_bytes()
    for s in json.loads(subprocess.check_output([str(BIN), "symbols", str(fixture)], text=True))["symbols"]:
        assert raw[s["start_byte"]:s["end_byte"]].strip()
    total = len(want)
    # what the oracle rejects, gramide rejects too: the direction a gate must get right
    broken = root / "broken.js"
    for source in ["function f() {\n  return (1\n}\n", "if (a) b() else c()\n", "let x = 'unterminated\n", "class A { m( {} }\n", "x = 3in\n"]:
        broken.write_text(source)
        assert not oracle([broken])[str(broken)]["accepted"], source
        p = subprocess.run([str(BIN), "symbols", str(broken)], capture_output=True, text=True)
        assert p.returncode != 0 and not p.stdout, (source, p.returncode, p.stdout)
    # a per-node copy of the token stream once made this path quadratic elsewhere
    large = root / "many.js"
    large.write_text("".join(f"function F{i}(x) {{ return x + {i} }}\n" for i in range(2000)))
    actual = symbols(large)
    assert actual == [{k: s[k] for k in COMPARED} for s in oracle([large])[str(large)]["symbols"]] and len(actual) == 2000
print(f"Structured ranges passed: TypeScript parser oracle on UTF-8, decorators, private names, templates, {total} fixture declarations, 5 rejections and 2,000 functions")
