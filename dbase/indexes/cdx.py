"""dBase Revival by Jair Lima - CDX index engine (FoxPro compound index format).

CDX is the FoxPro compound index format that supports multiple index tags
in a single file, each with its own expression and optional FOR clause.
"""

import struct
import os


CDX_PAGE_SIZE = 512
CDX_HEADER_SIZE = 1024


class CDXTag:
    """A single index tag within a CDX file."""

    def __init__(self, name=""):
        self.name = name.upper()
        self.expression = ""
        self.for_expression = ""
        self.key_length = 10
        self.key_type = 0  # 0=Char, 1=Numeric, 2=Date
        self.unique = False
        self.ascending = True
        self.keys = []

    def add_key(self, key, recno):
        if isinstance(key, str):
            key = key[:self.key_length]
        if self.unique:
            for k, r in self.keys:
                if isinstance(k, str) and isinstance(key, str):
                    if k.rstrip() == key.rstrip():
                        return False
                elif k == key:
                    return False
        self.keys.append((key, recno))
        self.keys.sort(key=lambda x: (x[0], x[1]), reverse=not self.ascending)
        return True

    def remove_key(self, recno):
        self.keys = [(k, r) for k, r in self.keys if r != recno]

    def find(self, key):
        results = []
        for k, r in self.keys:
            if isinstance(key, str) and isinstance(k, str):
                if k.rstrip() == key.rstrip():
                    results.append(r)
            elif k == key:
                results.append(r)
        return results

    def seek(self, key, exact=True, softseek=False):
        for k, r in self.keys:
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
        return [r for k, r in self.keys]


class CDXIndex:
    """CDX compound index file handler (FoxPro format)."""

    def __init__(self, filename=None, dbf=None):
        self.filename = filename
        self.dbf = dbf
        self.tags = {}
        self.tag_order = []
        self._dirty = False

        if filename and os.path.exists(filename):
            self._read_file()

    @property
    def tag_count(self):
        return len(self.tags)

    def _read_file(self):
        """Read CDX file and extract tags."""
        try:
            with open(self.filename, "rb") as f:
                header = f.read(CDX_HEADER_SIZE)
                if len(header) < CDX_HEADER_SIZE:
                    return

                root_page = struct.unpack("<I", header[0:4])[0]
                num_keys = struct.unpack("<I", header[4:8])[0]
                key_length = struct.unpack("<H", header[12:14])[0]
                options = header[16] if len(header) > 16 else 0

                expr_start = 24
                expression = header[expr_start:expr_start + 256].split(b"\x00")[0].decode("latin-1").strip()

                if expression:
                    tag = CDXTag("PRIMARY")
                    tag.expression = expression
                    tag.key_length = key_length
                    tag.unique = bool(options & 0x01)
                    self.tags["PRIMARY"] = tag
                    self.tag_order.append("PRIMARY")

        except Exception:
            pass

    def create(self, filename):
        """Create a new empty CDX file."""
        self.filename = filename
        self.tags = {}
        self.tag_order = []
        self._dirty = True

    def add_tag(self, name, expression, key_length=10, key_type=0,
                unique=False, ascending=True, for_expression=""):
        """Add a new tag to the compound index."""
        name = name.upper()[:10]
        tag = CDXTag(name)
        tag.expression = expression
        tag.for_expression = for_expression
        tag.key_length = key_length
        tag.key_type = key_type
        tag.unique = unique
        tag.ascending = ascending
        self.tags[name] = tag
        if name not in self.tag_order:
            self.tag_order.append(name)
        self._dirty = True
        return tag

    def remove_tag(self, name):
        """Remove a tag from the compound index."""
        name = name.upper()
        if name in self.tags:
            del self.tags[name]
            self.tag_order = [t for t in self.tag_order if t != name]
            self._dirty = True
            return True
        return False

    def get_tag(self, name_or_index):
        """Get a tag by name or index (1-based)."""
        if isinstance(name_or_index, int):
            idx = name_or_index - 1
            if 0 <= idx < len(self.tag_order):
                return self.tags[self.tag_order[idx]]
            return None
        name = name_or_index.upper()
        return self.tags.get(name)

    def tag_names(self):
        """Return ordered list of tag names."""
        return list(self.tag_order)

    def save(self):
        """Write CDX file to disk."""
        if not self._dirty:
            return
        self._write_file()
        self._dirty = False

    def _write_file(self):
        """Write CDX compound index file."""
        with open(self.filename, "wb") as f:
            header = bytearray(CDX_HEADER_SIZE)
            struct.pack_into("<I", header, 0, CDX_HEADER_SIZE)
            struct.pack_into("<I", header, 8, len(self.tags))

            tag_dir_offset = CDX_HEADER_SIZE

            f.write(bytes(header))

            for tag_name in self.tag_order:
                tag = self.tags[tag_name]
                tag_header = bytearray(CDX_PAGE_SIZE)

                name_bytes = tag.name.encode("latin-1")[:10]
                tag_header[0:len(name_bytes)] = name_bytes

                struct.pack_into("<H", tag_header, 12, tag.key_length)
                tag_header[16] = (0x01 if tag.unique else 0x00) | (0x00 if tag.ascending else 0x08)

                expr_bytes = tag.expression.encode("latin-1")[:255]
                tag_header[24:24 + len(expr_bytes)] = expr_bytes

                if tag.for_expression:
                    for_bytes = tag.for_expression.encode("latin-1")[:255]
                    tag_header[280:280 + len(for_bytes)] = for_bytes

                struct.pack_into("<I", tag_header, 4, len(tag.keys))

                f.write(bytes(tag_header))

                entry_size = tag.key_length + 8
                keys_per_page = max(1, (CDX_PAGE_SIZE - 4) // entry_size)

                for start in range(0, max(1, len(tag.keys)), keys_per_page):
                    chunk = tag.keys[start:start + keys_per_page]
                    page = bytearray(CDX_PAGE_SIZE)
                    struct.pack_into("<H", page, 0, len(chunk))

                    off = 4
                    for key, recno in chunk:
                        struct.pack_into("<I", page, off, recno)
                        if isinstance(key, (int, float)):
                            struct.pack_into("<d", page, off + 4, float(key))
                        else:
                            kb = str(key).encode("latin-1")[:tag.key_length]
                            kb = kb.ljust(tag.key_length, b"\x00")
                            page[off + 4:off + 4 + tag.key_length] = kb
                        off += entry_size
                    f.write(bytes(page))

    def rebuild_tag(self, tag_name, dbf, eval_func, for_eval_func=None):
        """Rebuild a single tag from DBF data."""
        tag = self.get_tag(tag_name)
        if not tag:
            return
        tag.keys = []
        for i, rec in enumerate(dbf.records):
            if rec.deleted:
                continue
            if tag.for_expression and for_eval_func:
                if not for_eval_func(tag.for_expression, rec, i):
                    continue
            key = eval_func(tag.expression, rec, i)
            tag.add_key(key, i + 1)
        self._dirty = True

    def rebuild_all(self, dbf, eval_func, for_eval_func=None):
        """Rebuild all tags from DBF data."""
        for name in self.tag_order:
            self.rebuild_tag(name, dbf, eval_func, for_eval_func)
