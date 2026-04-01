"""dBase Revival by Jair Lima

Clone funcional do dBASE classico para terminal com suporte a
indices NDX, NTX, CDX e MDX.

Uso: python -m dbase.main [arquivo.prg]
"""

import sys
import os
try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline
    except ImportError:
        readline = None

from .config import Config, config
from .workarea import Environment
from .expression import ExpressionEvaluator
from .functions import register_all
from .commands import CommandInterpreter


BANNER = r"""
  ____  ____                    ____            _            _
 |  _ \| __ )  __ _ ___  ___  |  _ \ _____   _(_)_   ____ _| |
 | | | |  _ \ / _` / __|/ _ \ | |_) / _ \ \ / / \ \ / / _` | |
 | |_| | |_) | (_| \__ \  __/ |  _ <  __/\ V /| |\ V / (_| | |
 |____/|____/ \__,_|___/\___| |_| \_\___| \_/ |_| \_/ \__,_|_|

                        by Jair Lima
                        Version 1.0.0

  Clone funcional do dBASE classico para terminal
  Suporte a indices: NDX, NTX, CDX, MDX
  Digite HELP para ajuda ou QUIT para sair.
"""

HISTORY_FILE = os.path.expanduser("~/.dbase_revival_history")


class DBaseREPL:
    """Main REPL (Read-Eval-Print Loop) with the classic dot prompt."""

    def __init__(self):
        self.config = config
        self.env = Environment(config)
        self.evaluator = ExpressionEvaluator(self.env)
        register_all(self.evaluator, config)
        self.cmd = CommandInterpreter(self.env, self.evaluator, config)
        self._setup_readline()
        self._multi_line_buffer = []
        self._in_block = False

    def _setup_readline(self):
        """Setup readline for history and tab completion."""
        if readline is None:
            return
        try:
            readline.set_history_length(1000)
            if os.path.exists(HISTORY_FILE):
                readline.read_history_file(HISTORY_FILE)
            readline.set_completer(self._completer)
            readline.parse_and_bind("tab: complete")
        except Exception:
            pass

    def _save_history(self):
        if readline is None:
            return
        try:
            readline.write_history_file(HISTORY_FILE)
        except Exception:
            pass

    def _completer(self, text, state):
        """Tab completion for commands, fields and functions."""
        text_upper = text.upper()
        completions = []

        # Commands
        commands = [
            "USE", "APPEND", "APPEND BLANK", "REPLACE", "DELETE", "RECALL",
            "PACK", "ZAP", "CREATE", "COPY TO", "COPY STRUCTURE",
            "GO", "GO TOP", "GO BOTTOM", "SKIP", "LOCATE", "CONTINUE",
            "SEEK", "FIND", "LIST", "DISPLAY", "DISPLAY STRUCTURE",
            "DISPLAY STATUS", "DISPLAY MEMORY", "BROWSE", "EDIT",
            "INDEX ON", "SET INDEX TO", "SET ORDER TO", "REINDEX",
            "SELECT", "COUNT", "SUM", "AVERAGE", "SORT",
            "STORE", "PUBLIC", "PRIVATE", "RELEASE", "DECLARE",
            "SET", "CLOSE", "DIR", "RENAME", "ERASE", "TYPE",
            "CLEAR", "DO", "RUN", "WAIT", "ACCEPT", "INPUT",
            "QUIT", "HELP", "IF", "ELSE", "ENDIF", "DO WHILE",
            "ENDDO", "FOR", "NEXT", "DO CASE", "CASE", "ENDCASE",
            "SCAN", "ENDSCAN", "RETURN", "PROCEDURE", "FUNCTION",
        ]

        for cmd in commands:
            if cmd.startswith(text_upper):
                completions.append(cmd + " ")

        # Field names from current table
        wa = self.env.current_workarea()
        if wa and wa.dbf:
            for f in wa.dbf.fields:
                if f.name.startswith(text_upper):
                    completions.append(f.name)

        # Variables
        for name in self.env.variables:
            if name.startswith(text_upper):
                completions.append(name)

        # Functions
        functions = [
            "ALLTRIM(", "LTRIM(", "RTRIM(", "UPPER(", "LOWER(",
            "SUBSTR(", "LEFT(", "RIGHT(", "AT(", "LEN(", "SPACE(",
            "STR(", "VAL(", "DTOC(", "DTOS(", "CTOD(", "STOD(",
            "DATE()", "TIME()", "YEAR(", "MONTH(", "DAY(",
            "RECNO()", "RECCOUNT()", "EOF()", "BOF()", "FOUND()",
            "DELETED()", "FIELD(", "FCOUNT()", "DBF()", "ALIAS()",
            "SELECT()", "USED()", "IIF(", "EMPTY(", "TYPE(",
            "FILE(", "BETWEEN(", "INLIST(", "ABS(", "INT(",
            "ROUND(", "SQRT(", "MOD(", "MIN(", "MAX(",
            "REPLICATE(", "STUFF(", "STRTRAN(", "PADL(", "PADR(",
            "CHR(", "ASC(", "TRANSFORM(", "CDOW(", "CMONTH(",
        ]
        for fn in functions:
            if fn.startswith(text_upper):
                completions.append(fn)

        if state < len(completions):
            return completions[state]
        return None

    def _is_block_start(self, line):
        """Check if line starts a multi-line block."""
        upper = line.upper().strip()
        return (upper.startswith("IF ") or
                upper.startswith("DO WHILE ") or
                upper.startswith("DO CASE") or
                upper.startswith("SCAN") or
                upper.startswith("FOR ") and " TO " in upper)

    def _is_block_end(self, line):
        """Check if line ends a multi-line block."""
        upper = line.upper().strip()
        return upper in ("ENDIF", "ENDDO", "ENDCASE", "ENDSCAN", "NEXT")

    def run(self, prg_file=None):
        """Start the REPL or execute a PRG file."""
        if prg_file:
            self._run_prg(prg_file)
            return

        print(BANNER)

        while True:
            try:
                if self._in_block:
                    prompt = "> "
                else:
                    prompt = ". "

                line = input(prompt)
                if line is None:
                    continue

                line = line.strip()
                if not line:
                    continue

                # Handle multi-line blocks in interactive mode
                if self._is_block_start(line) and not self._in_block:
                    self._in_block = True
                    self._multi_line_buffer = [line]
                    continue

                if self._in_block:
                    self._multi_line_buffer.append(line)
                    if self._is_block_end(line):
                        self._in_block = False
                        self._execute_block(self._multi_line_buffer)
                        self._multi_line_buffer = []
                    continue

                # Single line execution
                self._execute_line(line)

            except KeyboardInterrupt:
                print("\n*** Interrupted")
                self._in_block = False
                self._multi_line_buffer = []
            except EOFError:
                print("\n*** EOF")
                break
            except SystemExit:
                break

        self._shutdown()

    def _execute_line(self, line):
        """Execute a single command line."""
        try:
            output = self.cmd.execute(line)
            for text in output:
                print(text)
        except SystemExit:
            raise
        except Exception as e:
            print(f"*** Error: {e}")

    def _execute_block(self, lines):
        """Execute a multi-line block."""
        from .interpreter import ProgramInterpreter
        interp = ProgramInterpreter(self.env, self.evaluator, self.config, self.cmd)
        try:
            output = interp.run_lines(lines)
            for text in output:
                print(text)
        except SystemExit:
            raise
        except Exception as e:
            print(f"*** Error: {e}")

    def _run_prg(self, filename):
        """Execute a PRG file."""
        if not os.path.exists(filename):
            filename_prg = filename + ".prg" if "." not in filename else filename
            if not os.path.exists(filename_prg):
                print(f"File not found: {filename}")
                return
            filename = filename_prg

        from .interpreter import ProgramInterpreter
        interp = ProgramInterpreter(self.env, self.evaluator, self.config, self.cmd)
        try:
            output = interp.run_file(filename)
            for text in output:
                print(text)
        except SystemExit:
            pass
        except Exception as e:
            print(f"*** Error in {filename}: {e}")

        self._shutdown()

    def _shutdown(self):
        """Clean up before exit."""
        self.env.close_all()
        self._save_history()


