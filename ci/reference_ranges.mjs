// Independent range oracle using the TypeScript compiler's parser, not
// gramide's tree. One JSON object per input path, one per line:
//   {"path", "accepted", "symbols": [{"kind", "name", "owner", "start", "end", "start_byte", "end_byte"}]}
// `accepted` is whether the parser reported no syntax error. The symbols are
// what gramide's `symbols` should say about the file, in the same words:
// functions and function bindings, classes, methods named with the nearest
// enclosing class or binding, class fields, and the bindings declared at the
// top of the file.
import ts from "typescript";
import fs from "node:fs";

function byteTable(text) {
  // UTF-16 index -> UTF-8 byte offset, one entry per code unit plus the end
  const table = new Uint32Array(text.length + 1);
  let bytes = 0;
  for (let i = 0; i < text.length; i++) {
    table[i] = bytes;
    const c = text.charCodeAt(i);
    if (c < 0x80) bytes += 1;
    else if (c < 0x800) bytes += 2;
    else if (c >= 0xd800 && c <= 0xdbff) { bytes += 4; i++; table[i] = bytes; }
    else bytes += 3;
  }
  table[text.length] = bytes;
  return table;
}

function scriptKind(path) {
  if (path.endsWith(".ts") || path.endsWith(".mts") || path.endsWith(".cts")) return ts.ScriptKind.TS;
  if (path.endsWith(".tsx")) return ts.ScriptKind.TSX;
  return ts.ScriptKind.JS;
}

function nameText(node) {
  if (!node) return "";
  if (ts.isIdentifier(node) || ts.isPrivateIdentifier(node)) return node.text;
  if (ts.isStringLiteral(node) || ts.isNumericLiteral(node)) return node.getText();
  if (ts.isComputedPropertyName(node)) return joinedTokens(node.getText());
  return "";
}

// gramide joins a computed name from its tokens, without the whitespace
function joinedTokens(text) {
  const scanner = ts.createScanner(ts.ScriptTarget.Latest, true, ts.LanguageVariant.Standard, text);
  let out = "";
  while (scanner.scan() !== ts.SyntaxKind.EndOfFileToken) out += scanner.getTokenText();
  return out;
}

// A method is owned by the nearest class, or by the nearest binding or
// word-named property its object or class expression sits in; a method's
// body holds no methods, while a plain function or arrow between the two is
// transparent (`const P = Base.extend((B) => class extends B { m() {} })`
// declares `P.m`).
function ownerAbove(node) {
  for (let p = node.parent; p; p = p.parent) {
    if (ts.isClassDeclaration(p) && p.name) return p.name.text;
    if (ts.isVariableDeclaration(p) && ts.isIdentifier(p.name)) return p.name.text;
    if (ts.isPropertyAssignment(p) && ts.isIdentifier(p.name)) return p.name.text;
    if (ts.isMethodDeclaration(p) || ts.isAccessor(p) || ts.isConstructorDeclaration(p)) return "";
  }
  return "";
}

function symbolsOf(sf, text) {
  const table = byteTable(text);
  const out = [];
  const lineOf = (pos) => sf.getLineAndCharacterOfPosition(pos).line + 1;
  // where a declaration's last token ends: a trailing comment is the next
  // token's leading trivia to the compiler and no token at all to gramide,
  // and a closing `;` or `,` belongs to the statement or the list
  function tokenEnd(node) {
    const kids = node.getChildren(sf);
    if (kids.length === 0) return node.getEnd();
    for (let i = kids.length - 1; i >= 0; i--) {
      const k = kids[i];
      if (k.kind === ts.SyntaxKind.SemicolonToken || k.kind === ts.SyntaxKind.CommaToken) continue;
      return tokenEnd(k);
    }
    return node.getEnd();
  }
  const push = (kind, name, owner, startPos, endPos) => {
    // a trailing `;` belongs to the statement, not to the declaration
    let end = endPos;
    while (end > startPos && /[\s;]/.test(text[end - 1])) end--;
    out.push({ kind, name, owner, start: lineOf(startPos), end: lineOf(end - 1), start_byte: table[startPos], end_byte: table[end] });
  };
  const isFunctionInit = (init) => init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init));
  function visit(node, top) {
    if (ts.isFunctionDeclaration(node) && node.name) push("function", node.name.text, "", node.getStart(sf), tokenEnd(node));
    else if (ts.isClassDeclaration(node) && node.name) push("class", node.name.text, "", node.getStart(sf), tokenEnd(node));
    else if (ts.isMethodDeclaration(node) || ts.isAccessor(node) || ts.isConstructorDeclaration(node)) {
      const own = ownerAbove(node);
      const name = ts.isConstructorDeclaration(node) ? "constructor" : nameText(node.name);
      if (name && !(ts.isMethodDeclaration(node) && !ts.isClassLike(node.parent) && !ts.isObjectLiteralExpression(node.parent)))
        push("method", own ? own + "." + name : name, own, node.getStart(sf), tokenEnd(node));
    }
    else if (ts.isPropertyDeclaration(node) && nameText(node.name)) push("field", nameText(node.name), "", node.getStart(sf), tokenEnd(node));
    else if (ts.isVariableStatement(node) && top) {
      const flags = ts.getCombinedNodeFlags(node.declarationList);
      const word = flags & ts.NodeFlags.Const ? "const" : flags & ts.NodeFlags.Let ? "let" : flags & ts.NodeFlags.Using ? "using" : flags & ts.NodeFlags.AwaitUsing ? "using" : "var";
      const stmtStart = node.getStart(sf);
      for (const d of node.declarationList.declarations) {
        if (!ts.isIdentifier(d.name)) continue;
        const kind = isFunctionInit(d.initializer) ? "function" : word;
        push(kind, d.name.text, "", stmtStart, tokenEnd(d));
      }
    }
    const deeper = top && (ts.isExportDeclaration(node) || ts.isExportAssignment(node) || ts.isModuleBlock(node) || node === sf);
    ts.forEachChild(node, (child) => visit(child, deeper || (top && ts.isVariableStatement(node)) || (ts.isSourceFile(node))));
  }
  visit(sf, true);
  // the walk emits a declaration when it reaches it, which is source order
  return out;
}

for (const path of process.argv.slice(2)) {
  const text = fs.readFileSync(path, "utf8");
  const sf = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, scriptKind(path));
  const accepted = sf.parseDiagnostics.length === 0;
  const row = { path, accepted, symbols: accepted ? symbolsOf(sf, text) : [] };
  process.stdout.write(JSON.stringify(row) + "\n");
}
