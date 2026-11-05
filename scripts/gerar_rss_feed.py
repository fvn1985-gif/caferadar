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
from pathlib import Path
from xml.sax.saxutils import escape

BASE_DIR = Path(__file__).resolve().parent.parent
FECHAMENTO_JSON = BASE_DIR / "web" / "data" / "fechamento.json"
if not FECHAMENTO_JSON.exists():
    FECHAMENTO_JSON = BASE_DIR / "data" / "fechamento.json"

WEB_DIR = BASE_DIR / "web"
DEPLOY_DIR = BASE_DIR / "web_deploy"

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

def gerar_feed():
    if not FECHAMENTO_JSON.exists():
        print(f"ERRO: {FECHAMENTO_JSON} não encontrado.")
        return

    with open(FECHAMENTO_JSON, "r", encoding="utf-8") as f:
        dados = json.load(f)

    data_ref = dados.get("data_referencia", datetime.now().strftime("%Y-%m-%d"))
    agora_rfc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    itens_xml = []
    edicoes = dados.get("edicoes", {})

    ordem_chaves = ["fechamento", "negocios", "abertura"]
    for k in ordem_chaves:
        if k not in edicoes:
            continue
        ed = edicoes[k]
        titulo = escape(ed.get("titulo", f"Radar de Mercado — {k.capitalize()}"))
        subtitulo = escape(ed.get("subtitulo", ""))
        hora = ed.get("horario", "12h00")
        pub_date = formatar_data_rfc822(data_ref, hora)
        link = f"https://caferadar.com.br/#fechamento"
        guid = f"https://caferadar.com.br/{data_ref}/{k}"

        noticias_corpo = []
        for n in ed.get("leitura_rapida", []):
            texto_limpo = escape(n.get("texto", ""))
            fonte_limpa = escape(n.get("fonte", "Mercado"))
            noticias_corpo.append(f"<p>{texto_limpo} <em>(Fonte: {fonte_limpa})</em></p>")

        corpo_html = f"<p><strong>{subtitulo}</strong></p>" + "".join(noticias_corpo) + "<p><a href='https://caferadar.com.br/'>Acesse o painel completo de cotações em tempo real no Café Radar</a>.</p>"

        item_str = f"""    <item>
      <title>{titulo}</title>
      <link>{link}</link>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{pub_date}</pubDate>
      <description><![CDATA[{corpo_html}]]></description>
      <category>Mercados Financeiros</category>
    </item>"""
        itens_xml.append(item_str)

    xml_completo = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Café Radar — Notícias e Síntese Diária do Mercado B3</title>
    <link>https://caferadar.com.br/</link>
    <description>Veículo independente de inteligência financeira, síntese de pregão diário da B3, cotações ao vivo e scanner quantitativo.</description>
    <language>pt-br</language>
    <lastBuildDate>{agora_rfc}</lastBuildDate>
    <atom:link href="https://caferadar.com.br/feed.xml" rel="self" type="application/rss+xml" />
    <image>
      <url>https://caferadar.com.br/google-news-square-1000.png</url>
      <title>Café Radar</title>
      <link>https://caferadar.com.br/</link>
    </image>
{chr(10).join(itens_xml)}
  </channel>
</rss>"""

    p_web = WEB_DIR / "feed.xml"
    p_deploy = DEPLOY_DIR / "feed.xml"
    p_web.write_text(xml_completo, encoding="utf-8")
    p_deploy.write_text(xml_completo, encoding="utf-8")
    print(f"[OK] RSS Feed gravado com sucesso em:\n  - {p_web}\n  - {p_deploy}")

if __name__ == "__main__":
    gerar_feed()
