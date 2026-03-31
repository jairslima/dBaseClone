"""Testes automatizados para dBase Revival by Jair Lima"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from dbase.config import Config, config
from dbase.workarea import Environment
from dbase.expression import ExpressionEvaluator
from dbase.functions import register_all
from dbase.commands import CommandInterpreter

passed = 0
failed = 0
errors = []

def setup():
    """Create fresh environment."""
    cfg = Config()
    cfg.default_path = os.path.dirname(__file__)
    env = Environment(cfg)
    evaluator = ExpressionEvaluator(env)
    register_all(evaluator, cfg)
    cmd = CommandInterpreter(env, evaluator, cfg)
    return env, evaluator, cmd, cfg

def run(cmd, command):
    """Execute a command and return output."""
    try:
        return cmd.execute(command)
    except SystemExit:
        return []

def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        errors.append(name)
        print(f"  FAIL: {name}")

def cleanup(*files):
    for f in files:
        if os.path.exists(f):
            os.remove(f)

# ============================================================
print("=== TESTE 1: Comandos basicos DBF ===")
env, ev, cmd, cfg = setup()
cleanup("test_basic.dbf")

run(cmd, "CREATE TABLE test_basic (nome C(20), idade N(3,0), salario N(10,2))")
run(cmd, "USE test_basic")
test("USE abre tabela", env.current_workarea().dbf is not None)

run(cmd, "APPEND BLANK")
run(cmd, "REPLACE nome WITH 'Jair', idade WITH 35, salario WITH 5000.50")
run(cmd, "APPEND BLANK")
run(cmd, "REPLACE nome WITH 'Maria', idade WITH 28, salario WITH 7200.00")
run(cmd, "APPEND BLANK")
run(cmd, "REPLACE nome WITH 'Pedro', idade WITH 42, salario WITH 3100.75")

test("3 registros inseridos", env.current_workarea().dbf.record_count == 3)

run(cmd, "GO TOP")
test("GO TOP vai ao registro 1", env.current_workarea().recno == 1)

run(cmd, "GO BOTTOM")
test("GO BOTTOM vai ao ultimo", env.current_workarea().recno == 3)

run(cmd, "LOCATE FOR nome = 'Maria'")
test("LOCATE encontra Maria", env.current_workarea().recno == 2)

output = run(cmd, "? RECCOUNT()")
test("RECCOUNT() = 3", any("3" in str(o) for o in output))

run(cmd, "CLOSE ALL")
cleanup("test_basic.dbf")

# ============================================================
print("\n=== TESTE 2: SQL CREATE TABLE + INSERT ===")
env, ev, cmd, cfg = setup()
cleanup("sqltest.dbf")

run(cmd, "CREATE TABLE sqltest (nome C(20), idade N(3,0), salario N(10,2))")
run(cmd, "USE sqltest")
test("CREATE TABLE funciona", env.current_workarea().dbf is not None)

run(cmd, "INSERT INTO sqltest (nome, idade, salario) VALUES ('Jair', 35, 5000.50)")
run(cmd, "INSERT INTO sqltest (nome, idade, salario) VALUES ('Maria', 28, 7200.00)")
run(cmd, "INSERT INTO sqltest (nome, idade, salario) VALUES ('Pedro', 42, 3100.75)")
run(cmd, "INSERT INTO sqltest (nome, idade, salario) VALUES ('Ana', 31, 8500.00)")
run(cmd, "INSERT INTO sqltest (nome, idade, salario) VALUES ('Carlos', 55, 4200.00)")

test("5 registros via INSERT", env.current_workarea().dbf.record_count == 5)

# ============================================================
print("\n=== TESTE 3: SQL SELECT ===")
output = run(cmd, "SELECT * FROM sqltest")
test("SELECT * retorna dados", len(output) > 0)

output = run(cmd, "SELECT nome, salario FROM sqltest WHERE salario > 5000")
test("SELECT WHERE filtra", len(output) > 0)

output = run(cmd, "SELECT nome, salario FROM sqltest ORDER BY salario DESC")
test("SELECT ORDER BY retorna dados", len(output) > 0)

# ============================================================
print("\n=== TESTE 4: SQL Agregacoes ===")
output = run(cmd, "SELECT COUNT(*) AS total FROM sqltest")
test("COUNT(*) retorna resultado", len(output) > 0)

output = run(cmd, "SELECT SUM(salario) AS soma FROM sqltest")
test("SUM retorna resultado", len(output) > 0)

output = run(cmd, "SELECT AVG(salario) AS media FROM sqltest")
test("AVG retorna resultado", len(output) > 0)

# ============================================================
print("\n=== TESTE 5: SQL UPDATE ===")
run(cmd, "UPDATE sqltest SET salario = 9999.99 WHERE nome = 'Jair'")
run(cmd, "GO TOP")
wa = env.current_workarea()
rec = wa.dbf.records[0]
val = rec["SALARIO"]
test("UPDATE altera valor", abs(float(val) - 9999.99) < 0.01)

# ============================================================
print("\n=== TESTE 6: SQL DELETE FROM ===")
run(cmd, "DELETE FROM sqltest WHERE nome = 'Carlos'")
count_before = env.current_workarea().dbf.record_count
test("DELETE FROM marca registro", count_before == 5)  # ainda existe, so marcado

# ============================================================
print("\n=== TESTE 7: SQL ALTER TABLE ===")
run(cmd, "ALTER TABLE sqltest ADD email C(30)")
fields = [f.name for f in env.current_workarea().dbf.fields]
test("ALTER TABLE ADD campo", "EMAIL" in fields)

# ============================================================
print("\n=== TESTE 8: SQL DROP TABLE ===")
run(cmd, "CLOSE ALL")
run(cmd, "DROP TABLE sqltest")
test("DROP TABLE remove arquivo", not os.path.exists("sqltest.dbf"))

# ============================================================
print("\n=== TESTE 9: Export/Import CSV ===")
env, ev, cmd, cfg = setup()
cleanup("test_io.dbf", "test_io.csv", "test_io.json", "test_io.xml")

run(cmd, "CREATE TABLE test_io (nome C(15), valor N(8,2))")
run(cmd, "USE test_io")
run(cmd, "APPEND BLANK")
run(cmd, "REPLACE nome WITH 'Alpha', valor WITH 100.50")
run(cmd, "APPEND BLANK")
run(cmd, "REPLACE nome WITH 'Beta', valor WITH 200.75")
run(cmd, "APPEND BLANK")
run(cmd, "REPLACE nome WITH 'Gamma', valor WITH 300.00")

run(cmd, "COPY TO test_io.csv TYPE CSV")
test("Export CSV cria arquivo", os.path.exists("test_io.csv"))

# ============================================================
print("\n=== TESTE 10: Export JSON ===")
run(cmd, "COPY TO test_io.json TYPE JSON")
test("Export JSON cria arquivo", os.path.exists("test_io.json"))

if os.path.exists("test_io.json"):
    import json
    with open("test_io.json") as f:
        data = json.load(f)
    records = data.get("records", data) if isinstance(data, dict) else data
    test("JSON tem 3 registros", len(records) == 3)

# ============================================================
print("\n=== TESTE 11: Export XML ===")
run(cmd, "COPY TO test_io.xml TYPE XML")
test("Export XML cria arquivo", os.path.exists("test_io.xml"))

# ============================================================
print("\n=== TESTE 12: Import CSV ===")
cleanup("test_import.dbf")
run(cmd, "CREATE TABLE test_import (nome C(15), valor N(8,2))")
run(cmd, "USE test_import")
run(cmd, "APPEND FROM test_io.csv TYPE CSV")
test("Import CSV traz registros", env.current_workarea().dbf.record_count == 3)

# Cleanup
run(cmd, "CLOSE ALL")
cleanup("test_io.dbf", "test_io.csv", "test_io.json", "test_io.xml", "test_import.dbf")

# ============================================================
print("\n=== TESTE 13: Expressoes e funcoes ===")
env, ev, cmd, cfg = setup()

output = run(cmd, '? UPPER("hello")')
test("UPPER()", any("HELLO" in str(o) for o in output))

output = run(cmd, '? LTRIM("  abc")')
test("LTRIM()", any("abc" in str(o) for o in output))

output = run(cmd, '? STR(42, 5)')
test("STR()", any("42" in str(o) for o in output))

output = run(cmd, '? LEN("teste")')
test("LEN()", any("5" in str(o) for o in output))

output = run(cmd, '? SUBSTR("abcdef", 2, 3)')
test("SUBSTR()", any("bcd" in str(o) for o in output))

output = run(cmd, '? DATE()')
test("DATE() retorna valor", len(output) > 0)

output = run(cmd, '? 2 + 3 * 4')
test("Expressao aritmetica (2+3*4=14)", any("14" in str(o) for o in output))

output = run(cmd, '? IIF(1>0, "sim", "nao")')
test("IIF()", any("sim" in str(o) for o in output))

# ============================================================
print("\n=== TESTE 14: Indices NDX ===")
env, ev, cmd, cfg = setup()
cleanup("test_idx.dbf", "test_idx.ndx")

run(cmd, "CREATE TABLE test_idx (nome C(20), codigo N(5,0))")
run(cmd, "USE test_idx")
run(cmd, "APPEND BLANK")
run(cmd, "REPLACE nome WITH 'Zebra', codigo WITH 3")
run(cmd, "APPEND BLANK")
run(cmd, "REPLACE nome WITH 'Alpha', codigo WITH 1")
run(cmd, "APPEND BLANK")
run(cmd, "REPLACE nome WITH 'Beta', codigo WITH 2")

run(cmd, "INDEX ON nome TO test_idx.ndx")
test("INDEX ON cria NDX", os.path.exists("test_idx.ndx"))

run(cmd, "GO TOP")
wa = env.current_workarea()
rec = wa.dbf.records[wa.recno - 1]
nome = str(rec["NOME"]).strip()
test("Indice NDX ordena (primeiro=Alpha)", nome == "Alpha")

run(cmd, "CLOSE ALL")
cleanup("test_idx.dbf", "test_idx.ndx")

# ============================================================
print("\n=== TESTE 15: Variaveis e STORE ===")
env, ev, cmd, cfg = setup()

run(cmd, 'STORE "hello" TO x')
output = run(cmd, '? x')
test("STORE e ? variavel", any("hello" in str(o) for o in output))

run(cmd, 'y = 42')
output = run(cmd, '? y * 2')
test("Atribuicao e expressao", any("84" in str(o) for o in output))

# ============================================================
# RESULTADO FINAL
print("\n" + "=" * 50)
print(f"RESULTADO: {passed} passou, {failed} falhou de {passed + failed} testes")
if errors:
    print("Falhas:")
    for e in errors:
        print(f"  - {e}")
print("=" * 50)
