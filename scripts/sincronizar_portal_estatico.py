#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sincronizador estático do index.html do CafeRadar (fita de cotações,
cabeçalho, 5 cards de mercado e imagem hero da edição ativa).
Funciona tanto no repositório local (web/) quanto em nuvem (web_deploy/scripts/).
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _parse_capturado_em_info(ed: dict) -> tuple[datetime | None, str, str]:
    """Extrai (datetime em America/Sao_Paulo, DD/MM, DD/MM/YYYY) exclusivamente de capturado_em."""
    if not isinstance(ed, dict):
        return None, "", ""
    cap = ed.get("capturado_em")
    if not isinstance(cap, str) or not cap.strip():
        return None, "", ""
    raw = cap.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None, "", ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_SP)
    else:
        dt = dt.astimezone(TZ_SP)
    return dt, dt.strftime("%d/%m"), dt.strftime("%d/%m/%Y")


def _formatar_data_br_texto(valor: str | None) -> str:
    if not isinstance(valor, str) or not valor.strip():
        return ""
    s = valor.strip()
    m_iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m_iso:
        return f"{m_iso.group(3)}/{m_iso.group(2)}/{m_iso.group(1)}"
    m_br = re.match(r"^(\d{2}/\d{2}/\d{4})$", s)
    if m_br:
        return m_br.group(1)
    return ""


def _extrair_data_br_edicao(ed: dict, dados: dict) -> str:
    _, _, data_cap_br = _parse_capturado_em_info(ed)
    if data_cap_br:
        return data_cap_br
    for cand in (
        ed.get("data_referencia") if isinstance(ed, dict) else None,
        dados.get("data_referencia") if isinstance(dados, dict) else None,
        ed.get("data_formatada") if isinstance(ed, dict) else None,
        dados.get("data_formatada") if isinstance(dados, dict) else None,
        dados.get("data") if isinstance(dados, dict) else None,
    ):
        fmt = _formatar_data_br_texto(cand)
        if fmt:
            return fmt
    return ""


def _montar_itens_fita_estatica(ed: dict) -> list[dict]:
    """Constrói os itens da fita estática a partir de mercado_geral de uma edição."""
    mg = ed.get("mercado_geral") if isinstance(ed, dict) else None
    if not isinstance(mg, dict):
        return []
    especificacao = [
        ("ibov", "IBOV", ("pontos", "valor")),
        ("dolar", "DÓLAR", ("valor",)),
        ("sp500", "S&P 500", ("valor", "pontos")),
        ("bitcoin", "BTC", ("valor",)),
        ("brent", "BRENT", ("valor",)),
    ]
    itens = []
    for key, ticker, campos_val in especificacao:
        obj = mg.get(key)
        if not isinstance(obj, dict):
            continue
        preco = ""
        for campo in campos_val:
            v = obj.get(campo)
            if isinstance(v, str) and v.strip():
                preco = v.strip()
                break
        if not preco or preco.lower() in ("indisponível", "indisponivel", "—", "-"):
            continue
        var_txt = str(obj.get("variacao") or "").strip()
        pos = obj.get("positivo")
        itens.append({
            "ticker": ticker,
            "preco": preco,
            "variacao": var_txt,
            "positivo": pos if isinstance(pos, bool) else None,
        })
    return itens


def _selecionar_edicao_fita_estatica(dados: dict) -> tuple[str, dict, str, list[dict]] | None:
    """
    Seleciona a edição elegível mais recente (por capturado_em) para alimentar a fita estática.
    Ignora edições indisponíveis, marcadas com sem_captura_legitima ou sem capturado_em válido.
    """
    edicoes = dados.get("edicoes") if isinstance(dados, dict) else None
    if not isinstance(edicoes, dict):
        return None
    pesos = {"fechamento": 4, "negocios": 3, "almoco": 2, "abertura": 1}
    candidatos = []
    for ed_k in ("fechamento", "negocios", "almoco", "abertura"):
        ed = edicoes.get(ed_k)
        if not isinstance(ed, dict):
            continue
        if ed.get("disponivel") is False or ed.get("sem_captura_legitima") is True:
            continue
        dt_cap, dd_mm, _ = _parse_capturado_em_info(ed)
        if dt_cap is None or not dd_mm:
            continue
        itens = _montar_itens_fita_estatica(ed)
        if not itens:
            continue
        candidatos.append((dt_cap, pesos[ed_k], ed_k, ed, dd_mm, itens))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: (c[0], c[1]), reverse=True)
    _, _, ed_k, ed, dd_mm, itens = candidatos[0]
    return ed_k, ed, dd_mm, itens


