"""dBase Revival by Jair Lima - Import/Export module.

Supports exporting and importing data in multiple formats:
- CSV  (comma-separated values, with header row)
- JSON (array of objects or records)
- XML  (structured markup)
- SDF  (System Data Format, fixed-width text)
- DELIMITED (with optional custom delimiter and string qualifier)
- XLS  (tab-delimited, compatible with spreadsheets)
"""

import csv
import json
import os
from datetime import date, datetime
from xml.etree import ElementTree as ET
from xml.dom import minidom


# ============================================================
# EXPORT functions
# ============================================================

def export_csv(dbf, filename, field_list=None, for_func=None, while_func=None,
               delimiter=",", with_header=True, encoding="utf-8"):
    """Export DBF records to CSV file."""
    fields = _resolve_fields(dbf, field_list)
    count = 0

    with open(filename, "w", newline="", encoding=encoding) as f:
        writer = csv.writer(f, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)

        if with_header:
            writer.writerow([fld.name for fld in fields])

        for i, rec in enumerate(dbf.records):
            if rec.deleted:
                continue
            if while_func and not while_func(rec, i):
                break
            if for_func and not for_func(rec, i):
                continue

            row = [_serialize_value(rec[fld.name], fld) for fld in fields]
            writer.writerow(row)
            count += 1

    return count


def export_json(dbf, filename, field_list=None, for_func=None, while_func=None,
                pretty=True, encoding="utf-8"):
    """Export DBF records to JSON file (array of objects)."""
    fields = _resolve_fields(dbf, field_list)
    records = []

    for i, rec in enumerate(dbf.records):
        if rec.deleted:
            continue
        if while_func and not while_func(rec, i):
            break
        if for_func and not for_func(rec, i):
            continue

        obj = {}
        for fld in fields:
            val = rec[fld.name]
            obj[fld.name] = _json_value(val, fld)
        records.append(obj)

    data = {
        "table": os.path.splitext(os.path.basename(dbf.filename))[0],
        "record_count": len(records),
        "fields": [
            {
                "name": fld.name,
                "type": fld.field_type,
                "length": fld.length,
                "decimals": fld.decimals,
            }
            for fld in fields
        ],
        "records": records,
    }

    with open(filename, "w", encoding=encoding) as f:
        if pretty:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        else:
            json.dump(data, f, ensure_ascii=False, default=str)

    return len(records)


def export_xml(dbf, filename, field_list=None, for_func=None, while_func=None,
               encoding="utf-8"):
    """Export DBF records to XML file."""
    fields = _resolve_fields(dbf, field_list)
    table_name = os.path.splitext(os.path.basename(dbf.filename))[0].upper()

    root = ET.Element("dataroot")
    root.set("table", table_name)

    for i, rec in enumerate(dbf.records):
        if rec.deleted:
            continue
        if while_func and not while_func(rec, i):
            break
        if for_func and not for_func(rec, i):
            continue

        record_el = ET.SubElement(root, "record")
        record_el.set("recno", str(i + 1))

        for fld in fields:
            field_el = ET.SubElement(record_el, fld.name)
            val = rec[fld.name]
            field_el.text = _serialize_value(val, fld)
            field_el.set("type", fld.field_type)

    xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
    with open(filename, "w", encoding=encoding) as f:
        f.write(xml_str)

    return sum(1 for r in dbf.records if not r.deleted)


def export_sdf(dbf, filename, field_list=None, for_func=None, while_func=None,
               encoding="utf-8"):
    """Export DBF records to SDF (fixed-width text) file."""
    fields = _resolve_fields(dbf, field_list)
    count = 0

    with open(filename, "w", encoding=encoding) as f:
        for i, rec in enumerate(dbf.records):
            if rec.deleted:
                continue
            if while_func and not while_func(rec, i):
                break
            if for_func and not for_func(rec, i):
                continue

            line = ""
            for fld in fields:
                val = rec[fld.name]
                s = _serialize_value(val, fld)
                if fld.field_type in ("N", "F", "I", "B", "Y"):
                    line += s.rjust(fld.length)[:fld.length]
                else:
                    line += s.ljust(fld.length)[:fld.length]
            f.write(line + "\n")
            count += 1

    return count


def export_delimited(dbf, filename, field_list=None, for_func=None, while_func=None,
                     delimiter=",", qualifier='"', encoding="utf-8"):
    """Export DBF records to delimited text file with string qualifier."""
    fields = _resolve_fields(dbf, field_list)
    count = 0

    with open(filename, "w", encoding=encoding) as f:
        for i, rec in enumerate(dbf.records):
            if rec.deleted:
                continue
            if while_func and not while_func(rec, i):
                break
            if for_func and not for_func(rec, i):
                continue

            parts = []
            for fld in fields:
                val = rec[fld.name]
                s = _serialize_value(val, fld)
                if fld.field_type == "C" or fld.field_type == "M":
                    parts.append(f"{qualifier}{s}{qualifier}")
                else:
                    parts.append(s)
            f.write(delimiter.join(parts) + "\n")
            count += 1

    return count


