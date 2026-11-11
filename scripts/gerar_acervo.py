#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de Acervo Estático & URLs Permanentes para o CafeRadar
Cria páginas HTML 100% pré-renderizadas por edição:
  - /edicoes/YYYY-MM-DD-matinal.html (Café Matinal, 08h00)
  - /edicoes/YYYY-MM-DD-abertura.html (Abertura B3, 10h30)
  - /edicoes/YYYY-MM-DD-fechamento.html (Fechamento B3, 18h15)
Com redirecionamentos transparentes para URLs legadas (-almoco.html, -negocios.html),
imagens exclusivas em alta definição por edição (Discover / Rich Results),
Schema NewsArticle + BreadcrumbList, bloco de matérias relacionadas e sitemap dinâmico.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
TZ_SP = ZoneInfo("America/Sao_Paulo")


def _esc(valor: object) -> str:
    return escape("" if valor is None else str(valor), quote=True)


def _url_http_segura(url: object) -> str:
    s = str(url or "").strip()
    return s if re.match(r"^https?://", s, flags=re.IGNORECASE) else ""


def _js_str(valor: object) -> str:
    return json.dumps("" if valor is None else str(valor), ensure_ascii=False).replace("</", "<\\/")


def _detectar_bases_acervo(include_deploy: bool = False) -> list[Path]:
    if (ROOT / "web" / "data" / "fechamento.json").is_file():
        bases = [ROOT / "web"]
        if include_deploy and (ROOT / "web_deploy").is_dir():
            bases.append(ROOT / "web_deploy")
        return bases
    if (ROOT / "data" / "fechamento.json").is_file():
        return [ROOT]
    return [ROOT / "web"]

# Mapeamento oficial de slugs canônicos e imagens de card
MAPA_SLUGS_CANONICOS = {
    "matinal": {
        "slug": "matinal",
        "nome_padrao": "Café Matinal",
        "horario": "08h00",
        "card_tipo": "matinal",
        "card_fallback": "abertura",
        "ordem": 1
    },
    "abertura": {
        "slug": "abertura",
        "nome_padrao": "Abertura B3",
        "horario": "10h30",
        "card_tipo": "negocios",
        "card_fallback": "abertura",
        "ordem": 2
    },
    "fechamento": {
        "slug": "fechamento",
        "nome_padrao": "Fechamento",
        "horario": "18h15",
        "card_tipo": "fechamento",
        "card_fallback": "fechamento",
        "ordem": 3
    }
}

def normalizar_chave_edicao(ed_key: str, titulo: str = "") -> str:
    """Normaliza chaves legadas ('abertura' contendo matinal, 'almoco', 'negocios') para slugs canônicos."""
    t_upper = titulo.upper()
    if "MATINAL" in t_upper or "MAPA DA SEMANA" in t_upper:
        return "matinal"
    if "ABERTURA" in t_upper or "RADAR DE SEGUNDA" in t_upper or ed_key in ["almoco", "negocios"]:
        return "abertura"
    if "FECHAMENTO" in t_upper or "BALANÇO DA SEMANA" in t_upper or ed_key == "fechamento":
        return "fechamento"
    if ed_key == "abertura":
        return "matinal"
    return ed_key

def obter_imagem_edicao(data_ref: str, slug_canonico: str, base_dir: Path) -> str:
    """
    Localiza o card PNG horizontal exclusivo (1200x675) da edição em web/marketing_output/.
    Se não encontrado, retorna o card oficial web/og-image.png (1200x630).
    """
    cfg_card = MAPA_SLUGS_CANONICOS.get(slug_canonico, {})
    card_tipo = cfg_card.get("card_tipo", slug_canonico)
    fallback_tipo = cfg_card.get("card_fallback", "")
    candidatos = [
        f"{data_ref}_{card_tipo}_x.png",
        f"{data_ref}_{fallback_tipo}_x.png" if fallback_tipo else None,
        f"{data_ref}_{slug_canonico}_x.png",
        f"{data_ref}_fechamento_x.png" if slug_canonico == "fechamento" else None
    ]
    mkt_dir = base_dir / "marketing_output"
    for cand in candidatos:
        if cand and (mkt_dir / cand).is_file():
            return f"https://caferadar.com.br/marketing_output/{cand}"
    
    return "https://caferadar.com.br/og-image.png"

