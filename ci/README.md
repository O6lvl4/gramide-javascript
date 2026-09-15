# Reproducible checks

Run `bash ci/check.sh` from a checkout with Almide and Node installed, or set
`ALMIDE_BIN` to an absolute compiler path. This runs the package's tests,
builds its own binary from `cli/main.almd`, fails if `src/table.almd` is not
what the grammar compiles to, drives the binary through temporary fixtures,
and compares `symbols` with `ci/reference_ranges.mjs`, an oracle over the
TypeScript compiler's own parser that knows nothing of gramide — on a UTF-8
fixture with decorators, private names, accessors, computed names, templates
holding declaration-looking text and a `using` binding; on five files the
oracle rejects, which gramide must reject too; and on 2,000 generated
functions. No model API or credentials are used.

The oracle is `typescript` 5.9.3 from npm, pinned in `ci/package.json`;
`cd ci && npm ci` fetches it, and `check.sh` skips the oracle steps with a
message when it is missing.

`python3 ci/reference_corpus.py /path/to/node/lib docs/evidence/corpus-node-lib.json`
runs the same comparison over every `.js`, `.mjs` and `.cjs` file under a
directory — acceptance both ways, then every declaration's kind, name, owner,
line and byte range — and writes the evidence the README cites.

`./gramide_javascript lex-check FILE...` runs the scanner alone, strictly,
and names the files that do not lex: the first gate a corpus goes through.

CI pins Almide to `dff9a458f2e581631bb6537c856a7974036e4153`, Rust to
`1.94.0` and Node to 22. Upgrade these deliberately and rerun the checks
together.