def export_xls(dbf, filename, field_list=None, for_func=None, while_func=None,
               encoding="utf-8"):
    """Export DBF records to tab-delimited file (XLS compatible)."""
    return export_csv(dbf, filename, field_list, for_func, while_func,
                      delimiter="\t", with_header=True, encoding=encoding)


# ============================================================
# IMPORT functions
# ============================================================

def import_csv(dbf, filename, field_list=None, delimiter=",", with_header=True,
               encoding="utf-8"):
    """Import records from CSV file into DBF."""
    fields = _resolve_fields(dbf, field_list)
    field_names = [fld.name for fld in fields]
    count = 0

    with open(filename, "r", encoding=encoding) as f:
        reader = csv.reader(f, delimiter=delimiter)

        csv_field_map = None
        if with_header:
            header = next(reader, None)
            if header:
                csv_field_map = []
                for h in header:
                    h_upper = h.strip().upper()
                    matched = None
                    for fld in fields:
                        if fld.name == h_upper:
                            matched = fld
                            break
                    csv_field_map.append(matched)

        for row in reader:
            if not row or all(c.strip() == "" for c in row):
                continue

            rec = dbf.append_blank()

            if csv_field_map:
                for col_idx, fld in enumerate(csv_field_map):
                    if fld and col_idx < len(row):
                        rec[fld.name] = _parse_import_value(row[col_idx], fld)
            else:
                for col_idx, fld in enumerate(fields):
                    if col_idx < len(row):
                        rec[fld.name] = _parse_import_value(row[col_idx], fld)

            count += 1

    return count


def import_json(dbf, filename, field_list=None, encoding="utf-8"):
    """Import records from JSON file into DBF."""
    fields = _resolve_fields(dbf, field_list)
    count = 0

    with open(filename, "r", encoding=encoding) as f:
        data = json.load(f)

    # Support both {records: [...]} and plain [...]
    if isinstance(data, dict):
        records = data.get("records", data.get("data", []))
    elif isinstance(data, list):
        records = data
    else:
        return 0

    for obj in records:
        if not isinstance(obj, dict):
            continue

        rec = dbf.append_blank()
        for fld in fields:
            # Try exact match, then case-insensitive
            val = obj.get(fld.name)
            if val is None:
                for k, v in obj.items():
                    if k.upper() == fld.name:
                        val = v
                        break
            if val is not None:
                rec[fld.name] = _parse_json_value(val, fld)
        count += 1

    return count


def import_xml(dbf, filename, field_list=None, encoding="utf-8"):
    """Import records from XML file into DBF."""
    fields = _resolve_fields(dbf, field_list)
    count = 0

    tree = ET.parse(filename)
    root = tree.getroot()

    # Find record elements (could be <record>, <row>, or direct children)
    record_tags = root.findall("record")
    if not record_tags:
        record_tags = root.findall("row")
    if not record_tags:
        record_tags = list(root)

    for record_el in record_tags:
        rec = dbf.append_blank()
        for fld in fields:
            # Try as child element
            el = record_el.find(fld.name)
            if el is None:
                el = record_el.find(fld.name.lower())
            if el is not None and el.text:
                rec[fld.name] = _parse_import_value(el.text.strip(), fld)
            else:
                # Try as attribute
                val = record_el.get(fld.name) or record_el.get(fld.name.lower())
                if val:
                    rec[fld.name] = _parse_import_value(val, fld)
        count += 1

    return count


def import_sdf(dbf, filename, field_list=None, encoding="utf-8"):
    """Import records from SDF (fixed-width) file into DBF."""
    fields = _resolve_fields(dbf, field_list)
    count = 0

    with open(filename, "r", encoding=encoding) as f:
        for line in f:
            if not line.strip():
                continue

            rec = dbf.append_blank()
            pos = 0
            for fld in fields:
                if pos >= len(line):
                    break
                raw = line[pos:pos + fld.length]
                rec[fld.name] = _parse_import_value(raw.strip(), fld)
                pos += fld.length
            count += 1

    return count


def import_delimited(dbf, filename, field_list=None, delimiter=",",
                     qualifier='"', encoding="utf-8"):
    """Import records from delimited text file with string qualifier."""
    fields = _resolve_fields(dbf, field_list)
    count = 0

    with open(filename, "r", encoding=encoding) as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if not line.strip():
                continue

            values = _split_delimited(line, delimiter, qualifier)
            rec = dbf.append_blank()
            for i, fld in enumerate(fields):
                if i < len(values):
                    rec[fld.name] = _parse_import_value(values[i], fld)
            count += 1

    return count


