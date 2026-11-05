#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

tools/gerar_marketing.py

========================

Gerador Local de Materiais para Redes Sociais do Café Radar (Marketing Engine v1.0.1).

Consome os JSONs públicos gerados pelo pipeline:

  - web/data/fechamento.json

  - web/data/swingtrade.json

  - web/data/dashboard.json

Produz:

  - Cards PNG em 2 formatos:

      * Instagram Feed: 1080 x 1350 px (Proporção 4:5 vertical)

      * X / Twitter: 1200 x 675 px (Proporção 16:9 horizontal)

  - Legendas TXT com textos estruturados, cashtags e disclaimers CVM 19/20.

Saída:

  - web/marketing_output/ (ou diretório customizado fornecido por output_dir)

Melhorias v1.0.1:

  - Separação explícita de data_publicacao, data_base e data_scanner.

  - Formato DD/MM/AAAA padronizado em todas as legendas.

  - Limite de 4 linhas com reticências para manchetes.

  - Layout do card X no Swing Trade em grade de 2 colunas para melhor legibilidade.

  - Cashtags inteligentes baseadas nos tickers presentes na sessão.

  - Suporte completo a injeção de output_dir para isolamento em testes unitários.

"""

from __future__ import annotations

import json

import os

import sys

from datetime import datetime

from pathlib import Path

from typing import Any, Dict, List, Optional, Tuple

try:

    from PIL import Image, ImageDraw, ImageFont

except ImportError:

    print("ERRO CRÍTICO: Pillow (PIL) não está instalado.", file=sys.stderr)

    sys.exit(1)

# Caminhos base
BASE_DIR = Path(__file__).resolve().parent.parent

if (BASE_DIR / "web" / "data" / "fechamento.json").is_file():
    DATA_DIR = BASE_DIR / "web" / "data"
elif (BASE_DIR / "data" / "fechamento.json").is_file():
    DATA_DIR = BASE_DIR / "data"
else:
    DATA_DIR = BASE_DIR / "data"

if (BASE_DIR / "marketing_output").is_dir() or not (BASE_DIR / "web").is_dir():
    DEFAULT_OUTPUT_DIR = BASE_DIR / "marketing_output"
else:
    DEFAULT_OUTPUT_DIR = BASE_DIR / "web" / "marketing_output"

ASSETS_DIR = BASE_DIR

# Paleta oficial Café Radar

PALETA = {

    "bg": "#0f172a",          # Slate dark 900

    "card_bg": "#1e293b",     # Slate dark 800

    "card_border": "#334155", # Slate 700

    "card_inner": "#172554",  # Azul escuro

    "destaque": "#2563eb",    # Azul Royal

    "destaque_claro": "#38bdf8", # Azul Celeste

    "verde": "#16a34a",       # Verde Positivo (+5%)

    "verde_texto": "#4ade80", # Verde claro para leitura

    "verde_bg": "#052e16",    # Fundo verde suave

    "vermelho": "#dc2626",    # Vermelho Negativo

    "vermelho_texto": "#f87171", # Vermelho claro

    "vermelho_bg": "#450a0a", # Fundo vermelho suave

    "neutro": "#64748b",      # Cinza neutro

    "texto_branco": "#ffffff",# Branco puro

    "texto_secundario": "#94a3b8", # Cinza claro

    "texto_mutado": "#64748b" # Cinza escuro

}

def carregar_fontes():

    """Tenta carregar fontes do sistema com fallbacks seguros."""

    font_bold_names = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]

    font_regular_names = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]

    font_mono_names = ["consolab.ttf", "consola.ttf", "Courier New.ttf"]

    def _obter_fonte(nomes, tamanho):

        for n in nomes:

            try:

                return ImageFont.truetype(n, tamanho)

            except Exception:

                continue

        return ImageFont.load_default()

    return {

        "header_title": lambda sz: _obter_fonte(font_bold_names, sz),

        "header_sub": lambda sz: _obter_fonte(font_regular_names, sz),

        "card_title": lambda sz: _obter_fonte(font_bold_names, sz),

        "body": lambda sz: _obter_fonte(font_regular_names, sz),

        "body_bold": lambda sz: _obter_fonte(font_bold_names, sz),

        "mono": lambda sz: _obter_fonte(font_mono_names, sz),

    }

FONTES = carregar_fontes()

# ==============================================================================

# CARREGADORES E VALIDADORES DE DADOS

# ==============================================================================

def carregar_fechamento(caminho: Optional[Path] = None) -> Tuple[bool, Optional[Dict[str, Any]], str]:

    """Valida e carrega fechamento.json."""

    p = caminho or (DATA_DIR / "fechamento.json")

    if not p.is_file():

        return False, None, f"Arquivo não encontrado: {p}"

    try:

        dados = json.loads(p.read_text(encoding="utf-8"))

    except Exception as e:

        return False, None, f"Erro ao decodificar JSON: {e}"

    if not isinstance(dados, dict) or "edicoes" not in dados:

        return False, None, "Estrutura inválida em fechamento.json: chave 'edicoes' ausente"

    return True, dados, "OK"

def carregar_swingtrade(caminho: Optional[Path] = None) -> Tuple[bool, Optional[Dict[str, Any]], str]:

    """Valida e carrega swingtrade.json."""

    p = caminho or (DATA_DIR / "swingtrade.json")

    if not p.is_file():

        return False, None, f"Arquivo não encontrado: {p}"

    try:

        dados = json.loads(p.read_text(encoding="utf-8"))

    except Exception as e:

        return False, None, f"Erro ao decodificar JSON: {e}"

    if not isinstance(dados, dict) or "estrategia" not in dados:

        return False, None, "Estrutura inválida em swingtrade.json: chave 'estrategia' ausente"

    return True, dados, "OK"

def carregar_dashboard(caminho: Optional[Path] = None) -> Tuple[bool, Optional[Dict[str, Any]], str]:

    """Valida e carrega dashboard.json."""

    p = caminho or (DATA_DIR / "dashboard.json")

    if not p.is_file():

        return False, None, f"Arquivo não encontrado: {p}"

    try:

        dados = json.loads(p.read_text(encoding="utf-8"))

    except Exception as e:

        return False, None, f"Erro ao decodificar JSON: {e}"

    if not isinstance(dados, dict) or "allocation" not in dados:

        return False, None, "Estrutura inválida em dashboard.json: chave 'allocation' ausente"

    return True, dados, "OK"

def formatar_data_br(data_iso: str) -> str:

    """Converte 'AAAA-MM-DD' para 'DD/MM/AAAA'."""

    if not data_iso or len(data_iso) < 10:

        return data_iso

    try:

        dt = datetime.strptime(data_iso[:10], "%Y-%m-%d")

        return dt.strftime("%d/%m/%Y")

    except Exception:

        return data_iso

# ==============================================================================

# DESENHO VISUAL BASE DOS CARDS (CANVAS, LOGO E RODAPÉ)

# ==============================================================================

def criar_canvas_base(largura: int, altura: int, categoria_badge: str, titulo: str, data_str: str) -> Tuple[Image.Image, ImageDraw.ImageDraw]:

    """Cria a estrutura estética padrão dos cards do Café Radar."""

    img = Image.new("RGB", (largura, altura), PALETA["bg"])

    draw = ImageDraw.Draw(img)

    # Margens proporcionais

    margem_x = int(largura * 0.055)

    margem_y = int(altura * 0.045)

    # 1. Topo: Logo "CR"

    tam_logo = 64 if altura > 800 else 50

    draw.rounded_rectangle([margem_x, margem_y, margem_x + tam_logo, margem_y + tam_logo], radius=14, fill=PALETA["destaque"])

    f_logo = FONTES["header_title"](tam_logo // 2)

    draw.text((margem_x + tam_logo * 0.18, margem_y + tam_logo * 0.18), "CR", font=f_logo, fill=PALETA["texto_branco"])

    # 2. Marca e categoria

    f_marca = FONTES["header_title"](26 if altura > 800 else 22)

    draw.text((margem_x + tam_logo + 16, margem_y + 2), "CAFERADAR", font=f_marca, fill=PALETA["texto_branco"])

    f_badge = FONTES["body_bold"](15 if altura > 800 else 13)

    badge_txt = f" {categoria_badge.upper()} "

    draw.text((margem_x + tam_logo + 16, margem_y + 36), badge_txt, font=f_badge, fill=PALETA["destaque_claro"])

    # 3. Data no canto direito do topo

    f_data = FONTES["body"](16 if altura > 800 else 14)

    data_label = f"Ref: {data_str}"

    bbox_d = draw.textbbox((0, 0), data_label, font=f_data)

    larg_d = bbox_d[2] - bbox_d[0]

    draw.text((largura - margem_x - larg_d, margem_y + 12), data_label, font=f_data, fill=PALETA["texto_secundario"])

    # Linha divisória suave

    y_div = margem_y + tam_logo + 24

    draw.line([margem_x, y_div, largura - margem_x, y_div], fill=PALETA["card_border"], width=1)

    # 4. Título Principal do Card

    f_titulo = FONTES["header_title"](38 if altura > 800 else 30)

    draw.text((margem_x, y_div + 18), titulo, font=f_titulo, fill=PALETA["texto_branco"])

    # 5. Rodapé Institucional e Compliance

    y_rodape = altura - margem_y - (55 if altura > 800 else 40)

    draw.line([margem_x, y_rodape, largura - margem_x, y_rodape], fill=PALETA["card_border"], width=1)

    f_rod = FONTES["body"](14 if altura > 800 else 12)

    draw.text((margem_x, y_rodape + 14), "caferadar.com.br • Inteligência de Mercado B3", font=f_rod, fill=PALETA["destaque_claro"])

    disc_txt = "Estudo quantitativo. Não é recomendação de investimento (CVM 19/20)."

    bbox_disc = draw.textbbox((0, 0), disc_txt, font=f_rod)

    larg_disc = bbox_disc[2] - bbox_disc[0]

    draw.text((largura - margem_x - larg_disc, y_rodape + 14), disc_txt, font=f_rod, fill=PALETA["texto_mutado"])

    return img, draw

# ==============================================================================

# GERADOR CATEGORIA A: CAFÉ MATINAL (ABERTURA DOS MERCADOS)

# ==============================================================================

def gerar_materiais_abertura(dados_fechamento: Dict[str, Any], output_dir: Optional[Path] = None) -> Tuple[List[Path], Path]:

    """Gera cards (Feed e X) e legenda para Abertura dos Mercados."""

    out = Path(output_dir or DEFAULT_OUTPUT_DIR)

    out.mkdir(parents=True, exist_ok=True)

    ed = dados_fechamento.get("edicoes", {}).get("abertura", {})

    data_pub = datetime.now().strftime("%Y-%m-%d")

    data_base = dados_fechamento.get("data_referencia", data_pub)

    data_fmt = dados_fechamento.get("data_formatada") or formatar_data_br(data_base)

    mercados = ed.get("mercado_geral", {})

    leitura = ed.get("leitura_rapida", [])

    def _obter_item(chave, nome_padrao):

        m = mercados.get(chave, {})

        val = m.get("valor") or "Indisponível"

        var = m.get("variacao") or "—"

        pos = m.get("positivo", True)

        return (nome_padrao, val, var, pos)

    itens_grid = [

        _obter_item("sp500", "S&P 500 Futuro"),

        _obter_item("nasdaq", "Nasdaq Futuro"),

        _obter_item("dolar", "Dólar Futuro"),

        _obter_item("brent", "Petróleo Brent"),

        _obter_item("bitcoin", "Bitcoin (BTC)")

    ]

    destaque_texto = ""

    if leitura:

        destaque_texto = leitura[0].get("texto", "")

    arquivos_png = []

    # 1. Instagram Feed (1080x1350)

    img_feed, draw_feed = criar_canvas_base(1080, 1350, "Café Matinal", "Pré-Mercado & Futuros Globais", data_fmt)

    y_start = 220

    x_left = 60

    col_w = 460

    card_h = 135

    gap_x = 40

    gap_y = 20

    for idx, (nome, val, var, pos) in enumerate(itens_grid[:4]):

        col = idx % 2

        lin = idx // 2

        cx = x_left + col * (col_w + gap_x)

        cy = y_start + lin * (card_h + gap_y)

        draw_feed.rounded_rectangle([cx, cy, cx + col_w, cy + card_h], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)

        f_lbl = FONTES["body"](16)

        draw_feed.text((cx + 20, cy + 18), nome, font=f_lbl, fill=PALETA["texto_secundario"])

        f_val = FONTES["mono"](28)

        draw_feed.text((cx + 20, cy + 54), str(val), font=f_val, fill=PALETA["texto_branco"])

        # Badge de variação

        if var != "—":

            cor_badge = PALETA["verde_texto"] if pos else PALETA["vermelho_texto"]

            cor_badge_bg = PALETA["verde_bg"] if pos else PALETA["vermelho_bg"]

            f_var = FONTES["body_bold"](20)

            draw_feed.rounded_rectangle([cx + col_w - 130, cy + 48, cx + col_w - 20, cy + 92], radius=8, fill=cor_badge_bg)

            draw_feed.text((cx + col_w - 118, cy + 58), str(var), font=f_var, fill=cor_badge)

    # 5º Item: Bitcoin em destaque horizontal

    cy5 = y_start + 2 * (card_h + gap_y)

    draw_feed.rounded_rectangle([x_left, cy5, x_left + 960, cy5 + 110], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)

    btc_nome, btc_val, btc_var, btc_pos = itens_grid[4]

    draw_feed.text((x_left + 24, cy5 + 20), btc_nome, font=FONTES["body"](16), fill=PALETA["texto_secundario"])

    draw_feed.text((x_left + 24, cy5 + 50), str(btc_val), font=FONTES["mono"](28), fill=PALETA["texto_branco"])

    if btc_var != "—":

        cor_b5 = PALETA["verde_texto"] if btc_pos else PALETA["vermelho_texto"]

        cor_bg5 = PALETA["verde_bg"] if btc_pos else PALETA["vermelho_bg"]

        draw_feed.rounded_rectangle([x_left + 960 - 150, cy5 + 32, x_left + 960 - 24, cy5 + 78], radius=8, fill=cor_bg5)

        draw_feed.text((x_left + 960 - 135, cy5 + 42), str(btc_var), font=FONTES["body_bold"](20), fill=cor_b5)

    # Bloco Destaque / Leitura Rápida (Limitado a 4 linhas elegantes com reticências)

    y_noticia = cy5 + 140

    draw_feed.rounded_rectangle([x_left, y_noticia, x_left + 960, y_noticia + 280], radius=16, fill="#0c1b33", outline=PALETA["destaque"], width=2)

    draw_feed.text((x_left + 28, y_noticia + 24), "☕ SÍNTESE DA MANHÃ ANTES DO SINO DA B3", font=FONTES["card_title"](20), fill=PALETA["destaque_claro"])

    linhas_texto = []

    palavras = destaque_texto.split()

    linha_atual = []

    for p in palavras:

        linha_atual.append(p)

        if len(" ".join(linha_atual)) > 48:

            linhas_texto.append(" ".join(linha_atual))

            linha_atual = []

    if linha_atual:

        linhas_texto.append(" ".join(linha_atual))

    # Limite estrito de 4 linhas com reticências se houver excedente

    linhas_exibicao = linhas_texto[:4]

    if len(linhas_texto) > 4:

        linhas_exibicao[-1] = linhas_exibicao[-1].rstrip(".,;") + "..."

    y_t = y_noticia + 75

    for l in linhas_exibicao:

        draw_feed.text((x_left + 28, y_t), l, font=FONTES["body"](22), fill=PALETA["texto_branco"])

        y_t += 38

    p_feed = out / f"{data_pub}_abertura_feed.png"

    img_feed.save(p_feed)

    arquivos_png.append(p_feed)

    # 2. X / Twitter (1200x675)

    img_x, draw_x = criar_canvas_base(1200, 675, "Café Matinal", "Pré-Mercado & Futuros Globais", data_fmt)

    y_x = 160

    col_w_x = 245

    card_h_x = 120

    gap_x_x = 20

    x_start_x = 66

    for idx, (nome, val, var, pos) in enumerate(itens_grid[:4]):

        cx = x_start_x + idx * (col_w_x + gap_x_x)

        draw_x.rounded_rectangle([cx, y_x, cx + col_w_x, y_x + card_h_x], radius=12, fill=PALETA["card_bg"], outline=PALETA["card_border"])

        draw_x.text((cx + 14, y_x + 14), nome[:15], font=FONTES["body"](14), fill=PALETA["texto_secundario"])

        draw_x.text((cx + 14, y_x + 46), str(val), font=FONTES["mono"](20), fill=PALETA["texto_branco"])

        cor_x = PALETA["verde_texto"] if pos else PALETA["vermelho_texto"]

        draw_x.text((cx + 14, y_x + 82), str(var), font=FONTES["body_bold"](16), fill=cor_x if var != "—" else PALETA["texto_mutado"])

    y_box_x = 310

    draw_x.rounded_rectangle([x_start_x, y_box_x, x_start_x + 1068, y_box_x + 230], radius=14, fill="#0c1b33", outline=PALETA["destaque"], width=1)

    draw_x.text((x_start_x + 24, y_box_x + 18), "PANORAMA DO PRÉ-MERCADO", font=FONTES["card_title"](17), fill=PALETA["destaque_claro"])

    y_tx = y_box_x + 55

    for l in linhas_exibicao:

        draw_x.text((x_start_x + 24, y_tx), l, font=FONTES["body"](18), fill=PALETA["texto_branco"])

        y_tx += 32

    p_x = out / f"{data_pub}_abertura_x.png"

    img_x.save(p_x)

    arquivos_png.append(p_x)

    # 3. Legenda TXT

    itens_legenda_str = "\n".join([f"• {nome}: {val} ({var})" for nome, val, var, _ in itens_grid if val != "Indisponível"])

    legenda = f"""☕ CAFÉ MATINAL — SÍNTESE DA ABERTURA DOS MERCADOS ({data_fmt})

