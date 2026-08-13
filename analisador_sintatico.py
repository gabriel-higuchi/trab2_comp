"""
Analisador Sintatico - Parte 2
Metodo ascendente (bottom-up) LR, com tabela SLR(1).

Recebe a lista de tokens do analisador lexico e reconhece o programa segundo a
gramatica de gramatica.py. Erros sintaticos sao tratados em modo panico: o
analisador registra o erro, sincroniza e continua, sem parar no primeiro.

Uso:
    python analisador_sintatico.py [arquivo] [opcoes]

Opcoes:
    --tokens      lista os tokens produzidos pelo analisador lexico
    --derivacao   lista as producoes aplicadas (derivacao mais a direita,
                  na ordem inversa)
    --arvore      imprime a arvore sintatica
    --itens       imprime a colecao canonica de itens LR(0), I0..In
    --tabela      imprime a matriz ACTION/GOTO (E<n>, R<n>, AC)
    --passos      imprime o traco da analise (Pilha | Entrada | Acao)

As tres ultimas expoem a construcao LR etapa por etapa, para conferencia a
mao. Como sao longas, convem redirecionar para arquivo:

    python analisador_sintatico.py programa_teste.txt --tabela > tabela.txt
"""

import sys

from analisador_lexico import analisador_lexico
from tabela_slr import FIM, construir

# Nao-terminais usados para sincronizar em modo panico. A ordem importa:
# tenta-se primeiro voltar ao nivel de comando (em qualquer profundidade da
# pilha), o que descarta o comando defeituoso inteiro e retoma no proximo.
# Sincronizar por 'expressao' repara menos, mas so serve quando o erro esta
# realmente dentro de uma expressao.
SINCRONIZADORES = ("comando", "expressao", "lista_comandos")

# Limite para nao inundar a saida caso a entrada esteja completamente fora da
# linguagem.
MAX_ERROS = 50

# Duas regras evitam a CASCATA - varias mensagens para um unico defeito:
#
#   1. No maximo um erro por posicao da entrada. A recuperacao pode falhar e
#      reincidir sobre o MESMO token; como a posicao nunca retrocede, basta
#      comparar com a ultima posicao reportada.
#
#   2. Depois de reportar um erro, e preciso deslocar MIN_DESLOCAMENTOS tokens
#      com sucesso antes de reportar o proximo. Enquanto o analisador nao
#      voltou a andar sobre entrada valida, um novo erro e mais provavelmente
#      eco da recuperacao anterior do que um defeito novo. Exemplo: em 'a + b;'
#      a sincronizacao retoma em 'b', que abre um comando que tambem nao se
#      completa - sem a regra 2, um unico defeito renderia dois erros.
#
# As mensagens omitidas por essas regras sao contadas e o total e informado ao
# final, para que nada seja escondido em silencio.
#
# A regra 2 e uma heuristica descrita na literatura de compiladores (Aho et al.,
# secao de recuperacao de erros em analise ascendente), reimplementada aqui em
# quatro linhas. NENHUM codigo de ferramenta externa foi usado ou consultado.
#
# O valor 2 foi calibrado sobre os casos de teste deste trabalho: mata a cascata
# de 'a + b;' e de 'a < b < c;' sem engolir defeitos distintos que estejam
# proximos. Com 3 - valor mais citado na literatura - a segunda das duas
# atribuicoes vazias de 'a = ; b = ;' deixava de ser reportada.
MIN_DESLOCAMENTOS = 2

# Nome legivel de cada terminal, para as mensagens de erro.
SIMBOLO = {
    "atrib": "'='", "igual": "'=='", "diferente": "'!='",
    "menor": "'<'", "menor_igual": "'<='", "maior": "'>'", "maior_igual": "'>='",
    "mais": "'+'", "menos": "'-'", "vezes": "'*'", "dividido": "'/'",
    "e_logico": "'&&'", "ou_logico": "'//'", "nao_logico": "'!'",
    "abre_par": "'('", "fecha_par": "')'",
    "abre_chave": "'{'", "fecha_chave": "'}'",
    "ponto_virgula": "';'", "virgula": "','",
    "id": "identificador", "num_int": "numero inteiro",
    "num_float": "numero real", "lit_string": "cadeia entre aspas",
    FIM: "fim do arquivo",
}