def gerar_pagina_edicao(
    ed_dados: dict,
    data_ref: str,
    data_fmt: str,
    slug_canonico: str,
    base_dir: Path,
    anterior: dict | None = None,
    proxima: dict | None = None,
    relacionados: list[dict] | None = None,
    data_publicada: str | None = None,
    data_modificada: str | None = None
) -> str:
    cfg = MAPA_SLUGS_CANONICOS.get(slug_canonico, {
        "slug": slug_canonico,
        "nome_padrao": ed_dados.get("nome", slug_canonico.capitalize()),
        "horario": ed_dados.get("horario", "18h15")
    })

    nome_ed = ed_dados.get("nome") or cfg["nome_padrao"]
    horario = ed_dados.get("horario") or cfg["horario"]
    titulo_raw = ed_dados.get("titulo", f"RADAR DE {nome_ed.upper()} — {data_fmt}")
    
    # Title otimizado para CTR e SERP sem duplicação de marca:
    if slug_canonico == "matinal":
        titulo_seo = f"Café Matinal B3 em 2 Minutos — {data_fmt} | CafeRadar B3"
    elif slug_canonico == "abertura":
        titulo_seo = f"Abertura da B3 em 2 Minutos — {data_fmt} | CafeRadar B3"
    else:
        titulo_seo = f"Fechamento do Pregão B3 em 2 Minutos — {data_fmt} | CafeRadar B3"
    subtitulo = ed_dados.get("subtitulo", f"Síntese informativa do pregão da B3 na edição {nome_ed} de {data_fmt}.")

    canonical_url = f"https://caferadar.com.br/edicoes/{data_ref}-{slug_canonico}.html"
    img_url = obter_imagem_edicao(data_ref, slug_canonico, base_dir)

    # Tickers rápidos
    tickers_html = ""
    mg = ed_dados.get("mercado_geral", {})
    for k in ["ibov", "dolar", "sp500", "bitcoin", "brent"]:
        if k in mg:
            item = mg[k]
            nome = item.get("nome", k.upper())
            val = item.get("pontos") or item.get("valor") or "—"
            var = item.get("variacao") or "0,00%"
            pos = item.get("positivo", True)
            cor = "#16a34a" if pos else "#dc2626"
            seta = "▲" if pos else "▼"
            tickers_html += f"""
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; text-align:center;">
              <div style="font-size:0.75rem; font-weight:700; color:#64748b; text-transform:uppercase;">{_esc(nome)}</div>
              <div style="font-size:1.25rem; font-weight:800; color:#0f172a; margin:4px 0; font-family:'JetBrains Mono',monospace;">{_esc(val)}</div>
              <div style="font-size:0.85rem; font-weight:700; color:{cor};">{seta} {_esc(var)}</div>
            </div>
            """

    # Leitura Rápida
    leitura_html = ""
    for item in ed_dados.get("leitura_rapida", []):
        txt = item.get("texto", "")
        fonte = item.get("fonte", "")
        link = _url_http_segura(item.get("link", ""))
        link_str = f' <a href="{_esc(link)}" target="_blank" rel="noopener" style="color:#2563eb; text-decoration:underline;">({_esc(fonte)} ↗)</a>' if link else (f' <span style="color:#64748b; font-size:0.85rem;">({_esc(fonte)})</span>' if fonte else "")
        leitura_html += f"""
        <li style="margin-bottom:12px; font-size:0.95rem; line-height:1.6; color:#334155;">
          {_esc(txt)}{link_str}
        </li>
        """

    # Blue chips com cabeçalho
    blue_html = """
    <thead>
      <tr style="background:#f1f5f9; text-align:left; font-size:0.82rem; color:#475569;">
        <th>Ativo</th>
        <th style="text-align:right;">Preço</th>
        <th style="text-align:right;">Dia</th>
      </tr>
    </thead>
    <tbody>
    """
    for ac in ed_dados.get("acoes_blue_chips", []):
        tick = ac.get("ticker", "")
        n = ac.get("nome", "")
        pr = ac.get("preco", "")
        vd = ac.get("variacao_dia", "")
        pos = ac.get("positivo", True)
        cor = "#16a34a" if pos else "#dc2626"
        blue_html += f"""
      <tr>
        <td style="padding:10px 12px; border-bottom:1px solid #e2e8f0; font-weight:700;">{_esc(tick)} <span style="font-weight:400; color:#64748b; font-size:0.82rem;">{_esc(n)}</span></td>
        <td style="padding:10px 12px; border-bottom:1px solid #e2e8f0; text-align:right; font-family:monospace;">{_esc(pr)}</td>
        <td style="padding:10px 12px; border-bottom:1px solid #e2e8f0; text-align:right; font-weight:700; color:{cor}; font-family:monospace;">{_esc(vd)}</td>
      </tr>
      """
    blue_html += "</tbody>"

    # Destaques B3 com tabela estruturada e cabeçalho <th>Ativo</th><th>Variação</th>
    destaques = ed_dados.get("destaques", {})
    altas_html = """
    <table style="width:100%; font-size:0.88rem; border-collapse:collapse; margin-bottom:8px;">
      <thead>
        <tr style="background:#f1f5f9; text-align:left; font-size:0.8rem; color:#475569;">
          <th>Ativo</th>
          <th style="text-align:right;">Variação</th>
        </tr>
      </thead>
      <tbody>
    """
    for a in destaques.get("altas", []):
        altas_html += f"""
        <tr>
          <td style="padding:6px 10px; border-bottom:1px dashed #e2e8f0; font-weight:700; color:#0f172a;">{_esc(a.get('ticker'))}</td>
          <td style="padding:6px 10px; border-bottom:1px dashed #e2e8f0; text-align:right; color:#16a34a; font-weight:700; font-family:monospace;">{_esc(a.get('variacao'))}</td>
        </tr>
        """
    altas_html += "</tbody></table>"

    quedas_html = """
    <table style="width:100%; font-size:0.88rem; border-collapse:collapse; margin-bottom:8px;">
      <thead>
        <tr style="background:#f1f5f9; text-align:left; font-size:0.8rem; color:#475569;">
          <th>Ativo</th>
          <th style="text-align:right;">Variação</th>
        </tr>
      </thead>
      <tbody>
    """
    for q in destaques.get("quedas", []):
        quedas_html += f"""
        <tr>
          <td style="padding:6px 10px; border-bottom:1px dashed #e2e8f0; font-weight:700; color:#0f172a;">{_esc(q.get('ticker'))}</td>
          <td style="padding:6px 10px; border-bottom:1px dashed #e2e8f0; text-align:right; color:#dc2626; font-weight:700; font-family:monospace;">{_esc(q.get('variacao'))}</td>
        </tr>
        """
    quedas_html += "</tbody></table>"

    # Navegação sequencial
    nav_itens = []
    if anterior:
        nav_itens.append(f'<a href="{_esc(anterior["arquivo"])}" style="color:var(--destaque); font-weight:700; text-decoration:none; font-size:0.88rem;">← {_esc(anterior["nome"])} ({_esc(anterior["data_fmt"])})</a>')
    else:
        nav_itens.append('<span></span>')
    if proxima:
        nav_itens.append(f'<a href="{_esc(proxima["arquivo"])}" style="color:var(--destaque); font-weight:700; text-decoration:none; font-size:0.88rem;">{_esc(proxima["nome"])} ({_esc(proxima["data_fmt"])}) →</a>')
    else:
        nav_itens.append('<span></span>')

    nav_edicoes_html = f"""
    <nav aria-label="Navegação entre edições" style="display:flex; justify-content:space-between; align-items:center; gap:16px; margin-top:28px; padding-top:20px; border-top:1px solid #e2e8f0; flex-wrap:wrap;">
      <div>{nav_itens[0]}</div>
      <div>{nav_itens[1]}</div>
    </nav>
    """

    # Bloco Mercado de Ações (Blue Chips + Destaques)
    tem_blue = bool(ed_dados.get("acoes_blue_chips", []))
    tem_destaques = bool(destaques.get("altas") or destaques.get("quedas"))
    sem_captura = ed_dados.get("sem_captura_legitima", False)

    if sem_captura or (not tem_blue and not tem_destaques):
        bloco_mercado_acoes = ""
    elif tem_blue:
        bloco_mercado_acoes = f'''
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:20px; margin-bottom:28px;">
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px;">
          <h3 style="font-size:0.95rem; color:var(--primaria); font-weight:700; margin-bottom:10px;">📈 Ações Mais Negociadas</h3>
          <table style="width:100%; font-size:0.88rem; border-collapse:collapse;">
            {blue_html}
          </table>
        </div>

        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px;">
          <h3 style="font-size:0.95rem; color:var(--primaria); font-weight:700; margin-bottom:10px;">🔥 Destaques entre as Blue Chips Monitoradas</h3>
          <div style="margin-bottom:12px;">
            <div style="font-size:0.8rem; font-weight:700; color:#16a34a; margin-bottom:6px;">▲ ALTAS NO GRUPO</div>
            {altas_html}
          </div>
          <div>
            <div style="font-size:0.8rem; font-weight:700; color:#dc2626; margin-bottom:6px;">▼ QUEDAS NO GRUPO</div>
            {quedas_html}
          </div>
        </div>
      </div>
        '''
    else:
        bloco_mercado_acoes = f'''
      <div style="display:grid; grid-template-columns:1fr; gap:20px; margin-bottom:28px;">
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px;">
          <h3 style="font-size:0.95rem; color:var(--primaria); font-weight:700; margin-bottom:10px;">🔥 Destaques entre as Blue Chips Monitoradas</h3>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:16px;">
            <div>
              <div style="font-size:0.8rem; font-weight:700; color:#16a34a; margin-bottom:6px;">▲ ALTAS NO GRUPO</div>
              {altas_html}
            </div>
            <div>
              <div style="font-size:0.8rem; font-weight:700; color:#dc2626; margin-bottom:6px;">▼ QUEDAS NO GRUPO</div>
              {quedas_html}
            </div>
          </div>
        </div>
      </div>
        '''

    # Bloco de 3 matérias relacionadas no rodapé
    relacionados_html = ""
    if relacionados:
        cards_rel = []
        for r in relacionados[:3]:
            cards_rel.append(f"""
            <a href="{_esc(r['arquivo'])}" style="display:block; text-decoration:none; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; transition:all 0.15s ease;">
              <div style="font-size:0.75rem; font-weight:800; color:var(--destaque); text-transform:uppercase; margin-bottom:4px;">{_esc(r['nome'])}</div>
              <div style="font-size:0.92rem; font-weight:700; color:#0f172a; line-height:1.35; margin-bottom:6px;">{_esc(r['titulo'])}</div>
              <div style="font-size:0.8rem; color:#64748b;">{_esc(r['data_fmt'])}</div>
            </a>
            """)
        relacionados_html = f"""
        <section style="margin-top:32px; padding-top:24px; border-top:1px solid #e2e8f0;">
          <h3 style="font-size:1.1rem; color:var(--primaria); font-weight:800; margin-bottom:14px;">📚 Outras Edições Recentes no Acervo</h3>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px;">
            {''.join(cards_rel)}
          </div>
        </section>
        """

    sem_captura = ed_dados.get("sem_captura_legitima", False)
    if sem_captura:
        tickers_html = ""
        grid_tickers_html = ""
    else:
        grid_tickers_html = f'''
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:12px; margin-bottom:28px;">
        {tickers_html}
      </div>
        ''' if tickers_html else ""

    # Horário ISO 8601
    hora_limpa = horario.replace('h', ':').strip()
    if ":" not in hora_limpa:
        hora_limpa = f"{hora_limpa}:00"
    if len(hora_limpa) == 4:
        hora_limpa = f"0{hora_limpa}"
    iso_datetime = f"{data_ref}T{hora_limpa}:00-03:00"
    iso_pub = data_publicada if data_publicada else iso_datetime
    capturado_em = ed_dados.get("capturado_em")
    iso_mod = capturado_em if capturado_em else (data_modificada if data_modificada else iso_datetime)

    sem_captura = ed_dados.get("sem_captura_legitima", False)
    if capturado_em:
        hora_cap_fmt = capturado_em[11:16]
        aviso_captura_html = f'<div style="font-size:0.8rem; color:#64748b; margin-top:4px;">⏱️ Dados capturados às {_esc(hora_cap_fmt)} (horário de Brasília)</div>'
    else:
        aviso_captura_html = ""

    if sem_captura:
        meta_robots = '<meta name="robots" content="noindex, nofollow">'
        banner_aviso_sem_captura = '''
      <div style="background:#fffbeb; border:1px solid #fef3c7; border-left:4px solid #f59e0b; border-radius:8px; padding:16px; margin-bottom:24px;">
        <strong style="color:#b45309;">⚠️ Edição sem captura no horário:</strong> <span style="color:#78350f; font-size:0.92rem;">Os dados de pré-mercado das 08h00 não foram capturados nesta data. Conteúdo preservado unicamente para integridade do acervo histórico.</span>
      </div>
        '''
    else:
        meta_robots = '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">'
        banner_aviso_sem_captura = "" 

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_esc(titulo_seo)}</title>
  <meta name="description" content="{_esc(subtitulo)}">
  <meta name="author" content="Fernando Rossi">
  {meta_robots}
  <link rel="canonical" href="{_esc(canonical_url)}">

  <!-- Preconnect & Preload de Performance -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="preload" href="../style.css" as="style">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../style.css">

  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" href="../apple-touch-icon.png">
  <link rel="apple-touch-icon" href="../apple-touch-icon.png">

  <!-- OpenGraph / Social Cards -->
  <meta property="og:site_name" content="CafeRadar">
  <meta property="og:title" content="{_esc(titulo_seo)}">
  <meta property="og:description" content="{_esc(subtitulo)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{_esc(canonical_url)}">
  <meta property="og:image" content="{_esc(img_url)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="675">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{_esc(titulo_seo)}">
  <meta name="twitter:description" content="{_esc(subtitulo)}">
  <meta name="twitter:image" content="{_esc(img_url)}">

  <!-- Google Consent Mode v2 (Conformidade com LGPD & DMA) -->
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('consent', 'default', {{
      'ad_storage': 'denied',
      'analytics_storage': 'denied',
      'ad_user_data': 'denied',
      'ad_personalization': 'denied',
      'wait_for_update': 500
    }});
    try {{
      if (localStorage.getItem('caferadar_cookies_ack') === 'true') {{
        gtag('consent', 'update', {{
          'ad_storage': 'granted',
          'analytics_storage': 'granted',
          'ad_user_data': 'granted',
          'ad_personalization': 'granted'
        }});
      }}
    }} catch (e) {{}}
    gtag('js', new Date());
    gtag('config', 'G-50J887FJDV');
  </script>
  <!-- Google Analytics 4 (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-50J887FJDV"></script>

  <!-- Google AdSense Oficial -->
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6721082194258309" crossorigin="anonymous"></script>

  <!-- Schema.org NewsArticle (Google Discover & Rich Results) -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": {_js_str(titulo_seo)},
    "description": {_js_str(subtitulo)},
    "image": [
      {_js_str(img_url)}
    ],
    "datePublished": {_js_str(iso_pub)},
    "dateModified": {_js_str(iso_mod)},
    "mainEntityOfPage": {_js_str(canonical_url)},
    "author": {{
      "@type": "Person",
      "name": "Fernando Rossi",
      "url": "https://caferadar.com.br/sobre.html"
    }},
    "publisher": {{
      "@type": "Organization",
      "name": "CafeRadar",
      "url": "https://caferadar.com.br/",
      "logo": {{
        "@type": "ImageObject",
        "url": "https://caferadar.com.br/apple-touch-icon.png"
      }}
    }}
  }}
  </script>

  <!-- Schema.org BreadcrumbList -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{
        "@type": "ListItem",
        "position": 1,
        "name": "Página Inicial",
        "item": "https://caferadar.com.br/"
      }},
      {{
        "@type": "ListItem",
        "position": 2,
        "name": "Acervo de Edições",
        "item": "https://caferadar.com.br/edicoes/"
      }},
      {{
        "@type": "ListItem",
        "position": 3,
        "name": {_js_str(f"{nome_ed} — {data_fmt}")},
        "item": {_js_str(canonical_url)}
      }}
    ]
  }}
  </script>
