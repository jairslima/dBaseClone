"""dBase Revival by Jair Lima - Report and Label engine.

REPORT FORM: generates columnar reports from DBF data.
Definition files use .FRM extension with JSON content:
{
    "title": "Report Title",
    "page_width": 80,
    "left_margin": 0,
    "right_margin": 0,
    "lines_per_page": 58,
    "double_space": false,
    "page_heading": "Custom heading",
    "group_field": "FIELD",
    "group_heading": "expression",
    "summary_only": false,
    "columns": [
        {"field": "NOME", "heading": "Name", "width": 20, "total": false},
        {"field": "SALARIO", "heading": "Salary", "width": 12, "decimals": 2, "total": true}
    ]
}

LABEL FORM: generates mailing labels from DBF data.
Definition files use .LBL extension with JSON content:
{
    "width": 35,
    "height": 5,
    "left_margin": 0,
    "lines_between": 1,
    "spaces_between": 0,
    "columns_count": 1,
    "lines": [
        "TRIM(nome)",
        "TRIM(endereco)",
        "TRIM(cidade)+', '+estado",
        "TRIM(cep)",
        ""
    ]
}
"""

import json
import os
from datetime import date


# ============================================================
# REPORT FORM
# ============================================================

class ReportEngine:
    """Generates columnar reports from DBF tables."""

    def __init__(self, evaluator, config):
        self.eval = evaluator
        self.config = config

    def create_report(self, frm_file, dbf):
        """Interactive report definition creator. Returns definition dict."""
        fields = [f.name for f in dbf.fields]
        definition = {
            "title": "",
            "page_width": 80,
            "left_margin": 8,
            "right_margin": 0,
            "lines_per_page": 58,
            "double_space": False,
            "page_heading": "",
            "group_field": "",
            "group_heading": "",
            "summary_only": False,
            "columns": [],
        }

        print("\n--- CREATE REPORT ---")
        print(f"Available fields: {', '.join(fields)}")

        try:
            title = input("Report title: ").strip()
            if title:
                definition["title"] = title

            pw = input(f"Page width [{definition['page_width']}]: ").strip()
            if pw:
                definition["page_width"] = int(pw)

            lm = input(f"Left margin [{definition['left_margin']}]: ").strip()
            if lm:
                definition["left_margin"] = int(lm)

            lpp = input(f"Lines per page [{definition['lines_per_page']}]: ").strip()
            if lpp:
                definition["lines_per_page"] = int(lpp)

            grp = input("Group on field (blank for none): ").strip().upper()
            if grp and grp in fields:
                definition["group_field"] = grp
                gh = input("Group heading expression: ").strip()
                if gh:
                    definition["group_heading"] = gh

            print("\nDefine columns (blank field name to finish):")
            col_num = 1
            while True:
                print(f"\n  Column {col_num}:")
                fname = input("    Field/expression: ").strip()
                if not fname:
                    break
                heading = input(f"    Heading [{fname}]: ").strip()
                if not heading:
                    heading = fname.upper()
                width = input("    Width [10]: ").strip()
                width = int(width) if width else 10
                dec = 0
                do_total = False

                field_upper = fname.upper()
                field_def = None
                for f in dbf.fields:
                    if f.name == field_upper:
                        field_def = f
                        break

                if field_def and field_def.field_type in ("N", "F"):
                    dec_str = input(f"    Decimals [{field_def.decimals}]: ").strip()
                    dec = int(dec_str) if dec_str else field_def.decimals
                    tot = input("    Total this column? (Y/N) [N]: ").strip().upper()
                    do_total = tot == "Y"

                definition["columns"].append({
                    "field": fname,
                    "heading": heading,
                    "width": width,
                    "decimals": dec,
                    "total": do_total,
                })
                col_num += 1

        except (EOFError, KeyboardInterrupt):
            pass

        if definition["columns"]:
            with open(frm_file, "w", encoding="utf-8") as f:
                json.dump(definition, f, indent=2)
            return definition, f"Report form saved to {os.path.basename(frm_file)}."
        return None, "No columns defined. Report not created."

    def run_report(self, frm_file, dbf, records, options):
        """Generate report output lines.

        Args:
            frm_file: path to .FRM file
            dbf: the DBF object
            records: list of (recno, record) tuples to include
            options: dict with keys: heading, plain, summary, noeject
        """
        with open(frm_file, "r", encoding="utf-8") as f:
            defn = json.load(f)

        columns = defn.get("columns", [])
        if not columns:
            return ["No columns defined in report form."]

        # Sort records by group field for proper grouping
        group_field = defn.get("group_field", "")
        if group_field and records:
            def group_key(item):
                val = item[1]._data.get(group_field.upper(), "")
                if isinstance(val, str):
                    return val.strip()
                return str(val)
            records = sorted(records, key=group_key)

        page_width = defn.get("page_width", 80)
        left_margin = defn.get("left_margin", 0)
        lines_per_page = defn.get("lines_per_page", 58)
        double_space = defn.get("double_space", False)
        title = defn.get("title", "")
        page_heading = options.get("heading", defn.get("page_heading", ""))
        plain = options.get("plain", False)
        summary = options.get("summary", defn.get("summary_only", False))
        noeject = options.get("noeject", False)

        group_field = defn.get("group_field", "")
        group_heading_expr = defn.get("group_heading", "")

        margin = " " * left_margin
        output = []
        line_count = 0
        page_num = 1
        grand_totals = [0.0] * len(columns)
        group_totals = [0.0] * len(columns)
        record_count = 0
        current_group = None

        def new_page():
            nonlocal line_count, page_num
            if not plain:
                if not noeject and page_num > 1:
                    output.append("\f")
                today = date.today().strftime("%m/%d/%Y" if not self.config.century else "%m/%d/%Y")
                header = f"{margin}Page No. {page_num:5d}"
                date_str = today
                pad = page_width - len(header) - len(date_str)
                if pad < 1:
                    pad = 1
                output.append(header + " " * pad + date_str)
                line_count = 1

                if title:
                    centered = title.center(page_width)
                    output.append(margin + centered.strip())
                    line_count += 1

                if page_heading:
                    output.append(margin + page_heading)
                    line_count += 1

                output.append("")
                line_count += 1

            # Column headings
            hdr_line = margin
            sep_line = margin
            for col in columns:
                w = col.get("width", 10)
                h = col.get("heading", col["field"])
                hdr_line += h[:w].ljust(w) + " "
                sep_line += "-" * w + " "
            output.append(hdr_line.rstrip())
            output.append(sep_line.rstrip())
            line_count += 2
            page_num += 1

        def check_page():
            nonlocal line_count
            if line_count >= lines_per_page:
                new_page()

        def format_value(val, col):
            w = col.get("width", 10)
            dec = col.get("decimals", 0)
            if val is None:
                return " " * w
            if isinstance(val, (int, float)):
                if dec > 0:
                    formatted = f"{val:>{w}.{dec}f}"
                else:
                    formatted = f"{val:>{w}d}" if isinstance(val, int) else f"{val:>{w}.0f}"
                return formatted[:w]
            if isinstance(val, bool):
                return (".T." if val else ".F.").center(w)
            if isinstance(val, date):
                return str(val)[:w].ljust(w)
            return str(val)[:w].ljust(w)

        def print_group_totals():
            if any(c.get("total") for c in columns):
                tot_line = margin + "** Subtotal **"
                output.append(tot_line)
                val_line = margin
                for i, col in enumerate(columns):
                    w = col.get("width", 10)
                    if col.get("total"):
                        dec = col.get("decimals", 0)
                        val_line += f"{group_totals[i]:>{w}.{dec}f}" + " "
                    else:
                        val_line += " " * w + " "
                output.append(val_line.rstrip())
                output.append("")

        # Start
        new_page()

        for recno, rec in records:
            # Group handling
            if group_field:
                gval = rec._data.get(group_field.upper(), "")
                if isinstance(gval, str):
                    gval = gval.strip()
                if current_group is not None and gval != current_group:
                    print_group_totals()
                    group_totals = [0.0] * len(columns)
                    if group_heading_expr:
                        try:
                            gh = str(self.eval.evaluate(group_heading_expr, rec, recno))
                        except Exception:
                            gh = str(gval)
                    else:
                        gh = f"** {group_field}: {gval}"
                    output.append(margin + gh)
                    output.append("")
                    line_count += 2
                    check_page()
                if current_group is None and group_heading_expr:
                    try:
                        gh = str(self.eval.evaluate(group_heading_expr, rec, recno))
                    except Exception:
                        gh = str(gval)
                    output.append(margin + gh)
                    output.append("")
                    line_count += 2
                current_group = gval

            # Data line
            if not summary:
                data_line = margin
                for i, col in enumerate(columns):
                    expr = col["field"]
                    try:
                        val = self.eval.evaluate(expr, rec, recno)
                    except Exception:
                        val = rec._data.get(expr.upper(), "")
                    data_line += format_value(val, col) + " "

                    if col.get("total") and isinstance(val, (int, float)):
                        grand_totals[i] += val
                        group_totals[i] += val

                output.append(data_line.rstrip())
                line_count += 1
                if double_space:
                    output.append("")
                    line_count += 1
                check_page()
            else:
                # Summary mode: just accumulate totals
                for i, col in enumerate(columns):
                    if col.get("total"):
                        expr = col["field"]
                        try:
                            val = self.eval.evaluate(expr, rec, recno)
                        except Exception:
                            val = rec._data.get(expr.upper(), 0)
                        if isinstance(val, (int, float)):
                            grand_totals[i] += val
                            group_totals[i] += val

            record_count += 1

        # Final group totals
        if group_field and current_group is not None:
            print_group_totals()

        # Grand totals
        if any(c.get("total") for c in columns):
            output.append(margin + "*** Total ***")
            val_line = margin
            for i, col in enumerate(columns):
                w = col.get("width", 10)
                if col.get("total"):
                    dec = col.get("decimals", 0)
                    val_line += f"{grand_totals[i]:>{w}.{dec}f}" + " "
                else:
                    val_line += " " * w + " "
            output.append(val_line.rstrip())

        output.append("")
        output.append(f"{margin}{record_count} record(s) in report.")

        return output


