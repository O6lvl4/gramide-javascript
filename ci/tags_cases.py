"""What the JavaScript package reports as references, and what it does not.

`tags` is the repo map's input: definitions to rank, references to rank them
by. A reference is a call of a name or a class's base. Everything this does
not cover is listed at the bottom, as a case with the output it does give, so
that adding it later is a diff here rather than a surprise. The corpora in
docs/evidence/tags-*.json check the same rules against the TypeScript
compiler's parser on real code; this file is the rules, one line each."""
from pathlib import Path
import subprocess, tempfile

BIN = Path(__file__).resolve().parents[1] / "gramide_javascript"

COVERED = [
 ("a plain call", "f(1)\n", ["ref call f L1"]),
 ("a call through a property of a name", "a.b(1)\n", ["ref call a.b L1"]),
 ("a call through a longer chain names the method only", "a.b.c(1)\nthis.m(2)\nsuper.m(3)\n", ["ref call c L1", "ref call m L2", "ref call m L3"]),
 ("an optional call", "a?.b(1)\nf?.(2)\n", ["ref call a.b L1", "ref call f L2"]),
 ("a class instantiated is a call", "new Foo(1)\nnew a.Foo(2)\n", ["ref call Foo L1", "ref call a.Foo L2"]),
 ("a decorator that is applied", "@dec() class K {}\n", ["def class K L1-1", "ref call dec L1"]),
 ("a call inside a call, in order", "f(g(1))\n", ["ref call f L1", "ref call g L1"]),
 ("a base class that is a bare name", "class A extends B {}\n", ["def class A L1-1", "ref type B L1"]),
 ("a call inside JSX", "const j = <Foo bar={g(1)} />\n", ["def const j L1-1", "ref call g L1"]),
 ("methods are named with their class, functions with nothing", "class A { m() { return h() } }\nfunction f() {}\n",
  ["def class A L1-1", "def method A.m L1-1", "ref call h L1", "def function f L2-2"]),
]

# Each of these is a reference a reader can see and `tags` does not report. None
# is a defect to be fixed quietly: each is a decision, and changing one should
# change this list. The oracle in reference_tags.mjs states the same decisions.
NOT_COVERED = [
 ("a call of a call, of an element, of a group: nothing is named", "f()()\narr[0]()\n(f)()\n", ["ref call f L1"]),
 ("a tagged template is not a call", "tag`x`\n", []),
 ("`new` without parentheses is not a call", "new Foo\n", []),
 ("a bare-name decorator names a callable, but there is no call to see", "@deco class K {}\n", ["def class K L1-1"]),
 ("a base that is an expression is not a name", "class A extends mix(B) {}\n", ["def class A L1-1", "ref call mix L1"]),
 ("a JSX tag names a component, and is not reported", "const j = <Foo />\n", ["def const j L1-1"]),
 ("an import is a reference, and Rust's `use` is not reported either", "import { x } from 'm'\nimport('n')\n", []),
]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    for label, source, expected in COVERED + NOT_COVERED:
        path = root / "case.js"
        path.write_text(source)
        result = subprocess.run([str(BIN), "tags", str(path)], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0 and not result.stderr, (label, result.returncode, result.stderr)
        assert result.stdout.split("\n")[:-1] == expected, (label, source, expected, result.stdout)
print(f"JavaScript tags: {len(COVERED)} reported cases and {len(NOT_COVERED)} deliberately unreported ones")