</head>
<body>
  <header class="cabecalho-portal">
    <div class="container container-header">
      <div class="marca-portal">
        <a href="../" style="text-decoration:none; display:flex; align-items:center; gap:12px;">
          <div class="logo-icone">CR</div>
          <div>
            <div class="portal-titulo">CAFERADAR</div>
            <p class="portal-slogan">Acervo de Mercado B3 &amp; Edições Oficiais</p>
          </div>
        </a>
      </div>
      <div class="status-topo">
        <a href="../" class="btn-tab ativa" style="text-decoration:none; border:1px solid var(--borda); border-radius:9999px; padding:6px 14px;">
          <span>← Voltar ao Portal ao Vivo</span>
        </a>
      </div>
    </div>
  </header>

  <main class="container" style="max-width:860px; margin:32px auto 60px;">
    <!-- Link canônico de retorno para a raiz do acervo /edicoes/ -->
    <div style="margin-bottom:16px;">
      <a href="./" style="color:var(--destaque); font-weight:600; text-decoration:none; font-size:0.9rem;">← Todas as Edições Anteriores (Acervo)</a>
    </div>

    <article class="card-bloco-noticia" style="padding:32px; border:1px solid var(--borda);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
        <div>
          <div style="display:flex; gap:10px; align-items:center;">
            <span style="background:var(--destaque); color:#fff; font-size:0.75rem; font-weight:800; padding:3px 10px; border-radius:9999px; text-transform:uppercase;">{_esc(nome_ed)}</span>
            <time datetime="{_esc(data_ref)}" style="font-size:0.85rem; color:var(--texto-secundario); font-weight:600;">{_esc(data_fmt)} às {_esc(horario)}</time>
          </div>
          {aviso_captura_html}
        </div>
        <div style="font-size:0.82rem; color:var(--texto-secundario);">
          Por <a href="../sobre.html" style="color:var(--destaque); font-weight:700; text-decoration:none;">Fernando Rossi</a> · Inteligência B3
        </div>
      </div>

      <h1 style="font-size:1.8rem; color:var(--primaria); font-weight:800; margin-bottom:12px; line-height:1.25;">{_esc(titulo_raw)}</h1>
      <p style="font-size:1.05rem; color:var(--texto-secundario); line-height:1.6; margin-bottom:20px;">{_esc(subtitulo)}</p>
      {banner_aviso_sem_captura}

      <!-- Imagem Hero 1200x675 (Elegibilidade Discover e CTR Social) -->
      <figure style="margin:0 0 24px; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0; background:#0f172a;">
        <img src="{_esc(img_url)}" alt="{_esc(titulo_seo)}" width="1200" height="675" fetchpriority="high" loading="eager" style="width:100%; height:auto; display:block; aspect-ratio:16/9; object-fit:cover;">
      </figure>

      {grid_tickers_html}

      <h2 style="font-size:1.2rem; color:var(--primaria); font-weight:800; margin-bottom:14px;">⏱️ Síntese do Pregão em 2 Minutos</h2>
      <ul style="padding-left:20px; margin-bottom:28px;">
        {leitura_html}
      </ul>

      {bloco_mercado_acoes}

      <div class="aviso-legal-cvm" style="margin-top:24px;">
        <span class="icone-balanca">⚖️</span>
        <p>
          <strong>Resoluções CVM nº 19/2021 e nº 20/2021:</strong> Conteúdo exclusivamente jornalístico e educativo com base em dados públicos da B3 e Banco Central. Não constitui recomendação individualizada nem consultoria de investimentos.
        </p>
      </div>

      {nav_edicoes_html}
      {relacionados_html}
    </article>
  </main>

  <footer class="rodape-portal">
    <div class="container" style="text-align:center; padding:24px 0; font-size:0.85rem; color:var(--texto-secundario);">
      <p>© 2026 CafeRadar. Todos os direitos reservados. <a href="../" style="color:var(--destaque);">Ir para a Página Inicial</a> · <a href="../sobre.html" style="color:var(--destaque);">Sobre Nós</a> · <a href="../calculadora-rendimento.html" style="color:var(--destaque);">Calculadora de Renda</a> · <a href="#" id="link-gerenciar-cookies" class="link-gerenciar-cookies">Gerenciar cookies</a></p>
    </div>
  </footer>
  <!-- Banner informativo de Cookies & Privacidade (LGPD) -->
  <div id="banner-cookies-lgpd" class="banner-cookies-lgpd" role="region" aria-label="Aviso de privacidade e cookies" style="display:none;">
    <div class="banner-cookies-texto">
      Utilizamos cookies e tecnologias semelhantes conforme nossa <a href="/privacy.html">Política de Privacidade</a> para melhorar sua experiência e analisar o tráfego.
    </div>
    <div class="banner-cookies-acoes">
      <button type="button" id="btn-recusar-cookies" class="btn-cookies-recusar">Recusar</button>
      <button type="button" id="btn-aceitar-cookies" class="btn-cookies-aceitar">Entendi</button>
    </div>
  </div>
  <script>
    (function(){{
      try {{
        var ack = localStorage.getItem('caferadar_cookies_ack');
        var banner = document.getElementById('banner-cookies-lgpd');
        var btnAceitar = document.getElementById('btn-aceitar-cookies');
        var btnRecusar = document.getElementById('btn-recusar-cookies');
        var linkGerenciar = document.getElementById('link-gerenciar-cookies');

        if (linkGerenciar) {{
          linkGerenciar.addEventListener('click', function(e) {{
            e.preventDefault();
            try {{ localStorage.removeItem('caferadar_cookies_ack'); }} catch(err){{}}
            if (banner) {{ banner.style.display = 'flex'; }}
          }});
        }}

        if (ack === null && banner) {{ banner.style.display = 'flex'; }}
        if (btnAceitar) {{
          btnAceitar.addEventListener('click', function() {{
            try {{ localStorage.setItem('caferadar_cookies_ack', 'true'); }} catch(e){{}}
            if (typeof gtag === 'function') {{
              gtag('consent', 'update', {{
                'ad_storage': 'granted',
                'analytics_storage': 'granted',
                'ad_user_data': 'granted',
                'ad_personalization': 'granted'
              }});
            }}
            if (banner) banner.style.display = 'none';
          }});
        }}
        if (btnRecusar) {{
          btnRecusar.addEventListener('click', function() {{
            try {{ localStorage.setItem('caferadar_cookies_ack', 'false'); }} catch(e){{}}
            if (typeof gtag === 'function') {{
              gtag('consent', 'update', {{
                'ad_storage': 'denied',
                'analytics_storage': 'denied',
                'ad_user_data': 'denied',
                'ad_personalization': 'denied'
              }});
            }}
            if (banner) banner.style.display = 'none';
          }});
        }}
      }} catch (e) {{}}
    }})();
  </script>