def legivel(terminal):
    return SIMBOLO.get(terminal, f"'{terminal}'")


def rotulo_curto(terminal):
    """Rotulo compacto para os cabecalhos da tabela: ';' em vez de
    'ponto_virgula'. Terminais sem simbolo proprio (id, num_int, palavras
    reservadas) ficam com o proprio nome."""
    nome = SIMBOLO.get(terminal)
    if nome and nome.startswith("'") and nome.endswith("'"):
        return nome[1:-1]
    return terminal


def _prioridade(terminal):
    """Ordem de exibicao dos terminais esperados: os que costumam ser a
    correcao procurada (delimitadores) vem antes dos operadores."""
    if terminal in ("ponto_virgula", "fecha_par", "fecha_chave",
                    "abre_chave", "abre_par", "virgula"):
        return 0
    if terminal not in SIMBOLO:
        return 1  # palavras reservadas
    if terminal in ("id", "num_int", "num_float", "lit_string"):
        return 2
    return 3      # operadores


class No:
    """No da arvore sintatica. Folhas carregam o token; nos internos, o
    nao-terminal e os filhos."""

    __slots__ = ("rotulo", "filhos", "token", "erro")

    def __init__(self, rotulo, filhos=None, token=None, erro=False):
        self.rotulo = rotulo
        self.filhos = filhos or []
        self.token = token
        self.erro = erro

    def imprimir(self, prefixo="", ultimo=True, saida=None):
        saida = saida if saida is not None else sys.stdout
        conector = "`-- " if ultimo else "|-- "
        if self.token is not None:
            texto = f"{self.rotulo}  ({self.token.lexema})"
        elif self.erro:
            texto = f"{self.rotulo}  <trecho com erro>"
        else:
            texto = self.rotulo
        saida.write(prefixo + (conector if prefixo or not ultimo else "") + texto + "\n")
        novo = prefixo + ("    " if ultimo else "|   ")
        for i, f in enumerate(self.filhos):
            f.imprimir(novo, i == len(self.filhos) - 1, saida)


class ErroSintatico:

    MAX_MOSTRADOS = 6

    def __init__(self, token, esperados):
        self.token = token
        self.esperados = sorted(esperados, key=lambda t: (_prioridade(t), t))

    def _encontrado(self):
        nome = legivel(self.token.terminal)
        # Para pontuacao e palavras reservadas o nome legivel ja e o proprio
        # lexema; repeti-lo produziria "nao era esperado ';' ';'".
        if nome.strip("'") == self.token.lexema:
            return nome
        return f"{nome} '{self.token.lexema}'"

    def __str__(self):
        mostrados = self.esperados[:self.MAX_MOSTRADOS]
        restantes = len(self.esperados) - len(mostrados)
        vistos = ", ".join(legivel(t) for t in mostrados)
        if restantes:
            vistos += f" (e mais {restantes})"
        return (f"ERRO SINTATICO (linha {self.token.linha}, "
                f"coluna {self.token.coluna}): "
                f"nao era esperado {self._encontrado()}; "
                f"esperado um de: {vistos}")


class LimiteDeErros:
    """Marca a interrupcao da analise por excesso de erros - a entrada esta
    tao fora da linguagem que continuar so produziria ruido."""

    def __init__(self, token, total):
        self.token = token
        self.total = total

    def __str__(self):
        return (f"ERRO SINTATICO (linha {self.token.linha}, "
                f"coluna {self.token.coluna}): limite de {self.total} erros "
                f"atingido; o resto do arquivo nao foi analisado.")


