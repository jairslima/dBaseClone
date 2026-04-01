# dBase Revival by Jair Lima

Clone funcional do dBASE classico para terminal, com suporte a indices NDX, NTX, CDX e MDX, SQL e import/export multi-formato.

## Stack e dependencias

- **Linguagem:** Python 3.8+
- **Dependencias:** `windows-curses` (apenas no Windows, para BROWSE com curses)
- **Sem dependencias externas** para funcionalidades core (DBF, indices, expressoes, comandos, SQL, I/O)

## Estrutura de pastas

```
dBaseClone/
  run.py                     # Launcher
  run_tests.py               # Suite de testes automatizados (48 testes)
  setup.py                   # Instalacao pip
  requirements.txt           # Dependencias
  demo.prg                   # Programa de demonstracao
  dbase/
    __init__.py              # Versao e metadados
    main.py                  # REPL (dot prompt), entry point
    config.py                # Configuracoes SET e formatacao
    dbf.py                   # Motor DBF (leitura/escrita .dbf)
    expression.py            # Parser e avaliador de expressoes xBase
    functions.py             # 100+ funcoes built-in
    workarea.py              # Work areas e gerenciamento de ambiente
    commands.py              # Interpretador de comandos (80+ comandos)
    interpreter.py           # Interpretador PRG (linguagem de programacao)
    sql.py                   # Motor SQL (SELECT, INSERT, UPDATE, DELETE, DDL)
    io_formats.py            # Import/Export (CSV, JSON, XML, SDF, DELIMITED, XLS)
    reports.py               # REPORT FORM e LABEL FORM engine
    debugger.py              # Debugger interativo para PRG
    compiler.py              # Compilador PRG para .exe standalone
    indexes/
      __init__.py
      ndx.py                 # Indice NDX (dBASE III original)
      ntx.py                 # Indice NTX (Clipper)
      cdx.py                 # Indice CDX (FoxPro compound)
      mdx.py                 # Indice MDX (dBASE IV compound)
    ui/
      __init__.py
      browse.py              # Interface BROWSE (curses + fallback texto)
```

## Comandos essenciais

```bash
# Executar o REPL (dot prompt)
python run.py

# Executar um arquivo .PRG
python run.py programa.prg

# Rodar testes automatizados
python run_tests.py

# Instalar como pacote
pip install -e .

# Apos instalacao, executar diretamente
dbase
dbase programa.prg
```

## Funcionalidades implementadas

### Comandos de banco de dados
USE, APPEND BLANK, APPEND FROM, REPLACE, DELETE, RECALL, PACK, ZAP, CREATE, COPY TO, COPY STRUCTURE, SORT

### Navegacao
GO TOP/BOTTOM/n, SKIP, LOCATE/CONTINUE, SEEK, FIND

### Exibicao
?, ??, LIST, DISPLAY, BROWSE (curses), EDIT, DISPLAY STRUCTURE/STATUS/MEMORY

### Indices (4 formatos)
- **NDX** (dBASE III): INDEX ON expr TO file.ndx
- **NTX** (Clipper): INDEX ON expr TO file.ntx TYPE NTX [DESCENDING] [FOR cond]
- **CDX** (FoxPro): INDEX ON expr TAG tagname [OF file.cdx] [UNIQUE] [FOR cond]
- **MDX** (dBASE IV): INDEX ON expr TO file.mdx TYPE MDX TAG tagname
- SET INDEX TO, SET ORDER TO, REINDEX

### SQL
- **SELECT** [DISTINCT] fields|* FROM table [alias] [JOIN ...] [WHERE ...] [GROUP BY ...] [HAVING ...] [ORDER BY ...] [LIMIT n] [OFFSET n] [INTO TABLE|CURSOR]
- **INSERT INTO** table (fields) VALUES (values) | INSERT INTO table FROM SELECT ...
- **UPDATE** table SET field=expr [, ...] [WHERE ...]
- **DELETE FROM** table [WHERE ...]
- **CREATE TABLE** name (field type(len[,dec]) [, ...])
- **DROP TABLE** name
- **ALTER TABLE** name ADD|DROP field
- Funcoes agregadas: COUNT, SUM, AVG, MIN, MAX
- Funcoes escalares: UPPER, LOWER, TRIM, LTRIM, RTRIM, SUBSTR, LEN