</body>
</html>
"""
    return html

def gerar_pagina_redirect(slug_destino: str, titulo_destino: str, canonical_url: str) -> str:
    """Gera uma página de redirect compatível com navegadores e bots (SEO 301 equivalente estático)."""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Redirecionando... | CafeRadar</title>
  <link rel="canonical" href="{_esc(canonical_url)}">
  <meta http-equiv="refresh" content="0; url={_esc(slug_destino)}">
  <script>window.location.replace({_js_str(slug_destino)});</script>
</head>
<body style="font-family:sans-serif; text-align:center; padding:40px; color:#334155;">
  <p>Esta edição foi movida para o endereço canônico permanente:</p>
  <p><a href="{_esc(slug_destino)}" style="color:#2563eb; font-weight:bold;">{_esc(titulo_destino)}</a></p>
  <p style="font-size:0.85rem; color:#64748b;">Redirecionando automaticamente...</p>
  <!-- Banner informativo de Cookies & Privacidade (LGPD) -->
  <div id="banner-cookies-lgpd" class="banner-cookies-lgpd" role="region" aria-label="Aviso de privacidade e cookies" style="display:none;">
    <div class="banner-cookies-texto">
      Utilizamos cookies e tecnologias semelhantes conforme nossa <a href="/privacy.html">Política de Privacidade</a> para melhorar sua experiência e analisar o tráfego.
    </div>
    <div class="banner-cookies-acoes">
      <button type="button" id="btn-recusar-cookies" class="btn-cookies-recusar">Recusar</button>
      <button type="button" id="btn-aceitar-cookies" class="btn-cookies-aceitar">Entendi</button>
    </div>
  </div>
  <script>
    (function(){{
      try {{
        var ack = localStorage.getItem('caferadar_cookies_ack');
        var banner = document.getElementById('banner-cookies-lgpd');
        var btnAceitar = document.getElementById('btn-aceitar-cookies');
        var btnRecusar = document.getElementById('btn-recusar-cookies');
        var linkGerenciar = document.getElementById('link-gerenciar-cookies');

        if (linkGerenciar) {{
          linkGerenciar.addEventListener('click', function(e) {{
            e.preventDefault();
            try {{ localStorage.removeItem('caferadar_cookies_ack'); }} catch(err){{}}
            if (banner) {{ banner.style.display = 'flex'; }}
          }});
        }}

        if (ack === null && banner) {{ banner.style.display = 'flex'; }}
        if (btnAceitar) {{
          btnAceitar.addEventListener('click', function() {{
            try {{ localStorage.setItem('caferadar_cookies_ack', 'true'); }} catch(e){{}}
            if (typeof gtag === 'function') {{
              gtag('consent', 'update', {{
                'ad_storage': 'granted',
                'analytics_storage': 'granted',
                'ad_user_data': 'granted',
                'ad_personalization': 'granted'
              }});
            }}
            if (banner) banner.style.display = 'none';
          }});
        }}
        if (btnRecusar) {{
          btnRecusar.addEventListener('click', function() {{
            try {{ localStorage.setItem('caferadar_cookies_ack', 'false'); }} catch(e){{}}
            if (typeof gtag === 'function') {{
              gtag('consent', 'update', {{
                'ad_storage': 'denied',
                'analytics_storage': 'denied',
                'ad_user_data': 'denied',
                'ad_personalization': 'denied'
              }});
            }}
            if (banner) banner.style.display = 'none';
          }});
        }}
      }} catch (e) {{}}
    }})();
  </script>
</body>
</html>
"""

