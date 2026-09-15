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

`.js`, `.mjs` and `.cjs`, as ECMAScript 2025 plus the syntax already shipping
in engines: modules with attributes, classes with private names, static
blocks, accessors and decorators, generators and async iteration, optional
chaining and logical assignment, `using` declarations, BigInt, numeric
separators, hashbangs. JSX is not read yet; a `.jsx` file is not this
package's.

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

([evidence](docs/evidence/corpus-node-lib.json),
[evidence](docs/evidence/corpus-typescript-lib-js.json).) A declaration here
is a function or a class, a method named with its class or with the binding
its object was assigned to (`handlers.onClick`), a class field, and a
`const`, `let`, `var` or `using` binding at the top of the file — a binding
whose value is a function is a function. The batched `check` over Node's
`lib/` runs at about 220 MB/s on eight cores; the 9.1 MB `typescript.js` is
checked in 0.20 s in one process.

The fixtures CI runs are in [ci/README.md](ci/README.md): decorators before
and after `export`, private names, accessors, computed names, a template
holding declaration-looking text, a `using` binding, five files the
reference rejects, and 2,000 generated functions.

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