Os mercados internacionais operam com volatilidade nesta manhã antes da abertura do pregão da B3:

📊 PRÉ-MERCADO GLOBAL:

{itens_legenda_str}

📌 PANORAMA:

{destaque_texto}

Acompanhe os dados consolidados e a varredura das 59 blue chips da B3 no painel ao vivo:

🔗 https://caferadar.com.br

—

$IBOV $USDBRL $BTC $SPX #CafeRadar #BolsaDeValores #MercadoFinanceiro #Investimentos

(Conteúdo com propósito estritamente informativo e educativo. Não constitui recomendação de investimento nos termos da CVM 19/2021 e 20/2021).

"""

    p_legenda = out / f"{data_pub}_abertura_legenda.txt"

    p_legenda.write_text(legenda, encoding="utf-8")

    return arquivos_png, p_legenda

# ==============================================================================

# ==============================================================================

# GERADOR CATEGORIA A.1: ABERTURA B3 (PRIMEIROS NEGÓCIOS - 10h30)

# ==============================================================================

def gerar_materiais_negocios(dados_fechamento: Dict[str, Any], output_dir: Optional[Path] = None) -> Tuple[List[Path], Path]:

    """Gera cards (Feed e X) e legenda para Primeiros Negócios da B3 (10h30)."""

    out = Path(output_dir or DEFAULT_OUTPUT_DIR)

    out.mkdir(parents=True, exist_ok=True)

    edicoes = dados_fechamento.get("edicoes", {})

    ed = edicoes.get("negocios") or edicoes.get("abertura") or {}

    data_pub = datetime.now().strftime("%Y-%m-%d")

    data_base = dados_fechamento.get("data_referencia", data_pub)

    data_fmt = dados_fechamento.get("data_formatada") or formatar_data_br(data_base)

    mercados = ed.get("mercado_geral", {})

    blue_chips = ed.get("acoes_blue_chips", [])

    ibov = mercados.get("ibov", {})

    dolar = mercados.get("dolar", {})

    arquivos_png = []

    # 1. Instagram Feed (1080x1350)

    img_feed, draw_feed = criar_canvas_base(1080, 1350, "Abertura B3", "Primeiros Negócios do Pregão", data_fmt)

    y_top = 220

    x_left = 60

    box_w = 460

    box_h = 170

    # Box Ibov

    pos_ibov = ibov.get("positivo", True)

    draw_feed.rounded_rectangle([x_left, y_top, x_left + box_w, y_top + box_h], radius=16, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)

    draw_feed.text((x_left + 24, y_top + 20), "IBOVESPA AO VIVO", font=FONTES["body_bold"](16), fill=PALETA["texto_secundario"])

    draw_feed.text((x_left + 24, y_top + 60), str(ibov.get("pontos", "—")), font=FONTES["mono"](34), fill=PALETA["texto_branco"])

    cor_ibov = PALETA["verde_texto"] if pos_ibov else PALETA["vermelho_texto"]

    cor_ibov_bg = PALETA["verde_bg"] if pos_ibov else PALETA["vermelho_bg"]

    draw_feed.rounded_rectangle([x_left + box_w - 140, y_top + 54, x_left + box_w - 20, y_top + 104], radius=8, fill=cor_ibov_bg)

    draw_feed.text((x_left + box_w - 128, y_top + 66), str(ibov.get("variacao", "—")), font=FONTES["body_bold"](22), fill=cor_ibov)

    # Box Dólar

    pos_dol = dolar.get("positivo", False)

    draw_feed.rounded_rectangle([x_left + box_w + 40, y_top, x_left + box_w * 2 + 40, y_top + box_h], radius=16, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)

    draw_feed.text((x_left + box_w + 64, y_top + 20), "DÓLAR COMERCIAL", font=FONTES["body_bold"](16), fill=PALETA["texto_secundario"])

    draw_feed.text((x_left + box_w + 64, y_top + 60), str(dolar.get("valor", "—")), font=FONTES["mono"](34), fill=PALETA["texto_branco"])

    cor_dol = PALETA["verde_texto"] if pos_dol else PALETA["vermelho_texto"]

    cor_dol_bg = PALETA["verde_bg"] if pos_dol else PALETA["vermelho_bg"]

    draw_feed.rounded_rectangle([x_left + box_w * 2 + 40 - 140, y_top + 54, x_left + box_w * 2 + 40 - 20, y_top + 104], radius=8, fill=cor_dol_bg)

    draw_feed.text((x_left + box_w * 2 + 40 - 128, y_top + 66), str(dolar.get("variacao", "—")), font=FONTES["body_bold"](22), fill=cor_dol)

    # Grid Blue Chips

    y_chips = y_top + box_h + 35

    draw_feed.text((x_left, y_chips), "PRIMEIRAS COTAÇÕES DAS BLUE CHIPS B3", font=FONTES["card_title"](22), fill=PALETA["destaque_claro"])

    y_chip_card = y_chips + 40

    chip_h = 95

    for idx, c_item in enumerate(blue_chips[:4]):

        cy_c = y_chip_card + idx * (chip_h + 16)

        draw_feed.rounded_rectangle([x_left, cy_c, x_left + 960, cy_c + chip_h], radius=12, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)

        draw_feed.text((x_left + 24, cy_c + 20), f"${c_item.get('ticker')}", font=FONTES["body_bold"](24), fill=PALETA["texto_branco"])

        draw_feed.text((x_left + 24, cy_c + 54), str(c_item.get("nome", "")), font=FONTES["body"](16), fill=PALETA["texto_secundario"])

        draw_feed.text((x_left + 520, cy_c + 30), str(c_item.get("preco", "—")), font=FONTES["mono"](26), fill=PALETA["texto_branco"])

        pos_c = c_item.get("positivo", True)

        cor_c = PALETA["verde_texto"] if pos_c else PALETA["vermelho_texto"]

        cor_c_bg = PALETA["verde_bg"] if pos_c else PALETA["vermelho_bg"]

        draw_feed.rounded_rectangle([x_left + 960 - 150, cy_c + 24, x_left + 960 - 20, cy_c + 70], radius=8, fill=cor_c_bg)

        draw_feed.text((x_left + 960 - 136, cy_c + 34), str(c_item.get("variacao_dia", "—")), font=FONTES["body_bold"](20), fill=cor_c)

    p_feed = out / f"{data_pub}_negocios_feed.png"

    img_feed.save(p_feed)

    arquivos_png.append(p_feed)

    # 2. X / Twitter (1200x675)

    img_x, draw_x = criar_canvas_base(1200, 675, "Abertura B3", "Primeiros Negócios da B3", data_fmt)

    y_xt = 160

    # Box Ibov X

    draw_x.rounded_rectangle([66, y_xt, 580, y_xt + 120], radius=12, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_x.text((86, y_xt + 18), "IBOVESPA AO VIVO", font=FONTES["body_bold"](16), fill=PALETA["texto_secundario"])

    draw_x.text((86, y_xt + 54), str(ibov.get("pontos", "—")), font=FONTES["mono"](28), fill=PALETA["texto_branco"])

    draw_x.rounded_rectangle([450, y_xt + 46, 560, y_xt + 92], radius=6, fill=cor_ibov_bg)

    draw_x.text((462, y_xt + 56), str(ibov.get("variacao", "—")), font=FONTES["body_bold"](18), fill=cor_ibov)

    # Box Dolar X

    draw_x.rounded_rectangle([620, y_xt, 1134, y_xt + 120], radius=12, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_x.text((640, y_xt + 18), "DÓLAR COMERCIAL", font=FONTES["body_bold"](16), fill=PALETA["texto_secundario"])

    draw_x.text((640, y_xt + 54), str(dolar.get("valor", "—")), font=FONTES["mono"](28), fill=PALETA["texto_branco"])

    draw_x.rounded_rectangle([1004, y_xt + 46, 1114, y_xt + 92], radius=6, fill=cor_dol_bg)

    draw_x.text((1016, y_xt + 56), str(dolar.get("variacao", "—")), font=FONTES["body_bold"](18), fill=cor_dol)

    # Mini cards de blue chips no X

    y_mini = y_xt + 145

    w_mini = 252

    h_mini = 100

    for idx, c_item in enumerate(blue_chips[:4]):

        cx_m = 66 + idx * (w_mini + 15)

        draw_x.rounded_rectangle([cx_m, y_mini, cx_m + w_mini, y_mini + h_mini], radius=10, fill=PALETA["card_bg"], outline=PALETA["card_border"])

        draw_x.text((cx_m + 14, y_mini + 14), f"${c_item.get('ticker')}", font=FONTES["body_bold"](18), fill=PALETA["texto_branco"])

        draw_x.text((cx_m + 14, y_mini + 48), str(c_item.get("preco", "—")), font=FONTES["mono"](18), fill=PALETA["texto_secundario"])

        pos_m = c_item.get("positivo", True)

        cor_m = PALETA["verde_texto"] if pos_m else PALETA["vermelho_texto"]

        draw_x.text((cx_m + 140, y_mini + 48), str(c_item.get("variacao_dia", "—")), font=FONTES["body_bold"](16), fill=cor_m)

    p_x = out / f"{data_pub}_negocios_x.png"

    img_x.save(p_x)

    arquivos_png.append(p_x)

    blue_str = "\n".join([f"• ${c.get('ticker')}: {c.get('preco')} ({c.get('variacao_dia')})" for c in blue_chips[:5]])

    cashtags_str = " ".join([f"${c.get('ticker')}" for c in blue_chips[:5] if c.get('ticker')])

    legenda = f"""🔔 ABERTURA B3 — PRIMEIROS NEGÓCIOS ({data_fmt})

