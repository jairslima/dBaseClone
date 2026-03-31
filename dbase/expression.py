"""dBase Revival by Jair Lima - Expression parser and evaluator.

Full xBase expression parser supporting:
- Arithmetic: +, -, *, /, %, **, ^
- String: +, -, $
- Comparison: =, ==, <>, !=, #, <, >, <=, >=
- Logical: .AND., .OR., .NOT., !
- Function calls with arguments
- Field references, variables, aliases (ALIAS->FIELD)
- Literal strings, numbers, dates, logicals (.T., .F.)
- Parenthesized expressions
- Array subscripts
- Macro substitution (&variable)
"""

import re
from datetime import date, datetime


# Token types
TK_NUMBER = "NUMBER"
TK_STRING = "STRING"
TK_DATE = "DATE"
TK_IDENT = "IDENT"
TK_OPERATOR = "OPERATOR"
TK_LPAREN = "LPAREN"
TK_RPAREN = "RPAREN"
TK_LBRACKET = "LBRACKET"
TK_RBRACKET = "RBRACKET"
TK_COMMA = "COMMA"
TK_DOT = "DOT"
TK_ARROW = "ARROW"
TK_LOGICAL = "LOGICAL"
TK_AND = "AND"
TK_OR = "OR"
TK_NOT = "NOT"
TK_EOF = "EOF"


class Token:
    def __init__(self, ttype, value, pos=0):
        self.type = ttype
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


class Lexer:
    """Tokenizer for xBase expressions."""

    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def peek_char(self):
        if self.pos < self.length:
            return self.text[self.pos]
        return None

    def advance(self):
        ch = self.text[self.pos] if self.pos < self.length else None
        self.pos += 1
        return ch

    def skip_whitespace(self):
        while self.pos < self.length and self.text[self.pos] in " \t\r":
            self.pos += 1

    def tokenize(self):
        tokens = []
        while self.pos < self.length:
            self.skip_whitespace()
            if self.pos >= self.length:
                break

            start = self.pos
            ch = self.text[self.pos]

            # Numbers
            if ch.isdigit() or (ch == "." and self.pos + 1 < self.length and self.text[self.pos + 1].isdigit()):
                num = self._read_number()
                tokens.append(Token(TK_NUMBER, num, start))
                continue

            # Strings
            if ch in ('"', "'"):
                s = self._read_string(ch)
                tokens.append(Token(TK_STRING, s, start))
                continue

            # Date literals {mm/dd/yy} or {^yyyy-mm-dd}
            if ch == "{":
                d = self._read_date_literal()
                tokens.append(Token(TK_DATE, d, start))
                continue

            # Dot-prefixed keywords (.T., .F., .AND., .OR., .NOT.)
            if ch == ".":
                upper_rest = self.text[self.pos:].upper()
                for kw, tk in [(".AND.", TK_AND), (".OR.", TK_OR), (".NOT.", TK_NOT),
                               (".T.", TK_LOGICAL), (".F.", TK_LOGICAL),
                               (".TRUE.", TK_LOGICAL), (".FALSE.", TK_LOGICAL)]:
                    if upper_rest.startswith(kw):
                        val = self.text[self.pos:self.pos + len(kw)]
                        self.pos += len(kw)
                        if tk == TK_LOGICAL:
                            tokens.append(Token(TK_LOGICAL, val.upper()[1] == "T", start))
                        else:
                            tokens.append(Token(tk, val.upper(), start))
                        break
                else:
                    self.pos += 1
                    tokens.append(Token(TK_DOT, ".", start))
                continue

            # Operators
            if ch == "(" :
                self.pos += 1
                tokens.append(Token(TK_LPAREN, "(", start))
                continue
            if ch == ")":
                self.pos += 1
                tokens.append(Token(TK_RPAREN, ")", start))
                continue
            if ch == "[":
                # Could be string literal [text] or array subscript
                if tokens and tokens[-1].type in (TK_IDENT, TK_RPAREN, TK_RBRACKET):
                    self.pos += 1
                    tokens.append(Token(TK_LBRACKET, "[", start))
                else:
                    s = self._read_bracket_string()
                    tokens.append(Token(TK_STRING, s, start))
                continue
            if ch == "]":
                self.pos += 1
                tokens.append(Token(TK_RBRACKET, "]", start))
                continue
            if ch == ",":
                self.pos += 1
                tokens.append(Token(TK_COMMA, ",", start))
                continue

            # Arrow ->
            if ch == "-" and self.pos + 1 < self.length and self.text[self.pos + 1] == ">":
                self.pos += 2
                tokens.append(Token(TK_ARROW, "->", start))
                continue

            # Two-char operators
            two = self.text[self.pos:self.pos + 2] if self.pos + 1 < self.length else ""
            if two in ("==", "<>", "!=", "<=", ">=", "**", "++", "--"):
                self.pos += 2
                tokens.append(Token(TK_OPERATOR, two, start))
                continue

            # Single-char operators
            if ch in "+-*/%^=<>#!$@":
                self.pos += 1
                if ch == "!":
                    tokens.append(Token(TK_NOT, "!", start))
                else:
                    tokens.append(Token(TK_OPERATOR, ch, start))
                continue

            # Identifiers (field names, function names, variables)
            if ch.isalpha() or ch == "_" or ch == "&":
                ident = self._read_identifier()
                upper = ident.upper()
                if upper == "AND":
                    tokens.append(Token(TK_AND, ".AND.", start))
                elif upper == "OR":
                    tokens.append(Token(TK_OR, ".OR.", start))
                elif upper == "NOT":
                    tokens.append(Token(TK_NOT, ".NOT.", start))
                else:
                    tokens.append(Token(TK_IDENT, ident, start))
                continue

            # Skip unknown
            self.pos += 1

        tokens.append(Token(TK_EOF, None, self.pos))
        return tokens

    def _read_number(self):
        start = self.pos
        has_dot = False
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch.isdigit():
                self.pos += 1
            elif ch == "." and not has_dot:
                has_dot = True
                self.pos += 1
            else:
                break
        s = self.text[start:self.pos]
        return float(s) if has_dot else int(s)

    def _read_string(self, quote):
        self.pos += 1  # skip opening quote
        result = []
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch == quote:
                self.pos += 1
                break
            result.append(ch)
            self.pos += 1
        return "".join(result)

    def _read_bracket_string(self):
        self.pos += 1  # skip [
        result = []
        while self.pos < self.length:
            if self.text[self.pos] == "]":
                self.pos += 1
                break
            result.append(self.text[self.pos])
            self.pos += 1
        return "".join(result)

    def _read_date_literal(self):
        self.pos += 1  # skip {
        result = []
        while self.pos < self.length:
            if self.text[self.pos] == "}":
                self.pos += 1
                break
            result.append(self.text[self.pos])
            self.pos += 1
        ds = "".join(result).strip()
        if ds.startswith("^"):
            # Strict date {^yyyy-mm-dd}
            parts = ds[1:].split("-")
            if len(parts) == 3:
                try:
                    return date(int(parts[0]), int(parts[1]), int(parts[2]))
                except ValueError:
                    pass
        return ds

    def _read_identifier(self):
        start = self.pos
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch.isalnum() or ch == "_":
                self.pos += 1
            else:
                break
        return self.text[start:self.pos]


