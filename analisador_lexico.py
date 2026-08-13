"""
Analisador Léxico - Parte 2 (versão corrigida)

Mantém a numeração de estados do autômato finito entregue na Parte 1
(estados 1, 2, 4, 6, 7, 9, 12, 15, 18, 21, 24, 26, 28) e acrescenta o que
o analisador sintático LR vai precisar consumir.

Diferenças em relação à versão da Parte 1:
  - Token virou estrutura (classe, terminal, lexema, linha, coluna) em vez
    de string formatada.
  - Todo erro carrega linha e coluna.
  - Erros são acumulados numa lista e o programa retorna código de saída != 0.
  - A lista de tokens termina com o marcador de fim '$', que é o lookahead
    da ação ACCEPT na tabela LR (a produção aumentada é S' -> S, sem o '$'
    na parte direita).
  - Cada símbolo tem um TERMINAL próprio ( ';' e '}' precisam ser distintos
    para servirem de sincronizadores no modo pânico do parser ).
  - String não fechada e string com quebra de linha agora são erros.
  - Número seguido de letra ('123abc') e número com dois pontos ('1.2.3')
    agora são erros de número malformado.
  - Alfabeto restrito a ASCII: 'contadôr' e '1²' deixam de ser aceitos.
  - Comentário de bloco /* ... */ implementado (o LEIA-ME da Parte 1 já o
    documentava, mas o código não o tinha).

DECISÕES DE LINGUAGEM ASSUMIDAS AQUI - reveja antes de escrever a gramática:
  (a) A vírgula ',' foi ADICIONADA ao alfabeto. Sem ela não há como escrever
      'int a, b;' nem chamada com dois argumentos. Para remover, apague a
      entrada ',' de SIMBOLOS_SIMPLES.
  (b) AND/OR/NOT (palavras) e &&/////! (símbolos) foram mapeados para o MESMO
      terminal, para não duplicar regras na gramática.
  (c) '[' ']' e '%' continuam fora do alfabeto (sem vetores, sem módulo).
  (d) O tipo 'bool' existe mas a linguagem não tem literais true/false.
"""

import sys
from bisect import bisect_right
from dataclasses import dataclass

EOF = "\0"  # sentinela de fim de arquivo (substitui o antigo truque de somar " ")


# ==========================================================================
# ESTRUTURAS
# ==========================================================================

@dataclass
class Token:
    classe: str     # categoria ampla, para a saída no formato da Parte 1
    terminal: str   # símbolo terminal da gramática, para a tabela LR
    lexema: str
    linha: int
    coluna: int

    def __str__(self):
        return f"[{self.classe}, {self.lexema}]"


@dataclass
class ErroLexico:
    mensagem: str
    linha: int
    coluna: int

    def __str__(self):
        return f"ERRO LEXICO (linha {self.linha}, coluna {self.coluna}): {self.mensagem}"


# ==========================================================================
# TABELAS
# ==========================================================================

# Palavra reservada -> terminal da gramática.
# AND/OR/NOT compartilham o terminal com &&, // e ! (decisão (b) do cabeçalho).
PALAVRAS_RESERVADAS = {
    "int": "int",
    "float": "float",
    "string": "string",
    "bool": "bool",
    "maybe": "maybe",
    "default": "default",
    "cycle": "cycle",
    "walk": "walk",
    "rd": "rd",
    "wt": "wt",
    "AND": "e_logico",
    "OR": "ou_logico",
    "NOT": "nao_logico",
}

# Símbolos de um caractere -> (classe, terminal).
SIMBOLOS_SIMPLES = {
    "+": ("op_arit", "mais"),
    "-": ("op_arit", "menos"),
    "*": ("op_arit", "vezes"),
    "(": ("delimitador", "abre_par"),
    ")": ("delimitador", "fecha_par"),
    "{": ("delimitador", "abre_chave"),
    "}": ("delimitador", "fecha_chave"),
    ";": ("delimitador", "ponto_virgula"),
    ",": ("delimitador", "virgula"),
}


# Alfabeto restrito a ASCII: str.isalpha()/str.isdigit() do Python aceitam
# Unicode ('ç'.isalpha() e '²'.isdigit() são True), o que deixava passar
# identificadores acentuados e inteiros como '1²'.
def eh_letra(c):
    return ("a" <= c <= "z") or ("A" <= c <= "Z")


