"""dBase Revival by Jair Lima - Work area management.

Manages up to 250 work areas (like dBASE V / Clipper), each with its own
open DBF, index files, record pointer, and settings.
"""

import os
from .dbf import DBF
from .indexes.ndx import NDXIndex
from .indexes.ntx import NTXIndex
from .indexes.cdx import CDXIndex
from .indexes.mdx import MDXIndex


MAX_WORK_AREAS = 250


class WorkArea:
    """A single work area holding an open table and its indexes."""

    def __init__(self, area_number):
        self.area_number = area_number
        self.alias = ""
        self.dbf = None
        self.recno = 0      # 1-based, 0 means no record
        self.eof = True
        self.bof = False
        self.found = False
        self.indexes = []     # List of open index objects
        self.active_order = 0  # 0=natural, 1+ = index in self.indexes
        self.filter_expr = ""
        self.relation_expr = ""
        self.relation_target = 0
        self.scope_top = None
        self.scope_bottom = None

    def is_open(self):
        return self.dbf is not None

    def open_table(self, filename, alias=None):
        """Open a DBF file in this work area."""
        if not os.path.exists(filename):
            base = os.path.splitext(filename)[0]
            for ext in (".dbf", ".DBF"):
                if os.path.exists(base + ext):
                    filename = base + ext
                    break
            else:
                raise FileNotFoundError(f"File not found: {filename}")

        self.dbf = DBF(filename)
        self.alias = (alias or os.path.splitext(os.path.basename(filename))[0]).upper()
        self.recno = 1 if self.dbf.record_count > 0 else 0
        self.eof = self.dbf.record_count == 0
        self.bof = False
        self.found = False
        self.indexes = []
        self.active_order = 0

        # Auto-open production MDX if exists
        mdx_path = os.path.splitext(filename)[0] + ".mdx"
        if os.path.exists(mdx_path):
            mdx = MDXIndex(mdx_path, self.dbf)
            self.indexes.append(mdx)

    def close_table(self):
        """Close the table and all indexes."""
        if self.dbf:
            self.dbf.save()
        for idx in self.indexes:
            if hasattr(idx, "save"):
                idx.save()
        self.dbf = None
        self.alias = ""
        self.recno = 0
        self.eof = True
        self.bof = False
        self.found = False
        self.indexes = []
        self.active_order = 0
        self.filter_expr = ""
        self.relation_expr = ""
        self.relation_target = 0

    def current_record(self):
        """Get the current record, or None if EOF/no records."""
        if not self.dbf or self.eof or self.recno < 1 or self.recno > self.dbf.record_count:
            return None
        return self.dbf.records[self.recno - 1]

    def go_to(self, recno):
        """Move to a specific record number (1-based)."""
        if not self.dbf:
            return
        if recno < 1:
            self.recno = 1
            self.bof = True
            self.eof = self.dbf.record_count == 0
            return
        if recno > self.dbf.record_count:
            self.recno = self.dbf.record_count + 1
            self.eof = True
            self.bof = False
            return
        self.recno = recno
        self.eof = False
        self.bof = False

    def go_top(self):
        """Move to the first record (respecting index order)."""
        if not self.dbf or self.dbf.record_count == 0:
            self.eof = True
            self.bof = True
            self.recno = 0
            return
        if self.active_order > 0:
            idx = self._active_index()
            if idx:
                recnos = self._get_ordered_recnos(idx)
                if recnos:
                    self.recno = recnos[0]
                    self.eof = False
                    self.bof = False
                    return
        self.recno = 1
        self.eof = False
        self.bof = False

    def go_bottom(self):
        """Move to the last record (respecting index order)."""
        if not self.dbf or self.dbf.record_count == 0:
            self.eof = True
            self.bof = True
            self.recno = 0
            return
        if self.active_order > 0:
            idx = self._active_index()
            if idx:
                recnos = self._get_ordered_recnos(idx)
                if recnos:
                    self.recno = recnos[-1]
                    self.eof = False
                    self.bof = False
                    return
        self.recno = self.dbf.record_count
        self.eof = False
        self.bof = False

    def skip(self, n=1):
        """Skip forward or backward n records (respecting index order)."""
        if not self.dbf or self.dbf.record_count == 0:
            self.eof = True
            return

        if self.active_order > 0:
            idx = self._active_index()
            if idx:
                recnos = self._get_ordered_recnos(idx)
                if not recnos:
                    self.eof = True
                    return
                try:
                    current_pos = recnos.index(self.recno)
                except ValueError:
                    current_pos = 0
                new_pos = current_pos + n
                if new_pos < 0:
                    self.bof = True
                    self.recno = recnos[0] if recnos else 1
                    return
                if new_pos >= len(recnos):
                    self.eof = True
                    self.recno = self.dbf.record_count + 1
                    return
                self.recno = recnos[new_pos]
                self.eof = False
                self.bof = False
                return

        new_recno = self.recno + n
        if new_recno < 1:
            self.recno = 1
            self.bof = True
        elif new_recno > self.dbf.record_count:
            self.recno = self.dbf.record_count + 1
            self.eof = True
        else:
            self.recno = new_recno
            self.eof = False
            self.bof = False

    def _active_index(self):
        """Get the currently active index object."""
        if self.active_order <= 0 or self.active_order > len(self.indexes):
            return None
        return self.indexes[self.active_order - 1]

    def _get_ordered_recnos(self, idx):
        """Get record numbers in index order, handling both simple and compound."""
        if hasattr(idx, "tags"):
            # Compound index (CDX/MDX)
            names = idx.tag_names()
            if names:
                tag = idx.get_tag(names[0])
                if tag:
                    return tag.get_ordered_recnos()
        elif hasattr(idx, "get_ordered_recnos"):
            return idx.get_ordered_recnos()
        return []

    def add_index(self, index_obj, set_active=True):
        """Add an index file and optionally make it active."""
        self.indexes.append(index_obj)
        if set_active:
            self.active_order = len(self.indexes)

    def set_order(self, order):
        """Set the active index order (0=natural, 1+=index number)."""
        if isinstance(order, int):
            self.active_order = order
        elif isinstance(order, str):
            # Find by tag name
            order_upper = order.upper()
            for i, idx in enumerate(self.indexes):
                if hasattr(idx, "tags"):
                    if order_upper in [t.upper() for t in idx.tag_names()]:
                        self.active_order = i + 1
                        return
                elif hasattr(idx, "expression"):
                    if hasattr(idx, "header") and hasattr(idx.header, "expression"):
                        pass
            # Also check by index filename
            for i, idx in enumerate(self.indexes):
                if hasattr(idx, "filename") and idx.filename:
                    base = os.path.splitext(os.path.basename(idx.filename))[0].upper()
                    if base == order_upper:
                        self.active_order = i + 1
                        return

    def seek(self, key, exact=True, softseek=False):
        """SEEK a key in the active index."""
        idx = self._active_index()
        if not idx:
            self.found = False
            return False

        if hasattr(idx, "tags"):
            names = idx.tag_names()
            if names:
                tag = idx.get_tag(names[0])
                if tag:
                    found, recno = tag.seek(key, exact, softseek)
                    self.found = found
                    if recno > 0:
                        self.go_to(recno)
                    else:
                        self.eof = True
                        self.recno = self.dbf.record_count + 1
                    return found
        elif hasattr(idx, "seek"):
            found, recno = idx.seek(key, exact, softseek)
            self.found = found
            if recno > 0:
                self.go_to(recno)
            else:
                self.eof = True
                self.recno = self.dbf.record_count + 1
            return found

        self.found = False
        return False


