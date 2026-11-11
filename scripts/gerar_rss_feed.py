#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/gerar_rss_feed.py
=======================
Gera o feed RSS oficial de notícias (feed.xml) em conformidade com os padrões do Google News.
Consome: data/fechamento.json
Produz: web/feed.xml e web_deploy/feed.xml
"""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from xml.sax.saxutils import escape

BASE_DIR = Path(__file__).resolve().parent.parent
if (BASE_DIR / "web" / "data" / "fechamento.json").is_file():
    WEB_DIR = BASE_DIR / "web"
    DEPLOY_DIR = BASE_DIR / "web_deploy"
    FECHAMENTO_JSON = WEB_DIR / "data" / "fechamento.json"
else:
    WEB_DIR = BASE_DIR
    DEPLOY_DIR = BASE_DIR
    FECHAMENTO_JSON = BASE_DIR / "data" / "fechamento.json"

TZ_SP = ZoneInfo("America/Sao_Paulo")





def formatar_data_rfc822(data_iso: str, hora_str: str = "12h00") -> str:
    """Converte '2026-11-05' e '10h30' em formato RFC-822 para RSS: 'Thu, 05 Nov 2026 10:30:00 -0300'."""
    try:
        partes_hora = hora_str.replace("h", ":").split(":")
        h = int(partes_hora[0]) if len(partes_hora) > 0 else 12
        m = int(partes_hora[1]) if len(partes_hora) > 1 else 0
        dt = datetime.strptime(data_iso, "%Y-%m-%d").replace(hour=h, minute=m, second=0)
        # RFC-822 com timezone de Brasília (-0300)
        dias = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        meses = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        dia_sem = dias[dt.weekday()]
        mes_str = meses[dt.month - 1]
        return f"{dia_sem}, {dt.day:02d} {mes_str} {dt.year} {dt.hour:02d}:{dt.minute:02d}:00 -0300"
    except Exception:
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

def gerar_feed(include_deploy: bool = False):
    if not FECHAMENTO_JSON.exists():
        print(f"ERRO: {FECHAMENTO_JSON} não encontrado.")
        return

    with open(FECHAMENTO_JSON, "r", encoding="utf-8") as f:
        dados = json.load(f)

    data_ref = dados.get("data_referencia", datetime.now(TZ_SP).strftime("%Y-%m-%d"))
    agora_rfc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    itens_xml = []
    edicoes = dados.get("edicoes", {})

    mapa_slug_rss = {
        "fechamento": ("fechamento", "fechamento", "fechamento"),
        "negocios": ("abertura", "negocios", "abertura"),
        "almoco": ("abertura", "negocios", "abertura"),
        "abertura": ("matinal", "abertura", "matinal")
    }

    mkt_dir = WEB_DIR / "marketing_output"

    ordem_chaves = ["fechamento", "negocios", "abertura"]
    for k in ordem_chaves:
        if k not in edicoes:
            continue
        ed = edicoes[k]
        if not ed.get("disponivel", True) or ed.get("sem_captura_legitima", False):
            continue
        
        cfg_ed = mapa_slug_rss.get(k, (k, k, k))
        slug_ed = cfg_ed[0]
        card_tipo = cfg_ed[1]
        card_fallback = cfg_ed[2]
        titulo = escape(ed.get("titulo", f"Radar de Mercado — {k.capitalize()}"))
        subtitulo = escape(ed.get("subtitulo", ""))
        hora = ed.get("horario", "12h00")
        pub_date = formatar_data_rfc822(data_ref, hora)
        link = f"https://caferadar.com.br/edicoes/{data_ref}-{slug_ed}.html"
        guid = f"https://caferadar.com.br/edicoes/{data_ref}-{slug_ed}.html"

        # Localiza imagem específica de alta definição da edição
        img_url = "https://caferadar.com.br/og-image.png"
        img_len = 180000
        card_file = mkt_dir / f"{data_ref}_{card_tipo}_x.png"
        if not card_file.is_file() and card_fallback:
            card_file = mkt_dir / f"{data_ref}_{card_fallback}_x.png"
        if card_file.is_file():
            img_url = f"https://caferadar.com.br/marketing_output/{card_file.name}"
            img_len = card_file.stat().st_size

        noticias_corpo = []
        for n in ed.get("leitura_rapida", []):
            texto_limpo = escape(n.get("texto", ""))
            fonte_limpa = escape(n.get("fonte", "Mercado"))
            noticias_corpo.append(f"<p>{texto_limpo} <em>(Fonte: {fonte_limpa})</em></p>")

        corpo_html = f"<p><img src='{img_url}' alt='{titulo}' width='1200' height='675' style='max-width:100%; height:auto;' /></p><p><strong>{subtitulo}</strong></p>" + "".join(noticias_corpo) + "<p><a href='https://caferadar.com.br/'>Acesse o painel completo de cotações no CafeRadar</a>.</p>"

        item_str = f"""    <item>
      <title>{titulo}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{guid}</guid>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{img_url}" length="{img_len}" type="image/png" />
      <description><![CDATA[{corpo_html}]]></description>
      <category>Mercados Financeiros</category>
    </item>"""
        itens_xml.append(item_str)

    xml_completo = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>CafeRadar — Notícias e Síntese Diária do Mercado B3</title>
    <link>https://caferadar.com.br/</link>
    <description>Veículo independente de inteligência financeira, síntese de pregão diário da B3, cotações de referência e scanner quantitativo.</description>
    <language>pt-br</language>
    <lastBuildDate>{agora_rfc}</lastBuildDate>
    <atom:link href="https://caferadar.com.br/feed.xml" rel="self" type="application/rss+xml" />
    <image>
      <url>https://caferadar.com.br/google-news-square-1000.png</url>
      <title>CafeRadar</title>
      <link>https://caferadar.com.br/</link>
    </image>
{chr(10).join(itens_xml)}
  </channel>
</rss>"""

    p_web = WEB_DIR / "feed.xml"
    p_web.write_text(xml_completo, encoding="utf-8")
    print(f"[OK] RSS Feed gravado com sucesso em: {p_web}")
    if include_deploy and DEPLOY_DIR != WEB_DIR and DEPLOY_DIR.exists():
        p_deploy = DEPLOY_DIR / "feed.xml"
        p_deploy.write_text(xml_completo, encoding="utf-8")
        print(f"[OK] RSS Feed gravado com sucesso em: {p_deploy}")

if __name__ == "__main__":
    import sys
    gerar_feed(include_deploy="--include-deploy" in sys.argv)
