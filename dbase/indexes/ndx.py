"""dBase Revival by Jair Lima - NDX index engine (dBASE III/IV format).

NDX is the original dBASE index format using a B-tree structure.
Each NDX file contains a single index on a single expression.
"""

import struct
import os
import math


NDX_PAGE_SIZE = 512
NDX_HEADER_SIZE = 512


class NDXHeader:
    def __init__(self):
        self.start_page = 0
        self.total_pages = 0
        self.key_length = 0
        self.keys_per_page = 0
        self.key_type = 0  # 0=Character, 1=Numeric
        self.unique = False
        self.expression = ""


class NDXNode:
    def __init__(self):
        self.num_keys = 0
        self.entries = []


class NDXEntry:
    def __init__(self):
        self.lower_page = 0
        self.recno = 0
        self.key = None


class NDXIndex:
    """NDX index file handler."""

    def __init__(self, filename=None, dbf=None):
        self.filename = filename
        self.dbf = dbf
        self.header = NDXHeader()
        self._pages = {}
        self._keys = []
        self._dirty = False

        if filename and os.path.exists(filename):
            self._read_file()

    @property
    def expression(self):
        return self.header.expression

    @property
    def key_count(self):
        return len(self._keys)

    def _read_file(self):
        """Read and parse the NDX file."""
        with open(self.filename, "rb") as f:
            data = f.read(NDX_HEADER_SIZE)
            self.header.start_page = struct.unpack("<I", data[0:4])[0]
            self.header.total_pages = struct.unpack("<I", data[4:8])[0]
            self.header.key_length = struct.unpack("<H", data[12:14])[0]
            self.header.keys_per_page = struct.unpack("<H", data[14:16])[0]
            self.header.key_type = struct.unpack("<H", data[16:18])[0]
            self.header.unique = data[23] != 0
            self.header.expression = data[24:512].split(b"\x00")[0].decode("latin-1").strip()

            self._keys = []
            self._read_node(f, self.header.start_page)

    def _read_node(self, f, page_num):
        """Recursively read B-tree nodes."""
        if page_num == 0:
            return
        f.seek(page_num * NDX_PAGE_SIZE)
        page_data = f.read(NDX_PAGE_SIZE)
        if len(page_data) < NDX_PAGE_SIZE:
            return

        num_keys = struct.unpack("<H", page_data[0:2])[0]
        entry_size = self.header.key_length + 8
        offset = 4

        for i in range(num_keys):
            if offset + entry_size > NDX_PAGE_SIZE:
                break
            lower_page = struct.unpack("<I", page_data[offset:offset + 4])[0]
            recno = struct.unpack("<I", page_data[offset + 4:offset + 8])[0]
            key_data = page_data[offset + 8:offset + 8 + self.header.key_length]

            if lower_page > 0:
                self._read_node(f, lower_page)

            if self.header.key_type == 1:
                try:
                    key = struct.unpack("<d", key_data[:8])[0]
                except struct.error:
                    key = 0.0
            else:
                key = key_data.decode("latin-1").rstrip("\x00").rstrip()

            self._keys.append((key, recno))
            offset += entry_size

        trailing_offset = offset
        if trailing_offset + 4 <= NDX_PAGE_SIZE:
            trailing_page = struct.unpack("<I", page_data[trailing_offset:trailing_offset + 4])[0]
            if trailing_page > 0:
                self._read_node(f, trailing_page)

    def create(self, filename, expression, key_type=0, key_length=10, unique=False):
        """Create a new empty NDX index."""
        self.filename = filename
        self.header = NDXHeader()
        self.header.expression = expression
        self.header.key_type = key_type
        self.header.key_length = key_length if key_type == 0 else 8
        self.header.unique = unique
        self.header.keys_per_page = (NDX_PAGE_SIZE - 4) // (self.header.key_length + 8)
        self.header.start_page = 1
        self.header.total_pages = 2
        self._keys = []
        self._dirty = True

    def add_key(self, key, recno):
        """Add a key to the index."""
        if self.header.unique:
            for k, r in self._keys:
                if k == key:
                    return False

        self._keys.append((key, recno))
        self._keys.sort(key=lambda x: (x[0], x[1]))
        self._dirty = True
        return True

    def remove_key(self, recno):
        """Remove a key by record number."""
        self._keys = [(k, r) for k, r in self._keys if r != recno]
        self._dirty = True

    def find(self, key):
        """Find exact key match. Returns list of record numbers."""
        results = []
        for k, r in self._keys:
            if isinstance(key, str) and isinstance(k, str):
                if k.rstrip() == key.rstrip():
                    results.append(r)
            elif k == key:
                results.append(r)
        return results

    def find_nearest(self, key):
        """Find nearest key (for SOFTSEEK). Returns record number or 0."""
        for k, r in self._keys:
            if isinstance(key, str) and isinstance(k, str):
                if k.rstrip() >= key.rstrip():
                    return r
            elif k >= key:
                return r
        return 0

    def seek(self, key, exact=True, softseek=False):
        """SEEK a key value. Returns (found, recno)."""
        for k, r in self._keys:
            if isinstance(key, str) and isinstance(k, str):
                if exact:
                    if k.rstrip() == key.rstrip():
                        return (True, r)
                else:
                    if k[:len(key)].rstrip() == key.rstrip():
                        return (True, r)
            else:
                if k == key:
                    return (True, r)

        if softseek:
            r = self.find_nearest(key)
            if r > 0:
                return (False, r)
        return (False, 0)

    def get_ordered_recnos(self):
        """Return record numbers in index order."""
        return [r for k, r in self._keys]

    def save(self):
        """Write the NDX file to disk."""
        if not self._dirty:
            return
        self._write_file()
        self._dirty = False

    def _write_file(self):
        """Build and write the B-tree to disk."""
        header = bytearray(NDX_HEADER_SIZE)
        kpp = self.header.keys_per_page
        if kpp == 0:
            kpp = max(1, (NDX_PAGE_SIZE - 4) // (self.header.key_length + 8))
            self.header.keys_per_page = kpp

        num_leaf_pages = max(1, math.ceil(len(self._keys) / kpp))
        total_pages = 1 + num_leaf_pages + 1
        self.header.total_pages = total_pages
        self.header.start_page = 1

        struct.pack_into("<I", header, 0, self.header.start_page)
        struct.pack_into("<I", header, 4, self.header.total_pages)
        struct.pack_into("<H", header, 12, self.header.key_length)
        struct.pack_into("<H", header, 14, self.header.keys_per_page)
        struct.pack_into("<H", header, 16, self.header.key_type)
        header[23] = 1 if self.header.unique else 0
        expr_bytes = self.header.expression.encode("latin-1")[:487]
        header[24:24 + len(expr_bytes)] = expr_bytes

        pages = [bytes(header)]

        if not self._keys:
            leaf = bytearray(NDX_PAGE_SIZE)
            struct.pack_into("<H", leaf, 0, 0)
            pages.append(bytes(leaf))
        else:
            entry_size = self.header.key_length + 8
            for page_idx in range(num_leaf_pages):
                start = page_idx * kpp
                end = min(start + kpp, len(self._keys))
                page_keys = self._keys[start:end]

                leaf = bytearray(NDX_PAGE_SIZE)
                struct.pack_into("<H", leaf, 0, len(page_keys))
                off = 4
                for key, recno in page_keys:
                    struct.pack_into("<I", leaf, off, 0)
                    struct.pack_into("<I", leaf, off + 4, recno)
                    if self.header.key_type == 1:
                        struct.pack_into("<d", leaf, off + 8, float(key))
                    else:
                        kb = str(key).encode("latin-1")[:self.header.key_length]
                        kb = kb.ljust(self.header.key_length, b"\x00")
                        leaf[off + 8:off + 8 + self.header.key_length] = kb
                    off += entry_size
                pages.append(bytes(leaf))

        with open(self.filename, "wb") as f:
            for page in pages:
                f.write(page.ljust(NDX_PAGE_SIZE, b"\x00"))

    def rebuild(self, dbf, eval_func):
        """Rebuild the index from the DBF using the given expression evaluator."""
        self._keys = []
        for i, rec in enumerate(dbf.records):
            if not rec.deleted:
                key = eval_func(self.header.expression, rec, i)
                self.add_key(key, i + 1)
        self._dirty = True
