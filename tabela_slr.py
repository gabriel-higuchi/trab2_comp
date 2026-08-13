"""
Construcao da tabela SLR(1) a partir da gramatica de gramatica.py.

Nenhum gerador automatico e usado: FIRST, FOLLOW, a colecao canonica de itens
LR(0) e as tabelas ACTION/GOTO sao calculados aqui.

Executado diretamente, imprime o relatorio de conflitos:
    python tabela_slr.py
"""

import sys

from gramatica import carregar

FIM = "$"
AUMENTADA = "<S'>"


class TabelaSLR:

    def __init__(self, producoes, inicial):
        # Producao 0 e sempre a aumentada: <S'> -> <inicial>
        self.producoes = [(AUMENTADA, (inicial,))] + list(producoes)
        self.inicial = inicial
        self.naoterminais = {e for e, _ in self.producoes}
        self.terminais = {s for _, d in self.producoes
                          for s in d if s not in self.naoterminais}

        self.anulaveis = self._calcular_anulaveis()
        self.first = self._calcular_first()
        self.follow = self._calcular_follow()

        self.estados, self.transicoes = self._colecao_canonica()
        self.acao, self.goto, self.conflitos = self._montar_tabela()

    # ------------------------------------------------------------ conjuntos

    def _calcular_anulaveis(self):
        anulaveis = set()
        mudou = True
        while mudou:
            mudou = False
            for esq, dir_ in self.producoes:
                if esq not in anulaveis and all(s in anulaveis for s in dir_):
                    anulaveis.add(esq)
                    mudou = True
        return anulaveis

    def _calcular_first(self):
        first = {t: {t} for t in self.terminais}
        for n in self.naoterminais:
            first[n] = set()
        mudou = True
        while mudou:
            mudou = False
            for esq, dir_ in self.producoes:
                antes = len(first[esq])
                for s in dir_:
                    first[esq] |= first[s]
                    if s not in self.anulaveis:
                        break
                if len(first[esq]) != antes:
                    mudou = True
        return first

    def first_sequencia(self, sequencia):
        """FIRST de uma sequencia de simbolos (sem o marcador de vazio)."""
        r = set()
        for s in sequencia:
            r |= self.first[s]
            if s not in self.anulaveis:
                return r
        return r

    def _anulavel_sequencia(self, sequencia):
        return all(s in self.anulaveis for s in sequencia)

    def _calcular_follow(self):
        follow = {n: set() for n in self.naoterminais}
        follow[AUMENTADA].add(FIM)
        follow[self.inicial].add(FIM)
        mudou = True
        while mudou:
            mudou = False
            for esq, dir_ in self.producoes:
                for i, s in enumerate(dir_):
                    if s not in self.naoterminais:
                        continue
                    antes = len(follow[s])
                    resto = dir_[i + 1:]
                    follow[s] |= self.first_sequencia(resto)
                    if self._anulavel_sequencia(resto):
                        follow[s] |= follow[esq]
                    if len(follow[s]) != antes:
                        mudou = True
        return follow

    # ------------------------------------------------------- itens LR(0)

    def fechamento(self, itens):
        """Um item e o par (indice da producao, posicao do ponto)."""
        itens = set(itens)
        pilha = list(itens)
        while pilha:
            ip, ponto = pilha.pop()
            dir_ = self.producoes[ip][1]
            if ponto < len(dir_) and dir_[ponto] in self.naoterminais:
                for j, (esq, _) in enumerate(self.producoes):
                    if esq == dir_[ponto] and (j, 0) not in itens:
                        itens.add((j, 0))
                        pilha.append((j, 0))
        return frozenset(itens)

    def ir_para(self, estado, simbolo):
        return self.fechamento({
            (ip, p + 1) for ip, p in estado
            if p < len(self.producoes[ip][1]) and self.producoes[ip][1][p] == simbolo
        })

    def _colecao_canonica(self):
        i0 = self.fechamento({(0, 0)})
        estados = [i0]
        indice = {i0: 0}
        transicoes = {}
        fila = [i0]
        simbolos = sorted(self.terminais | (self.naoterminais - {AUMENTADA}))
        while fila:
            atual = fila.pop(0)
            for s in simbolos:
                novo = self.ir_para(atual, s)
                if not novo:
                    continue
                if novo not in indice:
                    indice[novo] = len(estados)
                    estados.append(novo)
                    fila.append(novo)
                transicoes[(indice[atual], s)] = indice[novo]
        return estados, transicoes

    # ----------------------------------------------------------- ACTION/GOTO

    def _montar_tabela(self):
        acao, goto, conflitos = {}, {}, []

        def registrar(estado, terminal, nova):
            chave = (estado, terminal)
            if chave in acao and acao[chave] != nova:
                conflitos.append((estado, terminal, acao[chave], nova))
            else:
                acao[chave] = nova

        for i, estado in enumerate(self.estados):
            for s in self.terminais:
                if (i, s) in self.transicoes:
                    registrar(i, s, ("s", self.transicoes[(i, s)]))
            for n in self.naoterminais:
                if (i, n) in self.transicoes:
                    goto[(i, n)] = self.transicoes[(i, n)]
            for ip, ponto in estado:
                esq, dir_ = self.producoes[ip]
                if ponto != len(dir_):
                    continue
                if esq == AUMENTADA:
                    registrar(i, FIM, ("acc", None))
                else:
                    for t in self.follow[esq]:
                        registrar(i, t, ("r", ip))

        return acao, goto, conflitos

    # ------------------------------------------------------------- utilidades

    def esperados(self, estado):
        """Terminais com acao definida no estado - usado nas mensagens de erro."""
        return sorted(t for (s, t) in self.acao if s == estado)

    def formatar_producao(self, ip):
        esq, dir_ = self.producoes[ip]
        return f"{esq} -> {' '.join(dir_) if dir_ else 'vazio'}"

    def descrever_estado(self, i):
        linhas = []
        for ip, p in sorted(self.estados[i]):
            esq, dir_ = self.producoes[ip]
            corpo = list(dir_[:p]) + ["."] + list(dir_[p:])
            linhas.append(f"    {esq} -> {' '.join(corpo)}")
        return "\n".join(linhas)

    # ------------------------------------------------ impressao (Passos 2 e 3)

    def celula(self, estado, simbolo):
        """Conteudo de ACTION/GOTO na notacao usual: E<n> empilha,
        R<n> reduz pela producao n, AC aceita, vazio = erro."""
        if simbolo in self.naoterminais:
            destino = self.goto.get((estado, simbolo))
            return "" if destino is None else str(destino)
        acao = self.acao.get((estado, simbolo))
        if acao is None:
            return ""
        tipo, arg = acao
        if tipo == "s":
            return f"E{arg}"
        if tipo == "r":
            return f"R{arg}"
        return "AC"

    def imprimir_itens(self, saida=None):
        """A colecao canonica I0..In, com as transicoes de desvio que saem de
        cada estado."""
        saida = saida if saida is not None else sys.stdout
        saida.write("--- CONJUNTO DE ITENS (AUTOMATO LR(0)) ---\n\n")
        for i in range(len(self.estados)):
            saida.write(f"I{i}:\n")
            saida.write(self.descrever_estado(i) + "\n")
            saidas = sorted((s, d) for (e, s), d in self.transicoes.items() if e == i)
            if saidas:
                setas = ",  ".join(f"{s} -> I{d}" for s, d in saidas)
                saida.write(f"    desvios: {setas}\n")
            saida.write("\n")

    def imprimir_tabela(self, rotulo=None, largura_maxima=100, saida=None):
        """A matriz ACTION/GOTO.

        A matriz tem colunas demais para uma linha de terminal, entao e
        quebrada em blocos de colunas. 'rotulo' converte o nome do terminal
        em um rotulo curto (';' em vez de 'ponto_virgula')."""
        saida = saida if saida is not None else sys.stdout
        rotulo = rotulo or (lambda t: t)

        # Ordenar pelo nome interno deixaria a ordem visual arbitraria ('{'
        # antes de '(' porque 'abre_chave' < 'abre_par'). Ordena-se pelo
        # rotulo exibido, com os simbolos antes das palavras e '$' no fim.
        terminais = sorted(self.terminais - {FIM},
                           key=lambda t: (rotulo(t)[:1].isalnum(), rotulo(t)))
        terminais.append(FIM)
        naoterminais = sorted(self.naoterminais - {AUMENTADA})
        colunas = ([(t, rotulo(t)) for t in terminais]
                   + [(n, n) for n in naoterminais])

        # Cada coluna e larga o bastante para o rotulo e para o maior conteudo.
        larguras = {}
        for simbolo, texto in colunas:
            maior = max((len(self.celula(i, simbolo))
                         for i in range(len(self.estados))), default=0)
            larguras[simbolo] = max(len(texto), maior, 3)

        saida.write("--- TABELA SLR(1) - ACTION e GOTO ---\n")
        saida.write("Legenda: E<n> empilha e vai ao estado n | R<n> reduz pela "
                    "producao n\n         AC aceita | celula vazia = ERRO "
                    "(dispara a recuperacao)\n\n")

        # Quebra em blocos que caibam na largura pedida. ACTION e GOTO nunca
        # dividem um bloco: sao tabelas distintas e a fronteira tem que
        # aparecer.
        def quebrar(itens):
            blocos, atual, largura = [], [], 6
            for simbolo, texto in itens:
                w = larguras[simbolo] + 1
                if atual and largura + w > largura_maxima:
                    blocos.append(atual)
                    atual, largura = [], 6
                atual.append((simbolo, texto))
                largura += w
            if atual:
                blocos.append(atual)
            return blocos

        corte = len(terminais)
        blocos = ([("ACTION", b) for b in quebrar(colunas[:corte])]
                  + [("GOTO", b) for b in quebrar(colunas[corte:])])

        for n, (tipo, bloco) in enumerate(blocos, 1):
            saida.write(f"[{tipo} - bloco {n}/{len(blocos)}]\n")
            cabecalho = "estado" + "".join(
                f" {texto:>{larguras[s]}}" for s, texto in bloco)
            saida.write(cabecalho + "\n")
            saida.write("-" * len(cabecalho) + "\n")
            for i in range(len(self.estados)):
                linha = f"{i:>6}" + "".join(
                    f" {self.celula(i, s):>{larguras[s]}}" for s, _ in bloco)
                saida.write(linha + "\n")
            saida.write("\n")


def construir():
    producoes, _, _ = carregar()
    return TabelaSLR(producoes, producoes[0][0])


if __name__ == "__main__":
    t = construir()
    print(f"Producoes (incluindo a aumentada): {len(t.producoes)}")
    print(f"Terminais: {len(t.terminais)}   Nao-terminais: {len(t.naoterminais) - 1}")
    print(f"Estados LR(0): {len(t.estados)}")
    print(f"Entradas ACTION: {len(t.acao)}   Entradas GOTO: {len(t.goto)}")

    if t.conflitos:
        print(f"\n!!! {len(t.conflitos)} CONFLITO(S):")
        for estado, terminal, a, b in t.conflitos[:20]:
            print(f"\n  estado {estado}, lookahead '{terminal}': {a} vs {b}")
            print(t.descrever_estado(estado))
        raise SystemExit(1)

    print("\nOK: nenhum conflito shift/reduce ou reduce/reduce.")
    print("A gramatica e SLR(1).")