O pregão da bolsa brasileira abriu os trabalhos e as principais ações já operam com liquidez:

• $IBOV: {ibov.get('pontos', '—')} ({ibov.get('variacao', '—')})

• $USDBRL: {dolar.get('valor', '—')} ({dolar.get('variacao', '—')})

Destaques da B3 nesta manhã:

{blue_str}

Acompanhe as cotações completas e o scanner ao vivo:

🔗 https://caferadar.com.br

—

$IBOV $BOVA11 $USDBRL {cashtags_str}

#B3 #AberturaB3 #MercadoFinanceiro #Acoes #Investimentos #CafeRadar

(Conteúdo com propósito estritamente informativo e educativo. Não constitui recomendação de investimento nos termos da CVM 19/2021 e 20/2021).

"""

    p_legenda = out / f"{data_pub}_negocios_legenda.txt"

    p_legenda.write_text(legenda, encoding="utf-8")

    return arquivos_png, p_legenda

# GERADOR CATEGORIA B: FECHAMENTO B3

# ==============================================================================

def gerar_materiais_fechamento(dados_fechamento: Dict[str, Any], output_dir: Optional[Path] = None) -> Tuple[List[Path], Path]:

    """Gera cards (Feed e X) e legenda para Fechamento Oficial B3."""

    out = Path(output_dir or DEFAULT_OUTPUT_DIR)

    out.mkdir(parents=True, exist_ok=True)

    ed = dados_fechamento.get("edicoes", {}).get("fechamento", {})

    data_pub = datetime.now().strftime("%Y-%m-%d")

    data_base = dados_fechamento.get("data_referencia", data_pub)

    data_fmt = dados_fechamento.get("data_formatada") or formatar_data_br(data_base)

    mercados = ed.get("mercado_geral", {})

    destaques = ed.get("destaques", {})

    blue_chips = ed.get("acoes_blue_chips", [])

    ibov = mercados.get("ibov", {})

    dolar = mercados.get("dolar", {})

    altas = destaques.get("altas", [])

    quedas = destaques.get("quedas", [])

    arquivos_png = []

    # 1. Instagram Feed (1080x1350)

    img_feed, draw_feed = criar_canvas_base(1080, 1350, "Fechamento B3", "Panorama Oficial do Pregão", data_fmt)

    y_top = 220

    x_left = 60

    box_w = 460

    box_h = 170

    # Box Ibov

    pos_ibov = ibov.get("positivo", True)

    draw_feed.rounded_rectangle([x_left, y_top, x_left + box_w, y_top + box_h], radius=16, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)

    draw_feed.text((x_left + 24, y_top + 20), "IBOVESPA OFICIAL", font=FONTES["body_bold"](16), fill=PALETA["texto_secundario"])

    draw_feed.text((x_left + 24, y_top + 60), str(ibov.get("pontos", "—")), font=FONTES["mono"](34), fill=PALETA["texto_branco"])

    cor_ibov = PALETA["verde_texto"] if pos_ibov else PALETA["vermelho_texto"]

    cor_ibov_bg = PALETA["verde_bg"] if pos_ibov else PALETA["vermelho_bg"]

    draw_feed.rounded_rectangle([x_left + box_w - 140, y_top + 54, x_left + box_w - 20, y_top + 104], radius=8, fill=cor_ibov_bg)

    draw_feed.text((x_left + box_w - 128, y_top + 66), str(ibov.get("variacao", "—")), font=FONTES["body_bold"](22), fill=cor_ibov)

    # Box Dólar

    x_dol = x_left + box_w + 40

    pos_dol = dolar.get("positivo", True)

    draw_feed.rounded_rectangle([x_dol, y_top, x_dol + box_w, y_top + box_h], radius=16, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)

    draw_feed.text((x_dol + 24, y_top + 20), "DÓLAR COMERCIAL", font=FONTES["body_bold"](16), fill=PALETA["texto_secundario"])

    draw_feed.text((x_dol + 24, y_top + 60), str(dolar.get("valor", "—")), font=FONTES["mono"](34), fill=PALETA["texto_branco"])

    cor_dol = PALETA["verde_texto"] if pos_dol else PALETA["vermelho_texto"]

    cor_dol_bg = PALETA["verde_bg"] if pos_dol else PALETA["vermelho_bg"]

    draw_feed.rounded_rectangle([x_dol + box_w - 140, y_top + 54, x_dol + box_w - 20, y_top + 104], radius=8, fill=cor_dol_bg)

    draw_feed.text((x_dol + box_w - 128, y_top + 66), str(dolar.get("variacao", "—")), font=FONTES["body_bold"](22), fill=cor_dol)

    # Destaques da B3

    y_dest = y_top + box_h + 30

    draw_feed.rounded_rectangle([x_left, y_dest, x_left + 960, y_dest + 240], radius=16, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)

    draw_feed.text((x_left + 24, y_dest + 18), "DESTAQUES DA SESSÃO NA B3", font=FONTES["card_title"](18), fill=PALETA["destaque_claro"])

    # Coluna Altas

    draw_feed.text((x_left + 24, y_dest + 55), "Maiores Altas:", font=FONTES["body_bold"](16), fill=PALETA["verde_texto"])

    ya = y_dest + 85

    for a in altas[:3]:

        draw_feed.text((x_left + 24, ya), f"• {a.get('ticker')}", font=FONTES["mono"](20), fill=PALETA["texto_branco"])

        draw_feed.text((x_left + 220, ya), str(a.get("variacao")), font=FONTES["mono"](20), fill=PALETA["verde_texto"])

        ya += 32

    # Coluna Baixas

    x_baixa = x_left + 480

    draw_feed.text((x_baixa, y_dest + 55), "Maiores Baixas:", font=FONTES["body_bold"](16), fill=PALETA["vermelho_texto"])

    yb = y_dest + 85

    for b in quedas[:3]:

        draw_feed.text((x_baixa, yb), f"• {b.get('ticker')}", font=FONTES["mono"](20), fill=PALETA["texto_branco"])

        draw_feed.text((x_baixa + 220, yb), str(b.get("variacao")), font=FONTES["mono"](20), fill=PALETA["vermelho_texto"])

        yb += 32

    # Blue Chips Destaque

    y_bc = y_dest + 270

    draw_feed.rounded_rectangle([x_left, y_bc, x_left + 960, y_bc + 390], radius=16, fill="#0c1b33", outline=PALETA["destaque"], width=2)

    draw_feed.text((x_left + 24, y_bc + 20), "BLUE CHIPS & AÇÕES DE MAIOR LIQUIDEZ", font=FONTES["card_title"](18), fill=PALETA["destaque_claro"])

    y_chip = y_bc + 65

    for c in blue_chips[:6]:

        draw_feed.text((x_left + 24, y_chip), c.get("ticker", ""), font=FONTES["mono"](20), fill=PALETA["texto_branco"])

        draw_feed.text((x_left + 160, y_chip), c.get("nome", "")[:24], font=FONTES["body"](18), fill=PALETA["texto_secundario"])

        draw_feed.text((x_left + 640, y_chip), c.get("preco", ""), font=FONTES["mono"](20), fill=PALETA["texto_branco"])

        cor_c = PALETA["verde_texto"] if c.get("positivo", True) else PALETA["vermelho_texto"]

        draw_feed.text((x_left + 820, y_chip), c.get("variacao_dia", ""), font=FONTES["mono"](20), fill=cor_c)

        y_chip += 48

    p_feed = out / f"{data_pub}_fechamento_feed.png"

    img_feed.save(p_feed)

    arquivos_png.append(p_feed)

    # 2. X / Twitter (1200x675)

    img_x, draw_x = criar_canvas_base(1200, 675, "Fechamento B3", "Fechamento Oficial da B3", data_fmt)

    y_xt = 160

    draw_x.rounded_rectangle([66, y_xt, 580, y_xt + 130], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_x.text((90, y_xt + 18), "IBOVESPA", font=FONTES["body_bold"](16), fill=PALETA["texto_secundario"])

    draw_x.text((90, y_xt + 55), str(ibov.get("pontos", "—")), font=FONTES["mono"](32), fill=PALETA["texto_branco"])

    draw_x.text((440, y_xt + 60), str(ibov.get("variacao", "—")), font=FONTES["body_bold"](22), fill=cor_ibov)

    draw_x.rounded_rectangle([620, y_xt, 1134, y_xt + 130], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_x.text((644, y_xt + 18), "DÓLAR COMERCIAL", font=FONTES["body_bold"](16), fill=PALETA["texto_secundario"])

    draw_x.text((644, y_xt + 55), str(dolar.get("valor", "—")), font=FONTES["mono"](32), fill=PALETA["texto_branco"])

    draw_x.text((990, y_xt + 60), str(dolar.get("variacao", "—")), font=FONTES["body_bold"](22), fill=cor_dol)

    y_xb = 320

    draw_x.rounded_rectangle([66, y_xb, 1134, y_xb + 220], radius=14, fill="#0c1b33", outline=PALETA["destaque"], width=1)

    draw_x.text((90, y_xb + 18), "DESTAQUES DO PREGÃO (ALTAS & BAIXAS)", font=FONTES["card_title"](17), fill=PALETA["destaque_claro"])

    ya_x = y_xb + 55

    for a in altas[:4]:

        draw_x.text((90, ya_x), f"{a.get('ticker')}: {a.get('variacao')}", font=FONTES["mono"](18), fill=PALETA["verde_texto"])

        ya_x += 32

    yb_x = y_xb + 55

    for b in quedas[:4]:

        draw_x.text((640, yb_x), f"{b.get('ticker')}: {b.get('variacao')}", font=FONTES["mono"](18), fill=PALETA["vermelho_texto"])

        yb_x += 32

    p_x = out / f"{data_pub}_fechamento_x.png"

    img_x.save(p_x)

    arquivos_png.append(p_x)

    # 3. Legenda TXT com cashtags inteligentes dos tickers reais

    tickers_mencionados = []

    for a in altas:

        if a.get("ticker"): tickers_mencionados.append(f"${a['ticker']}")

    for b in quedas:

        if b.get("ticker"): tickers_mencionados.append(f"${b['ticker']}")

    for c in blue_chips[:4]:

        if c.get("ticker") and f"${c['ticker']}" not in tickers_mencionados:

            tickers_mencionados.append(f"${c['ticker']}")

    cashtags_str = " ".join(tickers_mencionados)

    altas_str = "\n".join([f"• ${a.get('ticker')}: {a.get('variacao')}" for a in altas])

    quedas_str = "\n".join([f"• ${b.get('ticker')}: {b.get('variacao')}" for b in quedas])

    blue_str = "\n".join([f"• ${c.get('ticker')}: {c.get('preco')} ({c.get('variacao_dia')})" for c in blue_chips[:5]])

    legenda = f"""🌙 FECHAMENTO OFICIAL B3 — {data_fmt}

