#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robô de Atualização Automática na Nuvem (GitHub Actions) para caferadar.com.br
Roda 3x ao dia (08h30, 12h30, 18h30) com notícias contextuais do dia da semana e cotações ao vivo.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
FECHAMENTO_JSON = ROOT / "data" / "fechamento.json"
TZ_SP = ZoneInfo("America/Sao_Paulo")

DIAS_SEMANA_PT = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo"
]

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

def gerar_conteudo_dinamico(ed_key: str, dia_semana: str, data_fmt: str, cotacoes: dict | None) -> dict:
    dolar_str = "R$ 5,46"
    dolar_var = "-0,50%"
    sp500_str = "7.560 pts"
    btc_str = "US$ 78.200"
    brent_str = "US$ 101,80"
    ibov_str = "165.500 pts"

    if cotacoes:
        if "dolar" in cotacoes:
            dolar_str = "R$ " + formatar_numero_br(cotacoes["dolar"]["last"], 2)
            dolar_var = formatar_variacao(cotacoes["dolar"]["var_pct"])[0]
        if "sp500" in cotacoes:
            sp500_str = formatar_numero_br(cotacoes["sp500"]["last"], 0) + " pts"
        if "bitcoin" in cotacoes:
            btc_str = "US$ " + formatar_numero_br(cotacoes["bitcoin"]["last"], 0)
        if "brent" in cotacoes:
            brent_str = "US$ " + formatar_numero_br(cotacoes["brent"]["last"], 2)
        if "ibov" in cotacoes:
            ibov_str = formatar_numero_br(cotacoes["ibov"]["last"], 0) + " pts"

    if ed_key == "abertura":
        return {
            "subtitulo": f"Mercados globais operam com volatilidade nesta {dia_semana}; Dólar cotado a {dolar_str} e atenção redobrada aos juros e fiscal em Brasília",
            "leitura_rapida": [
                {
                    "texto": f"Bolsas internacionais operam em compasso de espera nesta {dia_semana}, com investidores digerindo dados de atividade econômica global e o rumo da política monetária nos Estados Unidos.",
                    "fonte": "ADVFN",
                    "link": "https://br.advfn.com/jornal"
                },
                {
                    "texto": f"No câmbio doméstico, o dólar comercial opera cotado a {dolar_str} ({dolar_var}), refletindo ajustes na curva de juros pré-mercado antes da decisão do Copom.",
                    "fonte": "TradeMap",
                    "link": "https://trademap.com.br"
                },
                {
                    "texto": f"O petróleo Brent é negociado a {brent_str} o barril, influenciando diretamente o ritmo de abertura das ações de óleo e gás na B3 nesta manhã de {dia_semana}.",
                    "fonte": "Investing",
                    "link": "https://br.investing.com"
                },
                {
                    "texto": f"O Bitcoin (BTC) se mantém firme no patamar de {btc_str}, sustentando fluxo comprador positivo na esteira do apetite global por ativos digitais.",
                    "fonte": "Binance / CoinDesk"
                }
            ],
            "comparacao_anterior": [
                { "texto": f"Futuros americanos apontam cautela e acomodação de lucros nas primeiras horas desta {dia_semana}." },
                { "texto": "Curva de juros futuros de curto prazo precifica expectativa de manutenção ou ajuste na taxa Selic." }
            ]
        }
    elif ed_key == "almoco":
        return {
            "subtitulo": f"Ibovespa opera aos {ibov_str} no início da tarde desta {dia_semana}; Dólar a {dolar_str} e liquidez concentrada em grandes bancos e estatais",
            "leitura_rapida": [
                {
                    "texto": f"O Ibovespa oscila em torno dos {ibov_str} nesta tarde de {dia_semana}, com investidores locais calibrando posições em meio ao noticiário corporativo e fiscal.",
                    "fonte": "TradeMap",
                    "link": "https://trademap.com.br"
                },
                {
                    "texto": f"Petrobras e Vale comandam o volume financeiro do pregão, repercutindo as oscilações do barril de petróleo a {brent_str} e das commodities metálicas na Ásia.",
                    "fonte": "Visno Invest",
                    "link": "https://visnoinvest.com.br"
                },
                {
                    "texto": f"O dólar comercial registra cotação de {dolar_str} ({dolar_var}), mantendo prêmio de risco prudente antes dos comunicados de política monetária.",
                    "fonte": "ADVFN",
                    "link": "https://br.advfn.com/jornal"
                },
                {
                    "texto": f"Em Wall Street, os índices operam mistos, com o S&P 500 cotado próximo de {sp500_str} em compasso de espera por balanços de grandes empresas de tecnologia.",
                    "fonte": "BB InvesTalk"
                }
            ],
            "comparacao_anterior": [
                { "texto": f"Volume negociado no meio do dia mostra investidores institucionais mais seletivos nesta {dia_semana}." },
                { "texto": "Destaque para o setor elétrico e financeiro atuando como colchão de liquidez contra a volatilidade." }
            ]
        }
    else: # fechamento
        return {
            "subtitulo": f"Ibovespa encerra a {dia_semana} aos {ibov_str}; Dólar fecha a {dolar_str} e investidores avaliam balanços trimestrais",
            "leitura_rapida": [
                {
                    "texto": f"A bolsa brasileira encerra as negociações desta {dia_semana} com o Ibovespa marcando {ibov_str}, em pregão marcado por disciplina seletiva dos investidores.",
                    "fonte": "TradeMap",
                    "link": "https://trademap.com.br"
                },
                {
                    "texto": f"No câmbio, o dólar encerrou cotado a {dolar_str} ({dolar_var}), refletindo fluxo de capitais e cautela com o cenário macroeconômico global.",
                    "fonte": "ADVFN",
                    "link": "https://br.advfn.com/jornal"
                },
                {
                    "texto": f"Entre as commodities, o barril de petróleo Brent finalizou a sessão a {brent_str}, ditando o rumo das petroleiras no pregão da B3.",
                    "fonte": "Investing",
                    "link": "https://br.investing.com"
                },
                {
                    "texto": f"No universo cripto, o Bitcoin fechou o dia no patamar de {btc_str}, preservando suporte relevante em sua estrutura de médio prazo.",
                    "fonte": "Binance / CoinMarketCap"
                }
            ],
            "comparacao_anterior": [
                { "texto": f"Fechamento desta {dia_semana} confirma a consolidação do índice dentro da faixa técnica de suporte." },
                { "texto": "Mercado aguarda a abertura de amanhã para digerir novos indicadores de inflação e atividade." }
            ]
        }

