"""dBase Revival by Jair Lima - Command interpreter.

Implements all dBASE commands: database operations, navigation, display,
index management, variables, file operations, SET commands, and more.
"""

import os
import re
import shutil
import glob as globmod
from datetime import date

from .dbf import DBF
from . import io_formats
from .sql import SQLExecutor
from .indexes.ndx import NDXIndex
from .indexes.ntx import NTXIndex
from .indexes.cdx import CDXIndex
from .indexes.mdx import MDXIndex


class CommandInterpreter:
    """Interprets and executes dBASE commands."""

    def __init__(self, env, evaluator, config):
        self.env = env
        self.eval = evaluator
        self.config = config
        self.output_lines = []
        self.sql = SQLExecutor(env, evaluator, config)
        self._commands = self._build_command_table()

    def _output(self, text=""):
        self.output_lines.append(str(text))

    def execute(self, line):
        """Parse and execute a single command line."""
        self.output_lines = []
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("&&") or line.upper().startswith("NOTE "):
            return self.output_lines

        # Handle inline comments
        comment_pos = line.find("&&")
        if comment_pos > 0:
            line = line[:comment_pos].strip()

        # Handle ? and ?? (print expressions)
        if line.startswith("??"):
            return self._cmd_print(line[2:].strip(), no_newline=True)
        if line.startswith("?"):
            return self._cmd_print(line[1:].strip(), no_newline=False)

        # Handle @ row,col SAY/GET
        if line.startswith("@"):
            return self._cmd_at(line)

        # Handle assignment with =
        if "=" in line and not line.startswith("="):
            parts = line.split("=", 1)
            name = parts[0].strip()
            if re.match(r'^[A-Za-z_]\w*$', name):
                cmd_upper = name.upper()
                if cmd_upper not in self._commands:
                    val = self.eval.evaluate(parts[1].strip())
                    self.env.set_variable(name.upper(), val)
                    if self.config.talk:
                        self._output(f"{name.upper()} = {self._format_value(val)}")
                    return self.output_lines

        # Parse command word
        tokens = self._tokenize_command(line)
        if not tokens:
            return self.output_lines

        cmd = tokens[0].upper()
        rest = line[len(tokens[0]):].strip()
        self._last_cmd_word = cmd

        # Two-word commands
        if len(tokens) >= 2:
            two_word = f"{cmd} {tokens[1].upper()}"
            if two_word in self._commands:
                rest = line[len(tokens[0]) + 1 + len(tokens[1]):].strip()
                self._last_cmd_word = two_word
                return self._commands[two_word](rest)

        if cmd in self._commands:
            return self._commands[cmd](rest)

        # Try as expression
        try:
            val = self.eval.evaluate(line)
            if val is not None:
                self._output(self._format_value(val))
            return self.output_lines
        except Exception:
            self._output(f"Unrecognized command: {cmd}")
            return self.output_lines

    def _tokenize_command(self, line):
        """Simple tokenization of a command line."""
        tokens = []
        i = 0
        while i < len(line):
            if line[i] in " \t,":
                i += 1
                continue
            if line[i] in ('"', "'"):
                q = line[i]
                j = line.find(q, i + 1)
                if j < 0:
                    j = len(line)
                tokens.append(line[i:j + 1])
                i = j + 1
            elif line[i] == "[":
                j = line.find("]", i + 1)
                if j < 0:
                    j = len(line)
                tokens.append(line[i:j + 1])
                i = j + 1
            else:
                j = i
                while j < len(line) and line[j] not in " \t,":
                    j += 1
                tokens.append(line[i:j])
                i = j
        return tokens

    def _build_command_table(self):
        return {
            "USE": self._cmd_use,
            "APPEND": self._cmd_append,
            "APPEND BLANK": self._cmd_append_blank,
            "REPLACE": self._cmd_replace,
            "DELETE": self._cmd_delete,
            "RECALL": self._cmd_recall,
            "PACK": self._cmd_pack,
            "ZAP": self._cmd_zap,
            "CREATE": self._cmd_create,
            "MODIFY STRUCTURE": self._cmd_modify_structure,
            "COPY TO": self._cmd_copy_to,
            "COPY STRUCTURE": self._cmd_copy_structure,
            "SORT": self._cmd_sort,
            "GO": self._cmd_go,
            "GOTO": self._cmd_go,
            "SKIP": self._cmd_skip,
            "LOCATE": self._cmd_locate,
            "CONTINUE": self._cmd_continue,
            "SEEK": self._cmd_seek,
            "FIND": self._cmd_find,
            "LIST": self._cmd_list,
            "DISPLAY": self._cmd_display,
            "BROWSE": self._cmd_browse,
            "EDIT": self._cmd_edit,
            "CHANGE": self._cmd_edit,
            "INDEX": self._cmd_index,
            "INDEX ON": self._cmd_index_on,
            "SET INDEX": self._cmd_set_index,
            "SET INDEX TO": self._cmd_set_index,
            "SET ORDER": self._cmd_set_order,
            "SET ORDER TO": self._cmd_set_order,
            "REINDEX": self._cmd_reindex,
            "SELECT": self._cmd_select,
            "COUNT": self._cmd_count,
            "SUM": self._cmd_sum,
            "AVERAGE": self._cmd_average,
            "STORE": self._cmd_store,
            "PUBLIC": self._cmd_public,
            "PRIVATE": self._cmd_private,
            "LOCAL": self._cmd_private,
            "RELEASE": self._cmd_release,
            "DECLARE": self._cmd_declare,
            "DIMENSION": self._cmd_declare,
            "SET": self._cmd_set,
            "CLOSE": self._cmd_close,
            "CLOSE DATABASES": lambda r: self._cmd_close("DATABASES"),
            "CLOSE ALL": lambda r: self._cmd_close("ALL"),
            "CLOSE INDEX": lambda r: self._cmd_close("INDEX"),
            "DIR": self._cmd_dir,
            "DIRECTORY": self._cmd_dir,
            "RENAME": self._cmd_rename,
            "ERASE": self._cmd_erase,
            "DELETE FILE": self._cmd_erase,
            "TYPE": self._cmd_type,
            "CLEAR": self._cmd_clear,
            "CLEAR ALL": lambda r: self._cmd_clear("ALL"),
            "CLEAR MEMORY": lambda r: self._cmd_clear("MEMORY"),
            "DISPLAY STATUS": self._cmd_display_status,
            "DISPLAY MEMORY": self._cmd_display_memory,
            "DISPLAY STRUCTURE": self._cmd_display_structure,
            "LIST STATUS": self._cmd_display_status,
            "LIST STRUCTURE": self._cmd_display_structure,
            "LIST MEMORY": self._cmd_display_memory,
            "HELP": self._cmd_help,
            "QUIT": self._cmd_quit,
            "CANCEL": self._cmd_quit,
            "RETURN": self._cmd_return,
            "DO": self._cmd_do,
            "RUN": self._cmd_run,
            "WAIT": self._cmd_wait,
            "ACCEPT": self._cmd_accept,
            "INPUT": self._cmd_input,
            "SAVE TO": self._cmd_save_to,
            "RESTORE FROM": self._cmd_restore_from,
            "TOTAL": self._cmd_total,
            "UPDATE": self._cmd_update,
            "JOIN": self._cmd_join,
            "LABEL": self._cmd_label,
            "REPORT": self._cmd_report,
            "SELECT": self._cmd_sql,
            "INSERT": self._cmd_sql,
            "UPDATE": self._cmd_sql_update,
            "DROP": self._cmd_sql,
            "ALTER": self._cmd_sql,
            "CREATE TABLE": self._cmd_sql_create_table,
        }

    def _format_value(self, val):
        if val is None:
            return ".NULL."
        if isinstance(val, bool):
            return ".T." if val else ".F."
        if isinstance(val, date):
            return self.config.format_date(val)
        if isinstance(val, float):
            return f"{val:.{self.config.decimals}f}"
        return str(val)

    def _resolve_path(self, filename):
        if os.path.isabs(filename):
            return filename
        return os.path.join(self.config.default_path, filename)

    def _ensure_extension(self, filename, ext):
        if "." not in os.path.basename(filename):
            return filename + ext
        return filename

    def _require_dbf(self):
        wa = self.env.current_workarea()
        if not wa or not wa.dbf:
            self._output("No database is in use.")
            return None
        return wa

    # ===== DATABASE COMMANDS =====

    def _cmd_use(self, rest):
        rest = rest.strip()
        wa = self.env.get_workarea(self.env.current_area)

        if not rest:
            if wa.is_open():
                wa.close_table()
            return self.output_lines

        parts = self._tokenize_command(rest)
        filename = parts[0].strip('"').strip("'")
        filename = self._ensure_extension(filename, ".dbf")
        filename = self._resolve_path(filename)

        alias = None
        index_files = []
        exclusive = self.config.exclusive

        i = 1
        while i < len(parts):
            kw = parts[i].upper()
            if kw == "ALIAS" and i + 1 < len(parts):
                alias = parts[i + 1]
                i += 2
            elif kw == "INDEX" and i + 1 < len(parts):
                i += 1
                while i < len(parts) and parts[i].upper() not in ("ALIAS", "EXCLUSIVE", "SHARED"):
                    idx_file = parts[i].strip(",")
                    if idx_file:
                        index_files.append(idx_file)
                    i += 1
            elif kw == "EXCLUSIVE":
                exclusive = True
                i += 1
            elif kw == "SHARED":
                exclusive = False
                i += 1
            else:
                i += 1

        if wa.is_open():
            wa.close_table()

        try:
            wa.open_table(filename, alias)
            for idx_file in index_files:
                idx_file = self._ensure_extension(idx_file, ".ndx")
                idx_file = self._resolve_path(idx_file)
                idx = self._open_index_file(idx_file, wa.dbf)
                if idx:
                    wa.add_index(idx, set_active=True)
            if self.config.talk:
                self._output(f"Database: {os.path.basename(filename)}, {wa.dbf.record_count} records")
        except Exception as e:
            self._output(f"Error opening file: {e}")
        return self.output_lines

    def _open_index_file(self, filename, dbf):
        ext = os.path.splitext(filename)[1].upper()
        if ext == ".NTX":
            return NTXIndex(filename, dbf)
        elif ext == ".CDX":
            return CDXIndex(filename, dbf)
        elif ext == ".MDX":
            return MDXIndex(filename, dbf)
        else:
            return NDXIndex(filename, dbf)

    def _cmd_append(self, rest):
        rest = rest.strip().upper()
        if rest.startswith("BLANK"):
            return self._cmd_append_blank(rest[5:].strip())

        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        # APPEND FROM
        if rest.startswith("FROM"):
            parts = self._tokenize_command(rest[4:].strip())
            if not parts:
                self._output("Syntax: APPEND FROM <file> [TYPE CSV|JSON|XML|SDF|DELIMITED|XLS]")
                return self.output_lines

            src_file = parts[0].strip('"').strip("'")

            # Parse TYPE, DELIMITED WITH, FIELDS
            file_type = "DBF"
            delim_char = ","
            field_list = None
            i = 1
            while i < len(parts):
                kw = parts[i].upper()
                if kw == "TYPE" and i + 1 < len(parts):
                    file_type = parts[i + 1].upper()
                    i += 2
                elif kw == "DELIMITED":
                    file_type = "DELIMITED"
                    if i + 2 < len(parts) and parts[i + 1].upper() == "WITH":
                        delim_char = parts[i + 2].strip('"').strip("'")
                        if delim_char.upper() == "TAB":
                            delim_char = "\t"
                        elif delim_char.upper() == "BLANK":
                            delim_char = " "
                        i += 3
                    else:
                        i += 1
                elif kw == "SDF":
                    file_type = "SDF"
                    i += 1
                elif kw == "FIELDS" and i + 1 < len(parts):
                    field_list = [f.strip() for f in parts[i + 1].split(",")]
                    i += 2
                else:
                    i += 1

            # Auto-detect type from extension if not specified
            if file_type == "DBF":
                ext = os.path.splitext(src_file)[1].upper()
                type_map = {".CSV": "CSV", ".JSON": "JSON", ".XML": "XML",
                           ".TXT": "SDF", ".XLS": "XLS", ".TSV": "XLS"}
                file_type = type_map.get(ext, "DBF")

            src_file = self._resolve_path(src_file)

            try:
                if file_type == "DBF":
                    if "." not in os.path.basename(src_file):
                        src_file += ".dbf"
                    src = DBF(src_file)
                    count = 0
                    for rec in src.records:
                        if not rec.deleted:
                            data = {}
                            for f in wa.dbf.fields:
                                sf = src.field_by_name(f.name)
                                if sf:
                                    data[f.name] = rec[f.name]
                            wa.dbf.append_record(data)
                            count += 1
                elif file_type == "CSV":
                    count = io_formats.import_csv(wa.dbf, src_file, field_list)
                elif file_type == "JSON":
                    count = io_formats.import_json(wa.dbf, src_file, field_list)
                elif file_type == "XML":
                    count = io_formats.import_xml(wa.dbf, src_file, field_list)
                elif file_type == "SDF":
                    count = io_formats.import_sdf(wa.dbf, src_file, field_list)
                elif file_type == "DELIMITED":
                    count = io_formats.import_delimited(wa.dbf, src_file, field_list,
                                                        delimiter=delim_char)
                elif file_type in ("XLS", "TSV"):
                    count = io_formats.import_xls(wa.dbf, src_file, field_list)
                else:
                    self._output(f"Unsupported TYPE: {file_type}")
                    return self.output_lines

                wa.recno = wa.dbf.record_count
                wa.eof = wa.dbf.record_count == 0
                if self.config.talk:
                    self._output(f"{count} record(s) imported from {os.path.basename(src_file)} [{file_type}].")
            except Exception as e:
                self._output(f"Error: {e}")
        return self.output_lines

    def _cmd_append_blank(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines
        wa.dbf.append_blank()
        wa.recno = wa.dbf.record_count
        wa.eof = False
        if self.config.talk:
            self._output(f"Record {wa.recno} added.")
        return self.output_lines

    def _cmd_replace(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        # Parse: REPLACE field WITH expr [, field WITH expr] [scope] [FOR cond] [WHILE cond]
        scope, for_expr, while_expr, rest = self._parse_scope_for_while(rest)
        pairs = self._parse_replace_pairs(rest)

        if not pairs:
            self._output("Syntax: REPLACE field WITH expression [, field WITH expression]")
            return self.output_lines

        if scope == "ALL" or for_expr or while_expr:
            count = 0
            save_recno = wa.recno
            if scope == "ALL":
                wa.go_top()
            while not wa.eof:
                rec = wa.current_record()
                if rec is None:
                    break
                if self.config.deleted and rec.deleted:
                    wa.skip()
                    continue
                if while_expr:
                    if not self.eval.eval_condition(while_expr, rec, wa.recno - 1):
                        break
                if for_expr:
                    if not self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                        wa.skip()
                        continue
                for field_name, expr in pairs:
                    val = self.eval.evaluate(expr, rec, wa.recno - 1)
                    rec[field_name.upper()] = val
                count += 1
                wa.skip()
            if self.config.talk:
                self._output(f"{count} replacement(s) made.")
        else:
            rec = wa.current_record()
            if rec:
                for field_name, expr in pairs:
                    val = self.eval.evaluate(expr, rec, wa.recno - 1)
                    rec[field_name.upper()] = val
                if self.config.talk:
                    self._output(f"1 replacement(s) made.")
        return self.output_lines

    def _parse_replace_pairs(self, text):
        """Parse REPLACE field WITH expr [, field WITH expr ...]"""
        pairs = []
        parts = text.split(",")
        for part in parts:
            part = part.strip()
            m = re.match(r'(\w+)\s+WITH\s+(.+)', part, re.IGNORECASE)
            if m:
                pairs.append((m.group(1), m.group(2).strip()))
        return pairs

    def _parse_scope_for_while(self, text):
        """Extract scope, FOR and WHILE clauses from command text."""
        scope = None
        for_expr = None
        while_expr = None

        text_upper = text.upper()

        # Extract WHILE
        m = re.search(r'\bWHILE\b\s+(.+?)(?:\bFOR\b|\bALL\b|\bNEXT\b|\bREST\b|$)', text, re.IGNORECASE)
        if m:
            while_expr = m.group(1).strip()
            text = text[:m.start()].strip() + " " + text[m.end():].strip()

        # Extract FOR
        m = re.search(r'\bFOR\b\s+(.+?)(?:\bWHILE\b|\bALL\b|\bNEXT\b|\bREST\b|$)', text, re.IGNORECASE)
        if m:
            for_expr = m.group(1).strip()
            text = text[:m.start()].strip() + " " + text[m.end():].strip()

        text_upper = text.upper().strip()
        if "ALL" in text_upper.split():
            scope = "ALL"
            text = re.sub(r'\bALL\b', '', text, flags=re.IGNORECASE).strip()
        elif "REST" in text_upper.split():
            scope = "REST"
            text = re.sub(r'\bREST\b', '', text, flags=re.IGNORECASE).strip()

        return scope, for_expr, while_expr, text.strip()

    def _cmd_delete(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        rest = rest.strip()
        if rest.upper().startswith("FILE"):
            return self._cmd_erase(rest[4:].strip())

        scope, for_expr, while_expr, rest = self._parse_scope_for_while(rest)

        if scope == "ALL" or for_expr or while_expr:
            count = 0
            if scope == "ALL":
                wa.go_top()
            while not wa.eof:
                rec = wa.current_record()
                if rec is None:
                    break
                if while_expr and not self.eval.eval_condition(while_expr, rec, wa.recno - 1):
                    break
                if for_expr and not self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                    wa.skip()
                    continue
                rec.deleted = True
                count += 1
                wa.skip()
            if self.config.talk:
                self._output(f"{count} record(s) deleted.")
        else:
            rec = wa.current_record()
            if rec:
                rec.deleted = True
                if self.config.talk:
                    self._output("1 record deleted.")
        return self.output_lines

    def _cmd_recall(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        scope, for_expr, while_expr, rest = self._parse_scope_for_while(rest)

        if scope == "ALL" or for_expr:
            count = 0
            if scope == "ALL":
                wa.go_top()
            while not wa.eof:
                rec = wa.current_record()
                if rec is None:
                    break
                if while_expr and not self.eval.eval_condition(while_expr, rec, wa.recno - 1):
                    break
                if for_expr and not self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                    wa.skip()
                    continue
                if rec.deleted:
                    rec.deleted = False
                    count += 1
                wa.skip()
            if self.config.talk:
                self._output(f"{count} record(s) recalled.")
        else:
            rec = wa.current_record()
            if rec and rec.deleted:
                rec.deleted = False
                if self.config.talk:
                    self._output("1 record recalled.")
        return self.output_lines

    def _cmd_pack(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines
        count_before = wa.dbf.record_count
        wa.dbf.pack()
        removed = count_before - wa.dbf.record_count
        wa.go_top()
        if self.config.talk:
            self._output(f"{removed} record(s) removed. {wa.dbf.record_count} remaining.")
        return self.output_lines

    def _cmd_zap(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines
        wa.dbf.zap()
        wa.recno = 0
        wa.eof = True
        if self.config.talk:
            self._output("All records removed.")
        return self.output_lines

    def _cmd_create(self, rest):
        parts = self._tokenize_command(rest)
        if not parts:
            self._output("Syntax: CREATE <filename>")
            return self.output_lines

        filename = parts[0].strip('"').strip("'")
        filename = self._ensure_extension(filename, ".dbf")
        filename = self._resolve_path(filename)

        self._output("Enter field definitions (empty name to finish):")
        fields = []
        while True:
            try:
                name = input("  Field name: ").strip()
                if not name:
                    break
                ftype = input("  Type (C/N/D/L/M): ").strip().upper()
                if not ftype:
                    ftype = "C"
                length = input("  Length: ").strip()
                length = int(length) if length else (10 if ftype == "C" else 8)
                dec = 0
                if ftype in ("N", "F"):
                    dec_str = input("  Decimals: ").strip()
                    dec = int(dec_str) if dec_str else 0
                fields.append({"name": name, "type": ftype, "length": length, "decimals": dec})
            except (EOFError, KeyboardInterrupt):
                break

        if fields:
            dbf = DBF()
            dbf.create(filename, fields)
            dbf.save()
            if self.config.talk:
                self._output(f"Database {os.path.basename(filename)} created with {len(fields)} field(s).")
        return self.output_lines

    def _cmd_modify_structure(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines
        self._output("Current structure:")
        for i, f in enumerate(wa.dbf.fields, 1):
            self._output(f"  {i}. {f.name:<12s} {f.field_type}  {f.length:>4d}  {f.decimals:>2d}")
        self._output("(Modify structure is interactive, use CREATE to create new tables)")
        return self.output_lines

    # ===== NAVIGATION COMMANDS =====

    def _cmd_go(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        rest = rest.strip().upper()
        if rest == "TOP":
            wa.go_top()
        elif rest == "BOTTOM":
            wa.go_bottom()
        else:
            try:
                n = int(self.eval.evaluate(rest))
                wa.go_to(n)
            except Exception:
                self._output(f"Invalid record number: {rest}")
                return self.output_lines

        if self.config.talk and not wa.eof:
            self._output(f"Record No. {wa.recno}")
        elif wa.eof:
            self._output("End of file.")
        return self.output_lines

    def _cmd_skip(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        rest = rest.strip()
        n = 1
        if rest:
            try:
                n = int(self.eval.evaluate(rest))
            except Exception:
                n = 1

        wa.skip(n)
        if self.config.talk:
            if wa.eof:
                self._output("End of file.")
            elif wa.bof:
                self._output("Beginning of file.")
            else:
                self._output(f"Record No. {wa.recno}")
        return self.output_lines

    def _cmd_locate(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        scope, for_expr, while_expr, rest = self._parse_scope_for_while(rest)
        if not for_expr:
            for_expr = rest.strip()
        if not for_expr:
            self._output("Syntax: LOCATE FOR <condition>")
            return self.output_lines

        wa._locate_for = for_expr
        wa.go_top()
        while not wa.eof:
            rec = wa.current_record()
            if rec is None:
                break
            if self.config.deleted and rec.deleted:
                wa.skip()
                continue
            if self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                wa.found = True
                if self.config.talk:
                    self._output(f"Record = {wa.recno}")
                return self.output_lines
            wa.skip()

        wa.found = False
        wa.eof = True
        if self.config.talk:
            self._output("End of LOCATE scope.")
        return self.output_lines

    def _cmd_continue(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        for_expr = getattr(wa, "_locate_for", None)
        if not for_expr:
            self._output("No active LOCATE to continue.")
            return self.output_lines

        wa.skip()
        while not wa.eof:
            rec = wa.current_record()
            if rec is None:
                break
            if self.config.deleted and rec.deleted:
                wa.skip()
                continue
            if self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                wa.found = True
                if self.config.talk:
                    self._output(f"Record = {wa.recno}")
                return self.output_lines
            wa.skip()

        wa.found = False
        wa.eof = True
        if self.config.talk:
            self._output("End of LOCATE scope.")
        return self.output_lines

    def _cmd_seek(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        key = self.eval.evaluate(rest.strip())
        found = wa.seek(key, exact=self.config.exact, softseek=self.config.softseek)
        if self.config.talk:
            if found:
                self._output(f"Record = {wa.recno}")
            else:
                self._output("Not found.")
        return self.output_lines

    def _cmd_find(self, rest):
        # FIND is SEEK for string keys without quotes
        rest = rest.strip()
        if not rest:
            self._output("Syntax: FIND <key>")
            return self.output_lines
        return self._cmd_seek(f'"{rest}"')

    # ===== DISPLAY COMMANDS =====

    def _cmd_print(self, rest, no_newline=False):
        """Handle ? and ?? commands."""
        if not rest:
            if not no_newline:
                self._output("")
            return self.output_lines

        # Parse comma-separated expressions
        parts = self._split_expr_list(rest)
        values = []
        for part in parts:
            part = part.strip()
            if part:
                val = self.eval.evaluate(part)
                values.append(self._format_value(val))

        line = " ".join(values)
        self._output(line)
        return self.output_lines

    def _split_expr_list(self, text):
        """Split expression list respecting quotes and parentheses."""
        parts = []
        depth = 0
        current = ""
        in_string = False
        quote_char = None

        for ch in text:
            if in_string:
                current += ch
                if ch == quote_char:
                    in_string = False
                continue
            if ch in ('"', "'"):
                in_string = True
                quote_char = ch
                current += ch
            elif ch == "(":
                depth += 1
                current += ch
            elif ch == ")":
                depth -= 1
                current += ch
            elif ch == "," and depth == 0:
                parts.append(current)
                current = ""
            else:
                current += ch

        if current.strip():
            parts.append(current)
        return parts

    def _cmd_list(self, rest):
        return self._cmd_list_display(rest, all_records=True)

    def _cmd_display(self, rest):
        rest_upper = rest.strip().upper()
        if rest_upper.startswith("STATUS"):
            return self._cmd_display_status(rest[6:].strip())
        if rest_upper.startswith("MEMORY"):
            return self._cmd_display_memory(rest[6:].strip())
        if rest_upper.startswith("STRUCTURE"):
            return self._cmd_display_structure(rest[9:].strip())
        return self._cmd_list_display(rest, all_records=False)

    def _cmd_list_display(self, rest, all_records=True):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        scope, for_expr, while_expr, rest = self._parse_scope_for_while(rest)

        # Parse field list
        off_flag = False
        field_names = []
        if rest.strip():
            tokens = self._tokenize_command(rest)
            for t in tokens:
                if t.upper() == "OFF":
                    off_flag = True
                elif t.upper() not in ("TO", "PRINT", "PRINTER"):
                    field_names.append(t.upper())

        if not field_names:
            field_names = [f.name for f in wa.dbf.fields]

        # Header
        if self.config.heading:
            header = ""
            if not off_flag:
                header = "Record# "
            for fn in field_names:
                field = wa.dbf.field_by_name(fn)
                if field:
                    width = max(len(fn), field.length)
                    header += fn.ljust(width) + " "
            self._output(header)

        if all_records:
            wa.go_top()

        count = 0
        while not wa.eof:
            rec = wa.current_record()
            if rec is None:
                break
            if not self.config.deleted and rec.deleted:
                wa.skip()
                continue
            if while_expr and not self.eval.eval_condition(while_expr, rec, wa.recno - 1):
                break
            if for_expr and not self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                wa.skip()
                continue

            line = ""
            if not off_flag:
                del_flag = "*" if rec.deleted else " "
                line += f"{wa.recno:>6d}{del_flag} "
            for fn in field_names:
                field = wa.dbf.field_by_name(fn)
                if field:
                    val = rec[fn]
                    width = max(len(fn), field.length)
                    formatted = self._format_field_value(val, field)
                    line += formatted.ljust(width)[:width] + " "

            self._output(line)
            count += 1

            if not all_records and scope is None:
                break

            wa.skip()

        if self.config.talk:
            self._output(f"{count} record(s).")
        return self.output_lines

    def _format_field_value(self, val, field):
        if val is None:
            if field.field_type == "D":
                return "  /  /  "
            return ""
        if field.field_type == "D" and isinstance(val, date):
            return self.config.format_date(val)
        if field.field_type == "L":
            return ".T." if val else ".F."
        if field.field_type in ("N", "F"):
            if field.decimals > 0:
                return f"{float(val):{field.length}.{field.decimals}f}"
            return f"{int(val) if isinstance(val, (int, float)) else val:>{field.length}}"
        if field.field_type == "C":
            return str(val)
        return str(val)

    def _cmd_browse(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines
        try:
            from .ui.browse import browse_table
            browse_table(wa, self.config, self.eval)
        except ImportError:
            self._output("BROWSE requires curses support.")
            self._cmd_list("")
        except Exception as e:
            self._output(f"BROWSE error: {e}")
            self._cmd_list("")
        return self.output_lines

    def _cmd_edit(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines
        rec = wa.current_record()
        if not rec:
            self._output("No current record.")
            return self.output_lines

        self._output(f"Record No. {wa.recno}")
        for field in wa.dbf.fields:
            val = rec[field.name]
            formatted = self._format_field_value(val, field)
            try:
                new_val = input(f"  {field.name:<12s}: {formatted} -> ")
                if new_val.strip():
                    if field.field_type in ("N", "F"):
                        rec[field.name] = float(new_val) if field.decimals > 0 else int(new_val)
                    elif field.field_type == "D":
                        rec[field.name] = self.config.parse_date(new_val)
                    elif field.field_type == "L":
                        rec[field.name] = new_val.upper() in ("T", "Y", ".T.", "1", "TRUE")
                    else:
                        rec[field.name] = new_val
            except (EOFError, KeyboardInterrupt):
                break
        return self.output_lines

    # ===== INDEX COMMANDS =====

    def _cmd_index(self, rest):
        rest_upper = rest.strip().upper()
        if rest_upper.startswith("ON"):
            return self._cmd_index_on(rest[2:].strip())
        self._output("Syntax: INDEX ON <expression> TO <filename> [TYPE NDX|NTX|CDX|MDX] [UNIQUE] [DESCENDING] [FOR <condition>] [TAG <tagname>]")
        return self.output_lines

    def _cmd_index_on(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        # Parse: INDEX ON <expr> TO <file> [TYPE ...] [UNIQUE] [DESCENDING] [FOR <cond>] [TAG <tag>]
        m = re.match(r'(.+?)\s+TO\s+(\S+)(.*)', rest, re.IGNORECASE)
        if not m:
            # Might be TAG syntax for compound index
            m = re.match(r'(.+?)\s+TAG\s+(\S+)(.*)', rest, re.IGNORECASE)
            if m:
                return self._cmd_index_on_tag(m.group(1).strip(), m.group(2).strip(), m.group(3).strip())
            self._output("Syntax: INDEX ON <expression> TO <filename>")
            return self.output_lines

        expr = m.group(1).strip()
        filename = m.group(2).strip().strip('"').strip("'")
        options = m.group(3).strip()

        unique = False
        descending = False
        for_expr = ""
        idx_type = None
        tag_name = ""

        opt_tokens = self._tokenize_command(options)
        i = 0
        while i < len(opt_tokens):
            kw = opt_tokens[i].upper()
            if kw == "UNIQUE":
                unique = True
            elif kw == "DESCENDING":
                descending = True
            elif kw == "TYPE" and i + 1 < len(opt_tokens):
                idx_type = opt_tokens[i + 1].upper()
                i += 1
            elif kw == "FOR" and i + 1 < len(opt_tokens):
                for_expr = opt_tokens[i + 1]
                i += 1
            elif kw == "TAG" and i + 1 < len(opt_tokens):
                tag_name = opt_tokens[i + 1]
                i += 1
            i += 1

        # Determine index type from extension or TYPE clause
        if not idx_type:
            ext = os.path.splitext(filename)[1].upper()
            if ext == ".NTX":
                idx_type = "NTX"
            elif ext == ".CDX":
                idx_type = "CDX"
            elif ext == ".MDX":
                idx_type = "MDX"
            else:
                idx_type = "NDX"

        if idx_type in ("NDX",):
            filename = self._ensure_extension(filename, ".ndx")
        elif idx_type == "NTX":
            filename = self._ensure_extension(filename, ".ntx")
        elif idx_type == "CDX":
            filename = self._ensure_extension(filename, ".cdx")
        elif idx_type == "MDX":
            filename = self._ensure_extension(filename, ".mdx")

        filename = self._resolve_path(filename)

        # Determine key length from expression
        key_length = self._calc_key_length(expr, wa.dbf)
        key_type = self._calc_key_type(expr, wa.dbf)

        if idx_type == "NDX":
            idx = NDXIndex()
            idx.create(filename, expr, key_type=key_type, key_length=key_length, unique=unique)
            idx.rebuild(wa.dbf, lambda e, r, i: self.eval.evaluate(e, r, i))
            idx.save()
            wa.add_index(idx)
        elif idx_type == "NTX":
            idx = NTXIndex()
            idx.create(filename, expr, key_length=key_length, key_type=key_type,
                       unique=unique, descending=descending, for_expression=for_expr)
            idx.rebuild(wa.dbf, lambda e, r, i: self.eval.evaluate(e, r, i),
                       lambda e, r, i: self.eval.eval_condition(e, r, i) if for_expr else None)
            idx.save()
            wa.add_index(idx)
        elif idx_type == "CDX":
            # Check if CDX already open
            cdx = None
            for existing in wa.indexes:
                if isinstance(existing, CDXIndex) and existing.filename == filename:
                    cdx = existing
                    break
            if not cdx:
                cdx = CDXIndex()
                cdx.create(filename)
                wa.add_index(cdx)
            tname = tag_name or os.path.splitext(os.path.basename(filename))[0]
            cdx.add_tag(tname, expr, key_length=key_length, key_type=key_type,
                       unique=unique, ascending=not descending, for_expression=for_expr)
            cdx.rebuild_tag(tname, wa.dbf, lambda e, r, i: self.eval.evaluate(e, r, i),
                          lambda e, r, i: self.eval.eval_condition(e, r, i) if for_expr else None)
            cdx.save()
        elif idx_type == "MDX":
            mdx = None
            for existing in wa.indexes:
                if isinstance(existing, MDXIndex) and existing.filename == filename:
                    mdx = existing
                    break
            if not mdx:
                mdx = MDXIndex()
                mdx.create(filename, os.path.basename(wa.dbf.filename))
                wa.add_index(mdx)
            tname = tag_name or os.path.splitext(os.path.basename(filename))[0]
            mdx.add_tag(tname, expr, key_length=key_length, key_type=key_type,
                       unique=unique, ascending=not descending, for_expression=for_expr)
            mdx.rebuild_tag(tname, wa.dbf, lambda e, r, i: self.eval.evaluate(e, r, i),
                          lambda e, r, i: self.eval.eval_condition(e, r, i) if for_expr else None)
            mdx.save()

        if self.config.talk:
            count = wa.dbf.record_count
            self._output(f"{count} record(s) indexed. Index: {os.path.basename(filename)} [{idx_type}]")
        return self.output_lines

    def _cmd_index_on_tag(self, expr, tag_name, options):
        """Handle INDEX ON expr TAG tagname [OF cdxfile] [...]"""
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        unique = False
        descending = False
        for_expr = ""
        cdx_file = ""
        opt_tokens = self._tokenize_command(options)
        i = 0
        while i < len(opt_tokens):
            kw = opt_tokens[i].upper()
            if kw == "OF" and i + 1 < len(opt_tokens):
                cdx_file = opt_tokens[i + 1]
                i += 1
            elif kw == "UNIQUE":
                unique = True
            elif kw == "DESCENDING":
                descending = True
            elif kw == "FOR" and i + 1 < len(opt_tokens):
                for_expr = opt_tokens[i + 1]
                i += 1
            i += 1

        if not cdx_file:
            cdx_file = os.path.splitext(wa.dbf.filename)[0] + ".cdx"
        else:
            cdx_file = self._ensure_extension(cdx_file, ".cdx")
            cdx_file = self._resolve_path(cdx_file)

        key_length = self._calc_key_length(expr, wa.dbf)
        key_type = self._calc_key_type(expr, wa.dbf)

        cdx = None
        for existing in wa.indexes:
            if isinstance(existing, CDXIndex) and existing.filename == cdx_file:
                cdx = existing
                break
        if not cdx:
            cdx = CDXIndex()
            if os.path.exists(cdx_file):
                cdx = CDXIndex(cdx_file, wa.dbf)
            else:
                cdx.create(cdx_file)
            wa.add_index(cdx)

        cdx.add_tag(tag_name, expr, key_length=key_length, key_type=key_type,
                    unique=unique, ascending=not descending, for_expression=for_expr)
        cdx.rebuild_tag(tag_name, wa.dbf, lambda e, r, i: self.eval.evaluate(e, r, i))
        cdx.save()

        if self.config.talk:
            self._output(f"{wa.dbf.record_count} record(s) indexed. Tag: {tag_name}")
        return self.output_lines

    def _calc_key_length(self, expr, dbf):
        expr_upper = expr.upper().strip()
        field = dbf.field_by_name(expr_upper)
        if field:
            if field.field_type == "D":
                return 8
            if field.field_type in ("N", "F"):
                return max(field.length, 8)
            return field.length
        return 20

    def _calc_key_type(self, expr, dbf):
        expr_upper = expr.upper().strip()
        field = dbf.field_by_name(expr_upper)
        if field:
            if field.field_type in ("N", "F", "I", "B"):
                return 1
            if field.field_type == "D":
                return 0
        return 0

    def _cmd_set_index(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        rest = rest.strip()
        if rest.upper().startswith("TO"):
            rest = rest[2:].strip()

        if not rest:
            wa.indexes = [idx for idx in wa.indexes if isinstance(idx, MDXIndex)]
            wa.active_order = 0
            if self.config.talk:
                self._output("Index files closed.")
            return self.output_lines

        files = [f.strip().strip('"').strip("'") for f in rest.split(",")]
        for f in files:
            if f:
                f = self._resolve_path(f)
                idx = self._open_index_file(f, wa.dbf)
                if idx:
                    wa.add_index(idx)

        if self.config.talk:
            self._output(f"{len(files)} index file(s) opened.")
        return self.output_lines

    def _cmd_set_order(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        rest = rest.strip()
        if rest.upper().startswith("TO"):
            rest = rest[2:].strip()

        if not rest or rest == "0":
            wa.active_order = 0
            if self.config.talk:
                self._output("Natural record order.")
            return self.output_lines

        try:
            order = int(rest)
            wa.set_order(order)
        except ValueError:
            wa.set_order(rest)

        if self.config.talk:
            self._output(f"Order set to {rest}.")
        return self.output_lines

    def _cmd_reindex(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        for idx in wa.indexes:
            if hasattr(idx, "rebuild"):
                idx.rebuild(wa.dbf, lambda e, r, i: self.eval.evaluate(e, r, i))
                idx.save()
            elif hasattr(idx, "rebuild_all"):
                idx.rebuild_all(wa.dbf, lambda e, r, i: self.eval.evaluate(e, r, i))
                idx.save()

        if self.config.talk:
            self._output(f"{len(wa.indexes)} index(es) rebuilt.")
        return self.output_lines

    # ===== AGGREGATE COMMANDS =====

    def _cmd_count(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        scope, for_expr, while_expr, rest = self._parse_scope_for_while(rest)
        to_var = None
        m = re.search(r'\bTO\b\s+(\w+)', rest, re.IGNORECASE)
        if m:
            to_var = m.group(1)

        wa.go_top()
        count = 0
        while not wa.eof:
            rec = wa.current_record()
            if rec is None:
                break
            if not self.config.deleted and rec.deleted:
                wa.skip()
                continue
            if while_expr and not self.eval.eval_condition(while_expr, rec, wa.recno - 1):
                break
            if for_expr and not self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                wa.skip()
                continue
            count += 1
            wa.skip()

        if to_var:
            self.env.set_variable(to_var.upper(), count)
        if self.config.talk:
            self._output(f"{count} record(s).")
        return self.output_lines

    def _cmd_sum(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        scope, for_expr, while_expr, rest = self._parse_scope_for_while(rest)

        # Parse expressions and TO variables
        to_vars = []
        expr_part = rest
        m = re.search(r'\bTO\b\s+(.*)', rest, re.IGNORECASE)
        if m:
            expr_part = rest[:m.start()].strip()
            to_vars = [v.strip() for v in m.group(1).split(",")]

        exprs = [e.strip() for e in self._split_expr_list(expr_part) if e.strip()]
        sums = [0.0] * len(exprs)

        wa.go_top()
        count = 0
        while not wa.eof:
            rec = wa.current_record()
            if rec is None:
                break
            if not self.config.deleted and rec.deleted:
                wa.skip()
                continue
            if while_expr and not self.eval.eval_condition(while_expr, rec, wa.recno - 1):
                break
            if for_expr and not self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                wa.skip()
                continue
            for i, expr in enumerate(exprs):
                val = self.eval.evaluate(expr, rec, wa.recno - 1)
                sums[i] += float(val) if isinstance(val, (int, float)) else 0
            count += 1
            wa.skip()

        for i, var in enumerate(to_vars):
            if i < len(sums):
                self.env.set_variable(var.upper(), sums[i])

        if self.config.talk:
            self._output(f"{count} record(s) summed.")
            for i, expr in enumerate(exprs):
                self._output(f"  {expr}: {sums[i]:.{self.config.decimals}f}")
        return self.output_lines

    def _cmd_average(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        scope, for_expr, while_expr, rest = self._parse_scope_for_while(rest)
        to_vars = []
        expr_part = rest
        m = re.search(r'\bTO\b\s+(.*)', rest, re.IGNORECASE)
        if m:
            expr_part = rest[:m.start()].strip()
            to_vars = [v.strip() for v in m.group(1).split(",")]

        exprs = [e.strip() for e in self._split_expr_list(expr_part) if e.strip()]
        sums = [0.0] * len(exprs)

        wa.go_top()
        count = 0
        while not wa.eof:
            rec = wa.current_record()
            if rec is None:
                break
            if not self.config.deleted and rec.deleted:
                wa.skip()
                continue
            if while_expr and not self.eval.eval_condition(while_expr, rec, wa.recno - 1):
                break
            if for_expr and not self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                wa.skip()
                continue
            for i, expr in enumerate(exprs):
                val = self.eval.evaluate(expr, rec, wa.recno - 1)
                sums[i] += float(val) if isinstance(val, (int, float)) else 0
            count += 1
            wa.skip()

        avgs = [s / count if count > 0 else 0 for s in sums]
        for i, var in enumerate(to_vars):
            if i < len(avgs):
                self.env.set_variable(var.upper(), avgs[i])

        if self.config.talk:
            self._output(f"{count} record(s) averaged.")
            for i, expr in enumerate(exprs):
                self._output(f"  {expr}: {avgs[i]:.{self.config.decimals}f}")
        return self.output_lines

    def _cmd_total(self, rest):
        self._output("TOTAL: use SUM for aggregation in this version.")
        return self.output_lines

    # ===== COPY / SORT =====

    def _cmd_copy_to(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        parts = self._tokenize_command(rest)
        if not parts:
            self._output("Syntax: COPY TO <file> [TYPE CSV|JSON|XML|SDF|DELIMITED|XLS] [FIELDS f1,f2] [FOR cond]")
            return self.output_lines

        filename = parts[0].strip('"').strip("'")

        # Parse TYPE, DELIMITED WITH, FIELDS, FOR, WHILE
        file_type = None
        delim_char = ","
        qualifier = '"'
        field_list = None
        remaining_parts = []
        i = 1
        while i < len(parts):
            kw = parts[i].upper()
            if kw == "TYPE" and i + 1 < len(parts):
                file_type = parts[i + 1].upper()
                i += 2
            elif kw == "DELIMITED":
                file_type = "DELIMITED"
                if i + 2 < len(parts) and parts[i + 1].upper() == "WITH":
                    val = parts[i + 2].strip('"').strip("'")
                    if val.upper() == "TAB":
                        delim_char = "\t"
                    elif val.upper() == "BLANK":
                        delim_char = " "
                    else:
                        delim_char = val
                    i += 3
                else:
                    i += 1
            elif kw == "SDF":
                file_type = "SDF"
                i += 1
            elif kw == "CSV":
                file_type = "CSV"
                i += 1
            elif kw == "JSON":
                file_type = "JSON"
                i += 1
            elif kw == "XML":
                file_type = "XML"
                i += 1
            elif kw == "XLS":
                file_type = "XLS"
                i += 1
            elif kw == "FIELDS" and i + 1 < len(parts):
                field_list = [f.strip() for f in parts[i + 1].split(",")]
                i += 2
            else:
                remaining_parts.append(parts[i])
                i += 1

        # Auto-detect type from extension
        if not file_type:
            ext = os.path.splitext(filename)[1].upper()
            type_map = {".CSV": "CSV", ".JSON": "JSON", ".XML": "XML",
                       ".TXT": "SDF", ".XLS": "XLS", ".TSV": "XLS"}
            file_type = type_map.get(ext, "DBF")

        # Default extension based on type
        ext_map = {"DBF": ".dbf", "CSV": ".csv", "JSON": ".json", "XML": ".xml",
                   "SDF": ".txt", "DELIMITED": ".txt", "XLS": ".xls"}
        if "." not in os.path.basename(filename):
            filename += ext_map.get(file_type, ".dbf")

        filename = self._resolve_path(filename)

        scope, for_expr, while_expr, _ = self._parse_scope_for_while(" ".join(remaining_parts))
        for_fn = (lambda r, i: self.eval.eval_condition(for_expr, r, i)) if for_expr else None
        while_fn = (lambda r, i: self.eval.eval_condition(while_expr, r, i)) if while_expr else None

        try:
            if file_type == "DBF":
                count = wa.dbf.copy_to(filename, field_list=field_list,
                                       for_func=for_fn, while_func=while_fn)
            elif file_type == "CSV":
                count = io_formats.export_csv(wa.dbf, filename, field_list,
                                              for_func=for_fn, while_func=while_fn)
            elif file_type == "JSON":
                count = io_formats.export_json(wa.dbf, filename, field_list,
                                               for_func=for_fn, while_func=while_fn)
            elif file_type == "XML":
                count = io_formats.export_xml(wa.dbf, filename, field_list,
                                              for_func=for_fn, while_func=while_fn)
            elif file_type == "SDF":
                count = io_formats.export_sdf(wa.dbf, filename, field_list,
                                              for_func=for_fn, while_func=while_fn)
            elif file_type == "DELIMITED":
                count = io_formats.export_delimited(wa.dbf, filename, field_list,
                                                     for_func=for_fn, while_func=while_fn,
                                                     delimiter=delim_char, qualifier=qualifier)
            elif file_type in ("XLS", "TSV"):
                count = io_formats.export_xls(wa.dbf, filename, field_list,
                                              for_func=for_fn, while_func=while_fn)
            else:
                self._output(f"Unsupported TYPE: {file_type}")
                return self.output_lines

            if self.config.talk:
                self._output(f"{count} record(s) exported to {os.path.basename(filename)} [{file_type}].")
        except Exception as e:
            self._output(f"Error: {e}")
        return self.output_lines

    def _cmd_copy_structure(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        rest = rest.strip()
        if rest.upper().startswith("TO"):
            rest = rest[2:].strip()
        parts = self._tokenize_command(rest)
        if not parts:
            self._output("Syntax: COPY STRUCTURE TO <filename>")
            return self.output_lines

        filename = parts[0].strip('"').strip("'")
        filename = self._ensure_extension(filename, ".dbf")
        filename = self._resolve_path(filename)

        wa.dbf.copy_structure(filename)
        if self.config.talk:
            self._output(f"Structure copied to {os.path.basename(filename)}.")
        return self.output_lines

    def _cmd_sort(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        m = re.match(r'TO\s+(\S+)\s+ON\s+(\S+)(.*)', rest, re.IGNORECASE)
        if not m:
            self._output("Syntax: SORT TO <file> ON <field> [/A] [/D]")
            return self.output_lines

        filename = m.group(1).strip('"').strip("'")
        filename = self._ensure_extension(filename, ".dbf")
        filename = self._resolve_path(filename)
        field_spec = m.group(2).strip()
        ascending = "/D" not in m.group(3).upper()

        field_name = field_spec.split("/")[0].strip()

        new_dbf = wa.dbf.copy_structure(filename)
        for rec in wa.dbf.records:
            if not rec.deleted:
                data = {f.name: rec[f.name] for f in new_dbf.fields}
                new_dbf.append_record(data)

        new_dbf.sort_by(field_name, ascending)
        new_dbf.save()

        if self.config.talk:
            self._output(f"{new_dbf.record_count} record(s) sorted to {os.path.basename(filename)}.")
        return self.output_lines

    # ===== VARIABLE COMMANDS =====

    def _cmd_store(self, rest):
        m = re.match(r'(.+?)\s+TO\s+(\S+)', rest, re.IGNORECASE)
        if not m:
            self._output("Syntax: STORE <expression> TO <variable>")
            return self.output_lines
        val = self.eval.evaluate(m.group(1).strip())
        name = m.group(2).strip().upper()
        self.env.set_variable(name, val)
        if self.config.talk:
            self._output(f"{name} = {self._format_value(val)}")
        return self.output_lines

    def _cmd_public(self, rest):
        names = [n.strip().upper() for n in rest.split(",")]
        for name in names:
            if name:
                self.env.declare_public(name)
        return self.output_lines

    def _cmd_private(self, rest):
        names = [n.strip().upper() for n in rest.split(",")]
        for name in names:
            if name:
                self.env.declare_private(name)
        return self.output_lines

    def _cmd_release(self, rest):
        rest = rest.strip().upper()
        if rest == "ALL":
            self.env.release_all()
        else:
            names = [n.strip() for n in rest.split(",")]
            for name in names:
                if name:
                    self.env.release_variable(name)
        return self.output_lines

    def _cmd_declare(self, rest):
        m = re.match(r'(\w+)\s*\[(\d+)(?:\s*,\s*(\d+))?\]', rest)
        if not m:
            m = re.match(r'(\w+)\s*\((\d+)(?:\s*,\s*(\d+))?\)', rest)
        if m:
            name = m.group(1)
            rows = int(m.group(2))
            cols = int(m.group(3)) if m.group(3) else 0
            self.env.declare_array(name, rows, cols)
            if self.config.talk:
                if cols:
                    self._output(f"Array {name.upper()} [{rows},{cols}] declared.")
                else:
                    self._output(f"Array {name.upper()} [{rows}] declared.")
        else:
            self._output("Syntax: DECLARE <name>[<rows>[,<cols>]]")
        return self.output_lines

    # ===== SELECT =====

    def _cmd_select(self, rest):
        rest = rest.strip()
        if not rest:
            self._output(f"Current work area: {self.env.current_area}")
            return self.output_lines
        self.env.select_area(rest)
        if self.config.talk:
            self._output(f"Work area: {self.env.current_area}")
        return self.output_lines

    # ===== SET COMMANDS =====

    def _cmd_set(self, rest):
        parts = self._tokenize_command(rest)
        if not parts:
            self._cmd_display_status("")
            return self.output_lines

        setting = parts[0].upper()
        value = " ".join(parts[1:]).strip() if len(parts) > 1 else ""

        # Remove "TO" if present
        if value.upper().startswith("TO "):
            value = value[3:].strip()

        settings_map = {
            "TALK": ("talk", "bool"),
            "ECHO": ("echo", "bool"),
            "EXACT": ("exact", "bool"),
            "DELETED": ("deleted", "bool"),
            "EXCLUSIVE": ("exclusive", "bool"),
            "CONFIRM": ("confirm", "bool"),
            "SAFETY": ("safety", "bool"),
            "BELL": ("bell", "bool"),
            "STATUS": ("status", "bool"),
            "SCOREBOARD": ("scoreboard", "bool"),
            "ESCAPE": ("escape", "bool"),
            "CARRY": ("carry", "bool"),
            "CENTURY": ("century", "bool"),
            "NEAR": ("near", "bool"),
            "SOFTSEEK": ("softseek", "bool"),
            "UNIQUE": ("unique", "bool"),
            "CONSOLE": ("console", "bool"),
            "PRINTER": ("printer", "bool"),
            "ALTERNATE": ("alternate", "bool"),
            "DEBUG": ("debug", "bool"),
        }

        if setting in settings_map:
            attr, stype = settings_map[setting]
            val_upper = value.upper()
            if val_upper == "ON":
                setattr(self.config, attr, True)
            elif val_upper == "OFF":
                setattr(self.config, attr, False)
            else:
                current = getattr(self.config, attr)
                self._output(f"SET {setting} is {'ON' if current else 'OFF'}")
                return self.output_lines
            if self.config.talk:
                new_val = getattr(self.config, attr)
                self._output(f"SET {setting} {'ON' if new_val else 'OFF'}")
            return self.output_lines

        if setting == "DATE":
            if value:
                self.config.date_format = value.upper()
                if self.config.talk:
                    self._output(f"Date format: {self.config.get_date_format_str()}")
            else:
                self._output(f"Date format: {self.config.get_date_format_str()}")
            return self.output_lines

        if setting == "DECIMALS":
            if value:
                self.config.decimals = int(value)
            else:
                self._output(f"Decimals: {self.config.decimals}")
            return self.output_lines

        if setting == "EPOCH":
            if value:
                self.config.epoch = int(value)
            else:
                self._output(f"Epoch: {self.config.epoch}")
            return self.output_lines

        if setting == "MEMOWIDTH":
            if value:
                self.config.memowidth = int(value)
            else:
                self._output(f"Memowidth: {self.config.memowidth}")
            return self.output_lines

        if setting == "DEFAULT":
            if value:
                path = value.strip('"').strip("'")
                if os.path.isdir(path):
                    self.config.default_path = path
                    os.chdir(path)
                else:
                    self._output(f"Directory not found: {path}")
            else:
                self._output(f"Default: {self.config.default_path}")
            return self.output_lines

        if setting == "PATH":
            if value:
                self.config.search_path = value.strip('"').strip("'")
            else:
                self._output(f"Path: {self.config.search_path}")
            return self.output_lines

        if setting == "COLOR" or setting == "COLOUR":
            if value:
                self.config.color = value
            else:
                self._output(f"Color: {self.config.color}")
            return self.output_lines

        if setting == "FILTER":
            wa = self.env.current_workarea()
            if wa:
                if value and value.upper() != "TO":
                    if value.upper().startswith("TO "):
                        value = value[3:].strip()
                    wa.filter_expr = value
                else:
                    wa.filter_expr = ""
                    self._output("Filter cleared.")
            return self.output_lines

        if setting == "RELATION":
            if value.upper() == "OFF" or not value:
                wa = self.env.current_workarea()
                if wa:
                    wa.relation_expr = ""
                    wa.relation_target = 0
            else:
                m = re.match(r'(.+?)\s+INTO\s+(\S+)', value, re.IGNORECASE)
                if m:
                    expr = m.group(1).strip()
                    target = m.group(2).strip()
                    wa = self.env.current_workarea()
                    if wa:
                        wa.relation_expr = expr
                        target_wa = self.env.get_workarea_by_alias(target)
                        wa.relation_target = target_wa.area_number if target_wa else 0
            return self.output_lines

        if setting in ("INDEX", "ORDER"):
            if setting == "INDEX":
                return self._cmd_set_index(value)
            return self._cmd_set_order(value)

        if setting == "HEADING":
            val_upper = value.upper()
            if val_upper == "ON":
                self.config.heading = True
            elif val_upper == "OFF":
                self.config.heading = False
            return self.output_lines

        if setting == "MARGIN":
            if value:
                self.config.margin = int(value)
            return self.output_lines

        if setting == "DELIMITER":
            if value.upper() == "ON":
                self.config.delimiters_on = True
            elif value.upper() == "OFF":
                self.config.delimiters_on = False
            elif value:
                self.config.delimiter = value.strip('"').strip("'")
            return self.output_lines

        self._output(f"Unknown SET command: {setting}")
        return self.output_lines

    # ===== FILE COMMANDS =====

    def _cmd_close(self, rest):
        rest = rest.strip().upper()
        if rest in ("ALL", "DATABASES"):
            self.env.close_all()
            if self.config.talk:
                self._output("All databases closed.")
        elif rest == "INDEX":
            wa = self.env.current_workarea()
            if wa:
                wa.indexes = [idx for idx in wa.indexes if isinstance(idx, MDXIndex)]
                wa.active_order = 0
            if self.config.talk:
                self._output("Index files closed.")
        else:
            wa = self.env.current_workarea()
            if wa and wa.is_open():
                wa.close_table()
            if self.config.talk:
                self._output("Database closed.")
        return self.output_lines

    def _cmd_dir(self, rest):
        rest = rest.strip() if rest else ""
        path = rest.strip('"').strip("'") if rest else "*.dbf"
        if "*" not in path and "?" not in path:
            path = os.path.join(path, "*.dbf") if os.path.isdir(path) else path

        pattern = self._resolve_path(path) if not os.path.isabs(path) else path
        files = globmod.glob(pattern)

        if not files:
            self._output("No files found.")
            return self.output_lines

        total_size = 0
        for f in sorted(files):
            size = os.path.getsize(f)
            total_size += size
            mtime = os.path.getmtime(f)
            dt = date.fromtimestamp(mtime)
            name = os.path.basename(f)
            self._output(f"  {name:<20s} {size:>10,d}  {self.config.format_date(dt)}")

        self._output(f"  {len(files)} file(s), {total_size:,d} bytes total.")
        return self.output_lines

    def _cmd_rename(self, rest):
        parts = self._tokenize_command(rest)
        if len(parts) < 3 or parts[1].upper() != "TO":
            self._output("Syntax: RENAME <old> TO <new>")
            return self.output_lines
        old = self._resolve_path(parts[0].strip('"'))
        new = self._resolve_path(parts[2].strip('"'))
        try:
            os.rename(old, new)
            if self.config.talk:
                self._output(f"File renamed.")
        except Exception as e:
            self._output(f"Error: {e}")
        return self.output_lines

    def _cmd_erase(self, rest):
        filename = rest.strip().strip('"').strip("'")
        filename = self._resolve_path(filename)
        try:
            os.remove(filename)
            if self.config.talk:
                self._output("File erased.")
        except Exception as e:
            self._output(f"Error: {e}")
        return self.output_lines

    def _cmd_type(self, rest):
        filename = rest.strip().strip('"').strip("'")
        filename = self._resolve_path(filename)
        try:
            with open(filename, "r") as f:
                for line in f:
                    self._output(line.rstrip())
        except Exception as e:
            self._output(f"Error: {e}")
        return self.output_lines

    # ===== DISPLAY COMMANDS =====

    def _cmd_display_structure(self, rest):
        wa = self._require_dbf()
        if not wa:
            return self.output_lines

        self._output(f"Structure for database: {os.path.basename(wa.dbf.filename)}")
        self._output(f"Number of data records: {wa.dbf.record_count}")
        self._output(f"Date of last update:    {self.config.format_date(date.today())}")
        self._output(f"{'Field':<5s}{'Field Name':<12s}{'Type':<12s}{'Width':<8s}{'Dec':<5s}")
        total_width = 1  # deletion flag
        for i, f in enumerate(wa.dbf.fields, 1):
            type_names = {"C": "Character", "N": "Numeric", "D": "Date", "L": "Logical",
                         "M": "Memo", "F": "Float", "I": "Integer", "B": "Double", "Y": "Currency"}
            tname = type_names.get(f.field_type, f.field_type)
            self._output(f"{i:<5d}{f.name:<12s}{tname:<12s}{f.length:<8d}{f.decimals:<5d}")
            total_width += f.length
        self._output(f"** Total **{' ' * 12}{total_width:>8d}")
        return self.output_lines

    def _cmd_display_status(self, rest):
        self._output("=== dBase Revival by Jair Lima - Status ===")
        self._output(f"Default directory: {self.config.default_path}")
        self._output(f"Search path:      {self.config.search_path or '(none)'}")
        self._output(f"Date format:      {self.config.get_date_format_str()}")
        self._output(f"Century:          {'ON' if self.config.century else 'OFF'}")
        self._output(f"Exact:            {'ON' if self.config.exact else 'OFF'}")
        self._output(f"Deleted:          {'ON' if self.config.deleted else 'OFF'}")
        self._output(f"Talk:             {'ON' if self.config.talk else 'OFF'}")
        self._output(f"Decimals:         {self.config.decimals}")
        self._output("")

        for area_num, wa in sorted(self.env.work_areas.items()):
            if wa.is_open():
                self._output(f"Work area {area_num}: {wa.alias}")
                self._output(f"  Database: {os.path.basename(wa.dbf.filename)}")
                self._output(f"  Records:  {wa.dbf.record_count}")
                self._output(f"  Record#:  {wa.recno}")
                for i, idx in enumerate(wa.indexes, 1):
                    active = " *" if wa.active_order == i else ""
                    if hasattr(idx, "filename"):
                        self._output(f"  Index {i}: {os.path.basename(idx.filename or '')}{active}")
                    if hasattr(idx, "tags"):
                        for tag in idx.tag_names():
                            t = idx.get_tag(tag)
                            self._output(f"    Tag: {tag} Expression: {t.expression}")
                self._output("")
        return self.output_lines

    def _cmd_display_memory(self, rest):
        self._output("=== Memory Variables ===")
        if not self.env.variables:
            self._output("No variables defined.")
        else:
            for name, val in sorted(self.env.variables.items()):
                vtype = "C" if isinstance(val, str) else "N" if isinstance(val, (int, float)) else "L" if isinstance(val, bool) else "D" if isinstance(val, date) else "U"
                scope = "PUBLIC" if name in self.env.public_vars else "PRIVATE"
                self._output(f"  {name:<20s} {scope:<10s} {vtype}  {self._format_value(val)}")
        self._output(f"\n{len(self.env.variables)} variable(s) defined.")
        return self.output_lines

    # ===== MISC COMMANDS =====

    def _cmd_clear(self, rest):
        rest = rest.strip().upper() if rest else ""
        if rest == "ALL":
            self.env.close_all()
            self.env.release_all()
        elif rest == "MEMORY":
            self.env.release_all()
        else:
            # Clear screen
            os.system("cls" if os.name == "nt" else "clear")
        return self.output_lines

    # ===== SQL COMMANDS =====

    def _cmd_sql(self, rest):
        """Handle SQL commands: SELECT, INSERT, DROP, ALTER."""
        # The command word was already parsed, reconstruct full SQL
        cmd = self._last_cmd_word
        full_sql = cmd + " " + rest
        try:
            output, result = self.sql.execute(full_sql.strip())
            self.output_lines.extend(output)
        except Exception as e:
            self._output(f"SQL Error: {e}")
        return self.output_lines

    def _cmd_sql_update(self, rest):
        """Handle SQL UPDATE (conflicts with dBase UPDATE command)."""
        rest_stripped = rest.strip()
        # If it looks like SQL UPDATE (has SET keyword), use SQL engine
        if re.search(r'\bSET\b', rest_stripped, re.IGNORECASE):
            try:
                output, result = self.sql.execute("UPDATE " + rest_stripped)
                self.output_lines.extend(output)
            except Exception as e:
                self._output(f"SQL Error: {e}")
        else:
            self._output("Syntax: UPDATE <table> SET <field>=<value> [WHERE <condition>]")
        return self.output_lines

    def _cmd_sql_create_table(self, rest):
        """Handle SQL CREATE TABLE."""
        try:
            output, result = self.sql.execute("CREATE TABLE " + rest.strip())
            self.output_lines.extend(output)
        except Exception as e:
            self._output(f"SQL Error: {e}")
        return self.output_lines

    def _cmd_help(self, rest):
        self._output("=== dBase Revival by Jair Lima - Help ===")
        self._output("")
        self._output("Database:   USE, APPEND, REPLACE, DELETE, RECALL, PACK, ZAP, CREATE")
        self._output("Navigation: GO/GOTO, SKIP, LOCATE, CONTINUE, SEEK, FIND")
        self._output("Display:    ?, ??, LIST, DISPLAY, BROWSE, EDIT")
        self._output("Index:      INDEX ON, SET INDEX TO, SET ORDER TO, REINDEX")
        self._output("Aggregate:  COUNT, SUM, AVERAGE")
        self._output("File:       COPY TO, COPY STRUCTURE, SORT, DIR, RENAME, ERASE, TYPE")
        self._output("Import:     APPEND FROM <file> TYPE CSV|JSON|XML|SDF|DELIMITED|XLS")
        self._output("Export:     COPY TO <file> TYPE CSV|JSON|XML|SDF|DELIMITED|XLS")
        self._output("Variables:  STORE, =, PUBLIC, PRIVATE, RELEASE, DECLARE")
        self._output("Flow:       IF/ELSE/ENDIF, DO WHILE/ENDDO, FOR/NEXT, DO CASE/ENDCASE")
        self._output("SET:        SET TALK/EXACT/DELETED/DATE/CENTURY/FILTER/RELATION/...")
        self._output("I/O:        ACCEPT, INPUT, WAIT, @...SAY...GET, READ")
        self._output("Other:      SELECT, CLOSE, CLEAR, DO <prg>, RUN, QUIT")
        self._output("")
        self._output("SQL:        SELECT, INSERT INTO, UPDATE SET, DELETE FROM")
        self._output("            CREATE TABLE, DROP TABLE, ALTER TABLE ADD/DROP")
        self._output("            JOIN, WHERE, GROUP BY, HAVING, ORDER BY, DISTINCT")
        self._output("            COUNT(), SUM(), AVG(), MIN(), MAX()")
        self._output("")
        self._output("Index formats: NDX (dBASE), NTX (Clipper), CDX (FoxPro), MDX (dBASE IV)")
        self._output("")
        self._output("Type DISPLAY STATUS for current settings.")
        self._output("Type DISPLAY STRUCTURE for table layout.")
        return self.output_lines

    def _cmd_quit(self, rest):
        self.env.close_all()
        raise SystemExit(0)

    def _cmd_return(self, rest):
        return self.output_lines

    def _cmd_do(self, rest):
        parts = self._tokenize_command(rest)
        if not parts:
            self._output("Syntax: DO <program>")
            return self.output_lines

        prg_name = parts[0].strip('"').strip("'")
        prg_file = self._ensure_extension(prg_name, ".prg")
        prg_file = self._resolve_path(prg_file)

        if not os.path.exists(prg_file):
            self._output(f"File not found: {prg_file}")
            return self.output_lines

        # Pass to interpreter
        from .interpreter import ProgramInterpreter
        interp = ProgramInterpreter(self.env, self.eval, self.config, self)
        try:
            output = interp.run_file(prg_file)
            self.output_lines.extend(output)
        except SystemExit:
            raise
        except Exception as e:
            self._output(f"Error in {prg_name}: {e}")
        return self.output_lines

    def _cmd_run(self, rest):
        rest = rest.strip()
        if rest.startswith("!"):
            rest = rest[1:].strip()
        try:
            os.system(rest)
        except Exception as e:
            self._output(f"Error: {e}")
        return self.output_lines

    def _cmd_wait(self, rest):
        msg = "Press any key to continue..."
        to_var = None
        if rest:
            m = re.match(r'(?:"([^"]*)"|(.*?))\s+TO\s+(\w+)', rest, re.IGNORECASE)
            if m:
                msg = m.group(1) or m.group(2) or msg
                to_var = m.group(3)
            else:
                msg = rest.strip('"').strip("'")
        try:
            ch = input(msg)
            if to_var:
                self.env.set_variable(to_var.upper(), ch[:1] if ch else "")
        except (EOFError, KeyboardInterrupt):
            pass
        return self.output_lines

    def _cmd_accept(self, rest):
        m = re.match(r'(?:"([^"]*)"|(.*?))\s+TO\s+(\w+)', rest, re.IGNORECASE)
        if m:
            prompt = m.group(1) or m.group(2) or ""
            var_name = m.group(3)
            try:
                val = input(prompt + " " if prompt else "")
                self.env.set_variable(var_name.upper(), val)
            except (EOFError, KeyboardInterrupt):
                pass
        else:
            self._output("Syntax: ACCEPT [<prompt>] TO <variable>")
        return self.output_lines

    def _cmd_input(self, rest):
        m = re.match(r'(?:"([^"]*)"|(.*?))\s+TO\s+(\w+)', rest, re.IGNORECASE)
        if m:
            prompt = m.group(1) or m.group(2) or ""
            var_name = m.group(3)
            try:
                val_str = input(prompt + " " if prompt else "")
                val = self.eval.evaluate(val_str)
                self.env.set_variable(var_name.upper(), val)
            except (EOFError, KeyboardInterrupt):
                pass
        else:
            self._output("Syntax: INPUT [<prompt>] TO <variable>")
        return self.output_lines

    def _cmd_at(self, line):
        """Handle @row,col SAY expr [GET var]"""
        # Simplified @...SAY/GET
        m = re.match(r'@\s*(\d+)\s*,\s*(\d+)\s+SAY\s+(.+?)(?:\s+GET\s+(\w+))?$', line, re.IGNORECASE)
        if m:
            row = int(m.group(1))
            col = int(m.group(2))
            expr = m.group(3).strip()
            get_var = m.group(4)

            val = self.eval.evaluate(expr)
            text = self._format_value(val)
            # Position cursor using ANSI
            self._output(f"\033[{row};{col}H{text}")

            if get_var:
                # Simplified GET
                try:
                    new_val = input("")
                    if new_val.strip():
                        self.env.set_variable(get_var.upper(), new_val)
                except (EOFError, KeyboardInterrupt):
                    pass
        else:
            self._output(f"Syntax error: {line}")
        return self.output_lines

    def _cmd_save_to(self, rest):
        self._output("SAVE TO: memory variable files not yet implemented in this version.")
        return self.output_lines

    def _cmd_restore_from(self, rest):
        self._output("RESTORE FROM: memory variable files not yet implemented in this version.")
        return self.output_lines

    def _cmd_update(self, rest):
        self._output("UPDATE: use SQL-style operations or manual REPLACE loops.")
        return self.output_lines

    def _cmd_join(self, rest):
        self._output("JOIN: use multiple work areas with SET RELATION for joins.")
        return self.output_lines

    def _cmd_label(self, rest):
        self._output("LABEL: label printing not yet implemented.")
        return self.output_lines

    def _cmd_report(self, rest):
        self._output("REPORT: report forms not yet implemented.")
        return self.output_lines
