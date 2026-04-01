"""dBase Revival by Jair Lima - PRG Compiler.

Compiles .PRG programs into standalone executables:

1. Resolves all DO <program> dependencies recursively
2. Generates a self-contained Python launcher with embedded PRG source
3. Uses PyInstaller to create a standalone .exe

Usage:
    from dbase.compiler import PRGCompiler
    compiler = PRGCompiler()
    compiler.compile("programa.prg", output="programa.exe")

Or from command line:
    python -m dbase.compiler programa.prg [-o output.exe] [--icon icon.ico] [--console]
"""

import os
import sys
import re
import shutil
import tempfile
import subprocess


class PRGCompiler:
    """Compiles PRG programs into standalone executables."""

    def __init__(self, verbose=True):
        self.verbose = verbose
        self._collected_prgs = {}
        self._collected_frms = {}
        self._collected_lbls = {}
        self._data_files = []

    def log(self, msg):
        if self.verbose:
            print(f"  [compile] {msg}")

    def compile(self, prg_file, output=None, icon=None, console=True, onefile=True,
                extra_data=None):
        """Compile a PRG file into a standalone executable.

        Args:
            prg_file: path to the main .PRG file
            output: output executable name (default: same as PRG without extension)
            icon: optional .ico file for the executable
            console: if True, create console app; if False, windowed
            onefile: if True, single .exe; if False, directory
            extra_data: list of extra files to bundle (dbf, frm, lbl, etc.)
        """
        prg_file = os.path.abspath(prg_file)
        if not os.path.exists(prg_file):
            raise FileNotFoundError(f"PRG file not found: {prg_file}")

        prg_dir = os.path.dirname(prg_file)
        prg_name = os.path.splitext(os.path.basename(prg_file))[0]

        if output is None:
            output = prg_name + ".exe"
        output = os.path.abspath(output)

        self.log(f"Compiling: {prg_file}")
        self.log(f"Output: {output}")

        # Step 1: Resolve dependencies
        self.log("Resolving dependencies...")
        self._collected_prgs = {}
        self._collected_frms = {}
        self._collected_lbls = {}
        self._data_files = list(extra_data or [])
        self._resolve_dependencies(prg_file, prg_dir)

        self.log(f"  PRG files: {len(self._collected_prgs)}")
        if self._collected_frms:
            self.log(f"  FRM files: {len(self._collected_frms)}")
        if self._collected_lbls:
            self.log(f"  LBL files: {len(self._collected_lbls)}")
        if self._data_files:
            self.log(f"  Data files: {len(self._data_files)}")

        # Step 2: Generate launcher
        self.log("Generating launcher...")
        build_dir = tempfile.mkdtemp(prefix="dbase_compile_")
        try:
            launcher_path = os.path.join(build_dir, f"{prg_name}_launcher.py")
            self._generate_launcher(launcher_path, prg_name, prg_file)

            # Step 3: Copy data files to build dir
            data_args = []
            for name, content in self._collected_frms.items():
                fpath = os.path.join(build_dir, name)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                data_args.append((fpath, "."))

            for name, content in self._collected_lbls.items():
                fpath = os.path.join(build_dir, name)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                data_args.append((fpath, "."))

            for dfile in self._data_files:
                if os.path.exists(dfile):
                    fname = os.path.basename(dfile)
                    dest = os.path.join(build_dir, fname)
                    shutil.copy2(dfile, dest)
                    data_args.append((dest, "."))

            # Step 4: Find the dbase package path
            dbase_pkg = os.path.dirname(os.path.abspath(__file__))

            # Step 5: Run PyInstaller
            self.log("Running PyInstaller...")
            self._run_pyinstaller(
                launcher_path, output, dbase_pkg,
                data_args, icon, console, onefile, build_dir
            )

            if os.path.exists(output):
                size_mb = os.path.getsize(output) / (1024 * 1024)
                self.log(f"Success! {output} ({size_mb:.1f} MB)")
                return output
            else:
                # Check in dist folder
                dist_path = os.path.join(build_dir, "dist", os.path.basename(output))
                if not dist_path.endswith(".exe"):
                    dist_path += ".exe"
                if os.path.exists(dist_path):
                    shutil.move(dist_path, output)
                    size_mb = os.path.getsize(output) / (1024 * 1024)
                    self.log(f"Success! {output} ({size_mb:.1f} MB)")
                    return output

                raise RuntimeError("PyInstaller finished but output file not found")

        finally:
            # Cleanup build dir
            try:
                shutil.rmtree(build_dir, ignore_errors=True)
            except Exception:
                pass

    def _resolve_dependencies(self, prg_file, search_dir):
        """Recursively find all PRG files referenced by DO commands."""
        basename = os.path.basename(prg_file).upper()
        if basename in self._collected_prgs:
            return

        with open(prg_file, "r", encoding="latin-1") as f:
            source = f.read()

        self._collected_prgs[basename] = source

        # Find DO <program> references
        for m in re.finditer(r'\bDO\s+(\w+)', source, re.IGNORECASE):
            ref_name = m.group(1)
            if ref_name.upper() in ("WHILE", "CASE"):
                continue
            ref_file = self._find_file(ref_name, ".prg", search_dir)
            if ref_file:
                self._resolve_dependencies(ref_file, search_dir)

        # Find REPORT FORM references
        for m in re.finditer(r'\bREPORT\s+FORM\s+(\w+)', source, re.IGNORECASE):
            ref_name = m.group(1)
            ref_file = self._find_file(ref_name, ".frm", search_dir)
            if ref_file:
                with open(ref_file, "r", encoding="utf-8") as f:
                    self._collected_frms[os.path.basename(ref_file)] = f.read()

        # Find LABEL FORM references
        for m in re.finditer(r'\bLABEL\s+FORM\s+(\w+)', source, re.IGNORECASE):
            ref_name = m.group(1)
            ref_file = self._find_file(ref_name, ".lbl", search_dir)
            if ref_file:
                with open(ref_file, "r", encoding="utf-8") as f:
                    self._collected_lbls[os.path.basename(ref_file)] = f.read()

        # Find USE <table> references (bundle .dbf files)
        for m in re.finditer(r'\bUSE\s+(\w+)', source, re.IGNORECASE):
            ref_name = m.group(1)
            ref_file = self._find_file(ref_name, ".dbf", search_dir)
            if ref_file and ref_file not in self._data_files:
                self._data_files.append(ref_file)

    def _find_file(self, name, ext, search_dir):
        """Find a file by name with given extension in search directory."""
        if "." not in name:
            name = name + ext
        fpath = os.path.join(search_dir, name)
        if os.path.exists(fpath):
            return fpath
        # Case-insensitive search
        for f in os.listdir(search_dir):
            if f.upper() == name.upper():
                return os.path.join(search_dir, f)
        return None

    def _generate_launcher(self, launcher_path, prg_name, main_prg_file):
        """Generate the Python launcher script with embedded PRG sources."""
        # Build embedded sources dict
        sources_dict = {}
        for name, src in self._collected_prgs.items():
            sources_dict[name] = src

        # Escape for embedding in Python source
        import json
        sources_json = json.dumps(sources_dict, ensure_ascii=False)

        launcher_code = f'''#!/usr/bin/env python3
"""dBase Revival - Compiled program: {prg_name}
Generated by dBase Revival Compiler by Jair Lima
"""
import sys
import os
import json
import shutil
import tempfile

# Ensure dbase package is importable (frozen or not)
if getattr(sys, "frozen", False):
    _base = sys._MEIPASS
else:
    _base = os.path.dirname(os.path.abspath(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)

# Import dBase runtime BEFORE changing directories
from dbase.config import Config, config
from dbase.workarea import Environment
from dbase.expression import ExpressionEvaluator
from dbase.functions import register_all
from dbase.commands import CommandInterpreter
from dbase.interpreter import ProgramInterpreter

# Embedded PRG sources
_EMBEDDED_SOURCES = json.loads({sources_json!r})

def main():
    work_dir = tempfile.mkdtemp(prefix="dbase_run_")
    original_dir = os.getcwd()
    try:
        # Write embedded PRG files
        for name, source in _EMBEDDED_SOURCES.items():
            fpath = os.path.join(work_dir, name.lower())
            with open(fpath, "w", encoding="latin-1") as f:
                f.write(source)

        # Copy bundled data files
        for fname in os.listdir(_base):
            lower = fname.lower()
            if lower.endswith((".dbf", ".frm", ".lbl", ".ndx", ".ntx", ".cdx", ".mdx")):
                src = os.path.join(_base, fname)
                dst = os.path.join(work_dir, fname)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)

        # Also copy data files from the directory where the exe is located
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        if exe_dir != _base:
            for fname in os.listdir(exe_dir):
                lower = fname.lower()
                if lower.endswith((".dbf", ".frm", ".lbl", ".ndx", ".ntx", ".cdx", ".mdx")):
                    src = os.path.join(exe_dir, fname)
                    dst = os.path.join(work_dir, fname)
                    if os.path.isfile(src) and not os.path.exists(dst):
                        shutil.copy2(src, dst)

        os.chdir(work_dir)

        # Initialize dBase runtime
        config.default_path = work_dir
        config.talk = False
        env = Environment(config)
        evaluator = ExpressionEvaluator(env)
        register_all(evaluator, config)
        cmd_interp = CommandInterpreter(env, evaluator, config)
        interp = ProgramInterpreter(env, evaluator, config, cmd_interp)

        # Execute the main PRG
        main_prg = os.path.join(work_dir, {os.path.basename(main_prg_file).lower()!r})
        try:
            result = interp.run_file(main_prg)
            for line in result:
                print(line)
        except SystemExit:
            pass
        except Exception as e:
            print(f"Runtime error: {{e}}", file=sys.stderr)
            sys.exit(1)
        finally:
            env.close_all()

    finally:
        os.chdir(original_dir)
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass

if __name__ == "__main__":
    main()
'''
        with open(launcher_path, "w", encoding="utf-8") as f:
            f.write(launcher_code)

    def _run_pyinstaller(self, launcher_path, output, dbase_pkg_path,
                         data_args, icon, console, onefile, build_dir):
        """Run PyInstaller to create the executable."""
        output_name = os.path.splitext(os.path.basename(output))[0]
        output_dir = os.path.dirname(output)
        if not output_dir:
            output_dir = os.getcwd()

        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            "--name", output_name,
            "--distpath", output_dir,
            "--workpath", os.path.join(build_dir, "build"),
            "--specpath", build_dir,
        ]

        if onefile:
            cmd.append("--onefile")

        if console:
            cmd.append("--console")
        else:
            cmd.append("--windowed")

        if icon and os.path.exists(icon):
            cmd.extend(["--icon", icon])

        # Add the dbase package
        # Collect all dbase module files
        cmd.extend(["--hidden-import", "dbase"])
        cmd.extend(["--hidden-import", "dbase.main"])
        cmd.extend(["--hidden-import", "dbase.config"])
        cmd.extend(["--hidden-import", "dbase.dbf"])
        cmd.extend(["--hidden-import", "dbase.expression"])
        cmd.extend(["--hidden-import", "dbase.functions"])
        cmd.extend(["--hidden-import", "dbase.workarea"])
        cmd.extend(["--hidden-import", "dbase.commands"])
        cmd.extend(["--hidden-import", "dbase.interpreter"])
        cmd.extend(["--hidden-import", "dbase.sql"])
        cmd.extend(["--hidden-import", "dbase.io_formats"])
        cmd.extend(["--hidden-import", "dbase.reports"])
        cmd.extend(["--hidden-import", "dbase.debugger"])
        cmd.extend(["--hidden-import", "dbase.indexes"])
        cmd.extend(["--hidden-import", "dbase.indexes.ndx"])
        cmd.extend(["--hidden-import", "dbase.indexes.ntx"])
        cmd.extend(["--hidden-import", "dbase.indexes.cdx"])
        cmd.extend(["--hidden-import", "dbase.indexes.mdx"])
        cmd.extend(["--hidden-import", "dbase.ui"])
        cmd.extend(["--hidden-import", "dbase.ui.browse"])

        # Add dbase package as data (for any resources)
        dbase_parent = os.path.dirname(dbase_pkg_path)
        cmd.extend(["--paths", dbase_parent])

        # Add bundled data files
        for src, dest in data_args:
            cmd.extend(["--add-data", f"{src}{os.pathsep}{dest}"])

        # The launcher script
        cmd.append(launcher_path)

        self.log(f"PyInstaller command: {' '.join(os.path.basename(c) for c in cmd[:5])}...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=build_dir,
        )

        if result.returncode != 0:
            if self.verbose:
                if result.stdout:
                    # Show only last 20 lines
                    lines = result.stdout.strip().split("\n")
                    for line in lines[-20:]:
                        self.log(f"  {line}")
                if result.stderr:
                    lines = result.stderr.strip().split("\n")
                    for line in lines[-10:]:
                        self.log(f"  ERR: {line}")
            raise RuntimeError(f"PyInstaller failed with exit code {result.returncode}")


def main():
    """CLI entry point for the compiler."""
    import argparse
    parser = argparse.ArgumentParser(
        description="dBase Revival Compiler by Jair Lima - Compile PRG to EXE"
    )
    parser.add_argument("prg_file", help="PRG file to compile")
    parser.add_argument("-o", "--output", help="Output executable name")
    parser.add_argument("--icon", help="Icon file (.ico) for the executable")
    parser.add_argument("--no-console", action="store_true",
                        help="Create windowed app (no console)")
    parser.add_argument("--dir", action="store_true",
                        help="Create directory instead of single file")
    parser.add_argument("--data", nargs="*", default=[],
                        help="Extra data files to bundle (dbf, frm, etc.)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Suppress output")

    args = parser.parse_args()

    compiler = PRGCompiler(verbose=not args.quiet)
    try:
        result = compiler.compile(
            args.prg_file,
            output=args.output,
            icon=args.icon,
            console=not args.no_console,
            onefile=not args.dir,
            extra_data=args.data,
        )
        print(f"\nCompiled successfully: {result}")
    except Exception as e:
        print(f"\nCompilation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