def main():
    """Entry point."""
    # Handle --compile mode
    if len(sys.argv) > 1 and sys.argv[1] == "--compile":
        from .compiler import PRGCompiler
        if len(sys.argv) < 3:
            print("Usage: dbase --compile <program.prg> [-o output.exe] [--icon file.ico] [--data file1 file2 ...]")
            sys.exit(1)

        prg_file = sys.argv[2]
        output = None
        icon = None
        extra_data = []

        i = 3
        while i < len(sys.argv):
            if sys.argv[i] in ("-o", "--output"):
                i += 1
                output = sys.argv[i] if i < len(sys.argv) else None
            elif sys.argv[i] == "--icon":
                i += 1
                icon = sys.argv[i] if i < len(sys.argv) else None
            elif sys.argv[i] == "--data":
                i += 1
                while i < len(sys.argv) and not sys.argv[i].startswith("-"):
                    extra_data.append(sys.argv[i])
                    i += 1
                continue
            i += 1

        compiler = PRGCompiler()
        try:
            result = compiler.compile(prg_file, output=output, icon=icon,
                                      extra_data=extra_data if extra_data else None)
            print(f"\nCompiled successfully: {result}")
        except Exception as e:
            print(f"\nCompilation failed: {e}", file=sys.stderr)
            sys.exit(1)
        return

    prg_file = None
    if len(sys.argv) > 1:
        prg_file = sys.argv[1]

    repl = DBaseREPL()
    repl.run(prg_file)


if __name__ == "__main__":
    main()
