"""dBase Revival by Jair Lima - PRG program interpreter.

Executes .PRG files with full support for:
- IF/ELSEIF/ELSE/ENDIF
- DO WHILE/ENDDO
- FOR/NEXT (Clipper extension)
- DO CASE/CASE/OTHERWISE/ENDCASE
- SCAN/ENDSCAN
- PROCEDURE/FUNCTION/RETURN
- DO <program> [WITH parameters]
- LOCAL, PRIVATE, PUBLIC variables
- Error handling
"""

import os
import re

from .debugger import Debugger


class ProgramInterpreter:
    """Interprets and executes dBASE .PRG program files."""

    def __init__(self, env, evaluator, config, cmd_interpreter):
        self.env = env
        self.eval = evaluator
        self.config = config
        self.cmd = cmd_interpreter
        self.output = []
        self.procedures = {}
        self._return_value = None
        self._loop_exit = False
        self._exit_flag = False
        self.debugger = getattr(env, '_debugger', None)
        if self.debugger is None:
            self.debugger = Debugger(env, evaluator, config)
            env._debugger = self.debugger

    def run_file(self, filename):
        """Load and execute a PRG file."""
        self.output = []
        with open(filename, "r", encoding="latin-1") as f:
            source = f.read()

        lines = self._preprocess(source)
        self.debugger.attach(lines, os.path.basename(filename))
        self._extract_procedures(lines)
        self._execute_block(lines, 0, len(lines))
        return self.output

    def run_lines(self, lines):
        """Execute a list of source lines."""
        self.output = []
        processed = self._preprocess("\n".join(lines))
        self.debugger.attach(processed, "<interactive>")
        self._execute_block(processed, 0, len(processed))
        return self.output

    def _preprocess(self, source):
        """Preprocess source: remove comments, handle continuation lines."""
        raw_lines = source.split("\n")
        result = []
        continued = ""

        for line in raw_lines:
            stripped = line.rstrip()

            # Skip pure comment lines
            if stripped.lstrip().startswith("*") or stripped.lstrip().upper().startswith("NOTE "):
                continue

            # Remove inline comments
            comment_pos = stripped.find("&&")
            if comment_pos >= 0:
                in_string = False
                quote_char = None
                for i, ch in enumerate(stripped):
                    if in_string:
                        if ch == quote_char:
                            in_string = False
                    elif ch in ('"', "'"):
                        in_string = True
                        quote_char = ch
                    elif i == comment_pos:
                        stripped = stripped[:i].rstrip()
                        break

            # Handle continuation (line ending with ;)
            if stripped.endswith(";"):
                continued += stripped[:-1].strip() + " "
                continue
            elif continued:
                stripped = continued + stripped.strip()
                continued = ""

            if stripped.strip():
                result.append(stripped.strip())

        return result

    def _extract_procedures(self, lines):
        """Find and extract PROCEDURE/FUNCTION definitions."""
        i = 0
        while i < len(lines):
            upper = lines[i].upper().strip()
            m = re.match(r'(PROCEDURE|FUNCTION)\s+(\w+)', upper)
            if m:
                proc_type = m.group(1)
                proc_name = m.group(2).upper()
                start = i + 1
                depth = 1
                j = start
                while j < len(lines):
                    ju = lines[j].upper().strip()
                    if re.match(r'(PROCEDURE|FUNCTION)\s+', ju):
                        break
                    if ju == "RETURN" or ju.startswith("RETURN "):
                        break
                    j += 1
                self.procedures[proc_name] = lines[start:j]
                self.env.procedures[proc_name] = lines[start:j]
            i += 1

    def _execute_block(self, lines, start, end):
        """Execute lines from start to end."""
        i = start
        while i < end and not self._exit_flag:
            if self._loop_exit:
                return
            line = lines[i]
            upper = line.upper().strip()

            # Skip procedure/function definitions
            if re.match(r'(PROCEDURE|FUNCTION)\s+', upper):
                i = self._skip_to_end_of_proc(lines, i)
                continue

            # IF block
            if upper.startswith("IF "):
                i = self._execute_if(lines, i, end)
                continue

            # DO WHILE block
            if upper.startswith("DO WHILE "):
                i = self._execute_do_while(lines, i, end)
                continue

            # FOR block
            if re.match(r'FOR\s+\w+\s*=', upper):
                i = self._execute_for(lines, i, end)
                continue

            # DO CASE block
            if upper == "DO CASE":
                i = self._execute_do_case(lines, i, end)
                continue

            # SCAN block
            if upper == "SCAN" or upper.startswith("SCAN "):
                i = self._execute_scan(lines, i, end)
                continue

            # EXIT
            if upper == "EXIT":
                self._loop_exit = True
                return

            # LOOP
            if upper == "LOOP":
                return  # Signal to continue loop

            # RETURN
            if upper == "RETURN" or upper.startswith("RETURN "):
                if upper.startswith("RETURN "):
                    expr = line[7:].strip()
                    self._return_value = self.eval.evaluate(expr)
                self._exit_flag = True
                return

            # Debugger check
            if self.debugger.should_break(i, line):
                action = self.debugger.prompt(i, line)
                if action == "quit":
                    self._exit_flag = True
                    return

            # Regular command
            self._execute_command(line)
            i += 1

    def _execute_command(self, line):
        """Execute a single command through the command interpreter."""
        try:
            result = self.cmd.execute(line)
            self.output.extend(result)
        except SystemExit:
            raise
        except Exception as e:
            self.output.append(f"Error: {e}")

    def _find_matching_end(self, lines, start, start_kw, end_kw):
        """Find matching END keyword accounting for nesting."""
        depth = 1
        i = start + 1
        while i < len(lines):
            upper = lines[i].upper().strip()
            if upper.startswith(start_kw):
                depth += 1
            elif upper.startswith(end_kw) or upper == end_kw:
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return len(lines)

    def _execute_if(self, lines, start, end):
        """Execute IF/ELSEIF/ELSE/ENDIF block."""
        line = lines[start]
        condition = line[line.upper().find("IF") + 2:].strip()

        # Find the ENDIF and all ELSEIF/ELSE positions
        endif_pos = self._find_matching_end(lines, start, "IF ", "ENDIF")
        branches = []
        current_start = start + 1
        i = start + 1
        depth = 0

        while i <= endif_pos:
            upper = lines[i].upper().strip()
            if upper.startswith("IF ") and i != start:
                depth += 1
            elif upper.startswith("ENDIF"):
                if depth > 0:
                    depth -= 1
                else:
                    branches.append(("END", current_start, i))
                    break
            elif depth == 0:
                if upper.startswith("ELSEIF "):
                    branches.append(("COND", current_start, i))
                    current_start = i
                elif upper == "ELSE":
                    branches.append(("COND", current_start, i))
                    current_start = i + 1
                    # Find ENDIF
                    j = i + 1
                    d2 = 0
                    while j <= endif_pos:
                        u2 = lines[j].upper().strip()
                        if u2.startswith("IF "):
                            d2 += 1
                        elif u2.startswith("ENDIF"):
                            if d2 > 0:
                                d2 -= 1
                            else:
                                branches.append(("ELSE", current_start, j))
                                break
                        j += 1
                    break
            i += 1

        if not branches:
            branches.append(("COND", start + 1, endif_pos))

        # Evaluate first condition
        if self.eval.eval_condition(condition):
            self._execute_block(lines, start + 1,
                              branches[0][2] if branches else endif_pos)
        else:
            executed = False
            for btype, bstart, bend in branches:
                if btype == "COND" and bstart > start + 1:
                    elseif_line = lines[bstart]
                    elseif_cond = elseif_line[elseif_line.upper().find("ELSEIF") + 6:].strip()
                    if self.eval.eval_condition(elseif_cond):
                        next_branch_end = bend
                        for nb in branches:
                            if nb[1] > bstart:
                                next_branch_end = nb[1]
                                break
                        self._execute_block(lines, bstart + 1, next_branch_end)
                        executed = True
                        break
                elif btype == "ELSE":
                    if not executed:
                        self._execute_block(lines, bstart, bend)
                    break

        return endif_pos + 1

    def _execute_do_while(self, lines, start, end):
        """Execute DO WHILE/ENDDO block."""
        condition = lines[start][lines[start].upper().find("DO WHILE") + 8:].strip()
        enddo_pos = self._find_matching_end(lines, start, "DO WHILE ", "ENDDO")

        while not self._exit_flag:
            if not self.eval.eval_condition(condition):
                break
            self._loop_exit = False
            self._execute_block(lines, start + 1, enddo_pos)
            if self._loop_exit:
                self._loop_exit = False
                break

        return enddo_pos + 1

    def _execute_for(self, lines, start, end):
        """Execute FOR/NEXT block (Clipper extension)."""
        line = lines[start]
        m = re.match(r'FOR\s+(\w+)\s*=\s*(.+?)\s+TO\s+(.+?)(?:\s+STEP\s+(.+))?$', line, re.IGNORECASE)
        if not m:
            self._execute_command(line)
            return start + 1

        var_name = m.group(1).upper()
        start_val = int(self.eval.evaluate(m.group(2).strip()))
        end_val = int(self.eval.evaluate(m.group(3).strip()))
        step = int(self.eval.evaluate(m.group(4).strip())) if m.group(4) else 1

        next_pos = self._find_matching_end(lines, start, "FOR ", "NEXT")

        self.env.set_variable(var_name, start_val)
        current = start_val

        while not self._exit_flag:
            if step > 0 and current > end_val:
                break
            if step < 0 and current < end_val:
                break

            self.env.set_variable(var_name, current)
            self._loop_exit = False
            self._execute_block(lines, start + 1, next_pos)
            if self._loop_exit:
                self._loop_exit = False
                break

            current += step

        return next_pos + 1

    def _execute_do_case(self, lines, start, end):
        """Execute DO CASE/CASE/OTHERWISE/ENDCASE block."""
        endcase_pos = self._find_matching_end(lines, start, "DO CASE", "ENDCASE")

        i = start + 1
        executed = False
        while i < endcase_pos:
            upper = lines[i].upper().strip()
            if upper.startswith("CASE ") and not executed:
                condition = lines[i][lines[i].upper().find("CASE") + 4:].strip()
                case_end = self._find_next_case(lines, i + 1, endcase_pos)
                if self.eval.eval_condition(condition):
                    self._execute_block(lines, i + 1, case_end)
                    executed = True
                i = case_end
            elif upper == "OTHERWISE" and not executed:
                self._execute_block(lines, i + 1, endcase_pos)
                executed = True
                i = endcase_pos
            else:
                i += 1

        return endcase_pos + 1

    def _find_next_case(self, lines, start, endcase):
        """Find next CASE, OTHERWISE, or ENDCASE."""
        i = start
        while i < endcase:
            upper = lines[i].upper().strip()
            if upper.startswith("CASE ") or upper == "OTHERWISE" or upper.startswith("ENDCASE"):
                return i
            i += 1
        return endcase

    def _execute_scan(self, lines, start, end):
        """Execute SCAN/ENDSCAN block."""
        endscan_pos = self._find_matching_end(lines, start, "SCAN", "ENDSCAN")
        rest = lines[start][4:].strip() if len(lines[start]) > 4 else ""

        for_expr = ""
        m = re.match(r'FOR\s+(.+)', rest, re.IGNORECASE)
        if m:
            for_expr = m.group(1).strip()

        wa = self.env.current_workarea()
        if not wa or not wa.dbf:
            return endscan_pos + 1

        wa.go_top()
        while not wa.eof and not self._exit_flag:
            rec = wa.current_record()
            if rec is None:
                break
            if for_expr:
                if not self.eval.eval_condition(for_expr, rec, wa.recno - 1):
                    wa.skip()
                    continue

            self._loop_exit = False
            self._execute_block(lines, start + 1, endscan_pos)
            if self._loop_exit:
                self._loop_exit = False
                break
            wa.skip()

        return endscan_pos + 1

    def _skip_to_end_of_proc(self, lines, start):
        """Skip past a procedure/function definition."""
        i = start + 1
        while i < len(lines):
            upper = lines[i].upper().strip()
            if re.match(r'(PROCEDURE|FUNCTION)\s+', upper):
                return i
            if upper == "RETURN" or upper.startswith("RETURN "):
                return i + 1
            i += 1
        return len(lines)

    def call_procedure(self, name, args=None):
        """Call a procedure/function by name."""
        name = name.upper()
        proc_lines = self.procedures.get(name) or self.env.procedures.get(name)
        if not proc_lines:
            raise ValueError(f"Procedure not found: {name}")

        self.env.push_private_scope()
        try:
            if args:
                params_line = proc_lines[0] if proc_lines else ""
                m = re.match(r'PARAMETERS?\s+(.+)', params_line.upper())
                if m:
                    param_names = [p.strip() for p in m.group(1).split(",")]
                    for i, pname in enumerate(param_names):
                        if i < len(args):
                            self.env.set_variable(pname, args[i])
                    proc_lines = proc_lines[1:]

            self._exit_flag = False
            self._execute_block(proc_lines, 0, len(proc_lines))
            self._exit_flag = False
        finally:
            self.env.pop_private_scope()

        return self._return_value