# AST Nodes
class ASTNode:
    pass

class NumberLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

class StringLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

class DateLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

class LogicalLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

class Identifier(ASTNode):
    def __init__(self, name):
        self.name = name.upper()

class AliasField(ASTNode):
    def __init__(self, alias, field):
        self.alias = alias.upper()
        self.field = field.upper()

class FunctionCall(ASTNode):
    def __init__(self, name, args):
        self.name = name.upper()
        self.args = args

class UnaryOp(ASTNode):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand

class BinaryOp(ASTNode):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

class ArrayAccess(ASTNode):
    def __init__(self, array, index):
        self.array = array
        self.index = index


class Parser:
    """Recursive descent parser for xBase expressions."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else Token(TK_EOF, None)

    def peek(self):
        return self.current()

    def advance(self):
        tok = self.current()
        self.pos += 1
        return tok

    def expect(self, ttype):
        tok = self.current()
        if tok.type != ttype:
            raise SyntaxError(f"Expected {ttype}, got {tok.type} ({tok.value!r}) at position {tok.pos}")
        return self.advance()

    def parse(self):
        node = self.parse_or()
        return node

    def parse_or(self):
        left = self.parse_and()
        while self.current().type == TK_OR:
            self.advance()
            right = self.parse_and()
            left = BinaryOp(".OR.", left, right)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.current().type == TK_AND:
            self.advance()
            right = self.parse_not()
            left = BinaryOp(".AND.", left, right)
        return left

    def parse_not(self):
        if self.current().type == TK_NOT:
            self.advance()
            operand = self.parse_not()
            return UnaryOp("NOT", operand)
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_contains()
        while self.current().type == TK_OPERATOR and self.current().value in ("=", "==", "<>", "!=", "#", "<", ">", "<=", ">="):
            op = self.advance().value
            right = self.parse_contains()
            left = BinaryOp(op, left, right)
        return left

    def parse_contains(self):
        left = self.parse_addition()
        while self.current().type == TK_OPERATOR and self.current().value == "$":
            self.advance()
            right = self.parse_addition()
            left = BinaryOp("$", left, right)
        return left

    def parse_addition(self):
        left = self.parse_multiplication()
        while self.current().type == TK_OPERATOR and self.current().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_multiplication()
            left = BinaryOp(op, left, right)
        return left

    def parse_multiplication(self):
        left = self.parse_power()
        while self.current().type == TK_OPERATOR and self.current().value in ("*", "/", "%"):
            op = self.advance().value
            right = self.parse_power()
            left = BinaryOp(op, left, right)
        return left

    def parse_power(self):
        left = self.parse_unary()
        while self.current().type == TK_OPERATOR and self.current().value in ("**", "^"):
            self.advance()
            right = self.parse_unary()
            left = BinaryOp("**", left, right)
        return left

    def parse_unary(self):
        if self.current().type == TK_OPERATOR and self.current().value == "-":
            self.advance()
            operand = self.parse_unary()
            return UnaryOp("-", operand)
        if self.current().type == TK_OPERATOR and self.current().value == "+":
            self.advance()
            return self.parse_unary()
        return self.parse_primary()

    def parse_primary(self):
        tok = self.current()

        if tok.type == TK_NUMBER:
            self.advance()
            node = NumberLiteral(tok.value)
            return self._parse_postfix(node)

        if tok.type == TK_STRING:
            self.advance()
            return StringLiteral(tok.value)

        if tok.type == TK_DATE:
            self.advance()
            return DateLiteral(tok.value)

        if tok.type == TK_LOGICAL:
            self.advance()
            return LogicalLiteral(tok.value)

        if tok.type == TK_LPAREN:
            self.advance()
            node = self.parse_or()
            self.expect(TK_RPAREN)
            return self._parse_postfix(node)

        if tok.type == TK_IDENT:
            name = tok.value
            self.advance()

            # ALIAS->FIELD
            if self.current().type == TK_ARROW:
                self.advance()
                field_tok = self.expect(TK_IDENT)
                return AliasField(name, field_tok.value)

            # Function call
            if self.current().type == TK_LPAREN:
                self.advance()
                args = []
                if self.current().type != TK_RPAREN:
                    args.append(self.parse_or())
                    while self.current().type == TK_COMMA:
                        self.advance()
                        args.append(self.parse_or())
                self.expect(TK_RPAREN)
                node = FunctionCall(name, args)
                return self._parse_postfix(node)

            node = Identifier(name)
            return self._parse_postfix(node)

        # If nothing matched, return a null identifier
        if tok.type == TK_EOF:
            return NumberLiteral(0)

        self.advance()
        return NumberLiteral(0)

    def _parse_postfix(self, node):
        while self.current().type == TK_LBRACKET:
            self.advance()
            index = self.parse_or()
            self.expect(TK_RBRACKET)
            node = ArrayAccess(node, index)
        return node


class ExpressionEvaluator:
    """Evaluates parsed AST nodes in the context of a dBase environment."""

    def __init__(self, env=None):
        self.env = env  # Reference to the Environment/WorkArea manager
        self.functions = {}  # Built-in function registry

    def register_functions(self, func_dict):
        """Register built-in functions."""
        self.functions.update(func_dict)

    def _expand_macros(self, text):
        """Expand &variable macro substitutions before parsing."""
        if "&" not in text or self.env is None:
            return text

        result = []
        i = 0
        in_string = False
        quote_char = None

        while i < len(text):
            ch = text[i]
            if ch in ('"', "'") and not in_string:
                in_string = True
                quote_char = ch
                result.append(ch)
                i += 1
                continue
            if in_string and ch == quote_char:
                in_string = False
                result.append(ch)
                i += 1
                continue
            if in_string:
                result.append(ch)
                i += 1
                continue

            if ch == "&" and i + 1 < len(text):
                next_ch = text[i + 1]
                if next_ch == "(":
                    depth = 1
                    j = i + 2
                    while j < len(text) and depth > 0:
                        if text[j] == "(":
                            depth += 1
                        elif text[j] == ")":
                            depth -= 1
                        j += 1
                    expr = text[i + 2:j - 1]
                    try:
                        val = self.evaluate(expr)
                        result.append(str(val) if val is not None else "")
                    except Exception:
                        result.append(text[i:j])
                    i = j
                    continue
                if next_ch.isalpha() or next_ch == "_":
                    j = i + 1
                    while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                        j += 1
                    var_name = text[i + 1:j].upper()
                    val = self.env.get_variable(var_name)
                    if val is not None:
                        result.append(str(val).strip() if isinstance(val, str) else str(val))
                    else:
                        result.append(text[i:j])
                    if j < len(text) and text[j] == ".":
                        j += 1
                    i = j
                    continue

            result.append(ch)
            i += 1

        return "".join(result)

    def evaluate(self, expr_str, record=None, recno=None):
        """Parse and evaluate an expression string."""
        if expr_str is None:
            return None
        expr_str = str(expr_str).strip()
        if not expr_str:
            return ""

        # Macro substitution (&variable)
        expr_str = self._expand_macros(expr_str)

        try:
            lexer = Lexer(expr_str)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()
            return self._eval_node(ast, record, recno)
        except Exception as e:
            raise ValueError(f"Expression error: {expr_str}: {e}")

    def eval_condition(self, expr_str, record=None, recno=None):
        """Evaluate an expression as a boolean condition."""
        result = self.evaluate(expr_str, record, recno)
        return self._to_bool(result)

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value.strip()) > 0
        return value is not None

    def _eval_node(self, node, record=None, recno=None):
        if isinstance(node, NumberLiteral):
            return node.value

        if isinstance(node, StringLiteral):
            return node.value

        if isinstance(node, DateLiteral):
            return node.value

        if isinstance(node, LogicalLiteral):
            return node.value

        if isinstance(node, Identifier):
            return self._resolve_identifier(node.name, record, recno)

        if isinstance(node, AliasField):
            return self._resolve_alias_field(node.alias, node.field, record, recno)

        if isinstance(node, FunctionCall):
            args = [self._eval_node(a, record, recno) for a in node.args]
            return self._call_function(node.name, args, record, recno)

        if isinstance(node, UnaryOp):
            val = self._eval_node(node.operand, record, recno)
            if node.op == "-":
                return -val if isinstance(val, (int, float)) else val
            if node.op == "NOT":
                return not self._to_bool(val)
            return val

        if isinstance(node, BinaryOp):
            return self._eval_binary(node, record, recno)

        if isinstance(node, ArrayAccess):
            arr = self._eval_node(node.array, record, recno)
            idx = self._eval_node(node.index, record, recno)
            if isinstance(arr, (list, tuple)):
                return arr[int(idx) - 1]
            if isinstance(arr, str):
                return arr[int(idx) - 1]
            return None

        return None

    def _eval_binary(self, node, record, recno):
        left = self._eval_node(node.left, record, recno)
        op = node.op

        # Short-circuit for logical operators
        if op == ".AND.":
            if not self._to_bool(left):
                return False
            right = self._eval_node(node.right, record, recno)
            return self._to_bool(right)
        if op == ".OR.":
            if self._to_bool(left):
                return True
            right = self._eval_node(node.right, record, recno)
            return self._to_bool(right)

        right = self._eval_node(node.right, record, recno)

        # Arithmetic
        if op == "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            if isinstance(left, date) and isinstance(right, (int, float)):
                from datetime import timedelta
                return left + timedelta(days=int(right))
            return (left or 0) + (right or 0)
        if op == "-":
            if isinstance(left, str) and isinstance(right, str):
                # String subtraction: trim trailing spaces from left, prepend to right
                return left.rstrip() + right + " " * (len(left) - len(left.rstrip()))
            if isinstance(left, date) and isinstance(right, date):
                return (left - right).days
            if isinstance(left, date) and isinstance(right, (int, float)):
                from datetime import timedelta
                return left - timedelta(days=int(right))
            return (left or 0) - (right or 0)
        if op == "*":
            return (left or 0) * (right or 0)
        if op == "/":
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return (left or 0) / (right or 0)
        if op == "%":
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return (left or 0) % (right or 0)
        if op == "**":
            return (left or 0) ** (right or 0)

        # String contains
        if op == "$":
            return str(left) in str(right)

        # Comparison
        exact = self.env.config.exact if self.env else False
        return self._compare(op, left, right, exact)

    def _compare(self, op, left, right, exact=False):
        # Normalize for comparison
        if isinstance(left, str) and isinstance(right, str):
            if not exact and op in ("=",):
                # Non-exact: right is trimmed, left compared for length of right
                right_trimmed = right.rstrip()
                left_trimmed = left[:len(right_trimmed)]
                if op == "=":
                    return left_trimmed == right_trimmed
            l, r = left, right
        else:
            l, r = left, right

        if op == "=" or op == "==":
            if op == "==" or exact:
                return l == r
            if isinstance(l, str) and isinstance(r, str):
                return l[:len(r)] == r if len(r) <= len(l) else l == r[:len(l)]
            return l == r
        if op in ("<>", "!=", "#"):
            return l != r
        if op == "<":
            return l < r
        if op == ">":
            return l > r
        if op == "<=":
            return l <= r
        if op == ">=":
            return l >= r
        return False

    def _resolve_identifier(self, name, record, recno):
        name = name.upper()

        # Check variables first
        if self.env:
            val = self.env.get_variable(name)
            if val is not None:
                return val

        # Check current record fields
        if record is not None:
            val = record.get(name)
            if val is not None:
                return val

        # Check environment work area
        if self.env:
            wa = self.env.current_workarea()
            if wa and wa.dbf:
                field = wa.dbf.field_by_name(name)
                if field:
                    rec = wa.current_record()
                    if rec:
                        return rec[name]

        return None

    def _resolve_alias_field(self, alias, field, record, recno):
        if self.env:
            wa = self.env.get_workarea_by_alias(alias)
            if wa and wa.dbf:
                rec = wa.current_record()
                if rec:
                    return rec[field]
        return None

    def _call_function(self, name, args, record, recno):
        name = name.upper()

        if name in self.functions:
            return self.functions[name](*args)

        # Special functions that need context
        if name == "RECNO":
            if self.env:
                wa = self.env.current_workarea()
                return wa.recno if wa else 0
            return (recno + 1) if recno is not None else 0
        if name == "RECCOUNT":
            if self.env:
                wa = self.env.current_workarea()
                return len(wa.dbf.records) if wa and wa.dbf else 0
            return 0
        if name == "EOF":
            if self.env:
                wa = self.env.current_workarea()
                return wa.eof if wa else True
            return False
        if name == "BOF":
            if self.env:
                wa = self.env.current_workarea()
                return wa.bof if wa else True
            return False
        if name == "DELETED":
            if self.env:
                wa = self.env.current_workarea()
                rec = wa.current_record() if wa else None
                return rec.deleted if rec else False
            if record:
                return record.deleted
            return False
        if name == "FOUND":
            if self.env:
                wa = self.env.current_workarea()
                return wa.found if wa else False
            return False
        if name == "FIELD" or name == "FIELDNAME":
            if args and self.env:
                wa = self.env.current_workarea()
                if wa and wa.dbf:
                    idx = int(args[0]) - 1
                    if 0 <= idx < len(wa.dbf.fields):
                        return wa.dbf.fields[idx].name
            return ""
        if name == "FCOUNT":
            if self.env:
                wa = self.env.current_workarea()
                return len(wa.dbf.fields) if wa and wa.dbf else 0
            return 0
        if name == "DBF":
            if self.env:
                wa = self.env.current_workarea()
                return wa.dbf.filename if wa and wa.dbf else ""
            return ""
        if name == "ALIAS":
            if self.env:
                wa = self.env.current_workarea()
                return wa.alias if wa else ""
            return ""
        if name == "SELECT":
            if args:
                if self.env:
                    wa = self.env.get_workarea_by_alias(str(args[0]))
                    return wa.area_number if wa else 0
                return 0
            else:
                if self.env:
                    return self.env.current_area
                return 1
        if name == "USED":
            if self.env:
                if args:
                    wa = self.env.get_workarea_by_alias(str(args[0]))
                    return wa is not None and wa.dbf is not None
                wa = self.env.current_workarea()
                return wa is not None and wa.dbf is not None
            return False
        if name == "TYPE":
            if args:
                try:
                    val = args[0]
                    if isinstance(val, str):
                        # Evaluate the expression passed as string
                        inner = self.evaluate(val, record, recno)
                        if isinstance(inner, bool):
                            return "L"
                        if isinstance(inner, int):
                            return "N"
                        if isinstance(inner, float):
                            return "N"
                        if isinstance(inner, str):
                            return "C"
                        if isinstance(inner, date):
                            return "D"
                        return "U"
                except Exception:
                    return "U"
            return "U"

        raise ValueError(f"Unknown function: {name}()")
