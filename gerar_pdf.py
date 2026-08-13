# -*- coding: utf-8 -*-
"""Renderiza gramatica.md em gramatica.pdf.

Ferramenta auxiliar: NAO faz parte do compilador. Serve apenas para regerar o
documento da gramatica depois de editar o .md. Requer reportlab:

    pip install reportlab
    python gerar_pdf.py
"""
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Preformatted, Spacer, Table, TableStyle)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

AQUI = Path(__file__).resolve().parent
ORIGEM = AQUI / "gramatica.md"
DESTINO = AQUI / "gramatica.pdf"

# As fontes embutidas do reportlab (Helvetica/Courier) nao tem os glifos
# U+2192 (seta), U+03B5 (epsilon) nem U+2022 (bullet): eles sairiam em branco.
# Por isso registramos fontes TrueType do sistema.
DIRETORIOS_DE_FONTE = [
    Path("C:/Windows/Fonts"),                       # Windows
    Path("/usr/share/fonts/truetype/dejavu"),       # Linux
    Path("/Library/Fonts"),                         # macOS
]
FONTES = [
    ("Texto", ["arial.ttf", "DejaVuSans.ttf", "Arial.ttf"]),
    ("TextoBold", ["arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"]),
    ("Mono", ["consola.ttf", "DejaVuSansMono.ttf", "Courier New.ttf"]),
    ("MonoBold", ["consolab.ttf", "DejaVuSansMono-Bold.ttf", "Courier New Bold.ttf"]),
]


def registrar_fontes():
    for apelido, candidatos in FONTES:
        caminho = next((d / n for d in DIRETORIOS_DE_FONTE for n in candidatos
                        if (d / n).is_file()), None)
        if caminho is None:
            sys.exit(f"Nenhuma fonte TrueType encontrada para '{apelido}'.\n"
                     f"Procurei por {candidatos} em "
                     f"{[str(d) for d in DIRETORIOS_DE_FONTE]}.")
        pdfmetrics.registerFont(TTFont(apelido, str(caminho)))
    pdfmetrics.registerFontFamily("Texto", normal="Texto", bold="TextoBold")
    pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="MonoBold")


registrar_fontes()

TINTA = colors.HexColor("#1a1a1a")
CINZA = colors.HexColor("#6b6b6b")
REGUA = colors.HexColor("#d4d4d4")
FUNDO = colors.HexColor("#f6f6f4")

ss = getSampleStyleSheet()

E = {
    "h1": ParagraphStyle("h1", parent=ss["Normal"], fontName="TextoBold",
                         fontSize=19, leading=24, spaceBefore=0, spaceAfter=4,
                         textColor=TINTA),
    "h2": ParagraphStyle("h2", parent=ss["Normal"], fontName="TextoBold",
                         fontSize=13.5, leading=17, spaceBefore=20, spaceAfter=7,
                         textColor=TINTA),
    "h3": ParagraphStyle("h3", parent=ss["Normal"], fontName="TextoBold",
                         fontSize=11, leading=14, spaceBefore=13, spaceAfter=5,
                         textColor=TINTA),
    "p": ParagraphStyle("p", parent=ss["Normal"], fontName="Texto",
                        fontSize=9.6, leading=14.2, spaceAfter=7,
                        alignment=TA_LEFT, textColor=TINTA),
    "sub": ParagraphStyle("sub", parent=ss["Normal"], fontName="Texto",
                          fontSize=10, leading=14, spaceAfter=2, textColor=CINZA),
    "li": ParagraphStyle("li", parent=ss["Normal"], fontName="Texto",
                         fontSize=9.6, leading=14, spaceAfter=3.5,
                         leftIndent=13, bulletIndent=3, textColor=TINTA),
    "code": ParagraphStyle("code", parent=ss["Normal"], fontName="Mono",
                           fontSize=8.1, leading=10.4, textColor=TINTA),
    "celula": ParagraphStyle("celula", parent=ss["Normal"], fontName="Texto",
                             fontSize=8.6, leading=11, textColor=TINTA),
    "celula_cab": ParagraphStyle("celula_cab", parent=ss["Normal"],
                                 fontName="TextoBold", fontSize=8.6,
                                 leading=11, textColor=TINTA),
}


def inline(txt):
    """Converte marcação inline do Markdown para as tags do ReportLab."""
    txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
    txt = re.sub(r"`(.+?)`",
                 r'<font face="Mono" size="8.8" color="#7a2f2f">\1</font>', txt)
    return txt


