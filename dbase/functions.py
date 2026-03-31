"""dBase Revival by Jair Lima - Built-in function library.

Complete set of xBase built-in functions including string, numeric,
date, conversion, and utility functions.
"""

import math
import os
import time
from datetime import date, datetime, timedelta


def register_all(evaluator, config):
    """Register all built-in functions with the expression evaluator."""
    funcs = {}

    # ===== STRING FUNCTIONS =====
    def fn_alltrim(s):
        return str(s).strip()
    funcs["ALLTRIM"] = fn_alltrim

    def fn_ltrim(s):
        return str(s).lstrip()
    funcs["LTRIM"] = fn_ltrim

    def fn_rtrim(s):
        return str(s).rstrip()
    funcs["RTRIM"] = fn_rtrim
    funcs["TRIM"] = fn_rtrim

    def fn_upper(s):
        return str(s).upper()
    funcs["UPPER"] = fn_upper

    def fn_lower(s):
        return str(s).lower()
    funcs["LOWER"] = fn_lower

    def fn_proper(s):
        return str(s).title()
    funcs["PROPER"] = fn_proper

    def fn_substr(s, start, length=None):
        s = str(s)
        start = int(start) - 1
        if start < 0:
            start = 0
        if length is not None:
            return s[start:start + int(length)]
        return s[start:]
    funcs["SUBSTR"] = fn_substr

    def fn_left(s, n):
        return str(s)[:int(n)]
    funcs["LEFT"] = fn_left

    def fn_right(s, n):
        s = str(s)
        n = int(n)
        return s[-n:] if n > 0 else ""
    funcs["RIGHT"] = fn_right

    def fn_at(search, target, start=1):
        s = str(target)
        search = str(search)
        start = int(start) - 1
        pos = s.find(search, start)
        return pos + 1 if pos >= 0 else 0
    funcs["AT"] = fn_at

    def fn_rat(search, target, occurrence=1):
        s = str(target)
        search = str(search)
        pos = s.rfind(search)
        return pos + 1 if pos >= 0 else 0
    funcs["RAT"] = fn_rat

    def fn_occurs(search, target):
        return str(target).count(str(search))
    funcs["OCCURS"] = fn_occurs

    def fn_len(s):
        return len(str(s))
    funcs["LEN"] = fn_len

    def fn_space(n):
        return " " * int(n)
    funcs["SPACE"] = fn_space

    def fn_replicate(s, n):
        return str(s) * int(n)
    funcs["REPLICATE"] = fn_replicate

    def fn_stuff(s, start, delete, insert):
        s = str(s)
        start = int(start) - 1
        delete = int(delete)
        insert = str(insert)
        return s[:start] + insert + s[start + delete:]
    funcs["STUFF"] = fn_stuff

    def fn_strtran(s, search, replace="", start=1, count=-1):
        s = str(s)
        search = str(search)
        replace = str(replace)
        if int(count) < 0:
            return s.replace(search, replace)
        return s.replace(search, replace, int(count))
    funcs["STRTRAN"] = fn_strtran

    def fn_padl(s, n, c=" "):
        return str(s).rjust(int(n), str(c)[0] if c else " ")
    funcs["PADL"] = fn_padl

    def fn_padr(s, n, c=" "):
        return str(s).ljust(int(n), str(c)[0] if c else " ")
    funcs["PADR"] = fn_padr

    def fn_padc(s, n, c=" "):
        return str(s).center(int(n), str(c)[0] if c else " ")
    funcs["PADC"] = fn_padc

    def fn_chr(n):
        return chr(int(n))
    funcs["CHR"] = fn_chr

    def fn_asc(s):
        s = str(s)
        return ord(s[0]) if s else 0
    funcs["ASC"] = fn_asc

    def fn_isalpha(s):
        s = str(s)
        return s[0].isalpha() if s else False
    funcs["ISALPHA"] = fn_isalpha

    def fn_isdigit(s):
        s = str(s)
        return s[0].isdigit() if s else False
    funcs["ISDIGIT"] = fn_isdigit

    def fn_isupper(s):
        s = str(s)
        return s[0].isupper() if s else False
    funcs["ISUPPER"] = fn_isupper

    def fn_islower(s):
        s = str(s)
        return s[0].islower() if s else False
    funcs["ISLOWER"] = fn_islower

    def fn_like(pattern, s):
        """SQL LIKE pattern matching."""
        import fnmatch
        pattern = str(pattern).replace("%", "*").replace("_", "?")
        return fnmatch.fnmatch(str(s), pattern)
    funcs["LIKE"] = fn_like

    def fn_transform(val, picture=""):
        """TRANSFORM() with picture formatting."""
        picture = str(picture)
        if not picture:
            return str(val)
        if isinstance(val, (int, float)):
            result = ""
            for ch in picture:
                if ch == "9" or ch == "#":
                    result += "N"
                elif ch == ".":
                    result += "."
                elif ch == ",":
                    result += ","
                else:
                    result += ch
            s = f"{val:,.{picture.count('9') if '.' in picture else 0}f}" if "," in picture else str(val)
            return s
        return str(val)
    funcs["TRANSFORM"] = fn_transform

    # ===== NUMERIC FUNCTIONS =====
    def fn_abs(n):
        return abs(float(n))
    funcs["ABS"] = fn_abs

    def fn_int(n):
        return int(float(n))
    funcs["INT"] = fn_int

    def fn_round(n, d=0):
        return round(float(n), int(d))
    funcs["ROUND"] = fn_round

    def fn_ceiling(n):
        return math.ceil(float(n))
    funcs["CEILING"] = fn_ceiling

    def fn_floor(n):
        return math.floor(float(n))
    funcs["FLOOR"] = fn_floor

    def fn_sqrt(n):
        return math.sqrt(float(n))
    funcs["SQRT"] = fn_sqrt

    def fn_exp(n):
        return math.exp(float(n))
    funcs["EXP"] = fn_exp

    def fn_log(n):
        return math.log(float(n))
    funcs["LOG"] = fn_log

    def fn_log10(n):
        return math.log10(float(n))
    funcs["LOG10"] = fn_log10

    def fn_mod(a, b):
        return float(a) % float(b)
    funcs["MOD"] = fn_mod

    def fn_min(a, b):
        return min(a, b)
    funcs["MIN"] = fn_min

    def fn_max(a, b):
        return max(a, b)
    funcs["MAX"] = fn_max

    def fn_sign(n):
        n = float(n)
        if n > 0:
            return 1
        elif n < 0:
            return -1
        return 0
    funcs["SIGN"] = fn_sign

    def fn_pi():
        return math.pi
    funcs["PI"] = fn_pi

    def fn_sin(n):
        return math.sin(float(n))
    funcs["SIN"] = fn_sin

    def fn_cos(n):
        return math.cos(float(n))
    funcs["COS"] = fn_cos

    def fn_tan(n):
        return math.tan(float(n))
    funcs["TAN"] = fn_tan

    def fn_asin(n):
        return math.asin(float(n))
    funcs["ASIN"] = fn_asin

    def fn_acos(n):
        return math.acos(float(n))
    funcs["ACOS"] = fn_acos

    def fn_atan(n):
        return math.atan(float(n))
    funcs["ATAN"] = fn_atan
    funcs["ATN"] = fn_atan

    def fn_dtor(n):
        return math.radians(float(n))
    funcs["DTOR"] = fn_dtor

    def fn_rtod(n):
        return math.degrees(float(n))
    funcs["RTOD"] = fn_rtod

    def fn_rand(seed=None):
        import random
        if seed is not None:
            random.seed(int(seed))
        return random.random()
    funcs["RAND"] = fn_rand

    # ===== CONVERSION FUNCTIONS =====
    def fn_val(s):
        s = str(s).strip()
        if not s:
            return 0
        try:
            num = ""
            for ch in s:
                if ch.isdigit() or ch in ".-+":
                    num += ch
                else:
                    break
            return float(num) if "." in num else int(num)
        except ValueError:
            return 0
    funcs["VAL"] = fn_val

    def fn_str(n, length=10, decimals=0):
        n = float(n) if not isinstance(n, (int, float)) else n
        length = int(length)
        decimals = int(decimals)
        if decimals > 0:
            result = f"{n:.{decimals}f}"
        else:
            result = f"{int(n)}"
        if len(result) > length:
            return "*" * length
        return result.rjust(length)
    funcs["STR"] = fn_str

    def fn_strzero(n, length=10, decimals=0):
        n = float(n) if not isinstance(n, (int, float)) else n
        length = int(length)
        decimals = int(decimals)
        if decimals > 0:
            result = f"{n:0{length}.{decimals}f}"
        else:
            result = f"{int(n):0{length}d}"
        return result[:length]
    funcs["STRZERO"] = fn_strzero

    def fn_dtoc(d):
        if d is None:
            return "  /  /  "
        if isinstance(d, date):
            return config.format_date(d)
        return str(d)
    funcs["DTOC"] = fn_dtoc

    def fn_dtos(d):
        if d is None:
            return "        "
        if isinstance(d, date):
            return f"{d.year:04d}{d.month:02d}{d.day:02d}"
        return str(d)
    funcs["DTOS"] = fn_dtos

    def fn_ctod(s):
        return config.parse_date(str(s))
    funcs["CTOD"] = fn_ctod

    def fn_stod(s):
        s = str(s).strip()
        if len(s) == 8:
            try:
                return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
            except ValueError:
                pass
        return None
    funcs["STOD"] = fn_stod

    def fn_ttoc(t, fmt=1):
        if isinstance(t, datetime):
            if int(fmt) == 1:
                return t.strftime("%m/%d/%Y %H:%M:%S")
            return t.strftime("%Y%m%d%H%M%S")
        return str(t) if t else ""
    funcs["TTOC"] = fn_ttoc

    def fn_ttod(t):
        if isinstance(t, datetime):
            return t.date()
        return t
    funcs["TTOD"] = fn_ttod

    # ===== DATE FUNCTIONS =====
    def fn_date():
        return date.today()
    funcs["DATE"] = fn_date

    def fn_time():
        return time.strftime("%H:%M:%S")
    funcs["TIME"] = fn_time

    def fn_datetime():
        return datetime.now()
    funcs["DATETIME"] = fn_datetime

    def fn_year(d):
        if isinstance(d, (date, datetime)):
            return d.year
        return 0
    funcs["YEAR"] = fn_year

    def fn_month(d):
        if isinstance(d, (date, datetime)):
            return d.month
        return 0
    funcs["MONTH"] = fn_month

    def fn_day(d):
        if isinstance(d, (date, datetime)):
            return d.day
        return 0
    funcs["DAY"] = fn_day

    def fn_dow(d, first_day=1):
        if isinstance(d, (date, datetime)):
            # dBase DOW: Sunday=1 ... Saturday=7
            return d.isoweekday() % 7 + 1
        return 0
    funcs["DOW"] = fn_dow

    def fn_cdow(d):
        days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        if isinstance(d, (date, datetime)):
            return days[d.isoweekday() % 7]
        return ""
    funcs["CDOW"] = fn_cdow

    def fn_cmonth(d):
        months = ["", "January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
        if isinstance(d, (date, datetime)):
            return months[d.month]
        return ""
    funcs["CMONTH"] = fn_cmonth

    def fn_gomonth(d, months):
        if isinstance(d, (date, datetime)):
            m = d.month + int(months)
            y = d.year
            while m > 12:
                m -= 12
                y += 1
            while m < 1:
                m += 12
                y -= 1
            import calendar
            max_day = calendar.monthrange(y, m)[1]
            return date(y, m, min(d.day, max_day))
        return d
    funcs["GOMONTH"] = fn_gomonth

    def fn_elapsed(d1, d2):
        if isinstance(d1, date) and isinstance(d2, date):
            return abs((d2 - d1).days)
        return 0
    funcs["ELAPSED"] = fn_elapsed

    # ===== LOGIC / UTILITY FUNCTIONS =====
    def fn_iif(cond, true_val, false_val):
        if isinstance(cond, bool):
            return true_val if cond else false_val
        if isinstance(cond, (int, float)):
            return true_val if cond != 0 else false_val
        if isinstance(cond, str):
            return true_val if cond.strip() else false_val
        return true_val if cond else false_val
    funcs["IIF"] = fn_iif

    def fn_between(val, low, high):
        return low <= val <= high
    funcs["BETWEEN"] = fn_between

    def fn_inlist(val, *items):
        return val in items
    funcs["INLIST"] = fn_inlist

    def fn_empty(val):
        if val is None:
            return True
        if isinstance(val, bool):
            return not val
        if isinstance(val, (int, float)):
            return val == 0
        if isinstance(val, str):
            return val.strip() == ""
        if isinstance(val, date):
            return False
        return True
    funcs["EMPTY"] = fn_empty

    def fn_vartype(val):
        if val is None:
            return "X"
        if isinstance(val, bool):
            return "L"
        if isinstance(val, int):
            return "N"
        if isinstance(val, float):
            return "N"
        if isinstance(val, str):
            return "C"
        if isinstance(val, date):
            return "D"
        if isinstance(val, datetime):
            return "T"
        return "U"
    funcs["VARTYPE"] = fn_vartype

    def fn_nvl(val, default):
        return default if val is None or (isinstance(val, str) and val.strip() == "") else val
    funcs["NVL"] = fn_nvl

    def fn_evl(val, default):
        if val is None:
            return default
        if isinstance(val, str) and val.strip() == "":
            return default
        if isinstance(val, (int, float)) and val == 0:
            return default
        return val
    funcs["EVL"] = fn_evl

    # ===== FILE FUNCTIONS =====
    def fn_file(filename):
        return os.path.exists(str(filename))
    funcs["FILE"] = fn_file

    def fn_curdir():
        return os.getcwd()
    funcs["CURDIR"] = fn_curdir

    def fn_fullpath(filename):
        return os.path.abspath(str(filename))
    funcs["FULLPATH"] = fn_fullpath

    def fn_justfname(path):
        return os.path.basename(str(path))
    funcs["JUSTFNAME"] = fn_justfname

    def fn_justpath(path):
        return os.path.dirname(str(path))
    funcs["JUSTPATH"] = fn_justpath

    def fn_justext(path):
        return os.path.splitext(str(path))[1].lstrip(".")
    funcs["JUSTEXT"] = fn_justext

    def fn_juststem(path):
        return os.path.splitext(os.path.basename(str(path)))[0]
    funcs["JUSTSTEM"] = fn_juststem

    def fn_addbs(path):
        path = str(path)
        if not path.endswith(os.sep):
            return path + os.sep
        return path
    funcs["ADDBS"] = fn_addbs

    # ===== MISCELLANEOUS =====
    def fn_seconds():
        now = datetime.now()
        return now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1000000
    funcs["SECONDS"] = fn_seconds

    def fn_sys(n, *args):
        n = int(n)
        if n == 0:
            return "dBase Revival by Jair Lima"
        if n == 1:
            return datetime.now().strftime("%Y%m%d")
        if n == 2:
            return str(int(fn_seconds()))
        if n == 3:
            return os.getcwd()
        if n == 5:
            return config.default_path
        if n == 10:
            return str(args[0]) if args else ""
        if n == 2015:
            return os.name
        return ""
    funcs["SYS"] = fn_sys

    def fn_version():
        return "dBase Revival by Jair Lima 1.0"
    funcs["VERSION"] = fn_version

    def fn_os():
        import platform
        return f"{platform.system()} {platform.release()}"
    funcs["OS"] = fn_os

    def fn_memory(n=0):
        return 999999
    funcs["MEMORY"] = fn_memory

    def fn_row():
        return 0
    funcs["ROW"] = fn_row

    def fn_col():
        return 0
    funcs["COL"] = fn_col

    def fn_lastkey():
        return 0
    funcs["LASTKEY"] = fn_lastkey

    def fn_readkey():
        return 0
    funcs["READKEY"] = fn_readkey

    def fn_inkey(timeout=0):
        return 0
    funcs["INKEY"] = fn_inkey

    def fn_messagebox(msg, flags=0, title=""):
        print(str(msg))
        return 1
    funcs["MESSAGEBOX"] = fn_messagebox

    evaluator.register_functions(funcs)
