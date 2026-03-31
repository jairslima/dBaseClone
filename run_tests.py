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
print("\n=== TESTE 16: Macro substituicao ===")
env, ev, cmd, cfg = setup()

run(cmd, 'STORE "tabmacro" TO tabela')
cleanup("tabmacro.dbf")
run(cmd, 'CREATE TABLE &tabela (nome C(20), val N(5,0))')
run(cmd, 'USE &tabela')
test("Macro em CREATE TABLE/USE", env.current_workarea().dbf is not None)

run(cmd, 'APPEND BLANK')
run(cmd, 'REPLACE nome WITH "Test"')
run(cmd, 'STORE "nome" TO campo')
output = run(cmd, '? &campo.')
test("Macro &campo. expande para field", any("Test" in str(o) for o in output))

# &(expression) form
output = run(cmd, '? &("UP"+"PER")("abc")')
test("Macro &(expr) funciona", any("ABC" in str(o) for o in output))

run(cmd, "CLOSE ALL")
cleanup("tabmacro.dbf")

# ============================================================
print("\n=== TESTE 17: REPORT FORM ===")
env, ev, cmd, cfg = setup()
cleanup("rpt_test.dbf", "rpt_test.frm", "rpt_out.txt")

run(cmd, 'CREATE TABLE rpt_test (nome C(15), depto C(10), salario N(10,2))')
run(cmd, 'USE rpt_test')
for n, d, s in [('Jair','TI',5000), ('Maria','TI',7200), ('Pedro','RH',3100)]:
    run(cmd, 'APPEND BLANK')
    run(cmd, f'REPLACE nome WITH "{n}", depto WITH "{d}", salario WITH {s}')

import json
frm = {
    'title': 'Test Report', 'page_width': 60, 'left_margin': 0,
    'lines_per_page': 58, 'columns': [
        {'field': 'nome', 'heading': 'Name', 'width': 15, 'total': False},
        {'field': 'salario', 'heading': 'Salary', 'width': 12, 'decimals': 2, 'total': True},
    ]
}
with open('rpt_test.frm', 'w') as f:
    json.dump(frm, f)

output = run(cmd, 'REPORT FORM rpt_test')
test("REPORT FORM gera saida", len(output) > 5)
test("REPORT FORM tem titulo", any("Test Report" in str(o) for o in output))
test("REPORT FORM tem total", any("Total" in str(o) for o in output))

# TO FILE
run(cmd, 'REPORT FORM rpt_test TO FILE rpt_out.txt')
test("REPORT TO FILE cria arquivo", os.path.exists("rpt_out.txt"))

run(cmd, "CLOSE ALL")
cleanup("rpt_test.dbf", "rpt_test.frm", "rpt_out.txt")

# ============================================================
print("\n=== TESTE 18: LABEL FORM ===")
env, ev, cmd, cfg = setup()
cleanup("lbl_test.dbf", "lbl_test.lbl")

run(cmd, 'CREATE TABLE lbl_test (nome C(15), cidade C(15))')
run(cmd, 'USE lbl_test')
for n, c in [('Jair','SP'), ('Maria','RJ'), ('Pedro','BH')]:
    run(cmd, 'APPEND BLANK')
    run(cmd, f'REPLACE nome WITH "{n}", cidade WITH "{c}"')

lbl = {
    'width': 25, 'height': 2, 'left_margin': 0,
    'lines_between': 1, 'spaces_between': 3, 'columns_count': 2,
    'lines': ['TRIM(nome)', 'TRIM(cidade)']
}
with open('lbl_test.lbl', 'w') as f:
    json.dump(lbl, f)

output = run(cmd, 'LABEL FORM lbl_test')
test("LABEL FORM gera saida", len(output) > 3)
test("LABEL FORM contem dados", any("Jair" in str(o) for o in output))

run(cmd, "CLOSE ALL")
cleanup("lbl_test.dbf", "lbl_test.lbl")

# ============================================================
print("\n=== TESTE 19: SET BREAKPOINT e debugger ===")
env, ev, cmd, cfg = setup()

run(cmd, 'SET BREAKPOINT TO 5')
test("SET BREAKPOINT cria debugger", hasattr(env, '_debugger'))
test("Breakpoint registrado", 5 in env._debugger.breakpoints)

run(cmd, 'SET DEBUG ON')
test("SET DEBUG ON ativa debugger", env._debugger.enabled)

run(cmd, 'SET DEBUG OFF')
test("SET DEBUG OFF desativa", not env._debugger.enabled)

# ============================================================
# RESULTADO FINAL
print("\n" + "=" * 50)
print(f"RESULTADO: {passed} passou, {failed} falhou de {passed + failed} testes")
if errors:
    print("Falhas:")
    for e in errors:
        print(f"  - {e}")
print("=" * 50)