class AnalisadorSintatico:

    def __init__(self, tabela=None):
        self.tabela = tabela or construir()
        if self.tabela.conflitos:
            raise RuntimeError(
                f"a gramatica tem {len(self.tabela.conflitos)} conflito(s) "
                f"SLR(1); rode 'python tabela_slr.py' para o relatorio")

    # -------------------------------------------------------------- analise

    def analisar(self, tokens, registrar_passos=False):
        """Retorna (aceito, raiz, erros, derivacao, suprimidos).

        Com registrar_passos, preenche self.passos com o traco
        (Pilha, Entrada, Acao) da analise."""
        pilha_estados = [0]
        pilha_nos = []          # pilha_nos[k] corresponde a pilha_estados[k+1]
        derivacao = []
        erros = []
        i = 0

        self.passos = [] if registrar_passos else None

        # Guarda contra laco infinito: se a recuperacao nao progredir, o
        # analisador passa a descartar tokens a forca.
        ultimo_erro_em = -1
        erros_no_mesmo_ponto = 0
        # Posicao do ultimo erro efetivamente reportado.
        ultima_reportada = -1
        suprimidos = 0
        # Tokens deslocados desde o ultimo erro reportado. Comeca ja "saldado"
        # para que o primeiro erro do arquivo seja sempre reportado.
        deslocamentos = MIN_DESLOCAMENTOS

        while True:
            estado = pilha_estados[-1]
            token = tokens[i]
            acao = self.tabela.acao.get((estado, token.terminal))

            if registrar_passos:
                self._registrar_passo(pilha_estados, pilha_nos, tokens, i, acao)

            if acao is None:
                if len(erros) >= MAX_ERROS:
                    erros.append(LimiteDeErros(token, MAX_ERROS))
                    return (False, self._raiz(pilha_nos), erros,
                            derivacao, suprimidos)

                # Regras 1 e 2 do cabecalho: uma mensagem por posicao, e so
                # depois de o analisador ter voltado a andar sobre entrada
                # valida.
                if i > ultima_reportada and deslocamentos >= MIN_DESLOCAMENTOS:
                    erros.append(ErroSintatico(token, self.tabela.esperados(estado)))
                    ultima_reportada = i
                    deslocamentos = 0
                else:
                    suprimidos += 1

                if i == ultimo_erro_em:
                    erros_no_mesmo_ponto += 1
                else:
                    ultimo_erro_em, erros_no_mesmo_ponto = i, 0

                forcar = erros_no_mesmo_ponto >= 2
                novo_i = self._recuperar(pilha_estados, pilha_nos, tokens, i, forcar)
                if novo_i is None:
                    return (False, self._raiz(pilha_nos), erros,
                            derivacao, suprimidos)
                i = novo_i
                continue

            tipo, arg = acao

            if tipo == "s":
                pilha_estados.append(arg)
                pilha_nos.append(No(token.terminal, token=token))
                i += 1
                deslocamentos += 1

            elif tipo == "r":
                esq, dir_ = self.tabela.producoes[arg]
                filhos = []
                for _ in dir_:
                    pilha_estados.pop()
                    filhos.insert(0, pilha_nos.pop())
                pilha_estados.append(self.tabela.goto[(pilha_estados[-1], esq)])
                pilha_nos.append(No(esq, filhos))
                derivacao.append(arg)

            else:  # 'acc'
                return (len(erros) == 0, self._raiz(pilha_nos), erros,
                        derivacao, suprimidos)

    @staticmethod
    def _raiz(pilha_nos):
        if len(pilha_nos) == 1:
            return pilha_nos[0]
        return No("<programa>", list(pilha_nos), erro=True)

    # ------------------------------------------------- traco da analise

    # Quanto do traco cabe em cada coluna antes de ser abreviado com '...'.
    LARGURA_PILHA = 58
    LARGURA_ENTRADA = 30

    @staticmethod
    def _simbolo_do_no(no):
        """Na pilha, terminais aparecem pelo lexema e nao-terminais pelo
        proprio nome."""
        return no.token.lexema if no.token is not None else no.rotulo

    def _registrar_passo(self, pilha_estados, pilha_nos, tokens, i, acao):
        # Pilha na forma intercalada: '$' no fundo, depois estado e simbolo
        # alternados. As duas pilhas paralelas do analisador sao entrelacadas
        # so para a exibicao.
        partes = [f"$ {pilha_estados[0]}"]
        for k, no in enumerate(pilha_nos):
            partes.append(f"{self._simbolo_do_no(no)} {pilha_estados[k + 1]}")
        pilha = " ".join(partes)
        if len(pilha) > self.LARGURA_PILHA:
            pilha = "..." + pilha[-(self.LARGURA_PILHA - 3):]

        entrada = " ".join(t.lexema for t in tokens[i:])
        if len(entrada) > self.LARGURA_ENTRADA:
            entrada = entrada[:self.LARGURA_ENTRADA - 3] + "..."

        if acao is None:
            texto = "ERRO"
        else:
            tipo, arg = acao
            texto = {"s": f"E{arg}", "r": f"R{arg}"}.get(tipo, "AC")

        self.passos.append((pilha, entrada, texto))

    def imprimir_passos(self, saida=None):
        saida = saida if saida is not None else sys.stdout
        saida.write("--- RECONHECIMENTO DA SENTENCA (PASSO A PASSO) ---\n")
        saida.write("Legenda: E<n> empilha e vai ao estado n | R<n> reduz pela "
                    "producao n | AC aceita\n"
                    "         ERRO celula vazia em ACTION; a linha seguinte ja "
                    "mostra a pilha apos a recuperacao\n\n")
        cab = (f"{'Pilha':<{self.LARGURA_PILHA}}  "
               f"{'Entrada':<{self.LARGURA_ENTRADA}}  Acao")
        saida.write(cab + "\n")
        saida.write("-" * len(cab) + "\n")
        for pilha, entrada, texto in self.passos:
            saida.write(f"{pilha:<{self.LARGURA_PILHA}}  "
                        f"{entrada:<{self.LARGURA_ENTRADA}}  {texto}\n")
        saida.write(f"\nTotal de passos: {len(self.passos)}\n")

    # ---------------------------------------------------- modo panico

    def _recuperar(self, pilha_estados, pilha_nos, tokens, i, forcar):
        """Recuperacao em modo panico.

        Procura, do topo para a base da pilha, um estado com GOTO definido para
        um nao-terminal de sincronizacao A; em seguida descarta tokens da
        entrada ate encontrar um que possa seguir A (isto e, que esteja em
        FOLLOW(A)). Entao desempilha ate aquele estado, empilha GOTO[estado, A]
        e retoma a analise dali.

        Retorna a nova posicao na entrada, ou None se nao houver como continuar.
        """
        if forcar:
            # A recuperacao ja falhou neste ponto: descarta um token para
            # garantir progresso.
            return i + 1 if tokens[i].terminal != FIM else None

        for nt in SINCRONIZADORES:
            for topo in range(len(pilha_estados) - 1, -1, -1):
                destino = self.tabela.goto.get((pilha_estados[topo], nt))
                if destino is None:
                    continue

                j = i
                while True:
                    if tokens[j].terminal in self.tabela.follow[nt]:
                        descartados = pilha_nos[topo:]
                        del pilha_estados[topo + 1:]
                        del pilha_nos[topo:]
                        pilha_estados.append(destino)
                        pilha_nos.append(No(nt, descartados, erro=True))
                        return j
                    if tokens[j].terminal == FIM:
                        break
                    j += 1

        # Nenhum sincronizador serviu: descarta o token e tenta de novo.
        return i + 1 if tokens[i].terminal != FIM else None


