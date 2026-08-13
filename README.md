# trab2_comp

Analisador sintático **ascendente (bottom-up) LR**, com tabela **SLR(1)**,
para a linguagem definida na primeira parte do trabalho de Compiladores.

Nenhum gerador automático de analisadores foi usado. FIRST, FOLLOW, a coleção
canônica de itens LR(0) e as tabelas ACTION/GOTO são construídos pelo próprio
código, em `tabela_slr.py`. As únicas dependências são módulos da biblioteca
padrão (`sys`, `bisect`, `dataclasses`).

## Como executar

Requer Python 3.7 ou superior. Em Linux/macOS, use `python3` no lugar de
`python`.

```bash
python analisador_sintatico.py programa_teste.txt
```

Para demonstrar a recuperação de erros em modo pânico:

```bash
python analisador_sintatico.py programa_com_erros.txt
```

Para verificar a gramática e o relatório de conflitos:

```bash
python tabela_slr.py
```

## Opções de visualização

| Opção | O que mostra |
|---|---|
| `--tokens` | os tokens, com classe, terminal, linha e coluna |
| `--derivacao` | as produções aplicadas, na ordem das reduções |
| `--arvore` | a árvore sintática |
| `--itens` | a coleção canônica de itens LR(0), `I0..I115` |
| `--tabela` | a matriz ACTION/GOTO (`E<n>`, `R<n>`, `AC`) |
| `--passos` | o traço da análise, no formato `Pilha \| Entrada \| Ação` |

As três últimas são longas; convém redirecionar para arquivo.

## A gramática

62 produções (incluindo a aumentada), 34 terminais e 26 não-terminais. A
coleção canônica LR(0) tem 116 estados e a tabela SLR(1) resultante **não tem
nenhum conflito** shift/reduce nem reduce/reduce — logo a gramática também é
LALR(1) e LR(1).

A precedência e a associatividade dos operadores estão embutidas na
estratificação dos não-terminais (`expressao → exp_e → exp_nao → exp_rel →
exp_arit → termo → fator`), e não em declarações externas de precedência.

Os detalhes estão em [`gramatica.pdf`](gramatica.pdf), gerado a partir de
[`gramatica.md`](gramatica.md).

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `analisador_lexico.py` | analisador léxico (autômato finito, modo pânico) |
| `analisador_sintatico.py` | analisador LR, recuperação de erros e programa principal |
| `tabela_slr.py` | FIRST, FOLLOW, itens LR(0), tabelas ACTION/GOTO |
| `gramatica.py` | a gramática em forma legível por máquina |
| `gramatica.md` / `gramatica.pdf` | documentação da gramática livre de contexto |
| `programa_teste.txt` | código de entrada que exercita todas as primitivas |
| `programa_com_erros.txt` | código com erros propositais |
| `gerar_pdf.py` | regenera `gramatica.pdf` a partir do `.md` (requer `reportlab`) |
