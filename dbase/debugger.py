"""dBase Revival by Jair Lima - PRG Debugger.

Interactive debugger for PRG programs with:
- Breakpoints (SET BREAKPOINT TO <line>)
- Step execution (SET STEP ON/OFF)
- Variable inspection
- Stack trace
- Continue/Step/Step Over/Quit

Debugger commands at the (debug) prompt:
  s, step      - Execute next line (step into)
  n, next      - Execute next line (step over)
  c, continue  - Continue until next breakpoint
  b <n>        - Set breakpoint at line n
  bl           - List breakpoints
  bd <n>       - Delete breakpoint at line n
  p <expr>     - Print/evaluate expression
  v, vars      - Show all variables
  w, where     - Show call stack
  l, list      - Show source around current line
  q, quit      - Abort execution
  h, help      - Show debugger help
"""


class Debugger:
    """Interactive debugger for PRG programs."""

    def __init__(self, env, evaluator, config):
        self.env = env
        self.eval = evaluator
        self.config = config
        self.enabled = False
        self.step_mode = False
        self.breakpoints = set()
        self.call_stack = []
        self._source_lines = []
        self._source_file = ""
        self._current_line = 0
        self._step_over_depth = -1
        self._quit_flag = False

    def attach(self, source_lines, filename="<interactive>"):
        """Attach debugger to a set of source lines."""
        self._source_lines = source_lines
        self._source_file = filename
        self._current_line = 0
        self._quit_flag = False

    def should_break(self, line_index, line_text):
        """Check if execution should pause at this line.
        Returns True if the debugger should prompt the user."""
        if not self.enabled:
            return False
        if self._quit_flag:
            return False

        self._current_line = line_index

        # Step mode: always break
        if self.step_mode:
            if self._step_over_depth >= 0:
                if len(self.call_stack) > self._step_over_depth:
                    return False
                self._step_over_depth = -1
            return True

        # Breakpoint hit
        if line_index + 1 in self.breakpoints:
            return True

        return False

    def enter_call(self, proc_name):
        """Track entering a procedure/function call."""
        self.call_stack.append({
            "name": proc_name,
            "file": self._source_file,
            "line": self._current_line,
        })

    def exit_call(self):
        """Track leaving a procedure/function call."""
        if self.call_stack:
            self.call_stack.pop()

    def prompt(self, line_index, line_text):
        """Show the debugger prompt and handle user commands.

        Returns:
            'continue' - resume execution
            'step' - execute one line
            'quit' - abort execution
        """
        line_num = line_index + 1
        print(f"\n[{self._source_file}:{line_num}] {line_text}")

        while True:
            try:
                cmd = input("(debug) ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return "continue"

            if not cmd:
                cmd = "s"  # Default: step

            parts = cmd.split(None, 1)
            command = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if command in ("s", "step"):
                self.step_mode = True
                self._step_over_depth = -1
                return "step"

            elif command in ("n", "next"):
                self.step_mode = True
                self._step_over_depth = len(self.call_stack)
                return "step"

            elif command in ("c", "continue", "cont"):
                self.step_mode = False
                self._step_over_depth = -1
                return "continue"

            elif command in ("b", "break", "breakpoint"):
                if arg:
                    try:
                        bp_line = int(arg)
                        self.breakpoints.add(bp_line)
                        print(f"Breakpoint set at line {bp_line}")
                    except ValueError:
                        print("Usage: b <line_number>")
                else:
                    self.breakpoints.add(line_num)
                    print(f"Breakpoint set at line {line_num}")

            elif command in ("bl", "breakpoints"):
                if self.breakpoints:
                    print("Breakpoints:")
                    for bp in sorted(self.breakpoints):
                        src = ""
                        if bp - 1 < len(self._source_lines):
                            src = self._source_lines[bp - 1]
                        print(f"  Line {bp}: {src}")
                else:
                    print("No breakpoints set.")

            elif command in ("bd", "delete"):
                if arg:
                    try:
                        bp_line = int(arg)
                        self.breakpoints.discard(bp_line)
                        print(f"Breakpoint at line {bp_line} removed")
                    except ValueError:
                        print("Usage: bd <line_number>")
                else:
                    print("Usage: bd <line_number>")

            elif command in ("p", "print", "?"):
                if arg:
                    try:
                        val = self.eval.evaluate(arg)
                        print(f"  = {self._format_val(val)}")
                    except Exception as e:
                        print(f"  Error: {e}")
                else:
                    print("Usage: p <expression>")

            elif command in ("v", "vars", "variables"):
                self._show_variables()

            elif command in ("w", "where", "stack", "bt"):
                self._show_stack()

            elif command in ("l", "list"):
                self._show_source(line_index)

            elif command in ("q", "quit", "abort"):
                self._quit_flag = True
                return "quit"

            elif command in ("h", "help"):
                self._show_help()

            else:
                print(f"Unknown debugger command: {command}. Type 'h' for help.")

    def _format_val(self, val):
        if val is None:
            return ".NULL."
        if isinstance(val, bool):
            return ".T." if val else ".F."
        if isinstance(val, str):
            return f'"{val}"'
        return str(val)

    def _show_variables(self):
        print("Variables:")
        if not self.env.variables:
            print("  (none)")
            return
        for name, val in sorted(self.env.variables.items()):
            print(f"  {name} = {self._format_val(val)}")

    def _show_stack(self):
        print("Call stack:")
        if not self.call_stack:
            print(f"  > {self._source_file}:{self._current_line + 1} (main)")
        else:
            for i, frame in enumerate(self.call_stack):
                prefix = "  > " if i == len(self.call_stack) - 1 else "    "
                print(f"{prefix}{frame['file']}:{frame['line'] + 1} in {frame['name']}")
            print(f"  > {self._source_file}:{self._current_line + 1} (current)")

    def _show_source(self, center_line):
        """Show source code around the current line."""
        start = max(0, center_line - 5)
        end = min(len(self._source_lines), center_line + 6)

        for i in range(start, end):
            marker = ">>>" if i == center_line else "   "
            bp = " *" if (i + 1) in self.breakpoints else "  "
            print(f"{bp}{marker} {i + 1:4d}: {self._source_lines[i]}")

    def _show_help(self):
        print("Debugger commands:")
        print("  s, step       Step into (execute one line)")
        print("  n, next       Step over (skip into calls)")
        print("  c, continue   Continue to next breakpoint")
        print("  b <line>      Set breakpoint at line")
        print("  bl            List breakpoints")
        print("  bd <line>     Delete breakpoint")
        print("  p <expr>      Print/evaluate expression")
        print("  v, vars       Show all variables")
        print("  w, where      Show call stack")
        print("  l, list       Show source around current line")
        print("  q, quit       Abort execution")
        print("  h, help       Show this help")