def eh_digito(c):
    return "0" <= c <= "9"


def eh_alfanumerico(c):
    return eh_letra(c) or eh_digito(c)


# ==========================================================================
# ANALISADOR
# ==========================================================================

class AnalisadorLexico:

    def __init__(self, codigo_fonte):
        self.codigo = codigo_fonte
        self.tokens = []
        self.erros = []
        # Posições das quebras de linha, para converter posição -> (linha, coluna)
        # sem precisar espalhar contadores por todos os ramos do autômato.
        self._quebras = [i for i, c in enumerate(codigo_fonte) if c == "\n"]

    # ---------------------------------------------------------------- apoio

    def posicao_para_linha_coluna(self, posicao):
        linha = bisect_right(self._quebras, posicao - 1) + 1
        inicio = self._quebras[linha - 2] + 1 if linha > 1 else 0
        return linha, posicao - inicio + 1

    def emitir(self, classe, terminal, lexema, inicio):
        linha, coluna = self.posicao_para_linha_coluna(inicio)
        self.tokens.append(Token(classe, terminal, lexema, linha, coluna))

    def erro(self, mensagem, posicao):
        linha, coluna = self.posicao_para_linha_coluna(posicao)
        self.erros.append(ErroLexico(mensagem, linha, coluna))

    def caractere(self, posicao):
        return self.codigo[posicao] if posicao < len(self.codigo) else EOF

    def descartar_resto_do_numero(self, posicao):
        """Modo pânico para número malformado: consome todo o resto da
        sequência (dígitos, letras, '_' e '.') para que um único lexema
        inválido gere um único erro, e não uma cascata."""
        while eh_alfanumerico(self.caractere(posicao)) or self.caractere(posicao) in ("_", "."):
            posicao += 1
        return posicao

    # ------------------------------------------------------------- autômato

    def analisar(self):
        estado = 1
        posicao = 0
        inicio = 0      # posição onde o lexema atual começou
        lexema = ""

        while True:
            char = self.caractere(posicao)

            # O laço só termina no estado 1: todos os demais estados tratam o
            # EOF fazendo o retrocesso e voltando ao estado 1, garantindo que
            # nenhum lexema pendente seja perdido (bug da versão anterior, em
            # que uma string aberta no fim do arquivo sumia sem aviso).
            if estado == 1 and char == EOF:
                break

            # ==============================================================
            # ESTADO 1: INÍCIO E SÍMBOLOS SIMPLES
            # ==============================================================
            if estado == 1:
                if char in (" ", "\t", "\n", "\r"):
                    posicao += 1
                    continue

                inicio = posicao
                lexema = char

                if eh_letra(char) or char == "_":
                    estado = 2
                    posicao += 1
                elif eh_digito(char):
                    estado = 4
                    posicao += 1
                elif char == "=":
                    estado = 9
                    posicao += 1
                elif char == ">":
                    estado = 12
                    posicao += 1
                elif char == "<":
                    estado = 15
                    posicao += 1
                elif char == "!":
                    estado = 18
                    posicao += 1
                elif char == "/":
                    estado = 21
                    posicao += 1
                elif char == "&":
                    estado = 24
                    posicao += 1
                elif char == '"':
                    estado = 26
                    posicao += 1
                elif char == "#":
                    estado = 28
                    posicao += 1
                elif char in SIMBOLOS_SIMPLES:
                    classe, terminal = SIMBOLOS_SIMPLES[char]
                    self.emitir(classe, terminal, lexema, inicio)
                    lexema = ""
                    posicao += 1
                else:
                    # Modo pânico: descarta o caractere e segue.
                    self.erro(f"caractere invalido {char!r} fora do alfabeto da linguagem", posicao)
                    lexema = ""
                    posicao += 1

            # ==============================================================
            # ESTADO 2: IDENTIFICADORES E PALAVRAS RESERVADAS
            # ==============================================================
            elif estado == 2:
                if eh_alfanumerico(char) or char == "_":
                    lexema += char
                    posicao += 1
                else:
                    # ESTADO 3* (retrocesso: não consome o caractere lido)
                    if lexema in PALAVRAS_RESERVADAS:
                        self.emitir("reservada", PALAVRAS_RESERVADAS[lexema], lexema, inicio)
                    else:
                        self.emitir("id", "id", lexema, inicio)
                    estado = 1
                    lexema = ""

            # ==============================================================
            # ESTADOS 4, 6, 7: NÚMEROS (INT E FLOAT)
            # ==============================================================
            elif estado == 4:
                if eh_digito(char):
                    lexema += char
                    posicao += 1
                elif char == ".":
                    estado = 6
                    lexema += char
                    posicao += 1
                elif eh_letra(char) or char == "_":
                    # '123abc' era aceito como [int,123] + [id,abc], sem erro.
                    fim = self.descartar_resto_do_numero(posicao)
                    self.erro(
                        f"numero malformado {self.codigo[inicio:fim]!r}: "
                        f"digito seguido de letra",
                        inicio,
                    )
                    posicao = fim
                    estado = 1
                    lexema = ""
                else:
                    # ESTADO 5* (retrocesso: inteiro finalizado)
                    self.emitir("num_int", "num_int", lexema, inicio)
                    estado = 1
                    lexema = ""

            elif estado == 6:
                if eh_digito(char):
                    estado = 7
                    lexema += char
                    posicao += 1
                else:
                    fim = self.descartar_resto_do_numero(posicao)
                    self.erro(
                        f"numero real malformado {self.codigo[inicio:fim]!r}: "
                        f"faltam digitos apos o ponto",
                        inicio,
                    )
                    posicao = fim
                    estado = 1
                    lexema = ""

            elif estado == 7:
                if eh_digito(char):
                    lexema += char
                    posicao += 1
                elif char == "." or eh_letra(char) or char == "_":
                    # '1.2.3' virava [float,1.2] + [int,3] + erro solto de '.'.
                    fim = self.descartar_resto_do_numero(posicao)
                    self.erro(
                        f"numero real malformado {self.codigo[inicio:fim]!r}",
                        inicio,
                    )
                    posicao = fim
                    estado = 1
                    lexema = ""
                else:
                    # ESTADO 8* (retrocesso: real finalizado)
                    self.emitir("num_float", "num_float", lexema, inicio)
                    estado = 1
                    lexema = ""

            # ==============================================================
            # ESTADOS 9, 12, 15, 18: RELACIONAIS E ATRIBUIÇÃO
            # ==============================================================
            elif estado == 9:  # via do '='
                if char == "=":
                    lexema += char
                    self.emitir("op_rel", "igual", lexema, inicio)
                    posicao += 1
                else:
                    self.emitir("op_atribuicao", "atrib", lexema, inicio)
                estado = 1
                lexema = ""

            elif estado == 12:  # via do '>'
                if char == "=":
                    lexema += char
                    self.emitir("op_rel", "maior_igual", lexema, inicio)
                    posicao += 1
                else:
                    self.emitir("op_rel", "maior", lexema, inicio)
                estado = 1
                lexema = ""

            elif estado == 15:  # via do '<'
                if char == "=":
                    lexema += char
                    self.emitir("op_rel", "menor_igual", lexema, inicio)
                    posicao += 1
                else:
                    self.emitir("op_rel", "menor", lexema, inicio)
                estado = 1
                lexema = ""

            elif estado == 18:  # via do '!'
                if char == "=":
                    lexema += char
                    self.emitir("op_rel", "diferente", lexema, inicio)
                    posicao += 1
                else:
                    self.emitir("op_logico", "nao_logico", lexema, inicio)
                estado = 1
                lexema = ""

            # ==============================================================
            # ESTADOS 21..24: DIVISÃO, OR LÓGICO, COMENTÁRIO DE BLOCO, AND
            # ==============================================================
            elif estado == 21:  # via do '/'
                if char == "/":
                    lexema += char
                    self.emitir("op_logico", "ou_logico", lexema, inicio)
                    posicao += 1
                    estado = 1
                    lexema = ""
                elif char == "*":
                    estado = 22          # abre comentário de bloco
                    posicao += 1
                    lexema = ""
                else:
                    self.emitir("op_arit", "dividido", lexema, inicio)
                    estado = 1
                    lexema = ""

            elif estado == 22:  # dentro de /* ... */
                if char == EOF:
                    self.erro("comentario de bloco aberto e nao fechado ate o fim do arquivo", inicio)
                    estado = 1
                elif char == "*":
                    estado = 23
                    posicao += 1
                else:
                    posicao += 1

            elif estado == 23:  # viu '*' dentro do bloco, procurando '/'
                if char == EOF:
                    self.erro("comentario de bloco aberto e nao fechado ate o fim do arquivo", inicio)
                    estado = 1
                elif char == "/":
                    estado = 1
                    posicao += 1
                elif char == "*":
                    posicao += 1         # '**/' continua fechando
                else:
                    estado = 22
                    posicao += 1

            elif estado == 24:  # via do '&'
                if char == "&":
                    lexema += char
                    self.emitir("op_logico", "e_logico", lexema, inicio)
                    posicao += 1
                else:
                    # A versão anterior reportava o caractere de lookahead
                    # (normalmente um espaço), apontando o lugar errado.
                    self.erro("operador invalido '&': o AND logico se escreve '&&'", inicio)
                estado = 1
                lexema = ""

            # ==============================================================
            # ESTADO 26: STRINGS
            # ==============================================================
            elif estado == 26:
                if char == '"':
                    lexema += char
                    self.emitir("lit_string", "lit_string", lexema, inicio)
                    posicao += 1
                    estado = 1
                    lexema = ""
                elif char == "\n":
                    # Antes: a string engolia a quebra de linha em silêncio.
                    self.erro("string nao fechada antes do fim da linha", inicio)
                    estado = 1
                    lexema = ""
                elif char == EOF:
                    # Antes: o laço terminava e o lexema sumia, sem token e sem erro.
                    self.erro("string nao fechada ate o fim do arquivo", inicio)
                    estado = 1
                    lexema = ""
                else:
                    lexema += char
                    posicao += 1

            # ==============================================================
            # ESTADO 28: COMENTÁRIO DE LINHA
            # ==============================================================
            elif estado == 28:
                if char == EOF:
                    estado = 1
                elif char == "\n":
                    estado = 1
                    lexema = ""
                    posicao += 1
                else:
                    posicao += 1

        # Marcador de fim de entrada: é o lookahead da ação ACCEPT da tabela LR.
        linha, coluna = self.posicao_para_linha_coluna(len(self.codigo))
        self.tokens.append(Token("eof", "$", "$", linha, coluna))

        return self.tokens, self.erros


