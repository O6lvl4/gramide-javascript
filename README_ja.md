# gramide-javascript

[gramide](https://github.com/O6lvl4/gramide) の JavaScript 言語パッケージ。
スキャナ、値としての文法、その文法をコンパイルしたテーブル、どのノードが名前を
宣言するかの規則、そして単体のバイナリを持ち、この言語だけを参照パーサと照合し、
計測し、再生成できる。[Almide](https://github.com/almide/almide) 製。

[English](README.md)

```
gramide_javascript check   src/*.js      パースできれば exit 0、でなければ `file:line:col: unexpected X (expected …)`
gramide_javascript outline app.js        `L12-40 class Widget`、`  L20-24 method Widget.render`、`L50-61 function main`
gramide_javascript symbols app.js        名前・所有者・行とバイト範囲のバージョン付き JSON
gramide_javascript tags    app.js        定義と参照。リポジトリマップの入力
gramide_javascript map .   --budget 1024 --task "fix the retry"
```

配布される `gramide` コマンド([gramide-cli](https://github.com/O6lvl4/gramide-cli))は
このパッケージを他の言語と合成したもので、普通は `almide install github.com/O6lvl4/gramide-cli`
で手に入る。このリポジトリは JavaScript を定義し、その正しさを検証する場所。

## 読めるもの

`.js` `.mjs` `.cjs` `.jsx` を ECMAScript 2025 と、エンジンに既に載っている構文で読む。
属性付きモジュール、private 名・static ブロック・アクセサ・デコレータを持つクラス、
ジェネレータと非同期反復、オプショナルチェーンと論理代入、`using` 宣言、BigInt、
数値区切り、シバン。そして JSX を、すべてのファイルで。TypeScript コンパイラはどの
JavaScript ファイルもそう読むし、React の世界もそうだから。オペランドが立てる位置の `<` に
名前か `>` が続けば要素が始まり、その中でスキャナはタグ・属性・`{ … }`・テキストを読み、
文法は形を読む。

意図的にやらないのは、エンジンが拒否するファイルをすべて拒否すること。`a + b = c` は
通り、`for` の初期化式の中の `in` は拒否せず、クラス外の `super` にも気づかない。
gramide が拒否したファイルはエンジンにとっても壊れている。それが構文ゲートが正しく
なければならない向きであり、下の oracle が検証する向き。

## 検証したこと

Node の `lib/` 配下の全 `.js` `.mjs` `.cjs` と、TypeScript 5.9.3 が配布する
JavaScript バンドルを、このパッケージと TypeScript コンパイラ自身のパーサの両方に
通し、答えを比較した。ファイルがパースできるか、そして各宣言の種別・名前・所有者・
行範囲・バイト範囲。

| コーパス | ファイル | バイト | 結果 |
|---|---:|---:|---|
| Node `lib/` (`5c5bd227`) | 427 | 5.7 MB | 全件パース。11,470 宣言すべてが参照と一致 |
| TypeScript 5.9.3 `lib/*.js` | 9 | 15.4 MB | 全件パース。21,216 宣言すべてが参照と一致 |
| MUI `docs/data/{material,joy}/components/**/*.js`(`053c4319`、JSX デモ） | 547 | 1.5 MB | 全件パース。1,100 宣言すべてが参照と一致 |
| React `fixtures/{ssr,flight}`(`ff8f88fc`、`.js` 内の JSX） | 43 | 0.2 MB | 全件パース。221 宣言すべてが参照と一致 |

同じファイルを `tags` にも通し、参照をすべて、コンパイラのパーサの上の第二の oracle
([規則](ci/reference_tags.mjs))と比較した:

| コーパス | 参照 | 結果 |
|---|---:|---|
| Node `lib/` | 38,678 | すべて一致([証拠](docs/evidence/tags-node-lib.json)) |
| TypeScript 5.9.3 `lib/*.js` | 127,406 | すべて一致([証拠](docs/evidence/tags-typescript-lib-js.json)) |
| MUI docs `.js` | 2,425 | すべて一致([証拠](docs/evidence/tags-mui-docs-jsx.json)) |
| React fixtures | 750 | すべて一致([証拠](docs/evidence/tags-react-fixtures.json)) |

([証拠](docs/evidence/corpus-node-lib.json)、
[証拠](docs/evidence/corpus-typescript-lib-js.json)、
[証拠](docs/evidence/corpus-mui-docs-jsx.json)、
[証拠](docs/evidence/corpus-react-fixtures.json))。ここでの宣言とは、関数と
クラス、クラス名または代入先の束縛名を冠したメソッド(`handlers.onClick`)、クラスの
フィールド、そしてファイル先頭レベルの `const` `let` `var` `using` 束縛。値が関数の
束縛は関数として扱う。参照とは、名前の呼び出し(`f(…)`、`a.b(…)`、`new Foo(…)`、適用された
デコレータ)と、クラスの裸の名前の基底。意図して参照にしないもの(`f()()`、タグ付きテンプレート、
JSX のタグ名、import)は [ci/tags_cases.py](ci/tags_cases.py) に列挙してある。Node `lib/` のバッチ `check` は 8 コアで約 220 MB/s、9.1 MB の
`typescript.js` は 1 プロセスで 0.20 秒。

CI が回す fixture は [ci/README.md](ci/README.md) に。`export` の前後のデコレータ、
private 名、アクセサ、計算プロパティ名、宣言に見えるテキストを含むテンプレート、
`using` 束縛、参照が拒否する 5 ファイル、生成した 2,000 関数。

## tree-sitter との比較

tree-sitter-javascript(`58404d8`)を tree-sitter ランタイム(`1b8407d`)の上で
[bench/tree_sitter_ranges.c](bench/tree_sitter_ranges.c) から呼び、ファイルごとに新しい
プロセスで、パースの合否と宣言の一覧を、両者交互に、3 回の最小値で計測
([証拠](docs/evidence/tree-sitter-node-lib.json)、方法は
[bench/tree_sitter.py](bench/tree_sitter.py))。

| Node `lib/`、427 ファイル、5.7 MB | gramide | tree-sitter |
|---|---:|---:|
| パースの合否、全ファイルの合計 | 0.909 秒 | 0.902 秒 |
| 宣言の一覧、全ファイルの合計 | 0.999 秒 | 0.984 秒 |
| 最大のファイル(`internal/quic/quic.js`、190 KB)、合否 | 4.6 ms | 7.0 ms |
| 最大のファイル、一覧 | 6.4 ms | 8.6 ms |
| 空ファイル(プロセスの床) | 1.78 ms | 1.31 ms |

合計は同等。ファイルの大半が小さく、合計はほぼプロセスの床。パースが効く大きさの
ファイルでは約 1.5 倍速い。床そのものは `posix_spawn` で測ると C のハーネスより
0.28 ms 高く、うち 0.15 ms は Rust の標準ランタイムの起動(`main` を持つ Rust プログラム
なら何でも同じ)、残りはこのバイナリのページインと言語のスキャナと表の準備
([証拠](docs/evidence/process-floor.json))。プロセスごとに一度払うだけで、まとめての
`check`、ディレクトリの outline、エディタの常駐では数百ファイルに一度なので、そのままにしている。
gramide の一覧はフィールド・先頭レベルの束縛・全メソッドの所有者を含む
(11,470 行に対して 7,977 行)ので、一覧の行は多い仕事と少ない仕事の比較になっている。

JSX でも同じ([証拠](docs/evidence/tree-sitter-mui-docs-jsx.json)):

| MUI docs `.js`、547 ファイル、1.5 MB | gramide | tree-sitter |
|---|---:|---:|
| パースの合否、全ファイルの合計 | 1.039 秒 | 0.922 秒 |
| 宣言の一覧、全ファイルの合計 | 1.072 秒 | 0.940 秒 |
| 最大のファイル(`autocomplete/movies.js`、266 KB)、合否 | 6.6 ms | 13.1 ms |

小さいファイルばかりなので、ここも床の勝負。そして tree-sitter-javascript は 547 のうち
18 に構文エラーを報告する。すべて `in` という名前の JSX 属性(`<Collapse in={open}>`)で、
JSX として正しく、コンパイラもこのパッケージも読む。

### キー入力 1 回

エディタはキー入力のたびに全文をパースし直さず、パーサに編集を渡す。gramide はパース済みの
ファイルを回復項目(ここではトップレベルの宣言と、波括弧の中の文・クラスメンバ)として持ち、
編集が触れた最小の項目だけを読み直す
([仕組み](https://github.com/O6lvl4/gramide/blob/main/docs/incremental.md))。
同じ 1,000 編集をプロセス内で、gramide の `reparse-bench` と tree-sitter の
`ts_tree_edit` + 再パース(同じ C ハーネス)に与える。各編集は 13 文字以上の単語の 6 文字目に
1 文字を打つか消すもので、構文は変わらない。50 回ごとに全文パースと照合
([証拠](docs/evidence/incremental-node-lib.json)):

| Node `internal/quic/quic.js`(190 KB) | gramide | tree-sitter |
|---|---:|---:|
| 中央値 | 48 µs | 97 µs |
| 90 パーセンタイル | 86 µs | 141 µs |
| 参考: 全文パース | 3.3 ms | |

出てくるものは全文パースと同じ。Node の `lib/` で 416 ファイルに 10 回ずつランダム編集
(4,160 編集、すべて同じテキストの全文パースとトークン単位・ノード単位で照合)して差は 0、
全文へのフォールバックも 0([証拠](docs/evidence/incremental-corpus-node-lib.json))。
10 回に 1 回、対応のない `{` を打ってファイルを壊し、回復パースと照合しても差は 0。
4,160 のうち 346 が全文読み直し(壊した編集と、壊れた箇所の中の窓)
([証拠](docs/evidence/incremental-corpus-node-lib-breaking.json))。`ci/incremental_check.py`
がこれを回し、`reparse --edit START:OLD_END:NEW_END --new FILE` が 1 編集のコマンド。

## 作り

- **`src/lexer.almd`**(`literals`、`words` と共に)— スキャナ。JavaScript はテーブルでは
  字句解析できない。理由は 3 つで、すべて文脈に帰着する。`/` が除算か正規表現の始まりかは
  直前のトークンで決まる。テンプレートリテラルは式を含み、式はテンプレートリテラルを含む。
  改行が文を終えるかどうかは自動セミコロン挿入の規則で決まる。スキャナはこの 3 つを
  片づけ、覚えているのは直前トークンの種別、開いている `{` と `(` がそれぞれ何か、
  改行を見たか、だけ。ストリームの `newline` トークンは文の区切りであってそれ以外の
  何物でもないので、文法は改行に一切触れない。
- **`src/grammar.almd`**(`expressions`、`declarations`、`statements` から合成)—
  ECMAScript の優先順位順に書いた、値としての文法。アロー関数は引数リストを括弧の
  釣り合いで読み飛ばす先読みで見つける。代入は、条件式を読んだ後に演算子が続いた
  ときにそうだと分かる。二項演算の段は 1 本の `prec` はしご。本体が `seq([])` か
  `nothing()` の規則はすべて拡張点で(型注釈、型パラメータ、修飾子、追加の宣言)、
  `with_overrides` が TypeScript パッケージが自分の規則をその名前に置く手段。
- **`src/symbols.almd`** — 関数・クラス・メソッド・フィールド・先頭レベルの束縛が
  名前を宣言し、クラスと束縛がその中のメソッドを所有する。`export` と宣言キーワードは
  宣言の開始位置を包む封筒。本体の中の束縛は `local_` 宣言子で、40 個のローカル変数を
  持つ関数は 40 個のシンボルではない。
- **`src/table.almd`** — `gen-table` が生成。古ければ CI が落ちる。

## 検証

`bash ci/check.sh` には Almide、Node 22、oracle のための `cd ci && npm ci` が要る。
`almide test`、テーブル検査、バイナリのスモークテスト、上記の fixture を回す。

## ライセンス

MIT または Apache-2.0。
