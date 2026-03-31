"""dBase Revival by Jair Lima - MDX index engine (dBASE IV compound index format).

MDX is the dBASE IV production index format. Like CDX it supports
multiple tags in one file, but uses a different internal structure.
When a DBF has an MDX, it is auto-opened with the table.
"""

import struct
import os
from datetime import date


MDX_PAGE_SIZE = 512
MDX_HEADER_SIZE = 544
MDX_TAG_HEADER_SIZE = 544


class MDXTag:
    """A single index tag in an MDX file."""

    def __init__(self, name=""):
        self.name = name.upper()
        self.expression = ""
        self.for_expression = ""
        self.key_length = 10
        self.key_type = 0
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
                        return (False, r) if softseek else (False, 0)
            else:
                if k == key:
                    return (True, r)
                if k > key:
                    return (False, r) if softseek else (False, 0)
        return (False, 0)

    def get_ordered_recnos(self):
        return [r for k, r in self.keys]


class MDXIndex:
    """MDX (dBASE IV production) compound index file handler."""

    def __init__(self, filename=None, dbf=None):
        self.filename = filename
        self.dbf = dbf
        self.tags = {}
        self.tag_order = []
        self.dbf_filename = ""
        self._dirty = False

        if filename and os.path.exists(filename):
            self._read_file()

    @property
    def tag_count(self):
        return len(self.tags)

    def _read_file(self):
        """Read MDX file."""
        try:
            with open(self.filename, "rb") as f:
                header = f.read(MDX_HEADER_SIZE)
                if len(header) < MDX_HEADER_SIZE:
                    return

                version = header[0]
                num_tags = struct.unpack("<H", header[28:30])[0]
                tag_size = struct.unpack("<H", header[30:32])[0]
                self.dbf_filename = header[32:43].split(b"\x00")[0].decode("latin-1").strip()

                for i in range(min(num_tags, 47)):
                    tag_entry_offset = MDX_HEADER_SIZE + (i * 32)
                    f.seek(tag_entry_offset)
                    tag_entry = f.read(32)
                    if len(tag_entry) < 32:
                        break

                    header_page = struct.unpack("<I", tag_entry[0:4])[0]
                    tag_name = tag_entry[4:15].split(b"\x00")[0].decode("latin-1").strip().upper()

                    if not tag_name:
                        continue

                    if header_page > 0:
                        f.seek(header_page * MDX_PAGE_SIZE)
                        th = f.read(MDX_TAG_HEADER_SIZE)
                        if len(th) >= MDX_TAG_HEADER_SIZE:
                            tag = MDXTag(tag_name)
                            tag.key_type = th[32]
                            tag.key_length = struct.unpack("<H", th[34:36])[0]
                            tag.unique = bool(th[40] & 0x01)
                            tag.ascending = not bool(th[40] & 0x08)
                            tag.expression = th[46:300].split(b"\x00")[0].decode("latin-1").strip()
                            tag.for_expression = th[300:512].split(b"\x00")[0].decode("latin-1").strip()
                            self.tags[tag_name] = tag
                            self.tag_order.append(tag_name)

        except Exception:
            pass

    def create(self, filename, dbf_name=""):
        """Create a new MDX file."""
        self.filename = filename
        self.dbf_filename = dbf_name
        self.tags = {}
        self.tag_order = []
        self._dirty = True

    def add_tag(self, name, expression, key_length=10, key_type=0,
                unique=False, ascending=True, for_expression=""):
        """Add a new tag."""
        name = name.upper()[:10]
        if len(self.tags) >= 47:
            raise ValueError("MDX supports a maximum of 47 tags")
        tag = MDXTag(name)
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
        """Remove a tag."""
        name = name.upper()
        if name in self.tags:
            del self.tags[name]
            self.tag_order = [t for t in self.tag_order if t != name]
            self._dirty = True
            return True
        return False

    def get_tag(self, name_or_index):
        """Get tag by name or 1-based index."""
        if isinstance(name_or_index, int):
            idx = name_or_index - 1
            if 0 <= idx < len(self.tag_order):
                return self.tags[self.tag_order[idx]]
            return None
        return self.tags.get(name_or_index.upper())

    def tag_names(self):
        return list(self.tag_order)

    def save(self):
        """Write MDX file."""
        if not self._dirty:
            return
        self._write_file()
        self._dirty = False

    def _write_file(self):
        """Write MDX file to disk."""
        today = date.today()
        header = bytearray(MDX_HEADER_SIZE)
        header[0] = 0x02
        header[1] = today.year - 1900
        header[2] = today.month
        header[3] = today.day
        struct.pack_into("<H", header, 28, len(self.tags))
        struct.pack_into("<H", header, 30, 32)
        dbf_bytes = self.dbf_filename.encode("latin-1")[:11]
        header[32:32 + len(dbf_bytes)] = dbf_bytes

        with open(self.filename, "wb") as f:
            f.write(bytes(header))

            current_page = (MDX_HEADER_SIZE + len(self.tags) * 32 + MDX_PAGE_SIZE - 1) // MDX_PAGE_SIZE

            for i, tag_name in enumerate(self.tag_order):
                tag = self.tags[tag_name]
                tag_entry = bytearray(32)
                struct.pack_into("<I", tag_entry, 0, current_page)
                name_bytes = tag_name.encode("latin-1")[:11]
                tag_entry[4:4 + len(name_bytes)] = name_bytes
                f.write(bytes(tag_entry))
                current_page += 1

            padding_needed = current_page * MDX_PAGE_SIZE - f.tell()
            if padding_needed > 0:
                f.write(b"\x00" * padding_needed)

            for tag_name in self.tag_order:
                tag = self.tags[tag_name]
                th = bytearray(MDX_TAG_HEADER_SIZE)
                th[32] = tag.key_type
                struct.pack_into("<H", th, 34, tag.key_length)
                th[40] = (0x01 if tag.unique else 0x00) | (0x00 if tag.ascending else 0x08)
                expr_bytes = tag.expression.encode("latin-1")[:253]
                th[46:46 + len(expr_bytes)] = expr_bytes
                if tag.for_expression:
                    for_bytes = tag.for_expression.encode("latin-1")[:211]
                    th[300:300 + len(for_bytes)] = for_bytes
                f.write(bytes(th))

    def rebuild_tag(self, tag_name, dbf, eval_func, for_eval_func=None):
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
        for name in self.tag_order:
            self.rebuild_tag(name, dbf, eval_func, for_eval_func)