def analisador_lexico(codigo_fonte):
    """Ponto de entrada usado pelo analisador sintático.
    Retorna (tokens, erros)."""
    return AnalisadorLexico(codigo_fonte).analisar()


# ==========================================================================
# EXECUÇÃO
# ==========================================================================

def saida_tolerante():
    """Ver o comentario homonimo em analisador_sintatico.py: evita
    UnicodeEncodeError ao imprimir um lexema que nao cabe na codificacao do
    terminal (cp1252 no console classico do Windows)."""
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="backslashreplace")


def main():
    saida_tolerante()
    caminho = sys.argv[1] if len(sys.argv) > 1 else "programa_teste.txt"

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            codigo = arquivo.read()
    except FileNotFoundError:
        print(f"Erro: arquivo '{caminho}' nao encontrado.")
        print("Uso: python analisador_lexico.py [arquivo_fonte]")
        return 2
    except OSError as e:
        print(f"Erro ao abrir '{caminho}': {e}")
        return 2

    print(f"Analisando '{caminho}'...\n")
    tokens, erros = analisador_lexico(codigo)

    print("--- TOKENS RECONHECIDOS ---")
    print(f"{'LINHA':>5} {'COL':>4}  {'CLASSE':<14} {'TERMINAL':<14} LEXEMA")
    for t in tokens:
        print(f"{t.linha:>5} {t.coluna:>4}  {t.classe:<14} {t.terminal:<14} {t.lexema}")

    print(f"\nTotal de tokens (incluindo '$'): {len(tokens)}")

    if erros:
        print(f"\n--- ERROS LEXICOS ({len(erros)}) ---")
        for e in erros:
            print(e)
        return 1

    print("\nNenhum erro lexico encontrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