O pregão da bolsa brasileira encerrou os trabalhos do dia. Confira o panorama consolidado:

📊 ÍNDICES PRINCIPAIS:

• Ibovespa: {ibov.get('pontos', '—')} ({ibov.get('variacao', '—')})

• Dólar Comercial: {dolar.get('valor', '—')} ({dolar.get('variacao', '—')})

🚀 MAIORES ALTAS DO DIA:

{altas_str}

📉 MAIORES BAIXAS DO DIA:

{quedas_str}

🏢 BLUE CHIPS:

{blue_str}

Confira a cobertura completa e os estudos quantitativos de mercado no Café Radar:

🔗 https://caferadar.com.br

—

$IBOV $BOVA11 $USDBRL {cashtags_str}

#B3 #FechamentoB3 #MercadoFinanceiro #Acoes #Investimentos #CafeRadar

(Conteúdo com propósito estritamente informativo e educativo. Não constitui recomendação de investimento nos termos da CVM 19/2021 e 20/2021).

"""

    p_legenda = out / f"{data_pub}_fechamento_legenda.txt"

    p_legenda.write_text(legenda, encoding="utf-8")

    return arquivos_png, p_legenda

# ==============================================================================

# GERADOR CATEGORIA C: RADAR SWING (FILTROS TÉCNICOS & AUDITORIA)

# ==============================================================================

def gerar_materiais_swing(dados_swing: Dict[str, Any], output_dir: Optional[Path] = None) -> Tuple[List[Path], Path]:

    """Gera cards e legenda para o Radar de Swing Trade com separação estrita de datas."""

    out = Path(output_dir or DEFAULT_OUTPUT_DIR)

    out.mkdir(parents=True, exist_ok=True)

    data_pub = datetime.now().strftime("%Y-%m-%d")

    data_base = dados_swing.get("data_referencia", data_pub)

    data_scanner = dados_swing.get("data_execucao_scanner") or dados_swing.get("atualizado_em") or data_pub

    data_base_br = formatar_data_br(data_base)

    data_pub_br = formatar_data_br(data_pub)

    est = dados_swing.get("estrategia", {})

    resumo = dados_swing.get("resumo_pregão_hoje", {})

    destaques = dados_swing.get("posicoes_destaque", [])

    total_monitoradas = est.get("universo_total", 59)

    vencedoras = est.get("operacoes_vencedoras", 154)

    totais_auditadas = est.get("operacoes_totais_1ano", 173)

    abertas = est.get("operacoes_em_aberto", 19)

    arquivos_png = []

    # 1. Instagram Feed (1080x1350)

    data_topo_feed = f"Data-base B3: {data_base_br}"

    img_feed, draw_feed = criar_canvas_base(1080, 1350, "Filtro Técnico", "Radar Swing Trade (+5%)", data_topo_feed)

    y_kpi = 220

    x_left = 60

    kw = 300

    kh = 130

    gap_k = 30

    # KPI 1

    draw_feed.rounded_rectangle([x_left, y_kpi, x_left + kw, y_kpi + kh], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_feed.text((x_left + 16, y_kpi + 16), "UNIVERSO B3", font=FONTES["body_bold"](14), fill=PALETA["texto_secundario"])

    draw_feed.text((x_left + 16, y_kpi + 48), f"{total_monitoradas} Ações", font=FONTES["mono"](28), fill=PALETA["texto_branco"])

    draw_feed.text((x_left + 16, y_kpi + 90), "Alta Liquidez", font=FONTES["body"](14), fill=PALETA["destaque_claro"])

    # KPI 2

    x2 = x_left + kw + gap_k

    draw_feed.rounded_rectangle([x2, y_kpi, x2 + kw, y_kpi + kh], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_feed.text((x2 + 16, y_kpi + 16), "NO ALVO (+5%)", font=FONTES["body_bold"](14), fill=PALETA["texto_secundario"])

    draw_feed.text((x2 + 16, y_kpi + 48), f"{vencedoras} / {totais_auditadas}", font=FONTES["mono"](28), fill=PALETA["verde_texto"])

    draw_feed.text((x2 + 16, y_kpi + 90), "Backtest Auditado", font=FONTES["body"](14), fill=PALETA["texto_secundario"])

    # KPI 3

    x3 = x2 + kw + gap_k

    draw_feed.rounded_rectangle([x3, y_kpi, x3 + kw, y_kpi + kh], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_feed.text((x3 + 16, y_kpi + 16), "EM ABERTO", font=FONTES["body_bold"](14), fill=PALETA["texto_secundario"])

    draw_feed.text((x3 + 16, y_kpi + 48), f"{abertas} Posições", font=FONTES["mono"](28), fill=PALETA["vermelho_texto"])

    draw_feed.text((x3 + 16, y_kpi + 90), "Marcadas a Mercado", font=FONTES["body"](14), fill=PALETA["texto_secundario"])

    # Resumo do Pregão

    y_res = y_kpi + kh + 24

    draw_feed.rounded_rectangle([x_left, y_res, x_left + 960, y_res + 90], radius=14, fill="#0c1b33", outline=PALETA["destaque"], width=1)

    draw_feed.text((x_left + 24, y_res + 18), "SITUAÇÃO DO SCANNER TÉCNICO:", font=FONTES["card_title"](16), fill=PALETA["destaque_claro"])

    txt_resumo = f"• Ativação: {resumo.get('oportunidades', 0)} | • Em Observação: {resumo.get('ressalvas', 0)} | • Desfavoráveis (Filtro Restritivo): {resumo.get('desfavoravel', 0)}"

    draw_feed.text((x_left + 24, y_res + 50), txt_resumo, font=FONTES["body_bold"](18), fill=PALETA["texto_branco"])

    # Tabela de Posições Monitoradas

    y_tab = y_res + 115

    draw_feed.rounded_rectangle([x_left, y_tab, x_left + 960, y_tab + 620], radius=16, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)

    draw_feed.text((x_left + 24, y_tab + 20), "ATIVOS MONITORADOS PELO MODELO MATEMÁTICO", font=FONTES["card_title"](18), fill=PALETA["texto_branco"])

    yt = y_tab + 70

    draw_feed.text((x_left + 24, yt), "TICKER", font=FONTES["body_bold"](15), fill=PALETA["texto_secundario"])

    draw_feed.text((x_left + 140, yt), "EMPRESA", font=FONTES["body_bold"](15), fill=PALETA["texto_secundario"])

    draw_feed.text((x_left + 520, yt), "SETUP", font=FONTES["body_bold"](15), fill=PALETA["texto_secundario"])

    draw_feed.text((x_left + 720, yt), "CONDIÇÃO", font=FONTES["body_bold"](15), fill=PALETA["texto_secundario"])

    draw_feed.text((x_left + 850, yt), "ALVO", font=FONTES["body_bold"](15), fill=PALETA["texto_secundario"])

    draw_feed.line([x_left + 24, yt + 28, x_left + 936, yt + 28], fill=PALETA["card_border"], width=1)

    yt += 45

    for item in destaques[:8]:

        draw_feed.text((x_left + 24, yt), item.get("ticker", ""), font=FONTES["mono"](18), fill=PALETA["texto_branco"])

        draw_feed.text((x_left + 140, yt), item.get("empresa", "")[:28], font=FONTES["body"](16), fill=PALETA["texto_secundario"])

        draw_feed.text((x_left + 520, yt), item.get("setup", ""), font=FONTES["mono"](15), fill=PALETA["destaque_claro"])

        badge = item.get("status_badge", "Monitorando")

        cor_b = PALETA["verde_texto"] if badge == "Ativado" else (PALETA["vermelho_texto"] if badge == "Desfavorável" else PALETA["texto_secundario"])

        draw_feed.text((x_left + 720, yt), badge, font=FONTES["body_bold"](15), fill=cor_b)

        draw_feed.text((x_left + 850, yt), item.get("alvo_saida", "+5%"), font=FONTES["mono"](16), fill=PALETA["verde_texto"])

        yt += 48

    p_feed = out / f"{data_pub}_swingtrade_feed.png"

    img_feed.save(p_feed)

    arquivos_png.append(p_feed)

    # 2. X / Twitter (1200x675) - Grade Refinada de 2 Colunas para Máxima Legibilidade

    img_x, draw_x = criar_canvas_base(1200, 675, "Filtro Técnico", "Radar Swing Trade B3 (+5%)", data_topo_feed)

    y_xk = 160

    draw_x.rounded_rectangle([66, y_xk, 390, y_xk + 130], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_x.text((86, y_xk + 18), "UNIVERSO AUDITADO", font=FONTES["body_bold"](15), fill=PALETA["texto_secundario"])

    draw_x.text((86, y_xk + 55), f"{total_monitoradas} Ações B3", font=FONTES["mono"](26), fill=PALETA["texto_branco"])

    draw_x.rounded_rectangle([420, y_xk, 744, y_xk + 130], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_x.text((440, y_xk + 18), "ENCERRADAS NO ALVO", font=FONTES["body_bold"](15), fill=PALETA["texto_secundario"])

    draw_x.text((440, y_xk + 55), f"{vencedoras} no alvo (+5%)", font=FONTES["mono"](24), fill=PALETA["verde_texto"])

    draw_x.rounded_rectangle([774, y_xk, 1134, y_xk + 130], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

    draw_x.text((794, y_xk + 18), "RISCO / EM ABERTO", font=FONTES["body_bold"](15), fill=PALETA["texto_secundario"])

    draw_x.text((794, y_xk + 55), f"{abertas} em aberto", font=FONTES["mono"](24), fill=PALETA["vermelho_texto"])

    # Grade de 2 colunas com cards compactos e legíveis

    y_xb = 315

    draw_x.rounded_rectangle([66, y_xb, 1134, y_xb + 235], radius=14, fill="#0c1b33", outline=PALETA["destaque"], width=1)

    draw_x.text((90, y_xb + 16), "MONITORAMENTO DE REVERSÃO À MÉDIA (DESTAQUES)", font=FONTES["card_title"](16), fill=PALETA["destaque_claro"])

    # Renderizar até 4 ativos em 2 colunas (2x2)

    col_w_x = 505

    card_h_x = 75

    for idx, it in enumerate(destaques[:4]):

        col = idx % 2

        lin = idx // 2

        cx = 90 + col * (col_w_x + 28)

        cy = y_xb + 55 + lin * (card_h_x + 14)

        draw_x.rounded_rectangle([cx, cy, cx + col_w_x, cy + card_h_x], radius=10, fill=PALETA["card_bg"], outline=PALETA["card_border"])

        draw_x.text((cx + 14, cy + 12), it.get("ticker", ""), font=FONTES["mono"](20), fill=PALETA["texto_branco"])

        draw_x.text((cx + 110, cy + 14), it.get("empresa", "")[:18], font=FONTES["body"](15), fill=PALETA["texto_secundario"])

        draw_x.text((cx + 14, cy + 44), f"Setup: {it.get('setup')}", font=FONTES["mono"](14), fill=PALETA["destaque_claro"])

        badge = it.get("status_badge", "Monitorando")

        cor_b = PALETA["verde_texto"] if badge == "Ativado" else (PALETA["vermelho_texto"] if badge == "Desfavorável" else PALETA["texto_secundario"])

        draw_x.text((cx + col_w_x - 130, cy + 44), badge, font=FONTES["body_bold"](14), fill=cor_b)

    p_x = out / f"{data_pub}_swingtrade_x.png"

    img_x.save(p_x)

    arquivos_png.append(p_x)

    # 3. Legenda TXT com explicação transparente de datas

    explicacao_data = ""

    if data_base != data_pub:

        explicacao_data = f"\nℹ️ Nota de Frescor: Os dados técnicos refletem os candles do pregão oficial de {data_base_br}, processados pelo scanner em {data_scanner}."

    tickers_swing = [f"${it['ticker']}" for it in destaques[:6] if it.get("ticker")]

    cashtags_str = " ".join(tickers_swing)

    legenda = f"""⚡ RADAR DE SWING TRADE B3 — FILTROS TÉCNICOS & BACKTEST ({data_pub_br})