def _formatar_rotulo_fita(ed_k: str, dd_mm: str) -> str:
    nomes_fita = {
        "fechamento": "fechamento",
        "negocios": "abertura B3",
        "almoco": "abertura B3",
        "abertura": "matinal",
    }
    nome = nomes_fita.get(ed_k, ed_k)
    return f"({nome} {dd_mm})" if dd_mm else f"({nome})"


def _render_item_fita_estatica(item: dict, aria_hidden: bool = False) -> str:
    pos = item.get("positivo")
    cls_pos = "positivo" if pos is True else ("negativo" if pos is False else "")
    seta = "▲" if pos is True else ("▼" if pos is False else "")
    var_txt = item.get("variacao") or ""
    var_exib = f"{seta} {var_txt}".strip() if var_txt and var_txt != "—" else ""
    cls_attr = f"fita-var {cls_pos}".strip()
    hidden_attr = ' aria-hidden="true"' if aria_hidden else ""
    return (
        f'        <span class="fita-item"{hidden_attr}>'
        f'<span class="fita-ticker">{escape(item["ticker"])}</span> '
        f'<span class="fita-preco">{escape(item["preco"])}</span> '
        f'<span class="{cls_attr}">{escape(var_exib)}</span>'
        f"</span>"
    )


def _resolver_card_tipo_hero(ed_ativa_k: str | None, ed: dict) -> str:
    """Mapeia edição ativa para o sufixo do arquivo *_x.png compatível com app.js."""
    id_ou_nome = f"{ed.get('id') or ''} {ed.get('nome') or ''}".lower()
    if "matinal" in id_ou_nome or "mapa" in id_ou_nome or ed_ativa_k == "abertura":
        return "abertura"
    if "negocios" in id_ou_nome or "abertura b3" in id_ou_nome or "almoco" in id_ou_nome or ed_ativa_k in ("negocios", "almoco"):
        return "negocios"
    return "fechamento"


