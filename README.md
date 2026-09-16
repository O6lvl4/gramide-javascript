# gramide-javascript

JavaScript for [gramide](https://github.com/O6lvl4/gramide), as a language
package: a scanner, a grammar value, that grammar compiled to a table, the
rules that say which nodes declare a name, and a binary of its own, so that
the language can be tested against its reference parser, measured and
regenerated without the others. Written in
[Almide](https://github.com/almide/almide).

[日本語](README_ja.md)

```
gramide_javascript check   src/*.js      exit 0 if it parses, else `file:line:col: unexpected X (expected …)`
gramide_javascript outline app.js        `L12-40 class Widget`, `  L20-24 method Widget.render`, `L50-61 function main`
gramide_javascript symbols app.js        versioned JSON names, owners, line and byte ranges
gramide_javascript tags    app.js        definitions and references: a repo map's input
gramide_javascript map .   --budget 1024 --task "fix the retry"
```

The shipped `gramide` command ([gramide-cli](https://github.com/O6lvl4/gramide-cli))
composes this package with the others; `almide install github.com/O6lvl4/gramide-cli`
is how most people get it. This repository is where JavaScript is defined
and where its correctness is checked.

## What it reads

`.js`, `.mjs`, `.cjs` and `.jsx`, as ECMAScript 2025 plus the syntax already
shipping in engines: modules with attributes, classes with private names,
static blocks, accessors and decorators, generators and async iteration,
optional chaining and logical assignment, `using` declarations, BigInt,
numeric separators, hashbangs — and JSX, in every file, because the
TypeScript compiler reads every JavaScript file that way and so does the
React world. A `<` where an operand may stand, followed by a name or `>`,
opens an element; inside it the scanner reads tags, attributes, `{ … }` and
text, and the grammar reads the shape.

The one thing the package deliberately does not do is refuse every file an
engine refuses. `a + b = c` parses, an `in` inside a `for` initialiser is not
refused, a `super` outside a class is not noticed. A file gramide rejects is
broken for the engine too; that is the direction a syntax gate must get
right, and it is the direction the oracle below checks.

## What was checked

Every `.js`, `.mjs` and `.cjs` file under Node's `lib/`, and the JavaScript
bundles TypeScript 5.9.3 ships, through this package and through the
TypeScript compiler's own parser, with the two answers compared: whether the
file parses, then for every declaration its kind, name, owner, line range and
byte range.

| corpus | files | bytes | result |
|---|---:|---:|---|
| Node `lib/` at `5c5bd227` | 427 | 5.7 MB | all parse; all 11,470 declarations match the reference |
| TypeScript 5.9.3 `lib/*.js` | 9 | 15.4 MB | all parse; all 21,216 declarations match the reference |
| MUI `docs/data/{material,joy}/components/**/*.js` at `053c4319` (JSX demos) | 547 | 1.5 MB | all parse; all 1,100 declarations match the reference |
| React `fixtures/{ssr,flight}` at `ff8f88fc` (JSX in `.js`) | 43 | 0.2 MB | all parse; all 221 declarations match the reference |

The same files through `tags`, with every reference compared against a second
oracle over the compiler's parser ([rules](ci/reference_tags.mjs)):

| corpus | references | result |
|---|---:|---|
| Node `lib/` | 38,678 | all match ([evidence](docs/evidence/tags-node-lib.json)) |
| TypeScript 5.9.3 `lib/*.js` | 127,406 | all match ([evidence](docs/evidence/tags-typescript-lib-js.json)) |
| MUI docs `.js` | 2,425 | all match ([evidence](docs/evidence/tags-mui-docs-jsx.json)) |
| React fixtures | 750 | all match ([evidence](docs/evidence/tags-react-fixtures.json)) |

([evidence](docs/evidence/corpus-node-lib.json),
[evidence](docs/evidence/corpus-typescript-lib-js.json),
[evidence](docs/evidence/corpus-mui-docs-jsx.json),
[evidence](docs/evidence/corpus-react-fixtures.json).) A declaration here
is a function or a class, a method named with its class or with the binding
its object was assigned to (`handlers.onClick`), a class field, and a
`const`, `let`, `var` or `using` binding at the top of the file — a binding
whose value is a function is a function. A reference is a call of a name
(`f(…)`, `a.b(…)`, `new Foo(…)`, an applied decorator) or a class's bare-name
base; what is deliberately not one (`f()()`, tagged templates, JSX tag names,
imports) is listed in [ci/tags_cases.py](ci/tags_cases.py). The batched `check` over Node's
`lib/` runs at about 220 MB/s on eight cores; the 9.1 MB `typescript.js` is
checked in 0.20 s in one process.

The fixtures CI runs are in [ci/README.md](ci/README.md): decorators before
and after `export`, private names, accessors, computed names, a template
holding declaration-looking text, a `using` binding, five files the
reference rejects, and 2,000 generated functions.

## Against tree-sitter

tree-sitter-javascript at `58404d8` on the tree-sitter runtime at `1b8407d`,
through [bench/tree_sitter_ranges.c](bench/tree_sitter_ranges.c): a fresh
process per file, the parse verdict and then the declaration listing, both
tools alternating, the minimum of three runs kept
([evidence](docs/evidence/tree-sitter-node-lib.json), method in
[bench/tree_sitter.py](bench/tree_sitter.py)).

| Node `lib/`, 427 files, 5.7 MB | gramide | tree-sitter |
|---|---:|---:|
| parse verdict, sum over the files | 0.909 s | 0.902 s |
| declaration listing, sum over the files | 0.999 s | 0.984 s |
| the largest file (`internal/quic/quic.js`, 190 KB), verdict | 4.6 ms | 7.0 ms |
| the largest file, listing | 6.4 ms | 8.6 ms |
| an empty file (the process floor) | 1.78 ms | 1.31 ms |

Parity on the sum, because most of these files are small and the sum is
mostly process floors, where the Almide runtime costs about half a
millisecond more than a C `main`; ahead by about 1.5× once a file is big
enough for parsing to matter. gramide's listing carries more (fields,
top-level bindings, owners on every method: 11,470 rows to 7,977), so the
listing row compares more work against less.

The same on JSX ([evidence](docs/evidence/tree-sitter-mui-docs-jsx.json)):

| MUI docs `.js`, 547 files, 1.5 MB | gramide | tree-sitter |
|---|---:|---:|
| parse verdict, sum over the files | 1.039 s | 0.922 s |
| declaration listing, sum over the files | 1.072 s | 0.940 s |
| the largest file (`autocomplete/movies.js`, 266 KB), verdict | 6.6 ms | 13.1 ms |

Small files, so the floor again; and tree-sitter-javascript reports a syntax
error on 18 of the 547, every one a JSX attribute named `in`
(`<Collapse in={open}>`), which is JSX and which the compiler and this
package read.

## How it is written

- **`src/lexer.almd`**, with `literals` and `words` — the scanner. JavaScript
  cannot be lexed by a table, for three reasons that all come down to
  context: a `/` divides or opens a regular expression depending on the token
  before it; a template literal holds expressions that hold template
  literals; and a line break ends a statement or does not, by the rules of
  automatic semicolon insertion. The scanner settles all three, keeping only
  the class of the previous token, what each open `{` and `(` is, and whether
  a line break was seen. A `newline` token in the stream is a statement
  separator and nothing else, so the grammar never mentions a line break.
  Inside a JSX element the scanner keeps a fourth thing, where it is in the
  element (a tag, its children, an expression in braces), and reads names,
  attribute strings and text as such.
- **`src/grammar.almd`**, composed from `expressions`, `declarations` and
  `statements` — the grammar as a value, in ECMAScript's precedence order.
  An arrow function is found by a balanced lookahead over its parameter
  list; an assignment is what a conditional turns out to be when an
  operator follows it; the binary levels are one `prec` ladder. Every rule
  whose body is `seq([])` or `nothing()` is an extension point — type
  annotations, type parameters, modifiers, extra declarations — and
  `with_overrides` is how the TypeScript package puts its own rules under
  those names.
- **`src/symbols.almd`** — functions, classes, methods, fields and top-level
  bindings declare names; a class or a binding owns the methods inside it;
  `export` and the declaration keyword are the envelope a declaration starts
  at. A binding inside a body is a `local_` declarator: a function with forty
  locals is not forty symbols.
- **`src/table.almd`** — generated by `gen-table`; CI fails if it is stale.

## Checks

`bash ci/check.sh` needs Almide, Node 22 and `cd ci && npm ci` for the
oracle. It runs `almide test`, the table check, the binary's smoke test and
the fixtures above.

## License

MIT or Apache-2.0, at your option.