Varredura quantitativa sobre as {total_monitoradas} ações mais líquidas da bolsa brasileira buscando reversão à média com alvo matemático parametrizado em +5%:{explicacao_data}

📋 SITUAÇÃO DO PREGÃO:

• Ativação Imediata: {resumo.get('oportunidades', 0)}

• Em Observação / Alerta: {resumo.get('ressalvas', 0)}

• Filtro Restritivo de Tendência: {resumo.get('desfavoravel', 0)}

🔍 AUDITORIA DO BACKTEST (23/10/2025 a 23/10/2026):

• 154 operações encerradas na meta (+5%)

• 19 posições em aberto marcadas a mercado (18 no vermelho, com média de -13,2%)

• Sem stop loss: o modelo não realiza perda, o risco reside integralmente nas posições em aberto.

Confira a auditoria pública e os 173 trades abertos em:

🔗 https://caferadar.com.br/historico-swing.html

—

$IBOV {cashtags_str}

#SwingTrade #B3 #AnaliseTecnica #Backtest #Investimentos #CafeRadar

(Simulação quantitativa algorítmica puramente educativa. Não constitui call de compra/venda nem consultoria financeira - CVM 19/2021 e 20/2021).

"""

    p_legenda = out / f"{data_pub}_swingtrade_legenda.txt"

    p_legenda.write_text(legenda, encoding="utf-8")

    return arquivos_png, p_legenda

# ==============================================================================

# GERADOR CATEGORIA D: RADAR LONGO PRAZO (ALOCAÇÃO MACRO)

# ==============================================================================

def gerar_materiais_longoprazo(dados_dashboard: Dict[str, Any], output_dir: Optional[Path] = None) -> Tuple[List[Path], Path]:

    """Gera cards e legenda para o Radar de Longo Prazo."""

    out = Path(output_dir or DEFAULT_OUTPUT_DIR)

    out.mkdir(parents=True, exist_ok=True)

    data_pub = datetime.now().strftime("%Y-%m-%d")

    data_base = dados_dashboard.get("reference_date", data_pub)

    data_base_br = formatar_data_br(data_base)

    alocacao = dados_dashboard.get("allocation", {})

    indicadores = dados_dashboard.get("indicators", {})

    ipca = alocacao.get("Tesouro IPCA+ 2040", 60)

    ivvb = alocacao.get("IVVB11", 30)

    btc = alocacao.get("Bitcoin", 10)

    bova = alocacao.get("BOVA11", 0)

    arquivos_png = []

    # 1. Instagram Feed (1080x1350)

    img_feed, draw_feed = criar_canvas_base(1080, 1350, "Alocação Patrimonial", "Radar de Longo Prazo", data_base_br)

    y_sub = 220

    x_left = 60

    draw_feed.text((x_left, y_sub), "Estudo Teórico de Alocação Macroeconômica do Modelo Matemático:", font=FONTES["body"](18), fill=PALETA["texto_secundario"])

    y_barras = y_sub + 40

    fatias = [

        ("🏛️ Tesouro IPCA+ (Juro Real)", ipca, "#1f77b4", "Âncora de proteção contra inflação"),

        ("🌐 IVVB11 (S&P 500 Dólar)", ivvb, "#2ca02c", "Exposição global às 500 maiores empresas dos EUA"),

        ("⚡ Bitcoin (Ativo de Escassez)", btc, "#ff7f0e", "Assimetria tecnológica global (máx. 10%)"),

        ("🛡️ BOVA11 (Ações Brasil)", bova, "#d62728", "Filtro de prudência ativo (Veto de governança)"),

    ]

    yb = y_barras

    for nome, pct, cor_barra, desc in fatias:

        draw_feed.rounded_rectangle([x_left, yb, x_left + 960, yb + 115], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

        draw_feed.text((x_left + 24, yb + 16), nome, font=FONTES["body_bold"](18), fill=PALETA["texto_branco"])

        draw_feed.text((x_left + 24, yb + 48), desc, font=FONTES["body"](15), fill=PALETA["texto_secundario"])

        draw_feed.rounded_rectangle([x_left + 24, yb + 82, x_left + 800, yb + 96], radius=6, fill="#0f172a")

        largura_pct = int(776 * (pct / 100.0))

        if largura_pct > 0:

            draw_feed.rounded_rectangle([x_left + 24, yb + 82, x_left + 24 + largura_pct, yb + 96], radius=6, fill=cor_barra)

        draw_feed.text((x_left + 840, yb + 32), f"{pct}%", font=FONTES["mono"](34), fill=PALETA["texto_branco"])

        yb += 135

    y_met = yb + 20

    draw_feed.rounded_rectangle([x_left, y_met, x_left + 960, y_met + 340], radius=16, fill="#0c1b33", outline=PALETA["destaque"], width=2)

    draw_feed.text((x_left + 28, y_met + 24), "🧭 DISCIPLINA DA BÚSSOLA QUANTITATIVA", font=FONTES["card_title"](20), fill=PALETA["destaque_claro"])

    linhas_met = [

        "• Alocação Marginal: O modelo prioriza novos aportes sem exigir o giro",

        "  ou a venda de posições antigas da carteira do investidor.",

        "• Prêmio de Risco: Bolsa local (BOVA11) só recebe pontuação favorável",

        "  quando os múltiplos e as contas fiscais compensarem o custo de oportunidade.",

        "• Dolarização e Juros Reais: Proteção conceitual contra choques cambiais",

        "  combinada à maior taxa de juro real do mundo civilizado."

    ]

    yt_m = y_met + 75

    for lm in linhas_met:

        draw_feed.text((x_left + 28, yt_m), lm, font=FONTES["body"](20), fill=PALETA["texto_branco"])

        yt_m += 38

    p_feed = out / f"{data_pub}_longoprazo_feed.png"

    img_feed.save(p_feed)

    arquivos_png.append(p_feed)

    # 2. X / Twitter (1200x675)

    img_x, draw_x = criar_canvas_base(1200, 675, "Alocação Patrimonial", "Radar de Longo Prazo", data_base_br)

    y_bx = 160

    cw_x = 245

    ch_x = 135

    for idx, (nome, pct, cor_barra, desc) in enumerate(fatias):

        cx = 66 + idx * (cw_x + 20)

        draw_x.rounded_rectangle([cx, y_bx, cx + cw_x, y_bx + ch_x], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])

        draw_x.text((cx + 14, y_bx + 14), nome[:16], font=FONTES["body_bold"](15), fill=PALETA["texto_secundario"])

        draw_x.text((cx + 14, y_bx + 48), f"{pct}%", font=FONTES["mono"](32), fill=PALETA["texto_branco"])

        draw_x.rounded_rectangle([cx + 14, y_bx + 104, cx + cw_x - 14, y_bx + 114], radius=4, fill="#0f172a")

        w_p = int((cw_x - 28) * (pct / 100.0))

        if w_p > 0:

            draw_x.rounded_rectangle([cx + 14, y_bx + 104, cx + 14 + w_p, y_bx + 114], radius=4, fill=cor_barra)

    y_desc_x = 325

    draw_x.rounded_rectangle([66, y_desc_x, 1134, y_desc_x + 220], radius=14, fill="#0c1b33", outline=PALETA["destaque"], width=1)

    draw_x.text((90, y_desc_x + 20), "ESTUDO CONCEITUAL DE ALOCAÇÃO MACROECONÔMICA", font=FONTES["card_title"](17), fill=PALETA["destaque_claro"])

    ytx = y_desc_x + 65

    for lm in linhas_met[:4]:

        draw_x.text((90, ytx), lm, font=FONTES["body"](17), fill=PALETA["texto_branco"])

        ytx += 34

    p_x = out / f"{data_pub}_longoprazo_x.png"

    img_x.save(p_x)

    arquivos_png.append(p_x)

    # 3. Legenda TXT

    legenda = f"""🧭 RADAR DE LONGO PRAZO — ESTUDO TEÓRICO DE ALOCAÇÃO ({data_base_br})

