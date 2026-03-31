"""dBase Revival by Jair Lima - DBF file format engine.

Full support for dBASE III/III+/IV/V DBF file format with read/write
capabilities for all field types.
"""

import struct
import os
from datetime import date, datetime


# DBF version bytes
DBF_VERSION_III = 0x03
DBF_VERSION_III_MEMO = 0x83
DBF_VERSION_IV = 0x04
DBF_VERSION_IV_MEMO = 0x8B
DBF_VERSION_FOXPRO = 0x30
DBF_VERSION_FOXPRO_MEMO = 0xF5

FIELD_TERMINATOR = 0x0D
FILE_TERMINATOR = 0x1A
HEADER_SIZE = 32
FIELD_DESC_SIZE = 32


class FieldDef:
    """Definition of a single field in a DBF table."""

    def __init__(self, name="", field_type="C", length=10, decimals=0):
        self.name = name.upper().strip()
        self.field_type = field_type.upper()
        self.length = length
        self.decimals = decimals
        self.offset = 0

    def __repr__(self):
        if self.decimals > 0:
            return f"FieldDef({self.name}, {self.field_type}, {self.length}, {self.decimals})"
        return f"FieldDef({self.name}, {self.field_type}, {self.length})"


class Record:
    """A single record in a DBF table."""

    def __init__(self, fields, data=None):
        self.fields = fields
        self.deleted = False
        self._data = {}
        if data:
            self._data = dict(data)
        else:
            for f in fields:
                self._data[f.name] = self._default_value(f)

    def _default_value(self, field):
        if field.field_type == "C":
            return ""
        elif field.field_type in ("N", "F", "B", "I", "Y"):
            return 0 if field.decimals == 0 else 0.0
        elif field.field_type == "D":
            return None
        elif field.field_type == "L":
            return False
        elif field.field_type == "M":
            return ""
        elif field.field_type == "T":
            return None
        return ""

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self.fields[key].name]
        return self._data.get(key.upper(), "")

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self._data[self.fields[key].name] = value
        else:
            self._data[key.upper()] = value

    def get(self, key, default=None):
        if isinstance(key, str):
            return self._data.get(key.upper(), default)
        return default

    def keys(self):
        return [f.name for f in self.fields]

    def values(self):
        return [self._data.get(f.name) for f in self.fields]

    def items(self):
        return [(f.name, self._data.get(f.name)) for f in self.fields]


