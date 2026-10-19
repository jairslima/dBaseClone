# dBase Revival by Jair Lima

Clone funcional do dBASE clássico para terminal, escrito em Python, sem dependências externas no núcleo. Abre e grava arquivos `.dbf`, executa programas `.prg` e entende SQL.

## Recursos

- **Dot prompt (REPL)** e interpretador de programas `.PRG`.
- **Motor DBF** de leitura e escrita, com mais de 80 comandos (`USE`, `APPEND`, `REPLACE`, `LOCATE`, `SEEK`, `SORT`, `PACK`, `ZAP`, `LIST`, `DISPLAY`, `BROWSE`, `EDIT` e outros) e mais de 100 funções embutidas.
- **Quatro formatos de índice:** NDX (dBASE III), NTX (Clipper), CDX (FoxPro) e MDX (dBASE IV).
- **SQL:** `SELECT` com `JOIN`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`; `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE` e `DROP TABLE`.
- **Importação e exportação:** CSV, JSON, XML, SDF, DELIMITED e XLS.
- **Relatórios** (`REPORT FORM`, `LABEL FORM`), depurador interativo e compilador de `.PRG` para executável.

## Requisitos

Python 3.8 ou superior. No Windows, o `BROWSE` em modo curses usa o pacote `windows-curses`:

```bash
pip install -r requirements.txt
```

## Uso

```bash
python run.py              # abre o dot prompt
python run.py programa.prg # executa um programa .PRG
python run_tests.py        # roda os 48 testes automatizados
pip install -e .           # instala o comando `dbase`
```

O arquivo `demo.prg` mostra um exemplo de programa.

## Compatibilidade

Não é uma réplica exata de nenhum produto da Borland, da Ashton-Tate ou da Microsoft. Reproduz o comportamento e a sintaxe mais usados, e diferenças podem existir em comandos pouco comuns. Relatos de incompatibilidade são bem-vindos.

## Licença

MIT, veja `LICENSE`.

## Segurança

- Os comandos `RUN` e `!` executam o comando indicado no sistema operacional, como no dBASE original. **Rode apenas arquivos `.prg` em que você confia**: um programa pode executar qualquer comando.
- Importação de XML usa o parser padrão do Python; não importe XML de origem desconhecida.
