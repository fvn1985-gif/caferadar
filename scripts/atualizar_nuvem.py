#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robô de Atualização Automática na Nuvem (GitHub Actions) para caferadar.com.br
Roda 3x ao dia (08h30, 12h30, 18h30) e atualiza cotações e resumo do mercado.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
FECHAMENTO_JSON = ROOT / "data" / "fechamento.json"
TZ_SP = ZoneInfo("America/Sao_Paulo")

def formatar_numero_br(valor: float, decimais: int = 2) -> str:
    if decimais == 0:
        return f"{int(round(valor)):,}".replace(",", ".")
    fmt = f"{valor:,.{decimais}f}"
    partes = fmt.split(".")
    inteiro = partes[0].replace(",", ".")
    decimal = partes[1]
    return f"{inteiro},{decimal}"

def formatar_variacao(variacao_pct: float) -> tuple[str, bool]:
    sinal = "+" if variacao_pct >= 0 else ""
    positivo = variacao_pct >= 0
    return f"{sinal}{variacao_pct:.2f}%".replace(".", ","), positivo

def coletar_cotacoes():
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance não instalado.")
        return None

    tickers_map = {
        "^BVSP": "ibov",
        "USDBRL=X": "dolar",
        "^GSPC": "sp500",
        "BTC-USD": "bitcoin",
        "BZ=F": "brent",
        "PETR4.SA": "PETR4",
        "VALE3.SA": "VALE3",
        "ITUB4.SA": "ITUB4",
        "WEGE3.SA": "WEGE3"
    }

    simbolos = list(tickers_map.keys())
    print(f"Buscando cotações ao vivo na nuvem ({len(simbolos)} ativos)...")

    try:
        data = yf.Tickers(" ".join(simbolos))
        resultados = {}
        for symb in simbolos:
            key = tickers_map[symb]
            try:
                t = data.tickers[symb]
                fast = t.fast_info
                last = getattr(fast, "last_price", None)
                prev = getattr(fast, "previous_close", None)
                if last is not None and prev is not None and prev > 0:
                    var_pct = ((last - prev) / prev) * 100.0
                    resultados[key] = {
                        "last": float(last),
                        "prev": float(prev),
                        "var_pct": float(var_pct)
                    }
            except Exception as e:
                print(f"Aviso para {symb}: {e}")
        return resultados
    except Exception as exc:
        print(f"Erro no yfinance: {exc}")
        return None

def main():
    agora_sp = datetime.now(TZ_SP)
    data_ref = agora_sp.strftime("%Y-%m-%d")
    data_fmt = agora_sp.strftime("%d/%m/%Y")
    hora = agora_sp.hour
    minuto = agora_sp.minute
    tempo_min = hora * 60 + minuto

    # Determina edição pelo horário de Brasília
    forcar = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ["abertura", "almoco", "fechamento"] else None
    if forcar:
        edicao_ativa = forcar
    elif tempo_min < 12 * 60:
        edicao_ativa = "abertura"
    elif tempo_min < 17 * 60 + 30:
        edicao_ativa = "almoco"
    else:
        edicao_ativa = "fechamento"

    print(f"Atualizando Portal na Nuvem: {data_fmt} às {agora_sp.strftime('%Hh%M')} (Edição: {edicao_ativa.upper()})")

    if not FECHAMENTO_JSON.is_file():
        print(f"Arquivo {FECHAMENTO_JSON} não encontrado!")
        return

    with open(FECHAMENTO_JSON, "r", encoding="utf-8") as f:
        dados = json.load(f)

    dados["edicao_padrao"] = edicao_ativa
    dados["data_referencia"] = data_ref
    dados["data_formatada"] = data_fmt

    cotacoes = coletar_cotacoes()

    if cotacoes and "edicoes" in dados:
        for ed_key in ["abertura", "almoco", "fechamento"]:
            if ed_key not in dados["edicoes"]:
                continue
            ed = dados["edicoes"][ed_key]
            ed["titulo"] = f"RADAR DE {ed['nome'].upper()} — {data_fmt}"

            mg = ed.setdefault("mercado_geral", {})
            if "ibov" in cotacoes and "ibov" in mg:
                v = cotacoes["ibov"]
                mg["ibov"]["pontos"] = formatar_numero_br(v["last"], 0) + " pts"
                mg["ibov"]["variacao"], mg["ibov"]["positivo"] = formatar_variacao(v["var_pct"])

            if "dolar" in cotacoes and "dolar" in mg:
                v = cotacoes["dolar"]
                mg["dolar"]["valor"] = "R$ " + formatar_numero_br(v["last"], 2)
                mg["dolar"]["variacao"], mg["dolar"]["positivo"] = formatar_variacao(v["var_pct"])

            if "sp500" in cotacoes and "sp500" in mg:
                v = cotacoes["sp500"]
                mg["sp500"]["valor"] = formatar_numero_br(v["last"], 0) + " pts"
                mg["sp500"]["variacao"], mg["sp500"]["positivo"] = formatar_variacao(v["var_pct"])

            if "bitcoin" in cotacoes and "bitcoin" in mg:
                v = cotacoes["bitcoin"]
                mg["bitcoin"]["valor"] = "US$ " + formatar_numero_br(v["last"], 0)
                mg["bitcoin"]["variacao"], mg["bitcoin"]["positivo"] = formatar_variacao(v["var_pct"])

            if "brent" in cotacoes and "brent" in mg:
                v = cotacoes["brent"]
                mg["brent"]["valor"] = "US$ " + formatar_numero_br(v["last"], 2)
                mg["brent"]["variacao"], mg["brent"]["positivo"] = formatar_variacao(v["var_pct"])

            if "acoes_blue_chips" in ed:
                for acao in ed["acoes_blue_chips"]:
                    ticker = acao.get("ticker")
                    if ticker in cotacoes:
                        v = cotacoes[ticker]
                        acao["preco"] = "R$ " + formatar_numero_br(v["last"], 2)
                        acao["variacao_dia"], acao["positivo"] = formatar_variacao(v["var_pct"])

    with open(FECHAMENTO_JSON, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    print("fechamento.json atualizado na nuvem com sucesso!")

if __name__ == "__main__":
    main()
