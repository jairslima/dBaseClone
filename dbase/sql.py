"""dBase Revival by Jair Lima - SQL engine.

Supports SQL commands over DBF tables:

SELECT [DISTINCT] fields|* FROM table [alias]
    [JOIN table2 [alias2] ON condition]
    [WHERE condition]
    [GROUP BY field [, field ...]]
    [HAVING condition]
    [ORDER BY field [ASC|DESC] [, field ...]]
    [LIMIT n] [OFFSET n]
    [INTO TABLE filename | INTO CURSOR cursorname]

INSERT INTO table (fields) VALUES (values)
INSERT INTO table FROM SELECT ...

UPDATE table SET field=expr [, ...] [WHERE condition]

DELETE FROM table [WHERE condition]

CREATE TABLE name (field type(len[,dec]) [, ...])

DROP TABLE name

ALTER TABLE name ADD field type(len[,dec])
ALTER TABLE name DROP field

COUNT, SUM, AVG, MIN, MAX, UPPER, LOWER, TRIM aggregate/scalar functions
"""

import os
import re
from datetime import date, datetime
from .dbf import DBF


# ============================================================
# SQL Token types
# ============================================================

SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "ORDER", "BY", "GROUP", "HAVING",
    "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE",
    "CREATE", "TABLE", "DROP", "ALTER", "ADD", "MODIFY", "COLUMN",
    "AND", "OR", "NOT", "IN", "BETWEEN", "LIKE", "IS", "NULL",
    "AS", "ON", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS",
    "ASC", "DESC", "DISTINCT", "ALL", "TOP", "LIMIT", "OFFSET",
    "COUNT", "SUM", "AVG", "MIN", "MAX",
    "UPPER", "LOWER", "TRIM", "LTRIM", "RTRIM", "SUBSTR", "LEN",
    "CURSOR", "TO", "FILE",
}


class SQLToken:
    def __init__(self, ttype, value, pos=0):
        self.type = ttype
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"SQLToken({self.type}, {self.value!r})"


def sql_tokenize(text):
    """Tokenize a SQL statement."""
    tokens = []
    i = 0
    length = len(text)

    while i < length:
        # Skip whitespace
        if text[i] in " \t\r\n":
            i += 1
            continue

        start = i

        # String literals
        if text[i] in ("'", '"'):
            q = text[i]
            i += 1
            s = ""
            while i < length:
                if text[i] == q:
                    if i + 1 < length and text[i + 1] == q:
                        s += q
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    s += text[i]
                    i += 1
            tokens.append(SQLToken("STRING", s, start))
            continue

        # Numbers
        if text[i].isdigit() or (text[i] == "." and i + 1 < length and text[i + 1].isdigit()):
            while i < length and (text[i].isdigit() or text[i] == "."):
                i += 1
            val = text[start:i]
            tokens.append(SQLToken("NUMBER", float(val) if "." in val else int(val), start))
            continue

        # Operators
        two = text[i:i + 2]
        if two in ("<=", ">=", "<>", "!=", "||"):
            tokens.append(SQLToken("OP", two, start))
            i += 2
            continue
        if text[i] in "=<>+-*/%(),;.":
            tokens.append(SQLToken("OP", text[i], start))
            i += 1
            continue

        # Identifiers / keywords
        if text[i].isalpha() or text[i] == "_":
            while i < length and (text[i].isalnum() or text[i] == "_"):
                i += 1
            word = text[start:i]
            if word.upper() in SQL_KEYWORDS:
                tokens.append(SQLToken("KW", word.upper(), start))
            else:
                tokens.append(SQLToken("IDENT", word, start))
            continue

        # Wildcard
        if text[i] == "*":
            tokens.append(SQLToken("OP", "*", start))
            i += 1
            continue

        i += 1

    tokens.append(SQLToken("EOF", None, i))
    return tokens


# ============================================================
# SQL Parser - produces structured query dicts
# ============================================================