Ponderação matemática conceitual para novos aportes patrimoniais:

🏛️ DISTRIBUIÇÃO CONCEITUAL DO MODELO:

• Tesouro IPCA+ (Juro Real): {ipca}%

• IVVB11 (S&P 500 Dólar): {ivvb}%

• Bitcoin (Assimetria Global): {btc}%

• BOVA11 (Bolsa Brasil): {bova}% (Veto de governança ativo)

💡 FILOSOFIA DE APORTE MARGINAL:

O modelo não pressupõe giro de patrimônio nem venda de ativos antigos. Trata-se de uma modelagem sistemática para guiar o fluxo novo de economia mensal, otimizando o prêmio de risco real.

Simule o rendimento comparado na calculadora oficial:

🔗 https://caferadar.com.br/calculadora-rendimento.html

—

$IBOV $BOVA11 $IVVB11 $BTC

#AlocacaoDeAtivos #RendaFixa #TesouroDireto #Investimentos #LongoPrazo #CafeRadar

(Estudo teórico quantitativo. Não constitui recomendação de investimento nem consultoria financeira - CVM 19/2021 e 20/2021).

"""

    p_legenda = out / f"{data_pub}_longoprazo_legenda.txt"

    p_legenda.write_text(legenda, encoding="utf-8")

    return arquivos_png, p_legenda

# ==============================================================================

# EXECUÇÃO PRINCIPAL DO MARKETING ENGINE

# ==============================================================================


# ==============================================================================
# GERADOR CATEGORIA E: CALCULADORA DE RENDIMENTO REAL & EDUCAÇÃO FINANCEIRA
# ==============================================================================

def gerar_materiais_calculadora(output_dir: Optional[Path] = None) -> Tuple[List[Path], Path]:
    """Gera cards (Feed e X) e legenda magnética de Educação Financeira (Calculadora IR Real)."""
    out = Path(output_dir or DEFAULT_OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)

    data_pub = datetime.now().strftime("%Y-%m-%d")
    data_fmt = datetime.now().strftime("%d/%m/%Y")

    arquivos_png = []

    # 1. Instagram Feed (1080x1350)
    img_feed, draw_feed = criar_canvas_base(1080, 1350, "Simulador de Renda", "Poupança vs CDB 100% vs Tesouro Selic", data_fmt)
    y_sub = 220
    x_left = 60

    draw_feed.text((x_left, y_sub), "SIMULAÇÃO COMPARATIVA — R$ 10.000 APLICADOS POR 2 ANOS", font=FONTES["body_bold"](18), fill=PALETA["destaque_claro"])

    linhas_sim = [
        ("Poupança (Isenta)", "R$ 11.236", "+12,36%", "Rendimento tradicional corrigido pela TR", PALETA["neutro"]),
        ("CDB 100% CDI (Líquido IR)", "R$ 12.080", "+20,80%", "Desconto automático de 15% de IR regressivo", PALETA["verde_texto"]),
        ("Tesouro Selic (Líquido IR)", "R$ 12.115", "+21,15%", "Segurança máxima do Tesouro Nacional com juros compostos", PALETA["destaque_claro"])
    ]

    y_card = y_sub + 45
    card_h = 145
    for nome, total, ganho, obs, cor_dest in linhas_sim:
        draw_feed.rounded_rectangle([x_left, y_card, x_left + 960, y_card + card_h], radius=16, fill=PALETA["card_bg"], outline=PALETA["card_border"], width=1)
        draw_feed.text((x_left + 24, y_card + 20), nome, font=FONTES["body_bold"](20), fill=PALETA["texto_branco"])
        draw_feed.text((x_left + 24, y_card + 54), obs, font=FONTES["body"](15), fill=PALETA["texto_secundario"])
        draw_feed.text((x_left + 24, y_card + 90), f"Saldo Líquido Estimado: {total}", font=FONTES["mono"](24), fill=cor_dest)

        draw_feed.rounded_rectangle([x_left + 960 - 150, y_card + 35, x_left + 960 - 24, y_card + 90], radius=8, fill=PALETA["card_inner"])
        draw_feed.text((x_left + 960 - 138, y_card + 48), ganho, font=FONTES["body_bold"](24), fill=cor_dest)
        y_card += card_h + 20

    y_aviso = y_card + 20
    draw_feed.rounded_rectangle([x_left, y_aviso, x_left + 960, y_aviso + 220], radius=16, fill="#1e1b4b", outline="#6366f1", width=2)
    draw_feed.text((x_left + 28, y_aviso + 24), "💡 VOCÊ ESTÁ PERDENDO DINHEIRO POR FALTA DE CÁLCULO?", font=FONTES["card_title"](20), fill="#a5b4fc")
    aviso_textos = [
        "A maioria dos poupadores deixa o dinheiro parado achando que 'poupança é segura'.",
        "Porém, ao descontar a inflação real, o poder de compra é corroído ano a ano.",
        "Em 2 anos, a diferença a favor do Tesouro Selic passa de R$ 870 em apenas R$ 10.000.",
        "Simule qualquer valor gratuitamente na calculadora oficial do Café Radar."
    ]
    y_at = y_aviso + 70
    for at in aviso_textos:
        draw_feed.text((x_left + 28, y_at), f"• {at}", font=FONTES["body"](18), fill=PALETA["texto_branco"])
        y_at += 34

    p_feed = out / f"{data_pub}_calculadora_feed.png"
    img_feed.save(p_feed)
    arquivos_png.append(p_feed)

    # 2. X / Twitter (1200x675)
    img_x, draw_x = criar_canvas_base(1200, 675, "Calculadora de Renda", "Poupança vs CDB vs Tesouro Selic", data_fmt)
    y_xt = 160

    col_w_x = 330
    gap_x = 25
    x_start = 66

    for idx, (nome, total, ganho, obs, cor_dest) in enumerate(linhas_sim):
        cx = x_start + idx * (col_w_x + gap_x)
        draw_x.rounded_rectangle([cx, y_xt, cx + col_w_x, y_xt + 280], radius=14, fill=PALETA["card_bg"], outline=PALETA["card_border"])
        draw_x.text((cx + 18, y_xt + 20), nome.split("(")[0].strip()[:18], font=FONTES["body_bold"](18), fill=PALETA["texto_branco"])
        draw_x.text((cx + 18, y_xt + 50), "Rendimento 24 Meses", font=FONTES["body"](13), fill=PALETA["texto_secundario"])
        draw_x.text((cx + 18, y_xt + 90), total, font=FONTES["mono"](28), fill=cor_dest)

        draw_x.rounded_rectangle([cx + 18, y_xt + 140, cx + col_w_x - 18, y_xt + 185], radius=6, fill=PALETA["card_inner"])
        draw_x.text((cx + 30, y_xt + 150), f"Ganho Real Líquido: {ganho}", font=FONTES["body_bold"](15), fill=cor_dest)

        draw_x.text((cx + 18, y_xt + 205), obs[:36], font=FONTES["body"](12), fill=PALETA["texto_secundario"])
        if len(obs) > 36:
            draw_x.text((cx + 18, y_xt + 225), obs[36:72], font=FONTES["body"](12), fill=PALETA["texto_secundario"])

    y_bot = y_xt + 310
    draw_x.rounded_rectangle([66, y_bot, 1134, y_bot + 95], radius=12, fill="#1e1b4b", outline="#6366f1", width=1)
    draw_x.text((86, y_bot + 22), "💡 SIMULADOR INTERATIVO DISPONÍVEL NO PORTAL CAFE RADAR", font=FONTES["body_bold"](17), fill="#a5b4fc")
    draw_x.text((86, y_bot + 54), "Desconto automático oficial da tabela regressiva da Receita Federal (22,5% a 15% de IR).", font=FONTES["body"](15), fill=PALETA["texto_branco"])

    p_x = out / f"{data_pub}_calculadora_x.png"
    img_x.save(p_x)
    arquivos_png.append(p_x)

    legenda = f"""💡 O ERRO DE R$ 1.800 QUE QUASE TODO BRASILEIRO COMETE ({data_fmt})

