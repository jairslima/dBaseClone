"""dBase Revival by Jair Lima - NTX index engine (Clipper format).

NTX is the Clipper index format, an enhancement over NDX with better
B-tree implementation and support for conditional indexes (FOR clause).
"""

import struct
import os
import math


NTX_PAGE_SIZE = 1024
NTX_HEADER_SIZE = 1024
NTX_SIGNATURE = 0x0006


class NTXHeader:
    def __init__(self):
        self.signature = NTX_SIGNATURE
        self.version = 1
        self.root_page = 0
        self.next_available = 0
        self.key_length = 0
        self.key_decimals = 0
        self.max_keys = 0
        self.half_keys = 0
        self.key_type = 0  # 0=Char, 1=Numeric, 2=Date
        self.key_size = 0
        self.unique = False
        self.descending = False
        self.expression = ""
        self.for_expression = ""
        self.custom = False


class NTXIndex:
    """NTX (Clipper) index file handler."""

    def __init__(self, filename=None, dbf=None):
        self.filename = filename
        self.dbf = dbf
        self.header = NTXHeader()
        self._keys = []
        self._dirty = False

        if filename and os.path.exists(filename):
            self._read_file()

    @property
    def expression(self):
        return self.header.expression

    @property
    def for_expression(self):
        return self.header.for_expression

    @property
    def key_count(self):
        return len(self._keys)

    def _read_file(self):
        """Read and parse the NTX file."""
        with open(self.filename, "rb") as f:
            data = f.read(NTX_HEADER_SIZE)
            if len(data) < NTX_HEADER_SIZE:
                return

            self.header.signature = struct.unpack("<H", data[0:2])[0]
            self.header.version = struct.unpack("<H", data[2:4])[0]
            self.header.root_page = struct.unpack("<I", data[4:8])[0]
            self.header.next_available = struct.unpack("<I", data[8:12])[0]
            self.header.key_length = struct.unpack("<H", data[12:14])[0]
            self.header.key_decimals = struct.unpack("<H", data[14:16])[0]
            self.header.max_keys = struct.unpack("<H", data[16:18])[0]
            self.header.half_keys = struct.unpack("<H", data[18:20])[0]
            self.header.key_size = struct.unpack("<H", data[20:22])[0]
            self.header.unique = data[22] != 0
            self.header.descending = data[23] != 0

            self.header.expression = data[24:280].split(b"\x00")[0].decode("latin-1").strip()
            self.header.for_expression = data[280:536].split(b"\x00")[0].decode("latin-1").strip()

            self._keys = []
            if self.header.root_page > 0:
                self._read_node(f, self.header.root_page)

    def _read_node(self, f, offset):
        """Read B-tree node at given file offset."""
        if offset == 0:
            return
        f.seek(offset)
        page_data = f.read(NTX_PAGE_SIZE)
        if len(page_data) < 4:
            return

        num_keys = struct.unpack("<H", page_data[0:2])[0]
        entry_size = self.header.key_size
        if entry_size == 0:
            entry_size = self.header.key_length + 8

        off = 2
        items = []
        for i in range(num_keys + 1):
            if off + 2 > len(page_data):
                break
            item_offset = struct.unpack("<H", page_data[off:off + 2])[0]
            items.append(item_offset)
            off += 2

        for idx, item_off in enumerate(items):
            if item_off + 8 + self.header.key_length > len(page_data):
                continue

            child_page = struct.unpack("<I", page_data[item_off:item_off + 4])[0]
            recno = struct.unpack("<I", page_data[item_off + 4:item_off + 8])[0]
            key_data = page_data[item_off + 8:item_off + 8 + self.header.key_length]

            if child_page > 0:
                self._read_node(f, child_page)

            if recno > 0:
                key = key_data.decode("latin-1").rstrip("\x00").rstrip()
                self._keys.append((key, recno))

    def create(self, filename, expression, key_length=10, key_type=0,
               unique=False, descending=False, for_expression=""):
        """Create a new NTX index."""
        self.filename = filename
        self.header = NTXHeader()
        self.header.expression = expression
        self.header.for_expression = for_expression
        self.header.key_length = key_length
        self.header.key_type = key_type
        self.header.unique = unique
        self.header.descending = descending
        self.header.key_size = key_length + 8
        self.header.max_keys = max(4, (NTX_PAGE_SIZE - 2) // (self.header.key_size + 2) - 1)
        self.header.half_keys = self.header.max_keys // 2
        self.header.root_page = NTX_HEADER_SIZE
        self._keys = []
        self._dirty = True

    def add_key(self, key, recno):
        """Add a key to the index."""
        if isinstance(key, str):
            key = key[:self.header.key_length]

        if self.header.unique:
            for k, r in self._keys:
                if isinstance(k, str) and isinstance(key, str):
                    if k.rstrip() == key.rstrip():
                        return False
                elif k == key:
                    return False

        self._keys.append((key, recno))
        reverse = self.header.descending
        self._keys.sort(key=lambda x: (x[0], x[1]), reverse=reverse)
        self._dirty = True
        return True

    def remove_key(self, recno):
        """Remove all keys for a given record number."""
        self._keys = [(k, r) for k, r in self._keys if r != recno]
        self._dirty = True

    def find(self, key):
        """Find exact match. Returns list of recnos."""
        results = []
        for k, r in self._keys:
            if isinstance(key, str) and isinstance(k, str):
                if k.rstrip() == key.rstrip():
                    results.append(r)
            elif k == key:
                results.append(r)
        return results

    def seek(self, key, exact=True, softseek=False):
        """SEEK a key. Returns (found, recno)."""
        for k, r in self._keys:
            if isinstance(key, str) and isinstance(k, str):
                if exact:
                    if k.rstrip() == key.rstrip():
                        return (True, r)
                else:
                    if k[:len(key)].rstrip() == key.rstrip():
                        return (True, r)
                    if k.rstrip() > key.rstrip():
                        if softseek:
                            return (False, r)
                        return (False, 0)
            else:
                if k == key:
                    return (True, r)
                if k > key:
                    if softseek:
                        return (False, r)
                    return (False, 0)

        return (False, 0)

    def get_ordered_recnos(self):
        """Return record numbers in index order."""
        return [r for k, r in self._keys]

    def save(self):
        """Write the NTX file to disk."""
        if not self._dirty:
            return
        self._write_file()
        self._dirty = False

    def _write_file(self):
        """Write NTX file with B-tree structure."""
        kpp = max(4, (NTX_PAGE_SIZE - 2) // (self.header.key_size + 2) - 1)
        self.header.max_keys = kpp
        self.header.half_keys = kpp // 2

        header = bytearray(NTX_HEADER_SIZE)
        struct.pack_into("<H", header, 0, NTX_SIGNATURE)
        struct.pack_into("<H", header, 2, 1)
        struct.pack_into("<I", header, 4, NTX_HEADER_SIZE)
        struct.pack_into("<H", header, 12, self.header.key_length)
        struct.pack_into("<H", header, 14, self.header.key_decimals)
        struct.pack_into("<H", header, 16, self.header.max_keys)
        struct.pack_into("<H", header, 18, self.header.half_keys)
        struct.pack_into("<H", header, 20, self.header.key_size)
        header[22] = 1 if self.header.unique else 0
        header[23] = 1 if self.header.descending else 0

        expr_bytes = self.header.expression.encode("latin-1")[:255]
        header[24:24 + len(expr_bytes)] = expr_bytes
        if self.header.for_expression:
            for_bytes = self.header.for_expression.encode("latin-1")[:255]
            header[280:280 + len(for_bytes)] = for_bytes

        pages = [bytes(header)]

        if not self._keys:
            leaf = bytearray(NTX_PAGE_SIZE)
            struct.pack_into("<H", leaf, 0, 0)
            pages.append(bytes(leaf))
        else:
            leaf_pages = []
            for start in range(0, len(self._keys), kpp):
                chunk = self._keys[start:start + kpp]
                page = bytearray(NTX_PAGE_SIZE)
                struct.pack_into("<H", page, 0, len(chunk))

                item_area_start = 2 + (len(chunk) + 1) * 2
                off = item_area_start
                for i, (key, recno) in enumerate(chunk):
                    struct.pack_into("<H", page, 2 + i * 2, off)
                    struct.pack_into("<I", page, off, 0)
                    struct.pack_into("<I", page, off + 4, recno)
                    kb = str(key).encode("latin-1")[:self.header.key_length]
                    kb = kb.ljust(self.header.key_length, b"\x00")
                    page[off + 8:off + 8 + self.header.key_length] = kb
                    off += self.header.key_size

                leaf_pages.append(bytes(page))

            pages.extend(leaf_pages)

        next_avail = len(pages) * NTX_PAGE_SIZE
        header_buf = bytearray(pages[0])
        struct.pack_into("<I", header_buf, 8, next_avail)
        pages[0] = bytes(header_buf)

        with open(self.filename, "wb") as f:
            for page in pages:
                f.write(page.ljust(NTX_PAGE_SIZE, b"\x00")[:NTX_PAGE_SIZE])

    def rebuild(self, dbf, eval_func, for_eval_func=None):
        """Rebuild the index from DBF data."""
        self._keys = []
        for i, rec in enumerate(dbf.records):
            if rec.deleted:
                continue
            if self.header.for_expression and for_eval_func:
                if not for_eval_func(self.header.for_expression, rec, i):
                    continue
            key = eval_func(self.header.expression, rec, i)
            self.add_key(key, i + 1)
        self._dirty = True