def montar_tabela(linhas, largura):
    corpo = [l for l in linhas if not re.match(r"^\|[\s:|-]+\|$", l)]
    dados = []
    for i, l in enumerate(corpo):
        celulas = [c.strip() for c in l.strip().strip("|").split("|")]
        est = E["celula_cab"] if i == 0 else E["celula"]
        dados.append([Paragraph(inline(c), est) for c in celulas])

    ncols = max(len(r) for r in dados)
    for r in dados:
        while len(r) < ncols:
            r.append(Paragraph("", E["celula"]))

    t = Table(dados, colWidths=[largura / ncols] * ncols, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FUNDO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, colors.HexColor("#9a9a9a")),
        ("LINEBELOW", (0, 1), (-1, -2), 0.28, REGUA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def construir(md, largura):
    fluxo = []
    linhas = md.split("\n")
    i = 0
    primeiro_h1 = True

    while i < len(linhas):
        ln = linhas[i]

        if ln.strip() == "---":
            fluxo.append(Spacer(1, 9))
            i += 1
            continue

        if ln.startswith("```"):
            i += 1
            bloco = []
            while i < len(linhas) and not linhas[i].startswith("```"):
                bloco.append(linhas[i])
                i += 1
            i += 1
            pre = Preformatted("\n".join(bloco), E["code"])
            caixa = Table([[pre]], colWidths=[largura], hAlign="LEFT")
            caixa.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), FUNDO),
                ("BOX", (0, 0), (-1, -1), 0.4, REGUA),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
            fluxo.append(caixa)
            fluxo.append(Spacer(1, 9))
            continue

        if ln.startswith("|"):
            bloco = []
            while i < len(linhas) and linhas[i].startswith("|"):
                bloco.append(linhas[i])
                i += 1
            fluxo.append(montar_tabela(bloco, largura))
            fluxo.append(Spacer(1, 11))
            continue

        # No Markdown um paragrafo ou item de lista pode ocupar varias linhas.
        # Sem junta-las, uma marcacao **negrito** partida na quebra ficaria
        # literal e a continuacao do item perderia o recuo do bullet.
        def juntar_continuacao(texto, j):
            while (j < len(linhas) and linhas[j].strip()
                   and not linhas[j].startswith(("#", "|", "```", "- ", "---"))
                   and not re.match(r"^\d+\. ", linhas[j])):
                texto += " " + linhas[j].strip()
                j += 1
            return texto, j

        if ln.startswith("### "):
            fluxo.append(Paragraph(inline(ln[4:]), E["h3"]))
        elif ln.startswith("## "):
            fluxo.append(Paragraph(inline(ln[3:]), E["h2"]))
        elif ln.startswith("# "):
            fluxo.append(Paragraph(inline(ln[2:]), E["h1"]))
            primeiro_h1 = False
        elif ln.startswith("- "):
            texto, i = juntar_continuacao(ln[2:], i + 1)
            fluxo.append(Paragraph(inline(texto), E["li"], bulletText="•"))
            continue
        elif re.match(r"^\d+\. ", ln):
            n, resto = ln.split(". ", 1)
            texto, i = juntar_continuacao(resto, i + 1)
            fluxo.append(Paragraph(inline(texto), E["li"], bulletText=n + "."))
            continue
        elif ln.strip() == "":
            pass
        else:
            # linhas soltas logo abaixo do titulo viram subtitulo cinza
            estilo = E["sub"] if (not primeiro_h1 and len(fluxo) <= 3) else E["p"]
            texto, i = juntar_continuacao(ln, i + 1)
            fluxo.append(Paragraph(inline(texto), estilo))
            continue

        i += 1


    return fluxo


def rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Texto", 7.8)
    canvas.setFillColor(CINZA)
    canvas.drawRightString(A4[0] - 2.2 * cm, 1.35 * cm, str(canvas.getPageNumber()))
    canvas.drawString(2.2 * cm, 1.35 * cm,
                      "Compiladores \u2014 Parte 2 \u2014 Gram\u00e1tica Livre de Contexto")
    canvas.setStrokeColor(REGUA)
    canvas.setLineWidth(0.4)
    canvas.line(2.2 * cm, 1.72 * cm, A4[0] - 2.2 * cm, 1.72 * cm)
    canvas.restoreState()


with open(ORIGEM, encoding="utf-8") as f:
    md = f.read()

doc = BaseDocTemplate(str(DESTINO), pagesize=A4,  # reportlab nao aceita Path
                      leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                      topMargin=2.0 * cm, bottomMargin=2.2 * cm,
                      title="Gramatica Livre de Contexto - Compiladores Parte 2")
quadro = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="corpo")
doc.addPageTemplates([PageTemplate(id="padrao", frames=[quadro], onPage=rodape)])
doc.build(construir(md, doc.width))
print(f"PDF gerado: {DESTINO}")