def extrair_metadados_edicao_html(arq_path: Path) -> dict | None:
    """Extrai metadados completos de um arquivo HTML existente."""
    m_nome = re.match(r"^(\d{4}-\d{2}-\d{2})-([a-z0-9_]+)\.html$", arq_path.name)
    if not m_nome:
        return None
    data_ref = m_nome.group(1)
    ed_key = m_nome.group(2)

    try:
        html = arq_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    # Se for página de redirect prévia, pula para não duplicar no índice
    if "Redirecionando..." in html and 'http-equiv="refresh"' in html:
        return None

    m_h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.DOTALL)
    all_h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", html, flags=re.DOTALL)
    titulo = all_h1[-1].strip() if all_h1 else arq_path.stem

    m_time = re.search(r"<time[^>]*>(.*?)</time>", html, flags=re.DOTALL)
    time_txt = m_time.group(1).strip() if m_time else data_ref
    if " às " in time_txt:
        data_fmt, horario = [x.strip() for x in time_txt.split(" às ", 1)]
    else:
        partes_dt = data_ref.split("-")
        data_fmt = f"{partes_dt[2]}/{partes_dt[1]}/{partes_dt[0]}" if len(partes_dt) == 3 else data_ref
        horario = ""

    m_badge = re.search(r"text-transform:uppercase;\">(.*?)</span>", html)
    nome_badge = m_badge.group(1).strip() if m_badge else ed_key.capitalize()

    slug_canonico = normalizar_chave_edicao(ed_key, titulo)
    ordem_ed = MAPA_SLUGS_CANONICOS.get(slug_canonico, {}).get("ordem", 0)

    # Extração de dados internos para permitir reconstrução fiel com template v2
    subtitulo_m = re.search(r"<h1[^>]*>.*?</h1>\s*<p[^>]*>(.*?)</p>", html, flags=re.DOTALL)
    subtitulo = subtitulo_m.group(1).strip() if subtitulo_m else ""

    # Extrai bullets da síntese
    bullets = []
    ul_m = re.search(r"<ul[^>]*>(.*?)</ul>", html, flags=re.DOTALL)
    if ul_m:
        for li_m in re.finditer(r"<li[^>]*>(.*?)</li>", ul_m.group(1), flags=re.DOTALL):
            li_txt = re.sub(r"<[^>]+>", "", li_m.group(1)).strip()
            if li_txt:
                bullets.append({"texto": li_txt, "fonte": ""})

    return {
        "id": ed_key,
        "slug_canonico": slug_canonico,
        "nome": nome_badge,
        "horario": horario,
        "titulo": titulo,
        "subtitulo": subtitulo,
        "data_ref": data_ref,
        "data_fmt": data_fmt,
        "arquivo": arq_path.name,
        "raw_html": html,
        "bullets": bullets,
        "sort_key": (data_ref, ordem_ed, horario)
    }

