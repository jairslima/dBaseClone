"""dBase Revival by Jair Lima - BROWSE terminal interface.

Full-screen table browser using curses for navigation and editing.
Supports scrolling, field editing, record deletion/recall.

Keys:
  Up/Down      - Navigate records
  Left/Right   - Navigate fields
  PgUp/PgDn    - Page up/down
  Home/End     - First/last record
  Enter        - Edit current field
  Del          - Toggle delete mark
  Ctrl+W / Esc - Exit BROWSE
  Ctrl+N       - Append blank record
  Ctrl+T       - Go to top
  Ctrl+B       - Go to bottom
"""

import os
import sys


def browse_table(workarea, config, evaluator):
    """Launch the BROWSE screen for the given work area."""
    try:
        import curses
        curses.wrapper(lambda stdscr: _browse_main(stdscr, workarea, config, evaluator))
    except ImportError:
        _browse_fallback(workarea, config)
    except Exception as e:
        _browse_fallback(workarea, config)


def _browse_fallback(workarea, config):
    """Simple text-based browse when curses is not available."""
    if not workarea.dbf:
        print("No database in use.")
        return

    dbf = workarea.dbf
    page_size = 20
    current_top = workarea.recno if workarea.recno > 0 else 1

    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print(f"=== BROWSE: {os.path.basename(dbf.filename)} === Record {workarea.recno}/{dbf.record_count} ===")
        print()

        # Header
        header = f"{'Rec#':>6s} "
        for f in dbf.fields:
            header += f"{f.name:{f.length}s} "
        print(header)
        print("-" * len(header))

        # Records
        end = min(current_top + page_size - 1, dbf.record_count)
        for r in range(current_top, end + 1):
            rec = dbf.records[r - 1]
            del_mark = "*" if rec.deleted else " "
            marker = ">" if r == workarea.recno else " "
            line = f"{marker}{r:>5d}{del_mark}"
            for f in dbf.fields:
                val = rec[f.name]
                if f.field_type == "D":
                    if val and hasattr(val, "year"):
                        s = config.format_date(val)
                    else:
                        s = "  /  /  "
                elif f.field_type == "L":
                    s = ".T." if val else ".F."
                elif f.field_type in ("N", "F"):
                    if f.decimals > 0:
                        s = f"{float(val or 0):{f.length}.{f.decimals}f}"
                    else:
                        s = f"{int(val or 0):>{f.length}d}"
                else:
                    s = str(val or "")
                line += f"{s:{f.length}s} "
            print(line)

        print()
        print("[N]ext [P]rev [T]op [B]ottom [E]dit [D]elete [A]ppend [Q]uit")

        try:
            cmd = input("> ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd == "Q" or cmd == "":
            break
        elif cmd == "N":
            if current_top + page_size <= dbf.record_count:
                current_top += page_size
                workarea.recno = current_top
        elif cmd == "P":
            current_top = max(1, current_top - page_size)
            workarea.recno = current_top
        elif cmd == "T":
            current_top = 1
            workarea.recno = 1
        elif cmd == "B":
            current_top = max(1, dbf.record_count - page_size + 1)
            workarea.recno = dbf.record_count
        elif cmd == "D":
            rec = workarea.current_record()
            if rec:
                rec.deleted = not rec.deleted
        elif cmd == "A":
            dbf.append_blank()
            workarea.recno = dbf.record_count
            current_top = max(1, dbf.record_count - page_size + 1)
        elif cmd == "E":
            rec = workarea.current_record()
            if rec:
                print(f"\nEditing record {workarea.recno}:")
                for field in dbf.fields:
                    val = rec[field.name]
                    try:
                        new_val = input(f"  {field.name}: [{val}] ")
                        if new_val.strip():
                            if field.field_type in ("N", "F"):
                                rec[field.name] = float(new_val) if field.decimals > 0 else int(new_val)
                            elif field.field_type == "L":
                                rec[field.name] = new_val.upper() in ("T", "Y", ".T.", "1")
                            elif field.field_type == "D":
                                rec[field.name] = config.parse_date(new_val)
                            else:
                                rec[field.name] = new_val
                    except (EOFError, KeyboardInterrupt):
                        break
        elif cmd.isdigit():
            n = int(cmd)
            if 1 <= n <= dbf.record_count:
                workarea.recno = n
                current_top = max(1, n - page_size // 2)


def _browse_main(stdscr, workarea, config, evaluator):
    """Full curses-based BROWSE screen."""
    import curses

    curses.curs_set(0)
    stdscr.keypad(True)

    if not workarea.dbf or workarea.dbf.record_count == 0:
        stdscr.addstr(0, 0, "No records to browse. Press any key.")
        stdscr.getch()
        return

    dbf = workarea.dbf
    fields = dbf.fields
    current_row = workarea.recno if workarea.recno > 0 else 1
    current_col = 0
    top_row = current_row
    left_col = 0

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()
        data_rows = max_y - 3

        # Adjust view
        if current_row < top_row:
            top_row = current_row
        if current_row >= top_row + data_rows:
            top_row = current_row - data_rows + 1

        # Calculate visible columns
        visible_fields = []
        x_pos = 7  # After rec# column
        for i, f in enumerate(fields):
            if i < left_col:
                continue
            width = max(len(f.name), f.length) + 1
            if x_pos + width > max_x:
                break
            visible_fields.append((i, f, x_pos, width))
            x_pos += width

        # Title bar
        title = f" BROWSE: {os.path.basename(dbf.filename)} | Record {current_row}/{dbf.record_count} "
        try:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(0, 0, title.ljust(max_x)[:max_x - 1])
            stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

        # Column headers
        try:
            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(1, 0, "Rec# ")
            for idx, f, xp, w in visible_fields:
                stdscr.addstr(1, xp, f.name[:w - 1].ljust(w - 1))
            stdscr.attroff(curses.A_BOLD)
        except curses.error:
            pass

        # Data rows
        for screen_row in range(data_rows):
            rec_num = top_row + screen_row
            if rec_num > dbf.record_count:
                break

            rec = dbf.records[rec_num - 1]
            y = screen_row + 2
            is_current = (rec_num == current_row)

            del_mark = "*" if rec.deleted else " "
            try:
                attr = curses.A_REVERSE if is_current else 0
                stdscr.addstr(y, 0, f"{rec_num:>5d}{del_mark}", attr)

                for idx, f, xp, w in visible_fields:
                    val = rec[f.name]
                    s = _format_browse_value(val, f, config)
                    cell_attr = attr
                    if is_current and idx == current_col:
                        cell_attr = curses.A_REVERSE | curses.A_UNDERLINE
                    stdscr.addstr(y, xp, s[:w - 1].ljust(w - 1), cell_attr)
            except curses.error:
                pass

        # Status bar
        try:
            status = " Up/Down:Nav | PgUp/PgDn:Page | Enter:Edit | Del:Delete | Ctrl+N:New | Esc:Quit "
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(max_y - 1, 0, status.ljust(max_x)[:max_x - 1])
            stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

        stdscr.refresh()

        # Input
        key = stdscr.getch()

        if key == 27 or key == 23:  # Esc or Ctrl+W
            break
        elif key == curses.KEY_UP:
            if current_row > 1:
                current_row -= 1
        elif key == curses.KEY_DOWN:
            if current_row < dbf.record_count:
                current_row += 1
        elif key == curses.KEY_LEFT:
            if current_col > 0:
                current_col -= 1
                if current_col < left_col:
                    left_col = current_col
        elif key == curses.KEY_RIGHT:
            if current_col < len(fields) - 1:
                current_col += 1
        elif key == curses.KEY_PPAGE:
            current_row = max(1, current_row - data_rows)
            top_row = max(1, top_row - data_rows)
        elif key == curses.KEY_NPAGE:
            current_row = min(dbf.record_count, current_row + data_rows)
        elif key == curses.KEY_HOME:
            current_row = 1
            top_row = 1
        elif key == curses.KEY_END:
            current_row = dbf.record_count
        elif key == curses.KEY_DC or key == 330:  # Delete key
            rec = dbf.records[current_row - 1]
            rec.deleted = not rec.deleted
        elif key == 14:  # Ctrl+N
            dbf.append_blank()
            current_row = dbf.record_count
        elif key == 20:  # Ctrl+T
            current_row = 1
            top_row = 1
        elif key == 2:  # Ctrl+B
            current_row = dbf.record_count
        elif key == 10 or key == 13 or key == curses.KEY_ENTER:  # Enter
            _edit_field_curses(stdscr, dbf, current_row, current_col, config, max_y)

    workarea.recno = current_row
    workarea.eof = current_row > dbf.record_count


def _format_browse_value(val, field, config):
    """Format a value for display in BROWSE."""
    if val is None:
        return ""
    if field.field_type == "D":
        if hasattr(val, "year"):
            return config.format_date(val)
        return "  /  /  "
    if field.field_type == "L":
        return ".T." if val else ".F."
    if field.field_type in ("N", "F"):
        if field.decimals > 0:
            return f"{float(val or 0):{field.length}.{field.decimals}f}"
        return f"{int(val or 0):>{field.length}d}"
    return str(val or "")


def _edit_field_curses(stdscr, dbf, rec_num, col_idx, config, max_y):
    """Edit a single field value in BROWSE mode."""
    import curses

    rec = dbf.records[rec_num - 1]
    field = dbf.fields[col_idx]
    val = rec[field.name]
    current_str = _format_browse_value(val, field, config).strip()

    prompt = f"Edit {field.name}: "
    try:
        stdscr.addstr(max_y - 1, 0, " " * (stdscr.getmaxyx()[1] - 1))
        stdscr.addstr(max_y - 1, 0, prompt + current_str)
    except curses.error:
        pass
    stdscr.refresh()

    curses.echo()
    curses.curs_set(1)
    try:
        new_val = stdscr.getstr(max_y - 1, len(prompt), field.length + 10).decode("latin-1").strip()
    except Exception:
        new_val = ""
    curses.noecho()
    curses.curs_set(0)

    if new_val:
        try:
            if field.field_type in ("N", "F"):
                rec[field.name] = float(new_val) if field.decimals > 0 else int(new_val)
            elif field.field_type == "L":
                rec[field.name] = new_val.upper() in ("T", "Y", ".T.", "1", "TRUE")
            elif field.field_type == "D":
                rec[field.name] = config.parse_date(new_val)
            else:
                rec[field.name] = new_val
        except ValueError:
            pass