### Import/Export (6 formatos)
- **CSV**: COPY TO file.csv TYPE CSV / APPEND FROM file.csv TYPE CSV
- **JSON**: COPY TO file.json TYPE JSON / APPEND FROM file.json TYPE JSON
- **XML**: COPY TO file.xml TYPE XML / APPEND FROM file.xml TYPE XML
- **SDF**: COPY TO file.sdf TYPE SDF / APPEND FROM file.sdf TYPE SDF
- **DELIMITED**: COPY TO file.txt TYPE DELIMITED [WITH char] / APPEND FROM ...
- **XLS**: COPY TO file.xls TYPE XLS / APPEND FROM file.xls TYPE XLS

### Agregacao
COUNT, SUM, AVERAGE

### Variaveis
STORE/=, PUBLIC, PRIVATE, RELEASE, DECLARE (arrays)

### Report e Label
- **REPORT FORM** file [TO FILE f] [FOR cond] [WHILE cond] [HEADING text] [PLAIN] [SUMMARY] [NOEJECT]
- **LABEL FORM** file [TO FILE f] [FOR cond] [WHILE cond] [SAMPLE]
- **CREATE REPORT** file (interativo)
- **CREATE LABEL** file (interativo, com layouts pre-definidos: 3x10, 2x10, 1x10, cheshire)
- Definicoes em JSON (.FRM e .LBL) com suporte a grupos, subtotais e totais gerais

### Macro substituicao
- **&variavel**: substitui conteudo da variavel como texto
- **&variavel.**: ponto como terminador (permite concatenacao)
- **&(expressao)**: avalia expressao e substitui resultado
- Funciona em comandos e expressoes

### Configuracao (SET)
TALK, EXACT, DELETED, DATE, CENTURY, EPOCH, DECIMALS, DEFAULT, PATH, FILTER, RELATION, COLOR, HEADING, MARGIN, DELIMITER, INDEX, ORDER, SOFTSEEK, UNIQUE, NEAR, CARRY, BELL, ESCAPE, CONSOLE, PRINTER, ALTERNATE, DEBUG, STEP, BREAKPOINT

### Linguagem PRG
IF/ELSEIF/ELSE/ENDIF, DO WHILE/ENDDO, FOR/NEXT, DO CASE/CASE/OTHERWISE/ENDCASE, SCAN/ENDSCAN, PROCEDURE/FUNCTION/RETURN, DO programa.prg

### Debugger PRG
- **SET STEP ON/OFF**: execucao passo a passo
- **SET DEBUG ON/OFF**: ativar/desativar debugger
- **SET BREAKPOINT TO n**: definir breakpoint na linha n
- Comandos no prompt (debug): step, next, continue, break, print, vars, where, list, quit

### Compilador PRG
- **COMPILE programa.prg [TO output.exe] [DATA arq1,...] [ICON icone.ico]**: compila PRG em .exe standalone
- **python run.py --compile programa.prg [-o output.exe]**: compilacao via CLI
- **python -m dbase.compiler programa.prg [-o output.exe]**: compilacao direta
- Resolve dependencias automaticamente (DO, REPORT FORM, LABEL FORM, USE)
- Empacota runtime dBase completo + fontes PRG embarcados
- Gera executavel unico (~9.5 MB) via PyInstaller

### Expressoes e funcoes (100+)
- **String:** ALLTRIM, LTRIM, RTRIM, UPPER, LOWER, SUBSTR, LEFT, RIGHT, AT, RAT, LEN, SPACE, REPLICATE, STUFF, STRTRAN, PADL, PADR, PADC, CHR, ASC, LIKE, TRANSFORM, OCCURS, PROPER, ISALPHA, ISDIGIT, ISUPPER, ISLOWER
- **Numeric:** ABS, INT, ROUND, CEILING, FLOOR, SQRT, EXP, LOG, LOG10, MOD, MIN, MAX, SIGN, PI, SIN, COS, TAN, ASIN, ACOS, ATAN, DTOR, RTOD, RAND
- **Date:** DATE, TIME, DATETIME, YEAR, MONTH, DAY, DOW, CDOW, CMONTH, GOMONTH, ELAPSED
- **Conversao:** STR, STRZERO, VAL, DTOC, DTOS, CTOD, STOD, TTOC, TTOD
- **Logica:** IIF, BETWEEN, INLIST, EMPTY, TYPE, VARTYPE, NVL, EVL
- **Database:** RECNO, RECCOUNT, EOF, BOF, FOUND, DELETED, FIELD, FCOUNT, DBF, ALIAS, SELECT, USED
- **Arquivo:** FILE, CURDIR, FULLPATH, JUSTFNAME, JUSTPATH, JUSTEXT, JUSTSTEM, ADDBS
- **Sistema:** SYS, VERSION, OS, MEMORY, SECONDS, ROW, COL, LASTKEY, INKEY

