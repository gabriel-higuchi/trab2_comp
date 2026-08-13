# Gramatica da linguagem, em forma legivel por maquina.
# "" na direita = producao vazia (epsilon)

GRAMATICA = """
programa        -> lista_comandos

lista_comandos  -> lista_comandos comando
lista_comandos  ->

comando         -> declaracao
comando         -> atribuicao
comando         -> leitura
comando         -> escrita
comando         -> condicional
comando         -> repeticao_cond
comando         -> repeticao_cont
comando         -> bloco

bloco           -> abre_chave lista_comandos fecha_chave

declaracao      -> tipo lista_decl ponto_virgula
tipo            -> int
tipo            -> float
tipo            -> string
tipo            -> bool
lista_decl      -> lista_decl virgula item_decl
lista_decl      -> item_decl
item_decl       -> id
item_decl       -> id atrib expressao

atribuicao      -> id atrib expressao ponto_virgula

leitura         -> rd abre_par lista_id fecha_par ponto_virgula
lista_id        -> lista_id virgula id
lista_id        -> id

escrita         -> wt abre_par lista_expr fecha_par ponto_virgula
lista_expr      -> lista_expr virgula expressao
lista_expr      -> expressao

condicional     -> maybe abre_par expressao fecha_par bloco
condicional     -> maybe abre_par expressao fecha_par bloco default bloco

repeticao_cond  -> cycle abre_par expressao fecha_par bloco

repeticao_cont  -> walk abre_par inicializacao ponto_virgula expressao ponto_virgula passo fecha_par bloco
inicializacao   -> tipo id atrib expressao
inicializacao   -> id atrib expressao
passo           -> id atrib expressao

expressao       -> expressao ou_logico exp_e
expressao       -> exp_e
exp_e           -> exp_e e_logico exp_nao
exp_e           -> exp_nao
exp_nao         -> nao_logico exp_nao
exp_nao         -> exp_rel
exp_rel         -> exp_arit op_rel exp_arit
exp_rel         -> exp_arit
op_rel          -> igual
op_rel          -> diferente
op_rel          -> menor
op_rel          -> menor_igual
op_rel          -> maior
op_rel          -> maior_igual
exp_arit        -> exp_arit mais termo
exp_arit        -> exp_arit menos termo
exp_arit        -> termo
termo           -> termo vezes fator
termo           -> termo dividido fator
termo           -> fator
fator           -> abre_par expressao fecha_par
fator           -> menos fator
fator           -> id
fator           -> num_int
fator           -> num_float
fator           -> lit_string
"""


def carregar(texto=GRAMATICA):
    producoes = []
    for linha in texto.strip().splitlines():
        linha = linha.strip()
        if not linha:
            continue
        esq, dir_ = linha.split("->")
        producoes.append((esq.strip(), tuple(dir_.split())))
    naoterminais = {p[0] for p in producoes}
    simbolos = {s for _, r in producoes for s in r}
    terminais = simbolos - naoterminais
    return producoes, naoterminais, terminais
