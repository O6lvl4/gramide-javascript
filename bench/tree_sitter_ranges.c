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
extern const TSLanguage *LANG(void);

int main(int argc, char **argv) {
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