def sincronizar_index_html_estatico(dados: dict, base_dir: Path):
    """
    Reconstrói os valores estáticos de index.html a cada execução de edição,
    incluindo fita de cotações com data real extraída de capturado_em e imagem hero.
    """
    idx_path = base_dir / "index.html"
    if not idx_path.is_file():
        return

    raw_bytes = idx_path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw_bytes else "\n"
    html = raw_bytes.decode("utf-8").replace("\r\n", "\n")

    sel_fita = _selecionar_edicao_fita_estatica(dados)
    edicoes = dados.get("edicoes", {}) if isinstance(dados, dict) else {}
    candidatos_ed_k = []
    for k in (dados.get("edicao_padrao"), dados.get("edicao_ativa"), "fechamento", "negocios", "almoco", "abertura"):
        if isinstance(k, str) and k and k not in candidatos_ed_k:
            candidatos_ed_k.append(k)

    ed_ativa_k = None
    ed = {}
    for k in candidatos_ed_k:
        cand = edicoes.get(k)
        if not cand and k == "negocios":
            cand = edicoes.get("almoco")
        if (
            isinstance(cand, dict)
            and cand.get("disponivel") is not False
            and cand.get("sem_captura_legitima") is not True
            and cand.get("mercado_geral")
        ):
            ed_ativa_k = k
            ed = cand
            break
    if not ed and sel_fita is not None:
        ed_ativa_k, ed, _, _ = sel_fita
    elif sel_fita is not None and ed_ativa_k != sel_fita[0]:
        dt_cur, _, _ = _parse_capturado_em_info(ed)
        dt_sel, _, _ = _parse_capturado_em_info(sel_fita[1])
        if dt_sel is not None and (dt_cur is None or dt_sel > dt_cur):
            ed_ativa_k, ed, _, _ = sel_fita

    if ed:
        data_fmt = _extrair_data_br_edicao(ed, dados) or datetime.now(TZ_SP).strftime("%d/%m/%Y")
        hora = ed.get("horario_exibicao") or ed.get("horario", "18h15")
        nome = ed.get("nome", "Fechamento")
        txt_atualizacao = f"Edição de {data_fmt} às {hora} ({nome})"
        titulo = ed.get("titulo") or ""
        subtitulo = ed.get("subtitulo") or ""

        # 1. Atualização do cabeçalho da notícia
        html = re.sub(
            r'<span class="horario-tag" id="fechamento-atualizacao">[^<]*</span>',
            lambda _: f'<span class="horario-tag" id="fechamento-atualizacao">{escape(txt_atualizacao)}</span>',
            html,
        )
        if titulo:
            html = re.sub(
                r'<h2 class="titulo-destaque-fechamento" id="fechamento-titulo">[^<]*</h2>',
                lambda _: f'<h2 class="titulo-destaque-fechamento" id="fechamento-titulo">{escape(str(titulo))}</h2>',
                html,
            )
        if subtitulo:
            html = re.sub(
                r'<p class="subtitulo-destaque-fechamento" id="fechamento-subtitulo">[^<]*</p>',
                lambda _: f'<p class="subtitulo-destaque-fechamento" id="fechamento-subtitulo">{escape(str(subtitulo))}</p>',
                html,
            )

        # 1.1 Atualização do src da imagem hero estática quando o card existir no disco
        data_ref_iso = str(ed.get("data_referencia") or dados.get("data_referencia") or "").strip()[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", data_ref_iso):
            card_tipo = _resolver_card_tipo_hero(ed_ativa_k, ed)
            card_nome = f"{data_ref_iso}_{card_tipo}_x.png"
            if (base_dir / "marketing_output" / card_nome).is_file():
                html = re.sub(
                    r'(<img\b[^>]*\bid="fechamento-hero-img"[^>]*\bsrc=")[^"]*(")',
                    lambda m: f'{m.group(1)}marketing_output/{card_nome}{m.group(2)}',
                    html,
                    count=1,
                )

        # 2. Atualização dos 5 tickers estáticos da edição ativa
        mg = ed.get("mercado_geral", {})
        tickers_cards = []
        ordem_tickers = ["ibov", "dolar", "sp500", "bitcoin", "brent"]
        for k in ordem_tickers:
            if isinstance(mg, dict) and k in mg and isinstance(mg[k], dict):
                item = mg[k]
                t_nome = str(item.get("nome", k.upper()))
                t_val = str(item.get("pontos") or item.get("valor") or "—")
                t_var = str(item.get("variacao") or "—")
                t_pos = item.get("positivo", True)
                cor = "var(--alta)" if t_pos else "var(--baixa)"
                sinal = "▲ " if t_pos else "▼ "
                if t_var.startswith("+") or t_var.startswith("-"):
                    var_txt = f"{sinal}{t_var}"
                else:
                    var_txt = t_var
                tickers_cards.append(f"""        <div class="card-ticker-mercado">
          <div class="ticker-nome">{escape(t_nome)}</div>
          <div class="ticker-valor">{escape(t_val)}</div>
          <div class="ticker-variacao" style="color:{cor};">{escape(var_txt)}</div>
        </div>""")

        if tickers_cards:
            bloco_tickers = "\n".join(tickers_cards)
            html = re.sub(
                r'<div class="grid-tickers-fechamento" id="cards-mercado-fechamento">.*?</div>\s*<!-- Leitura Rápida',
                lambda _: f'<div class="grid-tickers-fechamento" id="cards-mercado-fechamento">\n{bloco_tickers}\n      </div>\n\n      <!-- Leitura Rápida',
                html,
                flags=re.DOTALL,
            )

    # 3. Atualização da fita de cotações estática com base no capturado_em real
    if sel_fita is not None:
        fita_ed_k, _, dd_mm_fita, itens_fita = sel_fita
        rotulo_fita = _formatar_rotulo_fita(fita_ed_k, dd_mm_fita)
        linhas_fita = [_render_item_fita_estatica(it, False) for it in itens_fita]
        linhas_fita.extend(_render_item_fita_estatica(it, True) for it in itens_fita)
        bloco_fita = "\n".join(linhas_fita)

        html = re.sub(
            r'<span class="fita-delay-aviso" id="fita-referencia">[^<]*</span>',
            lambda _: f'<span class="fita-delay-aviso" id="fita-referencia">{escape(rotulo_fita)}</span>',
            html,
            count=1,
        )
        html = re.sub(
            r'(<div class="fita-cotacoes-trilho" id="fita-cotacoes-trilho">)(.*?)(</div>\s*</div>\s*</div>)',
            lambda m: f"{m.group(1)}\n{bloco_fita}\n      {m.group(3)}",
            html,
            count=1,
            flags=re.DOTALL,
        )
        print(f"[OK] Fita estática sincronizada ({fita_ed_k}): {rotulo_fita}")

    if not sel_fita and not ed:
        return

    payload = html.replace("\n", newline).encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix="index_html.", suffix=".tmp", dir=str(idx_path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, idx_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    print(f"[OK] {idx_path} sincronizado estaticamente com a edição ativa: {ed_ativa_k}")


def main() -> int:
    raiz = Path(__file__).resolve().parent.parent
    include_deploy = "--include-deploy" in sys.argv[1:]
    if raiz.name == "web" and (raiz / "data" / "fechamento.json").is_file():
        bases = [raiz]
        if include_deploy and (raiz.parent / "web_deploy").is_dir():
            bases.append(raiz.parent / "web_deploy")
    else:
        bases = [raiz]

    for base in bases:
        fech_file = base / "data" / "fechamento.json"
        if not fech_file.is_file():
            continue
        dados = json.loads(fech_file.read_text(encoding="utf-8"))
        sincronizar_index_html_estatico(dados, base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