class DBF:
    """DBF file handler with full read/write support."""

    def __init__(self, filename=None):
        self.filename = filename
        self.version = DBF_VERSION_III
        self.fields = []
        self.records = []
        self.header_size = 0
        self.record_size = 0
        self.encoding = "latin-1"
        self.memo_file = None
        self._memo_data = {}

        if filename and os.path.exists(filename):
            self.open(filename)

    @property
    def field_count(self):
        return len(self.fields)

    @property
    def record_count(self):
        return len(self.records)

    def field_index(self, name):
        name = name.upper().strip()
        for i, f in enumerate(self.fields):
            if f.name == name:
                return i
        return -1

    def field_by_name(self, name):
        name = name.upper().strip()
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def create(self, filename, fields):
        """Create a new DBF file with the given field definitions."""
        self.filename = filename
        self.fields = []
        self.records = []
        offset = 1  # deletion flag byte

        for f in fields:
            fd = FieldDef(f["name"], f.get("type", "C"), f.get("length", 10), f.get("decimals", 0))
            fd.offset = offset
            offset += fd.length
            self.fields.append(fd)

        has_memo = any(f.field_type == "M" for f in self.fields)
        self.version = DBF_VERSION_III_MEMO if has_memo else DBF_VERSION_III
        self.record_size = offset
        self.header_size = HEADER_SIZE + (len(self.fields) * FIELD_DESC_SIZE) + 1
        self._write_file()
        if has_memo:
            self._create_memo_file()

    def open(self, filename):
        """Open and read an existing DBF file."""
        self.filename = filename
        with open(filename, "rb") as f:
            header = f.read(HEADER_SIZE)
            if len(header) < HEADER_SIZE:
                raise ValueError("Invalid DBF file: header too short")

            self.version = header[0]
            num_records = struct.unpack("<I", header[4:8])[0]
            self.header_size = struct.unpack("<H", header[8:10])[0]
            self.record_size = struct.unpack("<H", header[10:12])[0]

            self.fields = []
            offset = 1
            f.seek(HEADER_SIZE)
            while True:
                byte = f.read(1)
                if not byte or byte[0] == FIELD_TERMINATOR:
                    break
                field_data = byte + f.read(FIELD_DESC_SIZE - 1)
                if len(field_data) < FIELD_DESC_SIZE:
                    break

                fd = FieldDef()
                fd.name = field_data[0:11].split(b"\x00")[0].decode(self.encoding).strip().upper()
                fd.field_type = chr(field_data[11])
                fd.length = field_data[16]
                fd.decimals = field_data[17]
                fd.offset = offset
                offset += fd.length
                self.fields.append(fd)

            has_memo = self.version in (DBF_VERSION_III_MEMO, DBF_VERSION_IV_MEMO, DBF_VERSION_FOXPRO_MEMO)
            if has_memo:
                self._open_memo_file()

            self.records = []
            f.seek(self.header_size)
            for i in range(num_records):
                raw = f.read(self.record_size)
                if len(raw) < self.record_size:
                    break
                rec = self._parse_record(raw)
                self.records.append(rec)

    def _parse_record(self, raw):
        """Parse a raw record bytes into a Record object."""
        rec = Record(self.fields)
        rec.deleted = (raw[0:1] == b"*")

        for field in self.fields:
            raw_val = raw[field.offset:field.offset + field.length]
            try:
                val_str = raw_val.decode(self.encoding)
            except Exception:
                val_str = raw_val.decode("latin-1")

            if field.field_type == "C":
                rec[field.name] = val_str
            elif field.field_type in ("N", "F"):
                val_str = val_str.strip()
                if not val_str or val_str == "." or all(c in " *" for c in val_str):
                    rec[field.name] = 0 if field.decimals == 0 else 0.0
                else:
                    try:
                        if field.decimals == 0 and "." not in val_str:
                            rec[field.name] = int(val_str)
                        else:
                            rec[field.name] = float(val_str)
                    except ValueError:
                        rec[field.name] = 0
            elif field.field_type == "D":
                val_str = val_str.strip()
                if len(val_str) == 8 and val_str != "        ":
                    try:
                        rec[field.name] = date(int(val_str[:4]), int(val_str[4:6]), int(val_str[6:8]))
                    except ValueError:
                        rec[field.name] = None
                else:
                    rec[field.name] = None
            elif field.field_type == "L":
                val_str = val_str.strip()
                rec[field.name] = val_str.upper() in ("T", "Y", "1")
            elif field.field_type == "M":
                val_str = val_str.strip()
                if val_str and val_str.isdigit():
                    block = int(val_str)
                    rec[field.name] = self._read_memo(block)
                else:
                    rec[field.name] = ""
            elif field.field_type == "I":
                if len(raw_val) >= 4:
                    rec[field.name] = struct.unpack("<i", raw_val[:4])[0]
                else:
                    rec[field.name] = 0
            elif field.field_type == "B":
                if len(raw_val) >= 8:
                    rec[field.name] = struct.unpack("<d", raw_val[:8])[0]
                else:
                    rec[field.name] = 0.0
            elif field.field_type == "Y":
                if len(raw_val) >= 8:
                    rec[field.name] = struct.unpack("<q", raw_val[:8])[0] / 10000.0
                else:
                    rec[field.name] = 0.0
            elif field.field_type == "T":
                rec[field.name] = val_str.strip()
            else:
                rec[field.name] = val_str

        return rec

    def _serialize_record(self, rec):
        """Serialize a Record object to raw bytes."""
        buf = bytearray(self.record_size)
        buf[0] = ord("*") if rec.deleted else ord(" ")

        for field in self.fields:
            val = rec[field.name]
            if field.field_type == "C":
                s = str(val) if val is not None else ""
                raw = s.encode(self.encoding)[:field.length].ljust(field.length)
            elif field.field_type in ("N", "F"):
                if val is None:
                    val = 0
                if field.decimals > 0:
                    fmt = f"{float(val):{field.length}.{field.decimals}f}"
                else:
                    fmt = f"{int(val):>{field.length}d}" if isinstance(val, int) else f"{int(float(val)):>{field.length}d}"
                raw = fmt[:field.length].rjust(field.length).encode(self.encoding)
            elif field.field_type == "D":
                if val and isinstance(val, date):
                    s = f"{val.year:04d}{val.month:02d}{val.day:02d}"
                else:
                    s = " " * 8
                raw = s.encode(self.encoding)
            elif field.field_type == "L":
                raw = b"T" if val else b"F"
            elif field.field_type == "M":
                if val:
                    block = self._write_memo(str(val))
                    s = f"{block:>{field.length}d}"
                else:
                    s = " " * field.length
                raw = s.encode(self.encoding)
            elif field.field_type == "I":
                raw = struct.pack("<i", int(val or 0))
            elif field.field_type == "B":
                raw = struct.pack("<d", float(val or 0))
            elif field.field_type == "Y":
                raw = struct.pack("<q", int(float(val or 0) * 10000))
            else:
                s = str(val) if val is not None else ""
                raw = s.encode(self.encoding)[:field.length].ljust(field.length)

            buf[field.offset:field.offset + field.length] = raw[:field.length]

        return bytes(buf)

    def append_blank(self):
        """Append a blank record and return it."""
        rec = Record(self.fields)
        self.records.append(rec)
        return rec

    def append_record(self, data):
        """Append a record with the given field data dict."""
        rec = Record(self.fields)
        for k, v in data.items():
            rec[k.upper()] = v
        self.records.append(rec)
        return rec

    def mark_deleted(self, recno):
        """Mark a record as deleted (0-based index)."""
        if 0 <= recno < len(self.records):
            self.records[recno].deleted = True

    def recall(self, recno):
        """Undelete a record (0-based index)."""
        if 0 <= recno < len(self.records):
            self.records[recno].deleted = False

    def pack(self):
        """Remove all records marked as deleted."""
        self.records = [r for r in self.records if not r.deleted]

    def zap(self):
        """Remove all records."""
        self.records = []

    def save(self, filename=None):
        """Write the DBF file to disk."""
        if filename:
            self.filename = filename
        self._write_file()

    def _write_file(self):
        """Write the complete DBF file."""
        has_memo = any(f.field_type == "M" for f in self.fields)
        self.version = DBF_VERSION_III_MEMO if has_memo else DBF_VERSION_III
        self.header_size = HEADER_SIZE + (len(self.fields) * FIELD_DESC_SIZE) + 1

        offset = 1
        for f in self.fields:
            f.offset = offset
            offset += f.length
        self.record_size = offset

        today = date.today()
        header = bytearray(HEADER_SIZE)
        header[0] = self.version
        header[1] = today.year - 1900
        header[2] = today.month
        header[3] = today.day
        struct.pack_into("<I", header, 4, len(self.records))
        struct.pack_into("<H", header, 8, self.header_size)
        struct.pack_into("<H", header, 10, self.record_size)

        with open(self.filename, "wb") as f:
            f.write(header)

            for field in self.fields:
                fd = bytearray(FIELD_DESC_SIZE)
                name_bytes = field.name.encode(self.encoding)[:11]
                fd[0:len(name_bytes)] = name_bytes
                fd[11] = ord(field.field_type)
                fd[16] = field.length
                fd[17] = field.decimals
                f.write(fd)

            f.write(bytes([FIELD_TERMINATOR]))

            for rec in self.records:
                f.write(self._serialize_record(rec))

            f.write(bytes([FILE_TERMINATOR]))

    def _memo_filename(self):
        """Get the memo file path."""
        base = os.path.splitext(self.filename)[0]
        for ext in (".dbt", ".fpt", ".DBT", ".FPT"):
            path = base + ext
            if os.path.exists(path):
                return path
        return base + ".dbt"

    def _create_memo_file(self):
        """Create a new DBT memo file."""
        memo_path = os.path.splitext(self.filename)[0] + ".dbt"
        with open(memo_path, "wb") as f:
            header = bytearray(512)
            struct.pack_into("<I", header, 0, 1)
            f.write(header)

    def _open_memo_file(self):
        """Open memo file for reading."""
        memo_path = self._memo_filename()
        if os.path.exists(memo_path):
            self.memo_file = memo_path

    def _read_memo(self, block):
        """Read memo field data from the memo file."""
        if not self.memo_file or block <= 0:
            return ""
        try:
            with open(self.memo_file, "rb") as f:
                f.seek(block * 512)
                data = b""
                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    term = chunk.find(b"\x1a")
                    if term >= 0:
                        data += chunk[:term]
                        break
                    data += chunk
                return data.decode(self.encoding, errors="replace")
        except Exception:
            return ""

    def _write_memo(self, text):
        """Write memo data and return block number."""
        memo_path = os.path.splitext(self.filename)[0] + ".dbt"
        if not os.path.exists(memo_path):
            self._create_memo_file()

        with open(memo_path, "r+b") as f:
            f.seek(0)
            next_block = struct.unpack("<I", f.read(4))[0]

            f.seek(next_block * 512)
            data = text.encode(self.encoding) + b"\x1a"
            blocks_needed = (len(data) + 511) // 512
            data = data.ljust(blocks_needed * 512, b"\x00")
            f.write(data)

            f.seek(0)
            f.write(struct.pack("<I", next_block + blocks_needed))

        return next_block

    def copy_structure(self, target_filename):
        """Create a new DBF with the same structure but no records."""
        new_dbf = DBF()
        fields = [{"name": f.name, "type": f.field_type, "length": f.length, "decimals": f.decimals} for f in self.fields]
        new_dbf.create(target_filename, fields)
        return new_dbf

    def copy_to(self, target_filename, field_list=None, scope=None, for_func=None, while_func=None):
        """Copy records to a new DBF file."""
        new_dbf = DBF()
        if field_list:
            fields = [{"name": f.name, "type": f.field_type, "length": f.length, "decimals": f.decimals}
                      for f in self.fields if f.name in [x.upper() for x in field_list]]
        else:
            fields = [{"name": f.name, "type": f.field_type, "length": f.length, "decimals": f.decimals}
                      for f in self.fields]

        new_dbf.create(target_filename, fields)

        count = 0
        for i, rec in enumerate(self.records):
            if rec.deleted:
                continue
            if while_func and not while_func(rec, i):
                break
            if for_func and not for_func(rec, i):
                continue
            data = {f.name: rec[f.name] for f in new_dbf.fields}
            new_dbf.append_record(data)
            count += 1
            if scope and count >= scope:
                break

        new_dbf.save()
        return count

    def sort_by(self, field_name, ascending=True):
        """Sort records by a field."""
        field_name = field_name.upper()
        self.records.sort(key=lambda r: r[field_name] if r[field_name] is not None else "", reverse=not ascending)