# ==========================================================================
# EXECUCAO
# ==========================================================================

def compilar(caminho, mostrar_tokens=False, mostrar_derivacao=False,
             mostrar_arvore=False, mostrar_itens=False, mostrar_tabela=False,
             mostrar_passos=False):
    with open(caminho, "r", encoding="utf-8") as arquivo:
        codigo = arquivo.read()

    print(f"Analisando '{caminho}'...\n")

    # --- Analise lexica
    tokens, erros_lex = analisador_lexico(codigo)

    if mostrar_tokens:
        print("--- TOKENS ---")
        for t in tokens:
            print(f"{t.linha:>5}:{t.coluna:<4} {t.classe:<14} "
                  f"{t.terminal:<14} {t.lexema}")
        print()

    if erros_lex:
        print(f"--- ERROS LEXICOS ({len(erros_lex)}) ---")
        for e in erros_lex:
            print(e)
        print("\nA analise sintatica prossegue com os tokens reconhecidos.\n")

    # --- Analise sintatica
    analisador = AnalisadorSintatico()

    if mostrar_itens:
        analisador.tabela.imprimir_itens()
    if mostrar_tabela:
        analisador.tabela.imprimir_tabela(rotulo=rotulo_curto)

    aceito, raiz, erros_sin, derivacao, suprimidos = analisador.analisar(
        tokens, registrar_passos=mostrar_passos)

    if mostrar_passos:
        analisador.imprimir_passos()
        print()

    if mostrar_derivacao:
        print("--- DERIVACAO (reducoes na ordem em que ocorreram) ---")
        for n, ip in enumerate(derivacao, 1):
            print(f"{n:>4}. ({ip}) {analisador.tabela.formatar_producao(ip)}")
        print()

    if mostrar_arvore and raiz is not None:
        print("--- ARVORE SINTATICA ---")
        raiz.imprimir()
        print()

    if erros_sin:
        print(f"--- ERROS SINTATICOS ({len(erros_sin)}) ---")
        for e in erros_sin:
            print(e)
        if suprimidos:
            print(f"\n({suprimidos} mensagem(ns) omitida(s) por serem provavel "
                  f"eco da recuperacao, e nao defeitos novos.)")

    print()
    total = len(erros_lex) + len(erros_sin)
    if total == 0:
        print("PROGRAMA ACEITO: nenhum erro lexico ou sintatico.")
        return 0

    print(f"PROGRAMA REJEITADO: {len(erros_lex)} erro(s) lexico(s), "
          f"{len(erros_sin)} erro(s) sintatico(s).")
    return 1


