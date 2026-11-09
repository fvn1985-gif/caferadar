#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robô de Atualização Automática na Nuvem (GitHub Actions) para caferadar.com.br
Roda 3x ao dia (08h30, 12h30, 18h30) com notícias contextuais, cotações ao vivo e Destaques B3.
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

FERIADOS_B3_FIXOS = [
    "01-01", "04-21", "05-01", "09-07", "10-12", "11-02", "11-15", "11-20", "12-24", "12-25", "12-31"
]

def eh_dia_sem_pregao(dt: datetime) -> tuple[bool, str]:
    if dt.weekday() in (5, 6):
        return True, "fim_de_semana"
    if dt.strftime("%m-%d") in FERIADOS_B3_FIXOS:
        return True, "feriado"
    return False, "pregao_util"

def locucao_dia_semana(dia_semana: str) -> str:
    if dia_semana in ("sábado", "domingo"):
        return f"neste {dia_semana}"
    return f"nesta {dia_semana}"

def artigo_dia_semana(dia_semana: str) -> str:
    if dia_semana in ("sábado", "domingo"):
        return f"o {dia_semana}"
    return f"a {dia_semana}"

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
        "WEGE3.SA": "WEGE3",
        "B3SA3.SA": "B3SA3",
        "BBDC4.SA": "BBDC4",
        "BBAS3.SA": "BBAS3",
        "PRIO3.SA": "PRIO3"
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