def atualizar_sitemap_edicoes(novas_edicoes_urls: list[dict], bases: list[Path] | None = None, data_hoje: str = ""):
    target_bases = bases if bases is not None else _detectar_bases_acervo()
    for base in target_bases:
        sm_file = base / "sitemap.xml"
        if not sm_file.is_file():
            continue

        with open(sm_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Atualiza lastmod da Home e de /edicoes/
        if data_hoje:
            content = re.sub(
                r"(<loc>https://caferadar\.com\.br/</loc>\s*<lastmod>)[^<]+(</lastmod>)",
                rf"\g<1>{data_hoje}\g<2>",
                content
            )
            content = re.sub(
                r"(<loc>https://caferadar\.com\.br/edicoes/</loc>\s*<lastmod>)[^<]+(</lastmod>)",
                rf"\g<1>{data_hoje}\g<2>",
                content
            )

                # Remove URLs de stubs / redirects legados e páginas sem captura legítima
        content = re.sub(
            r"\s*<url>\s*<loc>https://caferadar\.com\.br/edicoes/2026-11-09-matinal\.html</loc>[\s\S]*?</url>",
            "",
            content
        )
        # Remove URLs de stubs / redirects legados do sitemap
        content = re.sub(
            r"\s*<url>\s*<loc>https://caferadar\.com\.br/edicoes/[^<]+-(?:almoco|negocios)\.html</loc>[\s\S]*?</url>",
            "",
            content
        )

        # Inserção de novas URLs canônicas
        for item in novas_edicoes_urls:
            url = item["url"]
            lastmod = item["lastmod"]
            if url not in content:
                prio = "0.7" if lastmod == data_hoje else "0.5"
                entry = f"""  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <priority>{prio}</priority>
  </url>
</urlset>"""
                content = content.replace("</urlset>", entry)

        # Reajuste de prioridades nas edições: 0.7 para data_hoje, 0.5 para passadas
        if data_hoje:
            def ajustar_prioridade_url(m):
                bloco = m.group(0)
                if "/edicoes/" in bloco and "index.html" not in bloco and "<loc>https://caferadar.com.br/edicoes/</loc>" not in bloco:
                    if f"<lastmod>{data_hoje}</lastmod>" in bloco:
                        bloco = re.sub(r"<priority>[^<]+</priority>", "<priority>0.7</priority>", bloco)
                    else:
                        bloco = re.sub(r"<priority>[^<]+</priority>", "<priority>0.5</priority>", bloco)
                return bloco

            content = re.sub(r"<url>[\s\S]*?</url>", ajustar_prioridade_url, content)

        with open(sm_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Sitemap atualizado com sucesso em {sm_file}")

def gerar_todas_edicoes(include_deploy: bool = False):
    novas_urls_sitemap = []
    target_bases = _detectar_bases_acervo(include_deploy)
    # target_bases já inclui web_deploy quando include_deploy=True

    for base in target_bases:
        edicoes_dir = base / "edicoes"
        edicoes_dir.mkdir(parents=True, exist_ok=True)

        fech_file = base / "data" / "fechamento.json"
        if not fech_file.is_file():
            continue

        with open(fech_file, "r", encoding="utf-8") as f:
            dados = json.load(f)

        data_ref = dados.get("data_referencia", datetime.now(TZ_SP).strftime("%Y-%m-%d"))
        data_fmt = dados.get("data_formatada", datetime.now(TZ_SP).strftime("%d/%m/%Y"))
        edicoes_dict = dados.get("edicoes", {})

        # 1. Coletar TODAS as edições existentes no diretório
        arquivos_acervo = []
        for arq in edicoes_dir.glob("*.html"):
            if arq.name == "index.html":
                continue
            meta = extrair_metadados_edicao_html(arq)
            if meta:
                arquivos_acervo.append(meta)

        arquivos_acervo.sort(key=lambda x: x["sort_key"], reverse=True)

        # 2. Gerar edições canônicas do dia de hoje a partir de fechamento.json
        # Mapeamos as chaves do json para os slugs canônicos
        mapa_chaves_json = {
            "abertura": "matinal",
            "almoco": "abertura",
            "negocios": "abertura",
            "fechamento": "fechamento"
        }

        edicoes_geradas_hoje = {}
        for k_json, ed_dados in edicoes_dict.items():
            if not ed_dados.get("disponivel", False):
                continue
            slug_canonico = mapa_chaves_json.get(k_json, k_json)
            # Evita duplicar se 'almoco' e 'negocios' ambos existirem
            if slug_canonico in edicoes_geradas_hoje:
                continue

            edicoes_geradas_hoje[slug_canonico] = ed_dados

        for slug_canonico, ed_dados in edicoes_geradas_hoje.items():
            nome_arq = f"{data_ref}-{slug_canonico}.html"
            
            # Localiza anteriores e próximas
            ant = None
            prox = None
            # Lista de navegação exclui edições sem captura legítima
            acervo_nav = [x for x in arquivos_acervo if x["arquivo"] != "2026-11-09-matinal.html"]
            for idx, item in enumerate(acervo_nav):
                if item["arquivo"] == nome_arq:
                    if idx + 1 < len(acervo_nav):
                        ant = acervo_nav[idx + 1]
                    if idx > 0:
                        prox = acervo_nav[idx - 1]
                    break

            # Matérias relacionadas: 3 mais recentes diferentes da atual
            relacionados = [x for x in arquivos_acervo if x["arquivo"] != nome_arq][:3]

            out_file = edicoes_dir / nome_arq
            dt_pub = None
            dt_mod = None
            if out_file.is_file():
                try:
                    conteudo_antigo_html = out_file.read_text(encoding="utf-8")
                    m_dp = re.search(r'"datePublished":\s*"([^"]+)"', conteudo_antigo_html)
                    m_dm = re.search(r'"dateModified":\s*"([^"]+)"', conteudo_antigo_html)
                    if m_dp:
                        dt_pub = m_dp.group(1)
                    if m_dm:
                        dt_mod = m_dm.group(1)
                    
                    # Detecta se houve alteração real no conteúdo analítico
                    # Comparando valores de mercado_geral e subtitulo
                    mg_antigos = re.findall(r'font-size:1\.25rem[^>]*>(.*?)</div>', conteudo_antigo_html)
                    mg_novos = []
                    for k_mg in ["ibov", "dolar", "sp500", "bitcoin", "brent"]:
                        if k_mg in ed_dados.get("mercado_geral", {}):
                            item_mg = ed_dados["mercado_geral"][k_mg]
                            mg_novos.append(str(item_mg.get("pontos") or item_mg.get("valor") or ""))
                    
                    subt_antigo = ""
                    m_subt = re.search(r'<h1[^>]*>.*?</h1>\s*<p[^>]*>(.*?)</p>', conteudo_antigo_html, flags=re.DOTALL)
                    if m_subt:
                        subt_antigo = m_subt.group(1).strip()
                    subt_novo = ed_dados.get("subtitulo", "").strip()

                    conteudo_mudou = (mg_antigos != mg_novos) or (subt_antigo != subt_novo)
                    if conteudo_mudou:
                        dt_mod = datetime.now(TZ_SP).strftime("%Y-%m-%dT%H:%M:%S-03:00")
                except Exception:
                    pass

            html_content = gerar_pagina_edicao(
                ed_dados,
                data_ref,
                data_fmt,
                slug_canonico,
                base,
                anterior=ant,
                proxima=prox,
                relacionados=relacionados,
                data_publicada=dt_pub,
                data_modificada=dt_mod
            )
            with open(out_file, "w", encoding="utf-8") as out:
                out.write(html_content)
            print(f"[OK] Edição canônica gerada: {out_file.name}")

            url_canonica = f"https://caferadar.com.br/edicoes/{nome_arq}"
            if not ed_dados.get("sem_captura_legitima", False):
                if not any(x["url"] == url_canonica for x in novas_urls_sitemap):
                    novas_urls_sitemap.append({"url": url_canonica, "lastmod": data_ref})

        # 3. Geração de redirects de compatibilidade para URLs legadas (-almoco.html, -negocios.html)
        # Para todos os dias presentes no acervo, se houver -almoco.html, ele deve redirecionar para -abertura.html
        for arq in list(edicoes_dir.glob("*-almoco.html")):
            d_ref = arq.name.split("-almoco.html")[0]
            alvo = f"{d_ref}-abertura.html"
            canon = f"https://caferadar.com.br/edicoes/{alvo}"
            redirect_html = gerar_pagina_redirect(alvo, f"Abertura B3 — {d_ref}", canon)
            with open(arq, "w", encoding="utf-8") as f_red:
                f_red.write(redirect_html)
            print(f"[REDIRECT] URL Legada redirecionada: {arq.name} -> {alvo}")

        for arq in list(edicoes_dir.glob("*-negocios.html")):
            d_ref = arq.name.split("-negocios.html")[0]
            alvo = f"{d_ref}-abertura.html"
            canon = f"https://caferadar.com.br/edicoes/{alvo}"
            redirect_html = gerar_pagina_redirect(alvo, f"Abertura B3 — {d_ref}", canon)
            with open(arq, "w", encoding="utf-8") as f_red:
                f_red.write(redirect_html)
            print(f"[REDIRECT] URL Legada redirecionada: {arq.name} -> {alvo}")

        # 4. Retroaplicação do template v2 em edições antigas que não tinham imagem/schema v2
        # Re-coleta todos os arquivos canônicos
        arquivos_acervo = []
        for arq in edicoes_dir.glob("*.html"):
            if arq.name == "index.html":
                continue
            meta = extrair_metadados_edicao_html(arq)
            if meta:
                arquivos_acervo.append(meta)
        arquivos_acervo.sort(key=lambda x: x["sort_key"], reverse=True)

        for meta in arquivos_acervo:
            arq_path = edicoes_dir / meta["arquivo"]
            conteudo_antigo = meta["raw_html"]
            # Se já tem o novo header v2 com BreadcrumbList e imagem, pula
            if 'BreadcrumbList' in conteudo_antigo and '<figure' in conteudo_antigo and 'fetchpriority="high"' in conteudo_antigo:
                continue

            # Retroaplica template enriquecido
            slug_c = meta["slug_canonico"]
            img_retro = obter_imagem_edicao(meta["data_ref"], slug_c, base)
            
            # Injeta Consent Mode v2 se faltar
            if "gtag('consent', 'default'" not in conteudo_antigo:
                snippet_consent = """  <!-- Google Consent Mode v2 -->
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('consent', 'default', {
      'ad_storage': 'denied',
      'analytics_storage': 'denied',
      'ad_user_data': 'denied',
      'ad_personalization': 'denied',
      'wait_for_update': 500
    });
    gtag('js', new Date());
    gtag('config', 'G-50J887FJDV');
  </script>
"""
                conteudo_antigo = conteudo_antigo.replace('<script async src="https://www.googletagmanager.com', snippet_consent + '  <script async src="https://www.googletagmanager.com')

            # Injeta preloads de CSS e fontes
            if 'rel="preload" href="../style.css"' not in conteudo_antigo:
                conteudo_antigo = conteudo_antigo.replace('<link rel="stylesheet" href="../style.css">', '<link rel="preload" href="../style.css" as="style">\n  <link rel="stylesheet" href="../style.css">')

            # Corrige link de retorno do topo para './'
            conteudo_antigo = conteudo_antigo.replace('href="index.html" style="color:var(--destaque)', 'href="./" style="color:var(--destaque)')

            # Injeta figura hero com imagem específica se não houver tag <figure
            if '<figure' not in conteudo_antigo:
                hero_tag = f"""      <!-- Imagem Hero 1200x675 (Elegibilidade Discover e CTR Social) -->
      <figure style="margin:0 0 24px; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0; background:#0f172a;">
        <img src="{_esc(img_retro)}" alt="{_esc(meta['titulo'])}" width="1200" height="675" fetchpriority="high" loading="eager" style="width:100%; height:auto; display:block; aspect-ratio:16/9; object-fit:cover;">
      </figure>
"""
                # Insere logo após o parágrafo de subtítulo
                conteudo_antigo = re.sub(
                    r"(<h1[^>]*>.*?</h1>\s*<p[^>]*>.*?</p>)",
                    rf"\g<1>\n{hero_tag}",
                    conteudo_antigo,
                    flags=re.DOTALL
                )

            # Injeta campo image no NewsArticle
            if '"image":' not in conteudo_antigo and '"@type": "NewsArticle"' in conteudo_antigo:
                conteudo_antigo = conteudo_antigo.replace(
                    '"@type": "NewsArticle",',
                    f'"@type": "NewsArticle",\n    "image": [\n      {_js_str(img_retro)}\n    ],'
                )

            # Injeta BreadcrumbList
            if 'BreadcrumbList' not in conteudo_antigo:
                breadcrumb_tag = f"""
  <!-- Schema.org BreadcrumbList -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{
        "@type": "ListItem",
        "position": 1,
        "name": "Página Inicial",
        "item": "https://caferadar.com.br/"
      }},
      {{
        "@type": "ListItem",
        "position": 2,
        "name": "Acervo de Edições",
        "item": "https://caferadar.com.br/edicoes/"
      }},
      {{
        "@type": "ListItem",
        "position": 3,
        "name": {_js_str(f"{meta['nome']} — {meta['data_fmt']}")},
        "item": {_js_str(f"https://caferadar.com.br/edicoes/{meta['arquivo']}")}
      }}
    ]
  }}
  </script>
"""
                conteudo_antigo = conteudo_antigo.replace('</head>', f'{breadcrumb_tag}\n</head>')

            with open(arq_path, "w", encoding="utf-8") as f_mod:
                f_mod.write(conteudo_antigo)
            print(f"[RETROFIT v2] Template atualizado: {meta['arquivo']}")

        # 5. Re-coletar para gerar o Acervo Geral (/edicoes/index.html)
        arquivos_acervo = []
        for arq in edicoes_dir.glob("*.html"):
            if arq.name == "index.html":
                continue
            meta = extrair_metadados_edicao_html(arq)
            if meta:
                arquivos_acervo.append(meta)
        arquivos_acervo.sort(key=lambda x: x["sort_key"], reverse=True)

        itens_acervo_html = ""
        for item in arquivos_acervo:
            horario_str = f" às {item['horario']}" if item['horario'] else ""
            itens_acervo_html += f"""
            <a href="{_esc(item['arquivo'])}" style="display:block; text-decoration:none; background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:20px; margin-bottom:14px; transition:all 0.15s ease;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="background:var(--destaque); color:#fff; font-size:0.75rem; font-weight:800; padding:2px 8px; border-radius:9999px;">{_esc(item['nome'])}</span>
                <span style="font-size:0.85rem; color:#64748b; font-weight:600;">{_esc(item['data_fmt'])}{_esc(horario_str)}</span>
              </div>
              <h2 style="font-size:1.15rem; color:#0f172a; font-weight:800; margin:0 0 6px;">{_esc(item['titulo'])}</h2>
              <span style="color:#2563eb; font-size:0.88rem; font-weight:700;">Ler edição completa com destaques da B3 →</span>
            </a>
            """

        index_acervo = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Acervo Histórico de Edições do Pregão B3 | CafeRadar B3</title>
  <meta name="description" content="Arquivo permanente com todas as edições diárias (Café Matinal, Abertura B3 e Fechamento) do CafeRadar. Dados históricos oficiais do pregão da B3.">
  <link rel="canonical" href="https://caferadar.com.br/edicoes/">
  
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="preload" href="../style.css" as="style">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../style.css">

  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" href="../apple-touch-icon.png">
  <link rel="apple-touch-icon" href="../apple-touch-icon.png">

  <meta property="og:site_name" content="CafeRadar">
  <meta property="og:title" content="Acervo Histórico de Edições do Pregão B3 | CafeRadar B3">
  <meta property="og:description" content="Arquivo permanente com todas as edições diárias do CafeRadar. Dados históricos oficiais do pregão da B3.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://caferadar.com.br/edicoes/">
  <meta property="og:image" content="https://caferadar.com.br/og-image.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Acervo Histórico de Edições do Pregão B3 | CafeRadar B3">
  <meta name="twitter:description" content="Arquivo permanente com todas as edições diárias do CafeRadar. Dados históricos oficiais do pregão da B3.">
  <meta name="twitter:image" content="https://caferadar.com.br/og-image.png">

  <!-- Google Consent Mode v2 -->
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('consent', 'default', {{
      'ad_storage': 'denied',
      'analytics_storage': 'denied',
      'ad_user_data': 'denied',
      'ad_personalization': 'denied',
      'wait_for_update': 500
    }});
    try {{
      if (localStorage.getItem('caferadar_cookies_ack') === 'true') {{
        gtag('consent', 'update', {{
          'ad_storage': 'granted',
          'analytics_storage': 'granted',
          'ad_user_data': 'granted',
          'ad_personalization': 'granted'
        }});
      }}
    }} catch (e) {{}}
    gtag('js', new Date());
    gtag('config', 'G-50J887FJDV');
  </script>
  <!-- Google Analytics 4 (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-50J887FJDV"></script>
</head>
<body>
  <header class="cabecalho-portal">
    <div class="container container-header">
      <div class="marca-portal">
        <a href="../" style="text-decoration:none; display:flex; align-items:center; gap:12px;">
          <div class="logo-icone">CR</div>
          <div>
            <div class="portal-titulo">CAFERADAR</div>
            <p class="portal-slogan">Acervo de Mercado B3</p>
          </div>
        </a>
      </div>
      <div class="status-topo">
        <a href="../" class="btn-tab ativa" style="text-decoration:none; border:1px solid var(--borda); border-radius:9999px; padding:6px 14px;">
          <span>← Voltar ao Portal ao Vivo</span>
        </a>
      </div>
    </div>
  </header>

  <main class="container" style="max-width:860px; margin:32px auto 60px;">
    <h1 style="font-size:1.6rem; color:var(--primaria); font-weight:800; margin-bottom:8px;">📚 Acervo Permanente de Edições</h1>
    <p style="font-size:0.95rem; color:var(--texto-secundario); margin-bottom:28px;">
      Consulte o histórico de todas as sínteses do pregão diário publicadas pelo CafeRadar, com cotações preservadas, blue chips e destaques da B3.
    </p>

    <div class="lista-edicoes-acervo">
      {itens_acervo_html}
    </div>
  </main>
  <!-- Banner informativo de Cookies & Privacidade (LGPD) -->
  <div id="banner-cookies-lgpd" class="banner-cookies-lgpd" role="region" aria-label="Aviso de privacidade e cookies" style="display:none;">
    <div class="banner-cookies-texto">
      Utilizamos cookies e tecnologias semelhantes conforme nossa <a href="/privacy.html">Política de Privacidade</a> para melhorar sua experiência e analisar o tráfego.
    </div>
    <div class="banner-cookies-acoes">
      <button type="button" id="btn-recusar-cookies" class="btn-cookies-recusar">Recusar</button>
      <button type="button" id="btn-aceitar-cookies" class="btn-cookies-aceitar">Entendi</button>
    </div>
  </div>
  <script>
    (function(){{
      try {{
        var ack = localStorage.getItem('caferadar_cookies_ack');
        var banner = document.getElementById('banner-cookies-lgpd');
        var btnAceitar = document.getElementById('btn-aceitar-cookies');
        var btnRecusar = document.getElementById('btn-recusar-cookies');
        var linkGerenciar = document.getElementById('link-gerenciar-cookies');

        if (linkGerenciar) {{
          linkGerenciar.addEventListener('click', function(e) {{
            e.preventDefault();
            try {{ localStorage.removeItem('caferadar_cookies_ack'); }} catch(err){{}}
            if (banner) {{ banner.style.display = 'flex'; }}
          }});
        }}

        if (ack === null && banner) {{ banner.style.display = 'flex'; }}
        if (btnAceitar) {{
          btnAceitar.addEventListener('click', function() {{
            try {{ localStorage.setItem('caferadar_cookies_ack', 'true'); }} catch(e){{}}
            if (typeof gtag === 'function') {{
              gtag('consent', 'update', {{
                'ad_storage': 'granted',
                'analytics_storage': 'granted',
                'ad_user_data': 'granted',
                'ad_personalization': 'granted'
              }});
            }}
            if (banner) banner.style.display = 'none';
          }});
        }}
        if (btnRecusar) {{
          btnRecusar.addEventListener('click', function() {{
            try {{ localStorage.setItem('caferadar_cookies_ack', 'false'); }} catch(e){{}}
            if (typeof gtag === 'function') {{
              gtag('consent', 'update', {{
                'ad_storage': 'denied',
                'analytics_storage': 'denied',
                'ad_user_data': 'denied',
                'ad_personalization': 'denied'
              }});
            }}
            if (banner) banner.style.display = 'none';
          }});
        }}
      }} catch (e) {{}}
    }})();
  </script>
</body>
</html>
"""
        with open(edicoes_dir / "index.html", "w", encoding="utf-8") as f_idx:
            f_idx.write(index_acervo)
        print(f"[OK] Acervo index gerado: {edicoes_dir / 'index.html'}")

    if novas_urls_sitemap:
        atualizar_sitemap_edicoes(novas_urls_sitemap, bases=target_bases, data_hoje=data_ref)

if __name__ == "__main__":
    import sys
    inc_deploy = "--include-deploy" in sys.argv
    gerar_todas_edicoes(include_deploy=inc_deploy)