# ============================================================
# LABEL FORM
# ============================================================

class LabelEngine:
    """Generates mailing labels from DBF tables."""

    PREDEFINED = {
        "3x10": {"width": 35, "height": 9, "left_margin": 0,
                 "lines_between": 1, "spaces_between": 0, "columns_count": 3},
        "2x10": {"width": 42, "height": 9, "left_margin": 0,
                 "lines_between": 1, "spaces_between": 0, "columns_count": 2},
        "1x10": {"width": 80, "height": 9, "left_margin": 0,
                 "lines_between": 1, "spaces_between": 0, "columns_count": 1},
        "cheshire": {"width": 35, "height": 4, "left_margin": 0,
                     "lines_between": 2, "spaces_between": 2, "columns_count": 3},
    }

    def __init__(self, evaluator, config):
        self.eval = evaluator
        self.config = config

    def create_label(self, lbl_file, dbf):
        """Interactive label definition creator."""
        fields = [f.name for f in dbf.fields]
        definition = {
            "width": 35,
            "height": 5,
            "left_margin": 0,
            "lines_between": 1,
            "spaces_between": 0,
            "columns_count": 1,
            "lines": [],
        }

        print("\n--- CREATE LABEL ---")
        print(f"Available fields: {', '.join(fields)}")
        print(f"Predefined layouts: {', '.join(self.PREDEFINED.keys())}")

        try:
            preset = input("Use predefined layout (blank for custom): ").strip().lower()
            if preset in self.PREDEFINED:
                definition.update(self.PREDEFINED[preset])
            else:
                w = input(f"Label width [{definition['width']}]: ").strip()
                if w:
                    definition["width"] = int(w)
                h = input(f"Label height (lines) [{definition['height']}]: ").strip()
                if h:
                    definition["height"] = int(h)
                lm = input(f"Left margin [{definition['left_margin']}]: ").strip()
                if lm:
                    definition["left_margin"] = int(lm)
                lb = input(f"Lines between labels [{definition['lines_between']}]: ").strip()
                if lb:
                    definition["lines_between"] = int(lb)
                nc = input(f"Number of columns [{definition['columns_count']}]: ").strip()
                if nc:
                    definition["columns_count"] = int(nc)
                if definition["columns_count"] > 1:
                    sb = input(f"Spaces between columns [{definition['spaces_between']}]: ").strip()
                    if sb:
                        definition["spaces_between"] = int(sb)

            print(f"\nDefine label lines (up to {definition['height']}):")
            print("Use expressions like: TRIM(nome), TRIM(cidade)+', '+estado")
            for i in range(definition["height"]):
                line = input(f"  Line {i + 1}: ").strip()
                definition["lines"].append(line)

        except (EOFError, KeyboardInterrupt):
            pass

        # Pad to height
        while len(definition["lines"]) < definition["height"]:
            definition["lines"].append("")

        with open(lbl_file, "w", encoding="utf-8") as f:
            json.dump(definition, f, indent=2)
        return definition, f"Label form saved to {os.path.basename(lbl_file)}."

    def run_labels(self, lbl_file, dbf, records, options):
        """Generate label output lines.

        Args:
            lbl_file: path to .LBL file
            dbf: the DBF object
            records: list of (recno, record) tuples
            options: dict with keys: sample
        """
        with open(lbl_file, "r", encoding="utf-8") as f:
            defn = json.load(f)

        label_width = defn.get("width", 35)
        label_height = defn.get("height", 5)
        left_margin = defn.get("left_margin", 0)
        lines_between = defn.get("lines_between", 1)
        spaces_between = defn.get("spaces_between", 0)
        num_columns = defn.get("columns_count", 1)
        line_exprs = defn.get("lines", [])
        sample = options.get("sample", False)

        margin = " " * left_margin
        output = []

        # Pad expressions to label height
        while len(line_exprs) < label_height:
            line_exprs.append("")

        if sample:
            # Print sample labels with X's
            sample_lines = [margin + ("X" * label_width)] * label_height
            for row in range(3):
                for ln in sample_lines:
                    cols = []
                    for c in range(num_columns):
                        cols.append(ln)
                    output.append((" " * spaces_between).join(cols))
                for _ in range(lines_between):
                    output.append("")
            return output

        # Process records in batches of num_columns
        rec_list = list(records)
        idx = 0

        while idx < len(rec_list):
            batch = rec_list[idx:idx + num_columns]
            idx += num_columns

            # Generate each line of the label row
            for line_num in range(label_height):
                cols = []
                for rec_idx, (recno, rec) in enumerate(batch):
                    expr = line_exprs[line_num] if line_num < len(line_exprs) else ""
                    if expr:
                        try:
                            val = str(self.eval.evaluate(expr, rec, recno))
                        except Exception:
                            val = ""
                    else:
                        val = ""
                    cols.append(margin + val[:label_width].ljust(label_width))

                # Pad if batch is smaller than num_columns
                while len(cols) < num_columns:
                    cols.append(margin + " " * label_width)

                output.append((" " * spaces_between).join(cols).rstrip())

            # Lines between label rows
            for _ in range(lines_between):
                output.append("")

        count = len(rec_list)
        output.append(f"{count} label(s) generated.")
        return output
