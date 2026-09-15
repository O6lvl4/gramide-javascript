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

`.js` `.mjs` `.cjs` を ECMAScript 2025 と、エンジンに既に載っている構文で読む。
属性付きモジュール、private 名・static ブロック・アクセサ・デコレータを持つクラス、
ジェネレータと非同期反復、オプショナルチェーンと論理代入、`using` 宣言、BigInt、
数値区切り、シバン。JSX はまだ読まない。`.jsx` はこのパッケージのものではない。

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

([証拠](docs/evidence/corpus-node-lib.json)、
[証拠](docs/evidence/corpus-typescript-lib-js.json))。ここでの宣言とは、関数と
クラス、クラス名または代入先の束縛名を冠したメソッド(`handlers.onClick`)、クラスの
フィールド、そしてファイル先頭レベルの `const` `let` `var` `using` 束縛。値が関数の
束縛は関数として扱う。Node `lib/` のバッチ `check` は 8 コアで約 220 MB/s、9.1 MB の
`typescript.js` は 1 プロセスで 0.20 秒。

CI が回す fixture は [ci/README.md](ci/README.md) に。`export` の前後のデコレータ、
private 名、アクセサ、計算プロパティ名、宣言に見えるテキストを含むテンプレート、
`using` 束縛、参照が拒否する 5 ファイル、生成した 2,000 関数。

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
