#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
compiler="${ALMIDE_BIN:-almide}"

"$compiler" test
"$compiler" build cli/main.almd --release -o gramide_javascript
./gramide_javascript gen-table | diff -u src/table.almd - \
  || { echo "src/table.almd is not what the grammar compiles to: ./gramide_javascript gen-table > src/table.almd"; exit 1; }
python3 ci/smoke.py

# The oracle is the TypeScript compiler's parser (typescript 5.x from npm):
# ci/package.json pins it, and `npm ci` in ci/ fetches it.
if command -v node >/dev/null && [ -d ci/node_modules/typescript ]; then
  python3 ci/reference_fixtures.py
else
  echo "node or ci/node_modules/typescript missing: oracle checks skipped (cd ci && npm ci)"
fi

# A per-file ratchet, not a target. Each file is held where it stands, so a
# clean one cannot rot up to the worst one. Numbers only ever fall;
# --write-baseline records a fall.
if command -v codopsy-almd >/dev/null; then cx=codopsy-almd
elif command -v codopsy_almd >/dev/null; then cx=codopsy_almd
else cx=""; fi
if [ -n "$cx" ]; then
  "$cx" --quiet --baseline .codopsy-almd.json src/
else
  echo "codopsy-almd not on PATH: structural check skipped (almide install github.com/O6lvl4/codopsy-almd)"
fi