### Interface
- REPL com dot prompt (.) e historico de comandos
- Tab completion para comandos, campos e funcoes
- BROWSE com curses (tela cheia) ou fallback texto
- Suporte a blocos multi-linha no prompt interativo

## Decisoes arquiteturais

1. **Python puro** para maxima portabilidade, sem dependencias pesadas
2. **Formato DBF nativo** com leitura/escrita binaria direta (sem bibliotecas externas)
3. **4 formatos de indice** implementados em modulos separados, com interface comum
4. **Parser de expressoes recursivo descendente** para suporte completo a sintaxe xBase
5. **Work areas** gerenciadas centralmente pelo Environment, com suporte a aliases e relacoes
6. **Interpretador PRG** separado do command interpreter, mas compartilhando o mesmo ambiente
7. **Motor SQL** proprio com tokenizer/parser/executor, operando sobre tabelas DBF existentes
8. **I/O multi-formato** com modulo dedicado, integrando com COPY TO e APPEND FROM

## Estado atual

- v1.0.0: Implementacao completa e funcional
- 10.177 linhas de codigo em 24 arquivos Python
- Todos os comandos core do dBASE III/IV implementados
- 4 formatos de indice com suporte a criacao, leitura, escrita e reconstrucao
- 100+ funcoes built-in
- Motor SQL completo (SELECT com JOINs, GROUP BY, HAVING, agregacoes)
- Import/Export em 6 formatos (CSV, JSON, XML, SDF, DELIMITED, XLS)
- Interpretador PRG com suporte a todas as estruturas de controle
- Report Form e Label Form com definicoes JSON
- Macro substituicao (&var, &var., &(expr))
- Debugger interativo para PRG (step, breakpoints, watch)
- 48 testes automatizados passando

## Melhorias planejadas

### Prioridade alta
- **Suporte a rede (file locking)**: FLOCK(), RLOCK(), UNLOCK, SET EXCLUSIVE, para uso multi-usuario
- **Macro substituicao em strings com aspas**: atualmente &var dentro de expressoes com aspas escapadas pode falhar; tratar corretamente nested quotes
- **Testes do compilador**: adicionar testes automatizados para COMPILE (compilar e executar PRG, verificar saida)

### Prioridade media
- **Compilador: reduzir tamanho do exe**: usar UPX compression (--upx-dir), excluir modulos Python desnecessarios (tkinter, unittest, etc.)
- **Compilador: suporte a PARAMETERS**: passar argumentos de linha de comando para o PRG compilado (sys.argv -> variaveis dBase)
- **MODIFY COMMAND**: editor de texto integrado para editar .PRG dentro do REPL (curses-based)
- **ON ERROR/ON ESCAPE**: tratamento de erros customizado no PRG
- **@...GET/READ**: formularios interativos completos com validacao
- **SET RELATION entre areas**: o SET RELATION existe mas pode precisar de mais testes com multi-tabela

### Prioridade baixa
- **Interface grafica para o compilador**: GUI com tkinter para selecionar PRG, opcoes, icone, e compilar
- **Debugger visual**: interface curses para o debugger (em vez de prompt texto)
- **Profiler PRG**: medir tempo de execucao por linha/funcao
- **SCATTER/GATHER**: copiar registro para variaveis e vice-versa
- **Memo fields (.FPT/.DBT)**: suporte completo a campos memo com arquivos externos
- **Suporte a .DBC (database container)**: container FoxPro com metadados de tabelas
- **Cross-compilation**: gerar .exe para Linux/Mac a partir do Windows (e vice-versa)

### Bugs conhecidos
- Tokenizer do commands.py: virgulas sao tratadas como separadores genericos, o que funciona para a maioria dos casos mas pode causar problemas em expressoes complexas com virgulas dentro de parenteses (ex: funcoes com multiplos argumentos em contextos especificos)
- QUIT dentro de PRG: agora funciona via _exit_flag em vez de SystemExit, mas o QUIT no REPL interativo ainda usa SystemExit (comportamento correto, mas arquiteturas diferentes)