Deixar R$ 10.000 parados na Poupança parece "seguro". Mas em 2 anos, você perde quase R$ 2.000 de retorno líquido comparado ao Tesouro Selic ou a um CDB 100% CDI com juros compostos.

E a maioria das pessoas esquece de descontar o Imposto de Renda regressivo real da Receita Federal.

Criamos uma calculadora gratuita no Café Radar que faz essa conta na ponta do lápis em segundos:
• Poupança: Isenta, porém rendendo menos que a inflação real
• CDB 100% CDI: Rendimento com tabela de IR calculada automaticamente
• Tesouro Selic: Segurança máxima institucional

Simule qualquer valor gratuitamente sem cadastro:
🔗 https://caferadar.com.br/calculadora-rendimento.html

—
$SELIC $CDI $TESOURO
#EducacaoFinanceira #RendaFixa #TesouroDireto #Investimentos #CafeRadar
(Ferramenta com propósito estritamente educativo e informativo. Não constitui recomendação de investimento nos termos da CVM 19/2021).
"""
    p_legenda = out / f"{data_pub}_calculadora_legenda.txt"
    p_legenda.write_text(legenda, encoding="utf-8")

    return arquivos_png, p_legenda


def main(categorias: Optional[List[str]] = None, output_dir: Optional[Path] = None) -> int:

    """Executa a geração completa de cards e legendas."""

    print("====================================================================")

    print("       CAFÉ RADAR — MARKETING ENGINE LOCAL v1.0.1")

    print("====================================================================")

    out = Path(output_dir or DEFAULT_OUTPUT_DIR)

    out.mkdir(parents=True, exist_ok=True)

    sucesso_total = True

    categorias_alvo = [c.lower() for c in (categorias or ["abertura", "fechamento", "swing", "longoprazo"])]

    # 1. Abertura

    if "abertura" in categorias_alvo:

        print("\n---> [1/4] Gerando materiais de Café Matinal (Abertura)...")

        ok, dados, msg = carregar_fechamento()

        if not ok or not dados:

            print(f"      [AVISO] Não foi possível carregar fechamento.json: {msg}")

            sucesso_total = False

        else:

            pngs, txt = gerar_materiais_abertura(dados, output_dir=out)

            print(f"      [OK] Gerados {len(pngs)} cards PNG e 1 arquivo de legenda TXT.")

    # 1.5 Negócios / Abertura B3

    if "negocios" in categorias_alvo or "abertura_b3" in categorias_alvo:

        print("\n---> [1.5/5] Gerando materiais de Abertura B3 (Primeiros Negócios)...")

        ok, dados, msg = carregar_fechamento()

        if not ok or not dados:

            print(f"      [AVISO] Não foi possível carregar fechamento.json: {msg}")

            sucesso_total = False

        else:

            pngs, txt = gerar_materiais_negocios(dados, output_dir=out)

            print(f"      [OK] Gerados {len(pngs)} cards PNG e 1 arquivo de legenda TXT.")

    # 2. Fechamento

    if "fechamento" in categorias_alvo:

        print("\n---> [2/4] Gerando materiais de Fechamento Oficial B3...")

        ok, dados, msg = carregar_fechamento()

        if not ok or not dados:

            print(f"      [AVISO] Não foi possível carregar fechamento.json: {msg}")

            sucesso_total = False

        else:

            pngs, txt = gerar_materiais_fechamento(dados, output_dir=out)

            print(f"      [OK] Gerados {len(pngs)} cards PNG e 1 arquivo de legenda TXT.")

    # 3. Swing Trade

    if "swing" in categorias_alvo:

        print("\n---> [3/4] Gerando materiais de Radar Swing Trade (+5%)...")

        ok, dados, msg = carregar_swingtrade()

        if not ok or not dados:

            print(f"      [AVISO] Não foi possível carregar swingtrade.json: {msg}")

            sucesso_total = False

        else:

            pngs, txt = gerar_materiais_swing(dados, output_dir=out)

            print(f"      [OK] Gerados {len(pngs)} cards PNG e 1 arquivo de legenda TXT.")

    # 4. Longo Prazo

        # 5. Calculadora de Renda e Educação Financeira
    if "calculadora" in categorias_alvo or "renda" in categorias_alvo:
        print("\n---> [5/5] Gerando materiais da Calculadora de Rendimento Real...")
        pngs, txt = gerar_materiais_calculadora(output_dir=out)
        print(f"      [OK] Gerados {len(pngs)} cards PNG e 1 arquivo de legenda TXT.")

    if "longoprazo" in categorias_alvo or "alocacao" in categorias_alvo:

        print("\n---> [4/4] Gerando materiais de Radar Longo Prazo...")

        ok, dados, msg = carregar_dashboard()

        if not ok or not dados:

            print(f"      [AVISO] Não foi possível carregar dashboard.json: {msg}")

            sucesso_total = False

        else:

            pngs, txt = gerar_materiais_longoprazo(dados, output_dir=out)

            print(f"      [OK] Gerados {len(pngs)} cards PNG e 1 arquivo de legenda TXT.")

    print("\n====================================================================")

    print(f"   [CONCLUÍDO] Materiais salvos em: {out}")

    print("====================================================================")

    return 0 if sucesso_total else 1

if __name__ == "__main__":

    args = sys.argv[1:]

    sys.exit(main(args if args else None))