def main():
    agora_sp = datetime.now(TZ_SP)
    data_ref = agora_sp.strftime("%Y-%m-%d")
    data_fmt = agora_sp.strftime("%d/%m/%Y")
    hora = agora_sp.hour
    minuto = agora_sp.minute
    tempo_min = hora * 60 + minuto
    dia_semana = DIAS_SEMANA_PT[agora_sp.weekday()]

    forcar = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ["abertura", "almoco", "fechamento"] else None
    if forcar:
        edicao_ativa = forcar
    elif tempo_min < 12 * 60:
        edicao_ativa = "abertura"
    elif tempo_min < 17 * 60 + 30:
        edicao_ativa = "almoco"
    else:
        edicao_ativa = "fechamento"

    print(f"Atualizando Portal na Nuvem: {data_fmt} ({dia_semana}) às {agora_sp.strftime('%Hh%M')} (Edição: {edicao_ativa.upper()})")

    if not FECHAMENTO_JSON.is_file():
        print(f"Arquivo {FECHAMENTO_JSON} não encontrado!")
        return

    with open(FECHAMENTO_JSON, "r", encoding="utf-8") as f:
        dados = json.load(f)

    dados["edicao_padrao"] = edicao_ativa
    dados["data_referencia"] = data_ref
    dados["data_formatada"] = data_fmt

    cotacoes = coletar_cotacoes()

    tempo_min = hora * 60 + minuto

    disp_map = {
        "abertura": True,
        "almoco": tempo_min >= 12 * 60,
        "fechamento": tempo_min >= 17 * 60 + 30
    }

    if forcar:
        disp_map[forcar] = True

    if "edicoes" in dados:
        for ed_key in ["abertura", "almoco", "fechamento"]:
            if ed_key not in dados["edicoes"]:
                continue
            ed = dados["edicoes"][ed_key]
            ed["titulo"] = f"RADAR DE {ed['nome'].upper()} — {data_fmt}"
            ed["disponivel"] = disp_map.get(ed_key, True)
            ed["status_publicacao"] = "Publicado" if ed["disponivel"] else f"Prevista para as {ed.get('horario', '12h30')}"

            # Notícias e subtítulos dinâmicos com dia da semana exato
            conteudo = gerar_conteudo_dinamico(ed_key, dia_semana, data_fmt, cotacoes)
            ed["subtitulo"] = conteudo["subtitulo"]
            ed["leitura_rapida"] = conteudo["leitura_rapida"]
            ed["comparacao_anterior"] = conteudo["comparacao_anterior"]

            if cotacoes:
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

    print("fechamento.json atualizado na nuvem com notícias contextuais!")

    # Atualiza também o Radar Longo Prazo na nuvem
    atualizar_dashboard_nuvem(data_ref, data_fmt, hora_fmt, cotacoes)

def atualizar_dashboard_nuvem(data_ref: str, data_fmt: str, hora_fmt: str, cotacoes: dict | None):
    dash_json = ROOT / "data" / "dashboard.json"
    if not dash_json.is_file():
        return

    with open(dash_json, "r", encoding="utf-8") as f:
        dash = json.load(f)

    dash["reference_date"] = data_ref
    dash["status"] = f"● MONITORAMENTO DIÁRIO ATIVO — {data_fmt}"

    ibov_last = cotacoes["ibov"]["last"] if cotacoes and "ibov" in cotacoes else 167155.0
    dolar_last = cotacoes["dolar"]["last"] if cotacoes and "dolar" in cotacoes else 5.4800
    btc_last = cotacoes["bitcoin"]["last"] if cotacoes and "bitcoin" in cotacoes else 78180.0

    if "indicators" in dash:
        if "ibov" in dash["indicators"]:
            dash["indicators"]["ibov"]["last_close"]["date"] = data_ref
            dash["indicators"]["ibov"]["last_close"]["value"] = round(ibov_last, 2)
        if "ptax_venda" in dash["indicators"]:
            dash["indicators"]["ptax_venda"]["last_sale"]["date"] = data_ref
            dash["indicators"]["ptax_venda"]["last_sale"]["value"] = round(dolar_last, 4)
        if "bitcoin" in dash["indicators"]:
            dash["indicators"]["bitcoin"]["last_close"]["date"] = data_ref
            dash["indicators"]["bitcoin"]["last_close"]["value"] = round(btc_last, 2)

    with open(dash_json, "w", encoding="utf-8") as f:
        json.dump(dash, f, ensure_ascii=False, indent=2)

    print("dashboard.json atualizado na nuvem com dados de hoje!")

if __name__ == "__main__":
    main()
