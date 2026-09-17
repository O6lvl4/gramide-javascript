// Independent full-parse baseline over tree-sitter: a fresh process reads
// one file, parses it whole (no tree is reused), and either answers whether
// the parse had errors (`--check`) or prints the functions, classes and
// methods it found with their line and byte ranges, one JSON object per line.
// Built once per grammar: -DLANG=tree_sitter_javascript, tree_sitter_typescript,
// tree_sitter_tsx.
#include <tree_sitter/api.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
extern const TSLanguage *LANG(void);

// The edit sequence a keystroke benchmark replays, the same one gramide's
// `reparse-bench` replays: a 31-bit linear congruential generator seeded by
// --seed, one edit per step at a position it picks, inserting one letter on
// even steps and deleting one byte on odd ones.
static unsigned long lcg_state;
static unsigned long lcg_next(void) { lcg_state = (lcg_state * 1103515245UL + 12345UL) % 2147483648UL; return lcg_state; }

// Where an edit goes: from a random byte, the next word of 13 letters or
// more, six letters in. Such a word is an identifier, or text in a string
// or comment; a letter typed or deleted there leaves the file as it was,
// syntactically, which is the edit an editor sees most and the one both
// tools are asked about. No JavaScript keyword has 13 letters.
static int letter(char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_'; }
static long edit_position(const char *text, long len, long from) {
  for (int pass = 0; pass < 2; pass++) {
    long p = pass == 0 ? from : 0;
    while (p < len) {
      while (p < len && !letter(text[p])) p++;
      long s = p;
      while (p < len && letter(text[p])) p++;
      if (p - s >= 13 && !(s > 0 && text[s - 1] >= '0' && text[s - 1] <= '9')) return s + 6;
    }
  }
  return -1;
}

static int compare_u64(const void *a, const void *b) { unsigned long x = *(const unsigned long *)a, y = *(const unsigned long *)b; return x < y ? -1 : x > y; }

// --edits N --seed S FILE: parse once, then N edits, each applied to the text
// and to the tree with ts_tree_edit, the tree reparsed with the old tree as
// the base. Prints median and p90 microseconds per edit.
static int bench_edits(const char *path, long edits, unsigned long seed) {
  FILE *file = fopen(path, "rb");
  if (!file || fseek(file, 0, SEEK_END)) return 2;
  long size = ftell(file);
  if (size < 0 || fseek(file, 0, SEEK_SET)) return 2;
  char *source = malloc((size_t)size + edits + 1);
  if (!source || fread(source, 1, (size_t)size, file) != (size_t)size) return 2;
  fclose(file);
  TSParser *parser = ts_parser_new();
  if (!parser || !ts_parser_set_language(parser, LANG())) return 2;
  TSTree *tree = ts_parser_parse_string(parser, NULL, source, (uint32_t)size);
  unsigned long *times = malloc(sizeof(unsigned long) * edits);
  lcg_state = seed;
  long len = size;
  long first_error = -1;
  for (long i = 0; i < edits; i++) {
    unsigned long r = lcg_next();
    long pos = edit_position(source, len, (long)(r % (unsigned long)(len + 1)));
    if (pos < 0) { fputs("no word of 13 letters to edit\n", stderr); return 2; }
    char typed = (char)('a' + (r / 65536) % 26);
    TSInputEdit edit;
    // points are needed by ts_tree_edit; rows/columns are recomputed from the text
    uint32_t row = 0, col = 0; for (long k = 0; k < pos; k++) { if (source[k] == '\n') { row++; col = 0; } else col++; }
    edit.start_byte = (uint32_t)pos; edit.start_point.row = row; edit.start_point.column = col;
    if (i % 2 == 0 || len == 0) {
      memmove(source + pos + 1, source + pos, (size_t)(len - pos));
      source[pos] = typed; len += 1;
      edit.old_end_byte = (uint32_t)pos; edit.old_end_point = edit.start_point;
      edit.new_end_byte = (uint32_t)pos + 1; edit.new_end_point.row = row; edit.new_end_point.column = col + 1;
    } else {
      if (pos >= len) pos = len - 1;
      char gone = source[pos];
      memmove(source + pos, source + pos + 1, (size_t)(len - pos - 1));
      len -= 1;
      edit.start_byte = (uint32_t)pos;
      edit.old_end_byte = (uint32_t)pos + 1;
      if (gone == '\n') { edit.old_end_point.row = row + 1; edit.old_end_point.column = 0; }
      else { edit.old_end_point.row = row; edit.old_end_point.column = col + 1; }
      edit.new_end_byte = (uint32_t)pos; edit.new_end_point = edit.start_point;
    }
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    ts_tree_edit(tree, &edit);
    TSTree *next = ts_parser_parse_string(parser, tree, source, (uint32_t)len);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    ts_tree_delete(tree);
    tree = next;
    if (first_error < 0 && ts_node_has_error(ts_tree_root_node(tree))) first_error = i;
    times[i] = (unsigned long)((t1.tv_sec - t0.tv_sec) * 1000000000L + (t1.tv_nsec - t0.tv_nsec));
  }
  const char *dump = getenv("TS_DUMP");
  if (dump) { FILE *out = fopen(dump, "wb"); if (out) { fwrite(source, 1, (size_t)len, out); fclose(out); } }
  qsort(times, (size_t)edits, sizeof(unsigned long), compare_u64);
  printf("{\"tool\":\"tree-sitter\",\"edits\":%ld,\"median_us\":%.1f,\"p90_us\":%.1f,\"max_us\":%.1f,\"errors_at_end\":%d,\"first_error_edit\":%ld}\n",
    edits, times[edits / 2] / 1000.0, times[(edits * 9) / 10] / 1000.0, times[edits - 1] / 1000.0, ts_node_has_error(ts_tree_root_node(tree)), first_error);
  ts_tree_delete(tree);
  ts_parser_delete(parser);
  free(times);
  free(source);
  return 0;
}

// --recover KIND,KIND,... FILE: parse the file (broken or not) and print every
// node of the named kinds with its `name` field, as the listing does, plus
// every ERROR and MISSING node as {"kind":"ERROR"|"MISSING",...} with its byte
// range, so that a recovery comparison can see what survived and what the
// parser gave up on. Exit 1 when the tree has an error.
static int recover(const char *path, const char *kinds_arg) {
  FILE *file = fopen(path, "rb");
  if (!file || fseek(file, 0, SEEK_END)) return 2;
  long size = ftell(file);
  if (size < 0 || fseek(file, 0, SEEK_SET)) return 2;
  char *source = malloc((size_t)size + 1);
  if (!source || fread(source, 1, (size_t)size, file) != (size_t)size) return 2;
  fclose(file);
  source[size] = 0;
  char *kinds = strdup(kinds_arg);
  TSParser *parser = ts_parser_new();
  if (!parser || !ts_parser_set_language(parser, LANG())) return 2;
  TSTree *tree = ts_parser_parse_string(parser, NULL, source, (uint32_t)size);
  if (!tree) return 2;
  int errors = ts_node_has_error(ts_tree_root_node(tree));
  TSTreeCursor cursor = ts_tree_cursor_new(ts_tree_root_node(tree));
  for (;;) {
    TSNode node = ts_tree_cursor_current_node(&cursor);
    const char *kind = ts_node_type(node);
    if (ts_node_is_error(node) || ts_node_is_missing(node)) {
      printf("{\"kind\":\"%s\",\"name\":\"\",\"start\":%u,\"end\":%u,\"start_byte\":%u,\"end_byte\":%u}\n",
        ts_node_is_missing(node) ? "MISSING" : "ERROR",
        ts_node_start_point(node).row+1, ts_node_end_point(node).row+1,
        ts_node_start_byte(node), ts_node_end_byte(node));
    } else if (ts_node_is_named(node)) {
      int wanted = 0;
      size_t klen = strlen(kind);
      for (const char *k = kinds; *k && !wanted; ) {
        const char *e = strchr(k, ','); size_t n = e ? (size_t)(e - k) : strlen(k);
        wanted = n == klen && !strncmp(k, kind, n);
        k = e ? e + 1 : k + n;
      }
      if (wanted) {
        TSNode name = ts_node_child_by_field_name(node, "name", 4);
        uint32_t start = ts_node_is_null(name) ? 0 : ts_node_start_byte(name), end = ts_node_is_null(name) ? 0 : ts_node_end_byte(name);
        printf("{\"kind\":\"%s\",\"name\":\"", kind);
        for (uint32_t i = start; i < end; i++) {  // a computed or quoted name holds JSON's own characters
          unsigned char c = (unsigned char)source[i];
          if (c == '"' || c == '\\') printf("\\%c", c); else if (c < 0x20) printf("\\u%04x", c); else putchar(c);
        }
        printf("\",\"start\":%u,\"end\":%u,\"start_byte\":%u,\"end_byte\":%u}\n",
          ts_node_start_point(node).row+1, ts_node_end_point(node).row+1,
          ts_node_start_byte(node), ts_node_end_byte(node));
      }
    }
    if (ts_tree_cursor_goto_first_child(&cursor)) continue;
    while (!ts_tree_cursor_goto_next_sibling(&cursor)) {
      if (!ts_tree_cursor_goto_parent(&cursor)) goto done;
    }
  }
done:
  ts_tree_cursor_delete(&cursor);
  ts_tree_delete(tree);
  ts_parser_delete(parser);
  free(source);
  free(kinds);
  return errors ? 1 : 0;
}

int main(int argc, char **argv) {
  if (argc == 6 && !strcmp(argv[1], "--edits") && !strcmp(argv[3], "--seed")) return bench_edits(argv[5], atol(argv[2]), strtoul(argv[4], NULL, 10));
  if (argc == 4 && !strcmp(argv[1], "--recover")) return recover(argv[3], argv[2]);
  int check = argc == 3 && !strcmp(argv[1], "--check");
  const char *path = argv[argc - 1];
  if (argc < 2 || argc > 3) return 2;
  FILE *file = fopen(path, "rb");
  if (!file || fseek(file, 0, SEEK_END)) return 2;
  long size = ftell(file);
  if (size < 0 || (unsigned long)size > UINT32_MAX || fseek(file, 0, SEEK_SET)) return 2;
  char *source = malloc((size_t)size + 1);
  if (!source || fread(source, 1, (size_t)size, file) != (size_t)size) return 2;
  fclose(file);
  source[size] = 0;
  TSParser *parser = ts_parser_new();
  if (!parser || !ts_parser_set_language(parser, LANG())) return 2;
  TSTree *tree = ts_parser_parse_string(parser, NULL, source, (uint32_t)size);
  if (!tree) return 2;
  int errors = ts_node_has_error(ts_tree_root_node(tree));
  if (check) { puts(errors ? "error" : "ok"); return errors ? 1 : 0; }
  TSTreeCursor cursor = ts_tree_cursor_new(ts_tree_root_node(tree));
  for (;;) {
    TSNode node = ts_tree_cursor_current_node(&cursor);
    const char *kind = ts_node_type(node);
    if (!strcmp(kind, "function_declaration") || !strcmp(kind, "class_declaration") || !strcmp(kind, "method_definition")
        || !strcmp(kind, "interface_declaration") || !strcmp(kind, "enum_declaration") || !strcmp(kind, "type_alias_declaration")) {
      TSNode name = ts_node_child_by_field_name(node, "name", 4);
      uint32_t start = ts_node_start_byte(name), end = ts_node_end_byte(name);
      printf("{\"kind\":\"%s\",\"name\":\"%.*s\",\"start\":%u,\"end\":%u,\"start_byte\":%u,\"end_byte\":%u}\n",
        kind, (int)(end-start), source+start,
        ts_node_start_point(node).row+1, ts_node_end_point(node).row+1,
        ts_node_start_byte(node), ts_node_end_byte(node));
    }
    if (ts_tree_cursor_goto_first_child(&cursor)) continue;
    while (!ts_tree_cursor_goto_next_sibling(&cursor)) {
      if (!ts_tree_cursor_goto_parent(&cursor)) goto done;
    }
  }
done:
  ts_tree_cursor_delete(&cursor);
  ts_tree_delete(tree);
  ts_parser_delete(parser);
  free(source);
  return errors ? 1 : 0;
}