class Environment:
    """Global environment managing all work areas and variables."""

    def __init__(self, config):
        self.config = config
        self.work_areas = {}
        self.current_area = 1
        self.variables = {}       # Memory variables
        self.public_vars = set()
        self.private_vars = {}    # Stack of private scopes
        self._private_stack = []
        self.arrays = {}
        self.procedures = {}      # Loaded procedures
        self.last_key = 0
        self._canceled = False

    def current_workarea(self):
        """Get the current work area."""
        return self.work_areas.get(self.current_area)

    def get_workarea(self, area):
        """Get or create a work area by number."""
        if area not in self.work_areas:
            self.work_areas[area] = WorkArea(area)
        return self.work_areas[area]

    def get_workarea_by_alias(self, alias):
        """Find a work area by alias name."""
        alias = alias.upper()
        # Check if it's a letter A-J (classic dBase area letters)
        if len(alias) == 1 and alias.isalpha():
            area_num = ord(alias) - ord("A") + 1
            if area_num in self.work_areas:
                return self.work_areas[area_num]
        # Check by alias name
        for wa in self.work_areas.values():
            if wa.alias == alias:
                return wa
        # Check if it's a number
        try:
            area_num = int(alias)
            return self.work_areas.get(area_num)
        except ValueError:
            pass
        return None

    def select_area(self, area):
        """Select a work area as current."""
        if isinstance(area, str):
            area_upper = area.upper()
            if len(area_upper) == 1 and area_upper.isalpha():
                self.current_area = ord(area_upper) - ord("A") + 1
                return
            wa = self.get_workarea_by_alias(area_upper)
            if wa:
                self.current_area = wa.area_number
                return
            try:
                self.current_area = int(area)
                return
            except ValueError:
                pass
            # Find first unused area
            for i in range(1, MAX_WORK_AREAS + 1):
                if i not in self.work_areas or not self.work_areas[i].is_open():
                    self.current_area = i
                    return
        else:
            if area == 0:
                # SELECT 0: find first unused
                for i in range(1, MAX_WORK_AREAS + 1):
                    if i not in self.work_areas or not self.work_areas[i].is_open():
                        self.current_area = i
                        return
            else:
                self.current_area = int(area)

    def close_all(self):
        """Close all open tables."""
        for wa in self.work_areas.values():
            if wa.is_open():
                wa.close_table()

    def close_databases(self):
        """Same as close_all."""
        self.close_all()

    # Variable management
    def get_variable(self, name):
        name = name.upper()
        return self.variables.get(name)

    def set_variable(self, name, value):
        name = name.upper()
        self.variables[name] = value

    def declare_public(self, name):
        name = name.upper()
        self.public_vars.add(name)
        if name not in self.variables:
            self.variables[name] = False

    def declare_private(self, name):
        name = name.upper()
        if self._private_stack:
            self._private_stack[-1].add(name)
        if name not in self.variables:
            self.variables[name] = False

    def push_private_scope(self):
        self._private_stack.append(set())

    def pop_private_scope(self):
        if self._private_stack:
            scope = self._private_stack.pop()
            for name in scope:
                if name not in self.public_vars:
                    self.variables.pop(name, None)

    def release_variable(self, name):
        name = name.upper()
        self.variables.pop(name, None)
        self.public_vars.discard(name)

    def release_all(self):
        keep = set(self.public_vars)
        self.variables = {k: v for k, v in self.variables.items() if k in keep}

    # Array management
    def declare_array(self, name, rows, cols=0):
        name = name.upper()
        if cols > 0:
            self.arrays[name] = [[False] * cols for _ in range(rows)]
        else:
            self.arrays[name] = [False] * rows
        self.variables[name] = self.arrays[name]

    def get_array_element(self, name, row, col=None):
        name = name.upper()
        arr = self.arrays.get(name)
        if arr is None:
            return None
        if col is not None and isinstance(arr[0], list):
            return arr[row - 1][col - 1]
        if isinstance(arr, list):
            return arr[row - 1]
        return None

    def set_array_element(self, name, row, col, value):
        name = name.upper()
        arr = self.arrays.get(name)
        if arr is None:
            return
        if col is not None and isinstance(arr[0], list):
            arr[row - 1][col - 1] = value
        else:
            arr[row - 1] = value