def import_xls(dbf, filename, field_list=None, encoding="utf-8"):
    """Import from tab-delimited file."""
    return import_csv(dbf, filename, field_list, delimiter="\t",
                      with_header=True, encoding=encoding)


# ============================================================
# Helper functions
# ============================================================

def _resolve_fields(dbf, field_list):
    """Resolve field list to actual field definitions."""
    if not field_list:
        return dbf.fields
    result = []
    for name in field_list:
        fld = dbf.field_by_name(name.upper())
        if fld:
            result.append(fld)
    return result if result else dbf.fields


def _serialize_value(val, field):
    """Convert a field value to string for export."""
    if val is None:
        return ""
    if field.field_type == "D":
        if isinstance(val, (date, datetime)):
            return f"{val.year:04d}-{val.month:02d}-{val.day:02d}"
        return str(val).strip()
    if field.field_type == "L":
        return "true" if val else "false"
    if field.field_type in ("N", "F"):
        if field.decimals > 0:
            return f"{float(val):.{field.decimals}f}"
        return str(int(val)) if isinstance(val, (int, float)) else str(val).strip()
    if field.field_type == "C":
        return str(val).rstrip()
    if field.field_type == "M":
        return str(val)
    return str(val).strip()


def _json_value(val, field):
    """Convert a field value for JSON serialization."""
    if val is None:
        return None
    if field.field_type == "D":
        if isinstance(val, (date, datetime)):
            return f"{val.year:04d}-{val.month:02d}-{val.day:02d}"
        return None
    if field.field_type == "L":
        return bool(val)
    if field.field_type in ("N", "F", "I", "B", "Y"):
        if field.decimals > 0:
            return float(val)
        return int(val) if isinstance(val, (int, float)) else val
    if field.field_type == "C":
        return str(val).rstrip()
    return str(val) if val else None


def _parse_import_value(text, field):
    """Parse a string value for import into the given field type."""
    text = str(text).strip()
    if not text:
        if field.field_type in ("N", "F", "I", "B", "Y"):
            return 0 if field.decimals == 0 else 0.0
        if field.field_type == "L":
            return False
        if field.field_type == "D":
            return None
        return ""

    if field.field_type == "C":
        return text
    elif field.field_type in ("N", "F"):
        try:
            return float(text) if field.decimals > 0 else int(float(text))
        except ValueError:
            return 0
    elif field.field_type == "I":
        try:
            return int(float(text))
        except ValueError:
            return 0
    elif field.field_type in ("B", "Y"):
        try:
            return float(text)
        except ValueError:
            return 0.0
    elif field.field_type == "D":
        # Try ISO format first (yyyy-mm-dd), then yyyymmdd
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y"):
            try:
                dt = datetime.strptime(text, fmt)
                return dt.date() if isinstance(dt, datetime) else dt
            except ValueError:
                continue
        return None
    elif field.field_type == "L":
        return text.upper() in ("T", "Y", "1", "TRUE", "YES", ".T.")
    elif field.field_type == "M":
        return text
    return text


def _parse_json_value(val, field):
    """Convert a JSON value to the appropriate field type."""
    if val is None:
        if field.field_type in ("N", "F"):
            return 0 if field.decimals == 0 else 0.0
        if field.field_type == "L":
            return False
        return "" if field.field_type == "C" else None

    if field.field_type in ("N", "F", "I", "B", "Y"):
        try:
            if field.decimals > 0:
                return float(val)
            return int(float(val))
        except (ValueError, TypeError):
            return 0
    elif field.field_type == "L":
        if isinstance(val, bool):
            return val
        return str(val).upper() in ("T", "Y", "1", "TRUE", "YES")
    elif field.field_type == "D":
        if isinstance(val, str):
            return _parse_import_value(val, field)
        return None
    elif field.field_type == "C":
        return str(val)
    return str(val)


def _split_delimited(line, delimiter, qualifier):
    """Split a delimited line respecting string qualifiers."""
    values = []
    current = ""
    in_qualified = False
    i = 0

    while i < len(line):
        ch = line[i]
        if in_qualified:
            if ch == qualifier:
                if i + 1 < len(line) and line[i + 1] == qualifier:
                    current += qualifier
                    i += 2
                    continue
                in_qualified = False
            else:
                current += ch
        elif ch == qualifier:
            in_qualified = True
        elif ch == delimiter:
            values.append(current.strip())
            current = ""
        else:
            current += ch
        i += 1

    values.append(current.strip())
    return values