def saida_tolerante():
    """O console classico do Windows usa cp1252, e nem todo caractere cabe
    nessa tabela. Um caractere fora do alfabeto da linguagem, ou uma cadeia
    com acentuacao incomum, quebraria a impressao do erro com
    UnicodeEncodeError - justo na mensagem que deveria explicar o problema.
    Escapar em vez de falhar mantem o compilador utilizavel em qualquer
    terminal, sem mudar nada onde a saida ja e UTF-8 (Linux, macOS, Windows
    Terminal)."""
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="backslashreplace")


def main():
    saida_tolerante()
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    opcoes = {a for a in sys.argv[1:] if a.startswith("--")}

    desconhecidas = opcoes - {"--tokens", "--derivacao", "--arvore",
                              "--itens", "--tabela", "--passos"}
    if desconhecidas:
        print(f"Opcao desconhecida: {', '.join(sorted(desconhecidas))}")
        print(__doc__)
        return 2

    caminho = argumentos[0] if argumentos else "programa_teste.txt"

    try:
        return compilar(caminho,
                        mostrar_tokens="--tokens" in opcoes,
                        mostrar_derivacao="--derivacao" in opcoes,
                        mostrar_arvore="--arvore" in opcoes,
                        mostrar_itens="--itens" in opcoes,
                        mostrar_tabela="--tabela" in opcoes,
                        mostrar_passos="--passos" in opcoes)
    except FileNotFoundError:
        print(f"Erro: arquivo '{caminho}' nao encontrado.")
        print(__doc__)
        return 2


if __name__ == "__main__":
    sys.exit(main())