def gerar_conteudo_dinamico(
    ed_key: str,
    dia_semana: str,
    data_fmt: str,
    cotacoes: dict | None,
    sem_pregao: bool = False,
    motivo_sem_pregao: str = "pregao_util"
) -> dict:
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

    loc_dia = locucao_dia_semana(dia_semana)
    art_dia = artigo_dia_semana(dia_semana)

    if sem_pregao:
        rotulo_pausa = "no fim de semana" if motivo_sem_pregao == "fim_de_semana" else "no feriado nacional"
        if ed_key == "abertura":
            return {
                "subtitulo": f"Especial de Fim de Semana ({loc_dia}): preparação para a abertura de segunda-feira com Ibovespa aos {ibov_str}, Dólar a {dolar_str} e Bitcoin 24h em {btc_str}",
                "leitura_rapida": [
                    {
                        "texto": f"Com a B3 fechada {rotulo_pausa} ({loc_dia}), o investidor organiza o mapa da próxima semana: na segunda-feira às 08h25 o Banco Central divulga o Boletim Focus, calibrando as expectativas para IPCA, Selic e PIB.",
                        "fonte": "Banco Central",
                        "link": "https://www.bcb.gov.br/publicacoes/focus"
                    },
                    {
                        "texto": f"No mercado cripto — único ativo de liquidez global contínua 24/7 — o Bitcoin opera {loc_dia} cotado a {btc_str}, servindo como termômetro antecipado de apetite por risco para a reabertura das bolsas.",
                        "fonte": "Binance / CoinDesk"
                    },
                    {
                        "texto": f"O dólar comercial encerrou o último pregão útil a {dolar_str} ({dolar_var}), enquanto o S&P 500 fechou aos {sp500_str} em Nova York e o barril de petróleo Brent marcou {brent_str}.",
                        "fonte": "Investing",
                        "link": "https://br.investing.com"
                    },
                    {
                        "texto": "Na renda fixa soberana, o prêmio real do Tesouro IPCA+ 2040 acima de 6,5% a.a. segue como âncora estrutural do Radar de Alocação 2038 para novos aportes.",
                        "fonte": "Tesouro Direto",
                        "link": "https://www.tesourodireto.com.br"
                    }
                ],
                "comparacao_anterior": [
                    { "texto": "Agenda da semana: Boletim Focus (segunda, 08h25), abertura do mercado futuro B3 (09h00) e pregão à vista (10h00)." },
                    { "texto": "Use o painel Especial de Fim de Semana para revisar os ativos no radar técnico e simular aportes em Renda Fixa." }
                ]
            }
        elif ed_key in ["almoco", "negocios"]:
            return {
                "subtitulo": f"Radar Tático para Segunda-feira ({loc_dia}): estudo quantitativo das 59 ações da B3, filtro de médias móveis e comparativo Selic vs CDI",
                "leitura_rapida": [
                    {
                        "texto": f"Durante {art_dia} sem pregão na B3, o Scanner Quantitativo de Swing Trade consolida o fechamento semanal das 59 ações monitoradas, destacando os papéis próximos às médias móveis de 21 e 200 períodos.",
                        "fonte": "Scanner B3 CafeRadar"
                    },
                    {
                        "texto": f"As blue chips encerraram a semana com o Ibovespa aos {ibov_str}: bancos, elétricas e seguradoras seguem no radar defensivo, enquanto exportadoras acompanham o Brent a {brent_str} e o dólar a {dolar_str}.",
                        "fonte": "B3 / TradeMap",
                        "link": "https://trademap.com.br"
                    },
                    {
                        "texto": "No Simulador de Renda Fixa do portal, o investidor pode comparar o rendimento líquido do Tesouro Selic e CDBs (100% a 110% do CDI) contra a poupança antes de enviar ordens na segunda-feira.",
                        "fonte": "Calculadora CafeRadar"
                    },
                    {
                        "texto": f"No cenário internacional, o S&P 500 ({sp500_str}) e o Bitcoin ({btc_str}) compõem os referenciais externos para precificação dos ETFs globais (IVVB11) na reabertura local.",
                        "fonte": "ADVFN",
                        "link": "https://br.advfn.com/jornal"
                    }
                ],
                "comparacao_anterior": [
                    { "texto": "Estudo de fim de semana permite avaliar pontos técnicos sem o ruído emocional do pregão intradiário." },
                    { "texto": "Confira na aba Swing Trade (+5%) a tabela completa de auditoria e o status atualizado dos 59 ativos." }
                ]
            }
        else:
            return {
                "subtitulo": f"Balanço Consolidado da B3 ({loc_dia}): último pregão útil fechou com Ibovespa aos {ibov_str} e Dólar a {dolar_str}; Bitcoin opera a {btc_str}",
                "leitura_rapida": [
                    {
                        "texto": f"Com o mercado brasileiro fechado {rotulo_pausa} ({loc_dia}), o fechamento consolidado do último pregão útil registra o Ibovespa aos {ibov_str}, refletindo o balanço semanal das ações de maior peso no índice.",
                        "fonte": "TradeMap",
                        "link": "https://trademap.com.br"
                    },
                    {
                        "texto": f"No câmbio comercial, a última cotação de fechamento ficou em {dolar_str} ({dolar_var}), em linha com o comportamento dos yields dos Treasuries americanos e o fluxo cambial na B3.",
                        "fonte": "ADVFN",
                        "link": "https://br.advfn.com/jornal"
                    },
                    {
                        "texto": f"Entre as commodities globais, o petróleo Brent encerrou a semana a {brent_str} o barril, enquanto o índice S&P 500 marcou {sp500_str} em Wall Street.",
                        "fonte": "Investing",
                        "link": "https://br.investing.com"
                    },
                    {
                        "texto": f"Em negociação ininterrupta {loc_dia}, o Bitcoin é cotado a {btc_str}, mantendo sua estrutura monitorada pelo motor quantitativo de longo prazo.",
                        "fonte": "Binance / CoinMarketCap"
                    }
                ],
                "comparacao_anterior": [
                    { "texto": f"Dados consolidados do último pregão útil da B3, disponíveis integralmente para consulta {loc_dia}." },
                    { "texto": "O pregão regular da B3 reabre no próximo dia útil às 10h00 (leilão de pré-abertura às 09h45)." }
                ]
            }

    if ed_key == "abertura":
        return {
            "subtitulo": f"Mercados globais operam com volatilidade {loc_dia}; Dólar cotado a {dolar_str} e atenção redobrada aos juros e fiscal em Brasília",
            "leitura_rapida": [
                {
                    "texto": f"Bolsas internacionais operam em compasso de espera {loc_dia}, com investidores digerindo dados de atividade econômica global e o rumo da política monetária nos Estados Unidos.",
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
                { "texto": f"Futuros americanos apontam cautela e acomodação de lucros nas primeiras horas {loc_dia}." },
                { "texto": "Curva de juros futuros de curto prazo precifica expectativa de manutenção ou ajuste na taxa Selic." }
            ]
        }
    elif ed_key == "negocios":
        return {
            "subtitulo": f"Pregão à vista da B3 aberto {loc_dia}; Ibovespa opera aos {ibov_str} e Dólar cotado a {dolar_str} na primeira hora de negociações",
            "leitura_rapida": [
                {
                    "texto": f"Com o pregão regular aberto a partir das 10h00 {loc_dia}, o Ibovespa opera na faixa de {ibov_str}, registrando os primeiros negócios do dia com foco no fluxo institucional.",
                    "fonte": "TradeMap",
                    "link": "https://trademap.com.br"
                },
                {
                    "texto": f"Grandes bancos e Vale concentram o giro financeiro da abertura, enquanto petroleiras monitoram o barril de petróleo Brent cotado a {brent_str}.",
                    "fonte": "Visno Invest",
                    "link": "https://visnoinvest.com.br"
                },
                {
                    "texto": f"No câmbio doméstico, o dólar comercial marca {dolar_str} ({dolar_var}) nas primeiras cotações, acompanhando os juros futuros e a curva de Treasuries.",
                    "fonte": "ADVFN",
                    "link": "https://br.advfn.com/jornal"
                },
                {
                    "texto": f"Em Nova York, os futuros de Wall Street e S&P 500 operam aos {sp500_str}, enquanto o Bitcoin se mantém cotado em {btc_str}.",
                    "fonte": "BB InvesTalk"
                }
            ],
            "comparacao_anterior": [
                { "texto": f"Primeiros negócios do pregão de {dia_semana} mostram liquidez concentrada nos papéis de maior peso do índice." },
                { "texto": "Os alvos de curto prazo e posições ativas podem ser acompanhados na aba Swing Trade (+5%)." }
            ]
        }
    elif ed_key == "almoco":
        return {
            "subtitulo": f"Ibovespa oscila em torno dos {ibov_str} no início da tarde {loc_dia}; Dólar cotado a {dolar_str} com giro concentrado no setor bancário e Vale",
            "leitura_rapida": [
                {
                    "texto": f"O Ibovespa opera próximo de {ibov_str} no balanço do meio-dia {loc_dia}, com o mercado monitorando o apetite por risco em Wall Street e declarações econômicas em Brasília.",
                    "fonte": "TradeMap",
                    "link": "https://trademap.com.br"
                },
                {
                    "texto": f"Grandes bancos e Vale puxam o volume financeiro do pregão, enquanto empresas ligadas a commodities reagem ao preço do petróleo Brent a {brent_str}.",
                    "fonte": "Visno Invest",
                    "link": "https://visnoinvest.com.br"
                },
                {
                    "texto": f"O dólar comercial registra cotação de {dolar_str} ({dolar_var}), mantendo postura prudente na curva de juros futuros antes da ata do Copom.",
                    "fonte": "ADVFN",
                    "link": "https://br.advfn.com/jornal"
                },
                {
                    "texto": f"Em Wall Street, o S&P 500 opera aos {sp500_str}, refletindo a temporada de resultados corporativos e indicadores de atividade nos EUA.",
                    "fonte": "BB InvesTalk"
                }
            ],
            "comparacao_anterior": [
                { "texto": f"Volume negociado na primeira metade do pregão de {dia_semana} mostra investidores institucionais atuando com seletividade." },
                { "texto": "Setor financeiro (Itaú e Bradesco) e B3 sustentam suporte relevante frente às oscilações externas." }
            ]
        }
    else: # fechamento
        return {
            "subtitulo": f"Ibovespa encerra {art_dia} aos {ibov_str}; Dólar fecha a {dolar_str} e investidores avaliam balanços trimestrais",
            "leitura_rapida": [
                {
                    "texto": f"A bolsa brasileira encerra as negociações {loc_dia} com o Ibovespa marcando {ibov_str}, em pregão marcado por disciplina seletiva dos investidores.",
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
                { "texto": f"Fechamento {loc_dia} confirma a consolidação do índice dentro da faixa técnica de suporte." },
                { "texto": "Mercado aguarda a abertura do próximo pregão para digerir novos indicadores de inflação e atividade." }
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
    sem_pregao, motivo_sem_pregao = eh_dia_sem_pregao(agora_sp)

    forcar = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ["abertura", "negocios", "almoco", "fechamento"] else None
    if forcar:
        edicao_ativa = "negocios" if forcar == "almoco" else forcar
    elif sem_pregao:
        edicao_ativa = "fechamento"
    elif tempo_min < 10 * 60:
        edicao_ativa = "abertura"
    elif tempo_min < 17 * 60 + 30:
        edicao_ativa = "negocios"
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
    dados["dia_semana"] = dia_semana
    dados["fim_de_semana"] = sem_pregao
    dados["modo_mercado"] = motivo_sem_pregao

    cotacoes = coletar_cotacoes()

    if sem_pregao:
        disp_map = {
            "abertura": True,
            "negocios": True,
            "almoco": True,
            "fechamento": True
        }
    else:
        disp_map = {
            "abertura": True,
            "negocios": tempo_min >= 10 * 60,
            "almoco": tempo_min >= 10 * 60,
            "fechamento": tempo_min >= 17 * 60 + 30
        }

    if forcar:
        k_force = "negocios" if forcar == "almoco" else forcar
        disp_map[k_force] = True
        disp_map["almoco"] = True

    # Montar Maiores Altas e Quedas reais da B3
    altas_reais = []
    quedas_reais = []
    if cotacoes:
        acoes_lista = []
        for ticker in ["PETR4", "VALE3", "ITUB4", "WEGE3", "B3SA3", "BBDC4", "BBAS3", "PRIO3"]:
            if ticker in cotacoes:
                acoes_lista.append((ticker, cotacoes[ticker]["var_pct"]))
        
        if acoes_lista:
            acoes_lista.sort(key=lambda x: x[1], reverse=True)
            for t, v_pct in acoes_lista[:2]:
                s = "+" if v_pct >= 0 else ""
                altas_reais.append({"ticker": t, "variacao": f"{s}{v_pct:.2f}%".replace(".", ",")})
            for t, v_pct in acoes_lista[-2:]:
                s = "+" if v_pct >= 0 else ""
                quedas_reais.append({"ticker": t, "variacao": f"{s}{v_pct:.2f}%".replace(".", ",")})

    nomes_padrao = {
        "abertura": ("Café Matinal", "08h00"),
        "negocios": ("Abertura B3", "10h30"),
        "almoco": ("Abertura B3", "10h30"),
        "fechamento": ("Fechamento", "18h15")
    }
    nomes_fds = {
        "abertura": ("Mapa da Semana", "Especial"),
        "negocios": ("Radar de Segunda", "Estudo"),
        "almoco": ("Radar de Segunda", "Estudo"),
        "fechamento": ("Balanço da Semana", "Consolidado")
    }

    if "edicoes" in dados:
        for ed_key in ["abertura", "negocios", "almoco", "fechamento"]:
            if ed_key not in dados["edicoes"]:
                continue
            ed = dados["edicoes"][ed_key]
            if sem_pregao:
                nome_ed, hora_ed = nomes_fds[ed_key]
                ed["nome"] = nome_ed
                ed["horario_exibicao"] = hora_ed
                ed["titulo"] = f"ESPECIAL DE FIM DE SEMANA: {nome_ed.upper()} — {data_fmt}"
            else:
                nome_ed, hora_ed = nomes_padrao[ed_key]
                ed["nome"] = nome_ed
                ed["horario"] = hora_ed
                ed["horario_exibicao"] = hora_ed
                ed["titulo"] = f"RADAR DE {nome_ed.upper()} — {data_fmt}"

            ed["disponivel"] = disp_map.get(ed_key, True)
            ed["status_publicacao"] = "Publicado" if ed["disponivel"] else f"Prevista para as {ed.get('horario', '12h30')}"

            conteudo = gerar_conteudo_dinamico(ed_key, dia_semana, data_fmt, cotacoes, sem_pregao, motivo_sem_pregao)
            ed["subtitulo"] = conteudo["subtitulo"]
            ed["leitura_rapida"] = conteudo["leitura_rapida"]
            ed["comparacao_anterior"] = conteudo["comparacao_anterior"]

            if altas_reais and quedas_reais:
                ed["destaques"] = {
                    "altas": altas_reais,
                    "quedas": quedas_reais
                }

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
    atualizar_dashboard_nuvem(data_ref, data_fmt, agora_sp.strftime("%Hh%M"), cotacoes)

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