class SQLParser:
    """Parse SQL statements into structured query dictionaries."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else SQLToken("EOF", None)

    def peek(self, offset=1):
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else SQLToken("EOF", None)

    def advance(self):
        tok = self.current()
        self.pos += 1
        return tok

    def expect_kw(self, kw):
        tok = self.current()
        if tok.type != "KW" or tok.value != kw:
            raise SyntaxError(f"Expected {kw}, got {tok.value!r} at pos {tok.pos}")
        return self.advance()

    def match_kw(self, kw):
        if self.current().type == "KW" and self.current().value == kw:
            return self.advance()
        return None

    def match_op(self, op):
        if self.current().type == "OP" and self.current().value == op:
            return self.advance()
        return None

    def parse(self):
        tok = self.current()
        if tok.type == "KW":
            if tok.value == "SELECT":
                return self.parse_select()
            elif tok.value == "INSERT":
                return self.parse_insert()
            elif tok.value == "UPDATE":
                return self.parse_update()
            elif tok.value == "DELETE":
                return self.parse_delete()
            elif tok.value == "CREATE":
                return self.parse_create()
            elif tok.value == "DROP":
                return self.parse_drop()
            elif tok.value == "ALTER":
                return self.parse_alter()
        raise SyntaxError(f"Unexpected token: {tok.value!r}")

    def parse_select(self):
        self.expect_kw("SELECT")
        query = {"type": "SELECT", "distinct": False, "top": None}

        if self.match_kw("DISTINCT"):
            query["distinct"] = True
        if self.match_kw("TOP"):
            tok = self.advance()
            query["top"] = int(tok.value)

        # Fields
        query["fields"] = self.parse_field_list()

        # FROM
        if self.match_kw("FROM"):
            query["tables"] = self.parse_table_list()
        else:
            query["tables"] = []

        # JOINs
        query["joins"] = []
        while self._is_join_keyword():
            query["joins"].append(self.parse_join())

        # WHERE
        if self.match_kw("WHERE"):
            query["where"] = self.collect_until("GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET", "INTO")
        else:
            query["where"] = None

        # GROUP BY
        if self.match_kw("GROUP"):
            self.expect_kw("BY")
            query["group_by"] = self.parse_group_list()
        else:
            query["group_by"] = None

        # HAVING
        if self.match_kw("HAVING"):
            query["having"] = self.collect_until("ORDER", "LIMIT", "OFFSET", "INTO")
        else:
            query["having"] = None

        # ORDER BY
        if self.match_kw("ORDER"):
            self.expect_kw("BY")
            query["order_by"] = self.parse_order_list()
        else:
            query["order_by"] = None

        # LIMIT / OFFSET
        query["limit"] = None
        query["offset"] = None
        if self.match_kw("LIMIT"):
            query["limit"] = int(self.advance().value)
        if self.match_kw("OFFSET"):
            query["offset"] = int(self.advance().value)

        # INTO TABLE / INTO CURSOR
        query["into"] = None
        if self.match_kw("INTO"):
            if self.match_kw("TABLE"):
                query["into"] = ("TABLE", self.advance().value)
            elif self.match_kw("CURSOR"):
                query["into"] = ("CURSOR", self.advance().value)
            else:
                query["into"] = ("TABLE", self.advance().value)

        return query

    def parse_field_list(self):
        """Parse SELECT field list."""
        fields = []
        fields.append(self.parse_select_field())
        while self.match_op(","):
            fields.append(self.parse_select_field())
        return fields

    def parse_select_field(self):
        """Parse a single SELECT field (could be expression, *, func, alias)."""
        if self.current().type == "OP" and self.current().value == "*":
            self.advance()
            return {"expr": "*", "alias": None}

        expr_parts = []
        alias = None
        depth = 0

        while self.pos < len(self.tokens):
            tok = self.current()
            if tok.type == "EOF":
                break
            if tok.type == "OP" and tok.value == "," and depth == 0:
                break
            if tok.type == "KW" and tok.value in ("FROM", "WHERE", "ORDER", "GROUP",
                                                    "HAVING", "INTO", "LIMIT") and depth == 0:
                break
            if tok.type == "KW" and tok.value == "AS" and depth == 0:
                self.advance()
                alias = self.advance().value
                break
            if tok.type == "OP" and tok.value == "(":
                depth += 1
            if tok.type == "OP" and tok.value == ")":
                depth -= 1

            expr_parts.append(tok)
            self.advance()

        # Check if last part is an alias (IDENT after expression, no AS)
        if not alias and len(expr_parts) >= 2:
            last = expr_parts[-1]
            prev = expr_parts[-2]
            if (last.type == "IDENT" and
                prev.type not in ("OP",) and
                prev.value not in (".", "(", ",")):
                # Could be alias, but be conservative
                pass

        expr_str = self._tokens_to_string(expr_parts)
        return {"expr": expr_str, "alias": alias}

    def parse_table_list(self):
        """Parse FROM table list."""
        tables = []
        tables.append(self.parse_table_ref())
        while self.match_op(","):
            tables.append(self.parse_table_ref())
        return tables

    def parse_table_ref(self):
        """Parse a single table reference with optional alias."""
        name = self.advance().value
        alias = None
        if self.current().type == "KW" and self.current().value == "AS":
            self.advance()
            alias = self.advance().value
        elif (self.current().type == "IDENT" and
              self.current().value.upper() not in ("WHERE", "ORDER", "GROUP",
                                                    "HAVING", "ON", "JOIN",
                                                    "LEFT", "RIGHT", "INNER",
                                                    "FULL", "CROSS", "SET")):
            alias = self.advance().value
        return {"name": name, "alias": alias or name}

    def _is_join_keyword(self):
        tok = self.current()
        if tok.type != "KW":
            return False
        return tok.value in ("JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS")

    def parse_join(self):
        """Parse a JOIN clause."""
        join_type = "INNER"
        tok = self.current()
        if tok.value in ("LEFT", "RIGHT", "FULL", "CROSS"):
            join_type = tok.value
            self.advance()
            self.match_kw("OUTER")

        if tok.value == "INNER":
            self.advance()

        self.expect_kw("JOIN")
        table = self.parse_table_ref()

        on_expr = None
        if self.match_kw("ON"):
            on_expr = self.collect_until("WHERE", "GROUP", "ORDER", "HAVING",
                                         "JOIN", "LEFT", "RIGHT", "INNER",
                                         "FULL", "CROSS", "LIMIT", "OFFSET", "INTO")

        return {"type": join_type, "table": table, "on": on_expr}

    def parse_group_list(self):
        groups = []
        groups.append(self.advance().value)
        while self.match_op(","):
            groups.append(self.advance().value)
        return groups

    def parse_order_list(self):
        orders = []
        while True:
            name_parts = []
            while self.current().type in ("IDENT", "OP") and self.current().value not in (",",):
                if self.current().type == "KW" and self.current().value in ("ASC", "DESC"):
                    break
                if self.current().type == "KW":
                    break
                name_parts.append(self.advance().value)
            name = "".join(str(p) for p in name_parts)

            direction = "ASC"
            if self.match_kw("ASC"):
                direction = "ASC"
            elif self.match_kw("DESC"):
                direction = "DESC"

            orders.append({"field": name, "direction": direction})

            if not self.match_op(","):
                break
        return orders

    def collect_until(self, *stop_keywords):
        """Collect tokens as a string until a stop keyword is found."""
        parts = []
        depth = 0
        while self.pos < len(self.tokens):
            tok = self.current()
            if tok.type == "EOF":
                break
            if tok.type == "KW" and tok.value in stop_keywords and depth == 0:
                break
            if tok.type == "OP" and tok.value == "(":
                depth += 1
            if tok.type == "OP" and tok.value == ")":
                depth -= 1
            parts.append(tok)
            self.advance()
        return self._tokens_to_string(parts)

    def _tokens_to_string(self, tokens):
        """Convert token list back to string."""
        parts = []
        for tok in tokens:
            if tok.type == "STRING":
                parts.append(f"'{tok.value}'")
            else:
                parts.append(str(tok.value))
        return " ".join(parts)

    # ---- INSERT ----
    def parse_insert(self):
        self.expect_kw("INSERT")
        self.expect_kw("INTO")
        table = self.advance().value

        query = {"type": "INSERT", "table": table, "fields": [], "values": [], "select": None}

        if self.match_op("("):
            # Field list
            while not self.match_op(")"):
                if self.current().type in ("IDENT", "KW"):
                    query["fields"].append(self.advance().value)
                self.match_op(",")

        if self.match_kw("VALUES"):
            self.expect_op("(")
            values = []
            while not self.match_op(")"):
                val_parts = []
                depth = 0
                while self.pos < len(self.tokens):
                    tok = self.current()
                    if tok.type == "OP" and tok.value == "," and depth == 0:
                        self.advance()
                        break
                    if tok.type == "OP" and tok.value == ")" and depth == 0:
                        break
                    if tok.type == "OP" and tok.value == "(":
                        depth += 1
                    if tok.type == "OP" and tok.value == ")":
                        depth -= 1
                    val_parts.append(tok)
                    self.advance()
                values.append(self._tokens_to_string(val_parts))
            query["values"] = values
        elif self.current().type == "KW" and self.current().value == "SELECT":
            query["select"] = self.parse_select()

        return query

    def expect_op(self, op):
        tok = self.current()
        if tok.type != "OP" or tok.value != op:
            raise SyntaxError(f"Expected '{op}', got {tok.value!r}")
        return self.advance()

    # ---- UPDATE ----
    def parse_update(self):
        self.expect_kw("UPDATE")
        table = self.advance().value
        self.expect_kw("SET")

        query = {"type": "UPDATE", "table": table, "assignments": [], "where": None}

        while True:
            field = self.advance().value
            self.expect_op("=")
            expr_parts = []
            depth = 0
            while self.pos < len(self.tokens):
                tok = self.current()
                if tok.type == "EOF":
                    break
                if tok.type == "OP" and tok.value == "," and depth == 0:
                    self.advance()
                    break
                if tok.type == "KW" and tok.value == "WHERE" and depth == 0:
                    break
                if tok.type == "OP" and tok.value == "(":
                    depth += 1
                if tok.type == "OP" and tok.value == ")":
                    depth -= 1
                expr_parts.append(tok)
                self.advance()
            query["assignments"].append({"field": field, "expr": self._tokens_to_string(expr_parts)})
            if self.current().type == "KW" and self.current().value == "WHERE":
                break
            if self.current().type == "EOF":
                break

        if self.match_kw("WHERE"):
            query["where"] = self.collect_until()

        return query

    # ---- DELETE ----
    def parse_delete(self):
        self.expect_kw("DELETE")
        self.expect_kw("FROM")
        table = self.advance().value

        query = {"type": "DELETE", "table": table, "where": None}

        if self.match_kw("WHERE"):
            query["where"] = self.collect_until()

        return query

    # ---- CREATE TABLE ----
    def parse_create(self):
        self.expect_kw("CREATE")
        self.expect_kw("TABLE")
        table = self.advance().value

        query = {"type": "CREATE", "table": table, "fields": []}

        self.expect_op("(")
        while not self.match_op(")"):
            name = self.advance().value
            ftype_tok = self.advance()
            ftype = ftype_tok.value.upper() if ftype_tok.type in ("IDENT", "KW") else "C"

            # Map SQL types to dBase types
            type_map = {
                "CHAR": "C", "CHARACTER": "C", "VARCHAR": "C", "TEXT": "C", "C": "C",
                "INT": "N", "INTEGER": "N", "NUMERIC": "N", "NUMBER": "N",
                "N": "N", "FLOAT": "F", "DOUBLE": "F", "REAL": "F", "F": "F",
                "DECIMAL": "N", "DEC": "N",
                "DATE": "D", "D": "D",
                "LOGICAL": "L", "BOOL": "L", "BOOLEAN": "L", "L": "L",
                "MEMO": "M", "M": "M", "BLOB": "M",
            }
            db_type = type_map.get(ftype, "C")

            length = 10
            decimals = 0
            if self.match_op("("):
                length = int(self.advance().value)
                if self.match_op(","):
                    decimals = int(self.advance().value)
                self.expect_op(")")

            if db_type == "D":
                length = 8
            elif db_type == "L":
                length = 1

            query["fields"].append({
                "name": name, "type": db_type,
                "length": length, "decimals": decimals
            })
            self.match_op(",")

        return query

    # ---- DROP TABLE ----
    def parse_drop(self):
        self.expect_kw("DROP")
        self.expect_kw("TABLE")
        table = self.advance().value
        return {"type": "DROP", "table": table}

    # ---- ALTER TABLE ----
    def parse_alter(self):
        self.expect_kw("ALTER")
        self.expect_kw("TABLE")
        table = self.advance().value

        query = {"type": "ALTER", "table": table, "action": None, "field": None}

        if self.match_kw("ADD"):
            self.match_kw("COLUMN")
            name = self.advance().value
            ftype = self.advance().value.upper()
            type_map = {
                "CHAR": "C", "CHARACTER": "C", "VARCHAR": "C", "C": "C",
                "INT": "N", "INTEGER": "N", "NUMERIC": "N", "N": "N",
                "FLOAT": "F", "DOUBLE": "F", "F": "F",
                "DATE": "D", "D": "D", "LOGICAL": "L", "BOOL": "L", "L": "L",
                "MEMO": "M", "M": "M",
            }
            db_type = type_map.get(ftype, "C")
            length = 10
            decimals = 0
            if self.match_op("("):
                length = int(self.advance().value)
                if self.match_op(","):
                    decimals = int(self.advance().value)
                self.expect_op(")")
            if db_type == "D":
                length = 8
            elif db_type == "L":
                length = 1
            query["action"] = "ADD"
            query["field"] = {"name": name, "type": db_type, "length": length, "decimals": decimals}

        elif self.match_kw("DROP"):
            self.match_kw("COLUMN")
            name = self.advance().value
            query["action"] = "DROP"
            query["field"] = name

        return query


# ============================================================
# SQL Executor
# ============================================================

class SQLExecutor:
    """Execute parsed SQL queries against DBF files."""

    def __init__(self, env, evaluator, config):
        self.env = env
        self.eval = evaluator
        self.config = config

    def execute(self, sql_text):
        """Parse and execute a SQL statement. Returns (output_lines, result_set)."""
        tokens = sql_tokenize(sql_text)
        parser = SQLParser(tokens)
        query = parser.parse()

        dispatch = {
            "SELECT": self._exec_select,
            "INSERT": self._exec_insert,
            "UPDATE": self._exec_update,
            "DELETE": self._exec_delete,
            "CREATE": self._exec_create,
            "DROP": self._exec_drop,
            "ALTER": self._exec_alter,
        }

        handler = dispatch.get(query["type"])
        if not handler:
            return [f"Unsupported SQL command: {query['type']}"], None

        return handler(query)

    def _open_table(self, name):
        """Open a table by name, return (DBF, workarea_or_none)."""
        name_clean = name.strip('"').strip("'").strip("`")

        # Check if already open by alias
        wa = self.env.get_workarea_by_alias(name_clean.upper())
        if wa and wa.dbf:
            return wa.dbf, wa

        # Try opening the file
        filename = name_clean
        if "." not in filename:
            filename += ".dbf"
        if not os.path.isabs(filename):
            filename = os.path.join(self.config.default_path, filename)

        if os.path.exists(filename):
            dbf = DBF(filename)
            return dbf, None

        raise FileNotFoundError(f"Table not found: {name_clean}")

    def _eval_where(self, where_expr, record, recno):
        """Evaluate a WHERE expression, translating SQL syntax to xBase."""
        if not where_expr:
            return True
        expr = self._sql_to_xbase(where_expr)
        return self.eval.eval_condition(expr, record, recno)

    def _sql_to_xbase(self, expr):
        """Convert SQL expression syntax to xBase syntax."""
        if not expr:
            return expr
        # IS NULL -> EMPTY()
        expr = re.sub(r'(\w+)\s+IS\s+NULL', r'EMPTY(\1)', expr, flags=re.IGNORECASE)
        expr = re.sub(r'(\w+)\s+IS\s+NOT\s+NULL', r'.NOT. EMPTY(\1)', expr, flags=re.IGNORECASE)
        # LIKE 'pattern' -> LIKE('pattern', field)
        expr = re.sub(r"(\w+)\s+LIKE\s+'([^']*)'", r"LIKE('\2', \1)", expr, flags=re.IGNORECASE)
        # IN (a,b,c) -> INLIST(field, a, b, c)
        expr = re.sub(r"(\w+)\s+IN\s*\(([^)]+)\)", r"INLIST(\1, \2)", expr, flags=re.IGNORECASE)
        # BETWEEN a AND b -> BETWEEN(field, a, b)
        expr = re.sub(r"(\w+)\s+BETWEEN\s+(.+?)\s+AND\s+(.+?)(?:\s+(?:AND|OR)|$)",
                      r"BETWEEN(\1, \2, \3)", expr, flags=re.IGNORECASE)
        # <> to !=
        expr = expr.replace("<>", "!=")
        # || string concat to +
        expr = expr.replace("||", "+")
        return expr

    def _eval_expr(self, expr_str, record=None, recno=None):
        """Evaluate a SQL expression."""
        expr = self._sql_to_xbase(expr_str)
        return self.eval.evaluate(expr, record, recno)

    # ---- SELECT ----
    def _exec_select(self, query):
        output = []

        if not query["tables"]:
            # SELECT without FROM (e.g., SELECT 1+1, DATE())
            row = {}
            values = []
            headers = []
            for f in query["fields"]:
                val = self._eval_expr(f["expr"])
                alias = f["alias"] or f["expr"]
                headers.append(alias)
                values.append(val)
            output.extend(self._format_result_table(headers, [values]))
            return output, [dict(zip(headers, values))]

        # Open primary table
        primary = query["tables"][0]
        dbf, wa = self._open_table(primary["name"])
        table_alias = primary["alias"].upper()

        # Open join tables
        join_dbfs = []
        for j in query["joins"]:
            jdbf, jwa = self._open_table(j["table"]["name"])
            join_dbfs.append({
                "dbf": jdbf,
                "alias": j["table"]["alias"].upper(),
                "on": j["on"],
                "type": j["type"],
            })

        # Resolve field list
        is_star = len(query["fields"]) == 1 and query["fields"][0]["expr"] == "*"

        # Detect aggregate functions
        has_aggregate = False
        for f in query["fields"]:
            if re.match(r'(COUNT|SUM|AVG|MIN|MAX)\s*\(', f["expr"], re.IGNORECASE):
                has_aggregate = True
                break

        # Collect matching records
        result_rows = []
        for i, rec in enumerate(dbf.records):
            if rec.deleted:
                continue

            # Handle JOINs
            if join_dbfs:
                joined_rows = self._do_joins(rec, i, join_dbfs, table_alias)
                for merged in joined_rows:
                    if query["where"]:
                        if not self._eval_where(query["where"], merged, i):
                            continue
                    result_rows.append(merged)
            else:
                if query["where"]:
                    if not self._eval_where(query["where"], rec, i):
                        continue
                result_rows.append(rec)

        # GROUP BY
        if query["group_by"] or has_aggregate:
            result_rows = self._do_group_by(result_rows, query)

            # HAVING
            if query["having"]:
                result_rows = [r for r in result_rows
                              if self._eval_having(query["having"], r, query["fields"])]

            # Format grouped output
            headers = []
            for f in query["fields"]:
                headers.append(f["alias"] or f["expr"])

            rows_data = []
            for rec in result_rows:
                row = []
                for h in headers:
                    row.append(rec.get(h.upper(), rec.get(h, "")))
                rows_data.append(row)

            # ORDER BY
            if query["order_by"]:
                rows_data = self._sort_rows(rows_data, headers, query["order_by"])

            # LIMIT/OFFSET
            offset = query["offset"] or 0
            rows_data = rows_data[offset:]
            if query["limit"]:
                rows_data = rows_data[:query["limit"]]
            if query["top"]:
                rows_data = rows_data[:query["top"]]

            output.extend(self._format_result_table(headers, rows_data))
            output.append(f"{len(rows_data)} record(s).")
            return output, [dict(zip(headers, r)) for r in rows_data]

        # ORDER BY (non-grouped)
        if query["order_by"]:
            result_rows = self._sort_records(result_rows, query["order_by"], dbf)

        # DISTINCT
        if query["distinct"]:
            result_rows = self._distinct(result_rows, query["fields"], dbf)

        # LIMIT/OFFSET
        offset = query["offset"] or 0
        result_rows = result_rows[offset:]
        if query["limit"]:
            result_rows = result_rows[:query["limit"]]
        if query["top"]:
            result_rows = result_rows[:query["top"]]

        # Build output
        if is_star:
            headers = [f.name for f in dbf.fields]
        else:
            headers = [f["alias"] or f["expr"] for f in query["fields"]]

        rows_data = []
        for rec in result_rows:
            row = []
            if is_star:
                for fname in headers:
                    row.append(rec[fname] if rec.get(fname) is not None else rec.get(fname, ""))
            else:
                for f in query["fields"]:
                    val = self._eval_expr(f["expr"], rec)
                    row.append(val)
            rows_data.append(row)

        # INTO TABLE
        if query["into"]:
            into_type, into_name = query["into"]
            if into_type == "TABLE":
                count = self._save_to_table(into_name, headers, rows_data, query["fields"], dbf)
                output.append(f"{count} record(s) saved to {into_name}.")
                return output, None

        output.extend(self._format_result_table(headers, rows_data))
        output.append(f"{len(rows_data)} record(s).")
        return output, [dict(zip(headers, r)) for r in rows_data]

    def _do_joins(self, rec, recno, join_dbfs, primary_alias):
        """Perform JOIN operations, returning merged record(s)."""
        from .dbf import Record

        results = [rec]

        for jinfo in join_dbfs:
            jdbf = jinfo["dbf"]
            jalias = jinfo["alias"]
            on_expr = jinfo["on"]
            join_type = jinfo["type"]

            new_results = []
            for current_rec in results:
                matched = False
                for j, jrec in enumerate(jdbf.records):
                    if jrec.deleted:
                        continue
                    # Create merged record for ON evaluation
                    merged = self._merge_records(current_rec, jrec)
                    if on_expr:
                        if self._eval_where(on_expr, merged, recno):
                            new_results.append(merged)
                            matched = True
                    else:
                        new_results.append(merged)
                        matched = True

                if not matched and join_type in ("LEFT", "FULL"):
                    # Add null join side
                    null_rec = self._null_record(jdbf)
                    merged = self._merge_records(current_rec, null_rec)
                    new_results.append(merged)

            results = new_results

        return results

    def _merge_records(self, rec1, rec2):
        """Merge two records into one combined record."""
        from .dbf import Record
        merged_fields = list(rec1.fields) if hasattr(rec1, 'fields') else []
        if hasattr(rec2, 'fields'):
            for f in rec2.fields:
                if not any(mf.name == f.name for mf in merged_fields):
                    merged_fields.append(f)

        merged = Record(merged_fields)
        for f in rec1.fields if hasattr(rec1, 'fields') else []:
            merged[f.name] = rec1[f.name]
        for f in rec2.fields if hasattr(rec2, 'fields') else []:
            merged[f.name] = rec2[f.name]
        return merged

    def _null_record(self, dbf):
        """Create a record with null/empty values."""
        from .dbf import Record
        return Record(dbf.fields)

    def _do_group_by(self, records, query):
        """Group records and compute aggregates."""
        group_fields = query["group_by"] or []
        select_fields = query["fields"]

        # Group records
        groups = {}
        for rec in records:
            key_parts = []
            for gf in group_fields:
                val = self._eval_expr(gf, rec)
                key_parts.append(str(val))
            key = tuple(key_parts) if key_parts else ("__ALL__",)

            if key not in groups:
                groups[key] = []
            groups[key].append(rec)

        # Compute results per group
        result = []
        for key, group_recs in groups.items():
            row = {}
            for f in select_fields:
                expr = f["expr"].strip()
                alias = (f["alias"] or expr).upper()

                m = re.match(r'(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(\*|\w+)\s*\)', expr, re.IGNORECASE)
                if m:
                    func = m.group(1).upper()
                    field = m.group(2)

                    if func == "COUNT":
                        row[alias] = len(group_recs)
                    elif func == "SUM":
                        row[alias] = sum(float(self._eval_expr(field, r) or 0) for r in group_recs)
                    elif func == "AVG":
                        vals = [float(self._eval_expr(field, r) or 0) for r in group_recs]
                        row[alias] = sum(vals) / len(vals) if vals else 0
                    elif func == "MIN":
                        vals = [self._eval_expr(field, r) for r in group_recs]
                        row[alias] = min(v for v in vals if v is not None) if vals else None
                    elif func == "MAX":
                        vals = [self._eval_expr(field, r) for r in group_recs]
                        row[alias] = max(v for v in vals if v is not None) if vals else None
                else:
                    # Regular field
                    row[alias] = self._eval_expr(expr, group_recs[0])

            result.append(row)

        return result

    def _sort_records(self, records, order_list, dbf):
        """Sort records by ORDER BY clause."""
        for order in reversed(order_list):
            field = order["field"]
            reverse = order["direction"] == "DESC"
            records.sort(
                key=lambda r: (self._eval_expr(field, r) is None,
                              self._eval_expr(field, r) or ""),
                reverse=reverse
            )
        return records

    def _sort_rows(self, rows, headers, order_list):
        """Sort result rows by ORDER BY."""
        for order in reversed(order_list):
            field = order["field"].upper()
            reverse = order["direction"] == "DESC"
            try:
                idx = [h.upper() for h in headers].index(field)
            except ValueError:
                continue
            rows.sort(key=lambda r: (r[idx] is None, r[idx] or ""), reverse=reverse)
        return rows

    def _distinct(self, records, fields, dbf):
        """Remove duplicate rows."""
        seen = set()
        result = []
        for rec in records:
            key_parts = []
            for f in fields:
                if f["expr"] == "*":
                    for fld in dbf.fields:
                        key_parts.append(str(rec[fld.name]))
                else:
                    key_parts.append(str(self._eval_expr(f["expr"], rec)))
            key = tuple(key_parts)
            if key not in seen:
                seen.add(key)
                result.append(rec)
        return result

    def _save_to_table(self, name, headers, rows, fields, src_dbf):
        """Save SELECT results INTO TABLE."""
        filename = name if "." in name else name + ".dbf"
        if not os.path.isabs(filename):
            filename = os.path.join(self.config.default_path, filename)

        new_fields = []
        for i, h in enumerate(headers):
            if fields[i]["expr"] == "*":
                for fld in src_dbf.fields:
                    new_fields.append({"name": fld.name, "type": fld.field_type,
                                       "length": fld.length, "decimals": fld.decimals})
                break
            else:
                new_fields.append({"name": h[:10].upper(), "type": "C", "length": 50, "decimals": 0})

        new_dbf = DBF()
        new_dbf.create(filename, new_fields)
        for row in rows:
            data = {}
            for i, h in enumerate(headers):
                if i < len(row):
                    fname = new_fields[i]["name"] if i < len(new_fields) else h[:10].upper()
                    data[fname] = row[i]
            new_dbf.append_record(data)
        new_dbf.save()
        return len(rows)

    def _format_result_table(self, headers, rows):
        """Format results as a text table."""
        if not headers:
            return []

        # Calculate column widths
        widths = [len(str(h)) for h in headers]
        for row in rows:
            for i, val in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(self._fmt(val)))

        # Cap widths
        widths = [min(w, 40) for w in widths]

        lines = []
        # Header
        header = " ".join(str(h).ljust(widths[i])[:widths[i]] for i, h in enumerate(headers))
        lines.append(header)
        lines.append(" ".join("-" * w for w in widths))

        # Rows
        for row in rows:
            line = " ".join(
                self._fmt(row[i] if i < len(row) else "").ljust(widths[i])[:widths[i]]
                for i in range(len(headers))
            )
            lines.append(line)

        return lines

    def _fmt(self, val):
        """Format a value for display."""
        if val is None:
            return ""
        if isinstance(val, bool):
            return ".T." if val else ".F."
        if isinstance(val, float):
            return f"{val:.{self.config.decimals}f}"
        if isinstance(val, date):
            return self.config.format_date(val)
        return str(val).rstrip() if isinstance(val, str) else str(val)

    # ---- INSERT ----
    def _exec_insert(self, query):
        output = []
        dbf, wa = self._open_table(query["table"])

        if query["select"]:
            # INSERT INTO ... SELECT ...
            sel_output, result_set = self._exec_select(query["select"])
            if result_set:
                for obj in result_set:
                    data = {}
                    for k, v in obj.items():
                        fld = dbf.field_by_name(k.upper())
                        if fld:
                            data[fld.name] = v
                    dbf.append_record(data)
                dbf.save()
                output.append(f"{len(result_set)} record(s) inserted.")
            return output, None

        fields = [f.upper() for f in query["fields"]]
        if not fields:
            fields = [f.name for f in dbf.fields]

        rec = dbf.append_blank()
        for i, fname in enumerate(fields):
            if i < len(query["values"]):
                val = self._eval_expr(query["values"][i])
                rec[fname] = val

        dbf.save()

        if wa:
            wa.recno = dbf.record_count
            wa.eof = False

        output.append("1 record inserted.")
        return output, None

    # ---- UPDATE ----
    def _exec_update(self, query):
        output = []
        dbf, wa = self._open_table(query["table"])

        count = 0
        for i, rec in enumerate(dbf.records):
            if rec.deleted:
                continue
            if query["where"]:
                if not self._eval_where(query["where"], rec, i):
                    continue
            for assign in query["assignments"]:
                val = self._eval_expr(assign["expr"], rec, i)
                rec[assign["field"].upper()] = val
            count += 1

        dbf.save()
        output.append(f"{count} record(s) updated.")
        return output, None

    # ---- DELETE ----
    def _exec_delete(self, query):
        output = []
        dbf, wa = self._open_table(query["table"])

        count = 0
        for i, rec in enumerate(dbf.records):
            if rec.deleted:
                continue
            if query["where"]:
                if not self._eval_where(query["where"], rec, i):
                    continue
            rec.deleted = True
            count += 1

        dbf.save()
        output.append(f"{count} record(s) marked for deletion.")
        return output, None

    # ---- CREATE TABLE ----
    def _exec_create(self, query):
        output = []
        filename = query["table"]
        if "." not in filename:
            filename += ".dbf"
        if not os.path.isabs(filename):
            filename = os.path.join(self.config.default_path, filename)

        dbf = DBF()
        dbf.create(filename, query["fields"])
        dbf.save()

        output.append(f"Table {query['table']} created with {len(query['fields'])} field(s).")
        return output, None

    # ---- DROP TABLE ----
    def _exec_drop(self, query):
        output = []
        filename = query["table"]
        if "." not in filename:
            filename += ".dbf"
        if not os.path.isabs(filename):
            filename = os.path.join(self.config.default_path, filename)

        # Close if open
        for wnum, wa in self.env.work_areas.items():
            if wa.dbf and os.path.abspath(wa.dbf.filename) == os.path.abspath(filename):
                wa.close_table()

        if os.path.exists(filename):
            os.remove(filename)
            output.append(f"Table {query['table']} dropped.")
        else:
            output.append(f"Table not found: {query['table']}")
        return output, None

    # ---- ALTER TABLE ----
    def _exec_alter(self, query):
        output = []
        dbf, wa = self._open_table(query["table"])

        if query["action"] == "ADD":
            finfo = query["field"]
            from .dbf import FieldDef
            fd = FieldDef(finfo["name"], finfo["type"], finfo["length"], finfo["decimals"])
            dbf.fields.append(fd)
            # Add default value to all existing records
            for rec in dbf.records:
                rec._data[fd.name] = rec._default_value(fd)
                rec.fields = dbf.fields
            dbf.save()
            output.append(f"Field {finfo['name']} added to {query['table']}.")

        elif query["action"] == "DROP":
            fname = query["field"].upper()
            dbf.fields = [f for f in dbf.fields if f.name != fname]
            for rec in dbf.records:
                rec._data.pop(fname, None)
                rec.fields = dbf.fields
            dbf.save()
            output.append(f"Field {fname} dropped from {query['table']}.")

        return output, None
