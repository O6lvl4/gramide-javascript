// Independent reference oracle using the TypeScript compiler's parser, not
// gramide's tree. One JSON object per input path, one per line:
//   {"path", "accepted", "refs": ["ref call f L3", "ref type Foo L1", ...]}
// The refs are what gramide's `tags` should say about the file, in the same
// words, by the same rules:
// - a call is a call or `new` expression whose callee is a bare name, or a
//   property read whose object is a bare name (`a.b(…)`) or anything else
//   (`this.m(…)`, `a.b.c(…)` and `f().g(…)` report `m`, `c`, `g`);
//   `f()()`, `a[0]()`, `(f)()`, tagged templates and `import()` are not calls
//   of a name, and `new Foo` without parentheses is not a call;
// - a type mention is a type reference (`x: Foo`, `Foo<T>`, `keyof Foo`,
//   `as Foo`), an `implements` or interface `extends` clause, or a class's
//   `extends` when what follows is a bare name; a qualified name (`ns.Foo`)
//   mentions its first segment; keyword types (`string`), `typeof x`,
//   `import("m").T` and JSX tag names are not mentions.
// The definitions are the symbols oracle's (reference_ranges.mjs) and are not
// repeated here.
import ts from "typescript";
import fs from "node:fs";

function scriptKind(path) {
  if (path.endsWith(".ts") || path.endsWith(".mts") || path.endsWith(".cts")) return ts.ScriptKind.TS;
  if (path.endsWith(".tsx")) return ts.ScriptKind.TSX;
  return ts.ScriptKind.JS;
}

function refsOf(sf) {
  const out = [];
  const line = (node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
  const nameOf = (node) => ts.isIdentifier(node) ? node.text : ts.isPrivateIdentifier(node) ? node.text : null;
  const call = (callee) => {
    if (ts.isIdentifier(callee)) out.push(`ref call ${callee.text} L${line(callee)}`);
    else if (ts.isPropertyAccessExpression(callee)) {
      const name = nameOf(callee.name);
      if (name === null) return;
      const owner = ts.isIdentifier(callee.expression) ? callee.expression.text + "." : "";
      out.push(`ref call ${owner}${name} L${line(callee.name)}`);
    }
  };
  const leftmost = (node) => {
    while (ts.isQualifiedName(node) || ts.isPropertyAccessExpression(node)) node = ts.isQualifiedName(node) ? node.left : node.expression;
    return ts.isIdentifier(node) ? node : null;
  };
  const type = (node) => { if (node) out.push(`ref type ${node.text} L${line(node)}`); };
  const visit = (node) => {
    if (ts.isCallExpression(node)) call(node.expression);
    else if (ts.isNewExpression(node)) { if (node.arguments !== undefined) call(node.expression); }
    else if (ts.isTypeReferenceNode(node)) type(leftmost(node.typeName));
    else if (ts.isExpressionWithTypeArguments(node) && node.parent && ts.isHeritageClause(node.parent)) {
      const classExtends = node.parent.token === ts.SyntaxKind.ExtendsKeyword && ts.isClassLike(node.parent.parent);
      type(classExtends ? (ts.isIdentifier(node.expression) ? node.expression : null) : leftmost(node.expression));
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return out;
}

for (const path of process.argv.slice(2)) {
  const text = fs.readFileSync(path, "utf8");
  const sf = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, scriptKind(path));
  const accepted = sf.parseDiagnostics.length === 0;
  process.stdout.write(JSON.stringify({ path, accepted, refs: accepted ? refsOf(sf) : [] }) + "\n");
}
