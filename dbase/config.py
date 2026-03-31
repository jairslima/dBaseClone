"""dBase Revival by Jair Lima - Configuration and SET commands state."""

import os
from datetime import date


class Config:
    """Global configuration / SET state for the dBase environment."""

    def __init__(self):
        self.talk = True
        self.echo = False
        self.exact = False
        self.deleted = False
        self.exclusive = True
        self.confirm = True
        self.safety = True
        self.bell = True
        self.status = True
        self.scoreboard = True
        self.escape = True
        self.carry = False
        self.century = False
        self.near = False
        self.unique = False
        self.softseek = False
        self.console = True
        self.printer = False
        self.alternate = False
        self.debug = False
        self.step = False
        self.heading = True
        self.intensity = True
        self.wrap = False
        self.fixed = False

        self.date_format = "AMERICAN"
        self.decimals = 2
        self.epoch = 1900
        self.margin = 0
        self.memowidth = 50
        self.typeahead = 20

        self.default_path = os.getcwd()
        self.search_path = ""
        self.alternate_file = ""
        self.print_file = ""
        self.color = "W/N,N/W,W/N,W/N,W/N"

        self.filter_expr = {}
        self.relation = {}
        self.index_order = {}

        self.delimiter = ":"
        self.delimiters_on = False
        self.separator = ","

    def get_date_format_str(self):
        """Return the date format string for the current SET DATE setting."""
        formats = {
            "AMERICAN": "MM/DD/YY",
            "ANSI": "YY.MM.DD",
            "BRITISH": "DD/MM/YY",
            "FRENCH": "DD/MM/YY",
            "GERMAN": "DD.MM.YY",
            "ITALIAN": "DD-MM-YY",
            "JAPAN": "YY/MM/DD",
            "USA": "MM-DD-YY",
            "MDY": "MM/DD/YY",
            "DMY": "DD/MM/YY",
            "YMD": "YY/MM/DD",
        }
        fmt = formats.get(self.date_format.upper(), "MM/DD/YY")
        if self.century:
            fmt = fmt.replace("YY", "YYYY")
        return fmt

    def format_date(self, d):
        """Format a date value according to current SET DATE / SET CENTURY."""
        if d is None:
            return "  /  /  "
        if isinstance(d, str):
            return d
        yy = d.year if self.century else d.year % 100
        fmt = self.date_format.upper()
        if fmt in ("AMERICAN", "USA", "MDY"):
            sep = "/" if fmt in ("AMERICAN", "MDY") else "-"
            return f"{d.month:02d}{sep}{d.day:02d}{sep}{yy:04d}" if self.century else f"{d.month:02d}{sep}{d.day:02d}{sep}{yy:02d}"
        elif fmt in ("BRITISH", "FRENCH", "DMY"):
            sep = "/"
            return f"{d.day:02d}{sep}{d.month:02d}{sep}{yy:04d}" if self.century else f"{d.day:02d}{sep}{d.month:02d}{sep}{yy:02d}"
        elif fmt == "GERMAN":
            return f"{d.day:02d}.{d.month:02d}.{yy:04d}" if self.century else f"{d.day:02d}.{d.month:02d}.{yy:02d}"
        elif fmt == "ITALIAN":
            return f"{d.day:02d}-{d.month:02d}-{yy:04d}" if self.century else f"{d.day:02d}-{d.month:02d}-{yy:02d}"
        elif fmt in ("ANSI",):
            return f"{yy:04d}.{d.month:02d}.{d.day:02d}" if self.century else f"{yy:02d}.{d.month:02d}.{d.day:02d}"
        elif fmt in ("JAPAN", "YMD"):
            return f"{yy:04d}/{d.month:02d}/{d.day:02d}" if self.century else f"{yy:02d}/{d.month:02d}/{d.day:02d}"
        else:
            return f"{d.month:02d}/{d.day:02d}/{yy:02d}"

    def parse_date(self, s):
        """Parse a date string according to current SET DATE format."""
        if not s or not s.strip():
            return None
        s = s.strip().strip("{").strip("}")
        import re
        parts = re.split(r"[/.\-]", s)
        if len(parts) != 3:
            return None
        try:
            parts = [int(p) for p in parts]
        except ValueError:
            return None

        fmt = self.date_format.upper()
        if fmt in ("AMERICAN", "USA", "MDY"):
            mm, dd, yy = parts
        elif fmt in ("BRITISH", "FRENCH", "GERMAN", "ITALIAN", "DMY"):
            dd, mm, yy = parts
        elif fmt in ("ANSI", "JAPAN", "YMD"):
            yy, mm, dd = parts
        else:
            mm, dd, yy = parts

        if yy < 100:
            if yy >= (self.epoch % 100):
                yy += (self.epoch // 100) * 100
            else:
                yy += ((self.epoch // 100) + 1) * 100

        try:
            return date(yy, mm, dd)
        except ValueError:
            return None


config = Config()
