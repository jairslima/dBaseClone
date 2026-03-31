* ================================================
* dBase Revival by Jair Lima - Demo Program
* ================================================

CLEAR

? "=== dBase Revival by Jair Lima ==="
? "    Demonstracao de funcionalidades"
? ""

* Demonstracao de funcoes e expressoes

? ""
? "Versao: " + VERSION()
? "Data:   " + DTOC(DATE())
? "Hora:   " + TIME()
? "SO:     " + OS()
? ""

? "=== Funcoes de String ==="
? "UPPER('hello')     = " + UPPER("hello")
? "LOWER('WORLD')     = " + LOWER("WORLD")
? "SUBSTR('dBase',1,4)= " + SUBSTR("dBase", 1, 4)
? "PADL('123',8,'0')  = " + PADL("123", 8, "0")
? "REPLICATE('=-',20) = " + REPLICATE("=-", 20)
? ""

? "=== Funcoes Matematicas ==="
? "SQRT(144)          = ", SQRT(144)
? "ROUND(3.14159,2)   = ", ROUND(3.14159, 2)
? "ABS(-42)           = ", ABS(-42)
? "PI()               = ", PI()
? ""

? "=== Funcoes de Data ==="
? "DATE()             = ", DATE()
? "YEAR(DATE())       = ", YEAR(DATE())
? "MONTH(DATE())      = ", MONTH(DATE())
? "DAY(DATE())        = ", DAY(DATE())
? "CDOW(DATE())       = " + CDOW(DATE())
? "CMONTH(DATE())     = " + CMONTH(DATE())
? ""

? "=== Expressoes Logicas ==="
? "3 > 2              = ", 3 > 2
? ".T. .AND. .F.      = ", .T. .AND. .F.
? ".T. .OR. .F.       = ", .T. .OR. .F.
? "'abc' $ 'xabcx'    = ", "abc" $ "xabcx"
? "IIF(1>0,'S','N')   = " + IIF(1 > 0, "Sim", "Nao")
? "BETWEEN(5,1,10)    = ", BETWEEN(5, 1, 10)
? ""

? "=== Variaveis ==="
nTotal = 100
cNome = "dBase Revival"
lAtivo = .T.
dHoje = DATE()
? "nTotal = ", nTotal
? "cNome  = " + cNome
? "lAtivo = ", lAtivo
? "dHoje  = ", dHoje
? ""

? "=== Demonstracao completa! ==="
? "Digite HELP no prompt para ver todos os comandos."
?

RETURN
