#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robô de Atualização Automática na Nuvem (GitHub Actions) para caferadar.com.br
Roda nos horários canônicos de pregão com notícias contextuais, cotações ao vivo e Destaques B3.

MAPA DE COMPATIBILIDADE (CHAVES LEGADAS -> EDIÇÕES CANÔNICAS):
+-----------------------+--------------------+---------------------+--------------------------------------------+
| Chave fechamento.json | Edição Canônica    | Janela Canônica BRT | Descrição / Papel no Portal                |
+-----------------------+--------------------+---------------------+--------------------------------------------+
| "abertura"            | matinal (08h00)    | 07:00 às 09:45      | Café Matinal / Pré-mercado B3 (Sem Ibov)   |
| "negocios" / "almoco" | abertura (10h30)   | 10:15 às 12:00      | Abertura B3 / Primeira hora de negócios    |
| "fechamento"          | fechamento (18h15) | a partir das 18:05  | Fechamento B3 Consolidado                  |
+-----------------------+--------------------+---------------------+--------------------------------------------+

DIRETRIZES DE GOVERNANÇA E ARQUITETURA:
1. DESACOPLAMENTO ESTRITO: data/dashboard.json (Radar de Longo Prazo) é SEMPRE atualizado em todos
   os runs do robô com `generated_at` fresco. Em pré-abertura (antes das 10h00) ou dias sem pregão,
   não carimba a data de hoje sobre cotações de fechamento anteriores de Ibovespa/PTAX.
2. JANELAS TEMPORAIS ESTRITAS: data/fechamento.json só pode ser alterado se o horário da execução
   estiver dentro da janela da respectiva edição canônica (em dias úteis).
3. IMUTABILIDADE DE CAPTURA OFICIAL: Se uma edição canônica do dia já possui um snapshot gravado com
   'capturado_em' dentro de sua janela no mesmo dia, execuções posteriores NÃO a sobrescrevem.
4. VIRADA DE DIA LIMPA: Quando data_referencia avança para um novo dia útil, edições anteriores que
   ainda carregam dados de pregões passados e não pertencem à janela atual são zeradas
   (disponivel=False, campos limpos, data_referencia atualizada por edição), evitando exibir dados
   de ontem sob a data de hoje.
5. MATINAL, FRESCOR E S&P 500 FUTURO: A edição Matinal não exibe Ibovespa, blue chips nem destaques de B3.
   Matinal e Abertura utilizam exclusivamente ES=F para S&P 500 Futuro; se ES=F falhar ou estiver
   obsoleto, exibem "Indisponível" (nunca ^GSPC do fechamento anterior nem fallback fixo).
   No Fechamento, usa-se apenas ^GSPC (nunca ES=F sob o rótulo "S&P 500"). Em dias úteis, ações B3,
   Ibovespa e ^GSPC têm frescor validado contra a data do pregão corrente.
6. PARÂMETRO FORÇAR: Respeita janelas e imutabilidade por padrão. O bypass emergencial só ocorre se
   a flag explícita --ignorar-janela for passada via linha de comando (NUNCA exposta no workflow_dispatch),
   restringindo-se sempre às chaves da edição alvo em dia útil.
"""

from __future__ import annotations

import copy
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
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

# Feriados fixos nacionais / B3.
# NOTA DE GOVERNANÇA (calendário móvel): Carnaval, Sexta-feira Santa e Corpus Christi
# não constam nesta lista estática (próximo feriado móvel relevante: Carnaval de 2027).
# Para cobertura de longo prazo, integrar cálculo móvel baseado em Páscoa antes de fev/2027.
FERIADOS_B3_FIXOS = [
    "01-01", "04-21", "05-01", "09-07", "10-12", "11-02", "11-15", "11-20", "12-24", "12-25", "12-31"
]

MAPA_LEGADO_CANONICO = {
    "abertura": "matinal",
    "negocios": "abertura",
    "almoco": "abertura",
    "fechamento": "fechamento"
}

JANELAS_CANONICAS = {
    "matinal": {
        "inicio_min": 7 * 60,
        "fim_min": 9 * 60 + 45,
        "rotulo": "07:00 às 09:45",
        "chaves_fechamento": ["abertura"]
    },
    "abertura": {
        "inicio_min": 10 * 60 + 15,
        "fim_min": 12 * 60,
        "rotulo": "10:15 às 12:00",
        "chaves_fechamento": ["negocios", "almoco"]
    },
    "fechamento": {
        "inicio_min": 18 * 60 + 5,
        "fim_min": 24 * 60,
        "rotulo": "a partir das 18:05",
        "chaves_fechamento": ["fechamento"]
    }
}

BLUE_CHIPS_MONITORADAS = [
    ("PETR4", "Petrobras PN"),
    ("VALE3", "Vale ON"),
    ("ITUB4", "Itaú Unibanco PN"),
    ("WEGE3", "WEG ON"),
    ("BBAS3", "Banco do Brasil ON"),
    ("BBDC4", "Bradesco PN"),
    ("B3SA3", "B3 ON"),
    ("PRIO3", "PRIO ON"),
]

NOMES_PADRAO = {
    "abertura": ("Café Matinal", "08h00"),
    "negocios": ("Abertura B3", "10h30"),
    "almoco": ("Abertura B3", "10h30"),
    "fechamento": ("Fechamento", "18h15")
}

NOMES_FDS = {
    "abertura": ("Mapa da Semana", "Especial"),
    "negocios": ("Radar de Segunda", "Estudo"),
    "almoco": ("Radar de Segunda", "Estudo"),
    "fechamento": ("Balanço da Semana", "Consolidado")
}

def eh_dia_sem_pregao(dt: datetime) -> tuple[bool, str]:
    if dt.weekday() in (5, 6):
        return True, "fim_de_semana"
    if dt.strftime("%m-%d") in FERIADOS_B3_FIXOS:
        return True, "feriado"
    return False, "pregao_util"

def validar_janela_edicao(ed_canonica: str, dt_captura: datetime, sem_pregao: bool = False) -> tuple[bool, str]:
    if sem_pregao:
        return True, "Fim de semana ou feriado B3: janela temporal dispensada."
    if ed_canonica not in JANELAS_CANONICAS:
        return False, f"Edição canônica '{ed_canonica}' desconhecida."

    cfg = JANELAS_CANONICAS[ed_canonica]
    tempo_min = dt_captura.hour * 60 + dt_captura.minute
    if cfg["inicio_min"] <= tempo_min <= cfg["fim_min"]:
        return True, f"Horário {dt_captura.strftime('%H:%M')} dentro da janela canônica ({cfg['rotulo']})."
    return False, f"Horário {dt_captura.strftime('%H:%M')} fora da janela canônica ({cfg['rotulo']})."

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

def _extrair_dt_capturado(ed: dict) -> datetime | None:
    cap = ed.get("capturado_em")
    if not cap or not isinstance(cap, str):
        return None
    try:
        dt = datetime.fromisoformat(cap)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_SP)
        return dt
    except Exception:
        return None

def mesclar_fechamento_por_capturado_em(dados_local: dict, dados_remoto: dict) -> dict:
    """
    Resolve divergências entre fechamento.json local e remoto mantendo:
    1) A `data_referencia` mais recente (nunca ressuscita captura de dia anterior sobre edição
       já rolada/zerada para o dia atual).
    2) Dentro da mesma `data_referencia`, o `capturado_em` mais recente de cada edição vence
       (e captura válida sempre vence edição vazia/não capturada do mesmo dia).
    """
    merged = copy.deepcopy(dados_remoto) if dados_remoto else copy.deepcopy(dados_local)
    ed_local = dados_local.get("edicoes", {}) if dados_local else {}
    ed_remoto = dados_remoto.get("edicoes", {}) if dados_remoto else {}
    todas_chaves = list(dict.fromkeys(list(ed_remoto.keys()) + list(ed_local.keys())))

    ref_l_top = (dados_local or {}).get("data_referencia", "")
    ref_r_top = (dados_remoto or {}).get("data_referencia", "")
    data_ref_alvo = max(ref_l_top, ref_r_top)

    def _ref_edicao(ed: dict, fallback_top: str) -> str:
        dt = _extrair_dt_capturado(ed)
        if dt:
            return dt.date().isoformat()
        return ed.get("data_referencia") or fallback_top

    merged_edicoes = {}
    decisoes = []

    for chv in todas_chaves:
        loc = ed_local.get(chv)
        rem = ed_remoto.get(chv)

        if loc is None:
            merged_edicoes[chv] = copy.deepcopy(rem)
            decisoes.append(f"{chv}: mantido remoto (ausente no local)")
            continue
        if rem is None:
            merged_edicoes[chv] = copy.deepcopy(loc)
            decisoes.append(f"{chv}: mantido local (ausente no remoto)")
            continue

        ref_loc = _ref_edicao(loc, ref_l_top)
        ref_rem = _ref_edicao(rem, ref_r_top)

        # Regra 1: Dia mais recente sempre prevalece (evita ressuscitar captura de ontem sobre hoje)
        if ref_loc != ref_rem:
            if ref_loc > ref_rem:
                merged_edicoes[chv] = copy.deepcopy(loc)
                decisoes.append(f"{chv}: local venceu por data mais recente ({ref_loc} > {ref_rem})")
            else:
                merged_edicoes[chv] = copy.deepcopy(rem)
                decisoes.append(f"{chv}: remoto venceu por data mais recente ({ref_rem} > {ref_loc})")
            continue

        # Regra 2: Mesmo dia -> compara capturado_em ISO
        dt_loc = _extrair_dt_capturado(loc)
        dt_rem = _extrair_dt_capturado(rem)

        if dt_loc and dt_rem:
            if dt_loc > dt_rem:
                merged_edicoes[chv] = copy.deepcopy(loc)
                decisoes.append(f"{chv}: local venceu ({dt_loc.isoformat()} > {dt_rem.isoformat()})")
            else:
                merged_edicoes[chv] = copy.deepcopy(rem)
                decisoes.append(f"{chv}: remoto venceu ({dt_rem.isoformat()} >= {dt_loc.isoformat()})")
        elif dt_loc and not dt_rem:
            merged_edicoes[chv] = copy.deepcopy(loc)
            decisoes.append(f"{chv}: local venceu ({dt_loc.isoformat()} vs remoto sem captura em {ref_loc})")
        elif dt_rem and not dt_loc:
            merged_edicoes[chv] = copy.deepcopy(rem)
            decisoes.append(f"{chv}: remoto venceu ({dt_rem.isoformat()} vs local sem captura em {ref_rem})")
        else:
            merged_edicoes[chv] = copy.deepcopy(rem)
            decisoes.append(f"{chv}: ambos sem captura em {data_ref_alvo}; mantido remoto")

    merged["edicoes"] = merged_edicoes

    base_topo = dados_local if ref_l_top > ref_r_top else dados_remoto
    if base_topo:
        for campo in ["data_referencia", "data_formatada", "dia_semana", "fim_de_semana", "modo_mercado", "edicao_padrao"]:
            if campo in base_topo:
                merged[campo] = base_topo[campo]

    merged["_merge_log"] = decisoes
    return merged

def coletar_cotacoes(agora_sp: datetime | None = None, sem_pregao: bool = False):
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance não instalado.")
        return None

    tickers_map = {
        "^BVSP": "ibov",
        "USDBRL=X": "dolar",
        "ES=F": "sp500_futuro",
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

    agora_ref = agora_sp or datetime.now(TZ_SP)
    data_hoje_iso = agora_ref.date().isoformat()
    candles_datas: dict[str, str] = {}
    var_mes_map: dict[str, float] = {}

    # Batch 1mo para validar data efetiva do último pregão (frescor) + variação mensal B3
    try:
        df_1m = yf.download(simbolos, period="1mo", progress=False)
        if df_1m is not None and not df_1m.empty and "Close" in df_1m:
            closes = df_1m["Close"]
            for s_sym in simbolos:
                if s_sym in closes:
                    serie = closes[s_sym].dropna()
                    if len(serie) >= 1:
                        last_idx = serie.index[-1]
                        try:
                            dt_c = last_idx.to_pydatetime()
                            candles_datas[s_sym] = dt_c.date().isoformat()
                        except Exception:
                            candles_datas[s_sym] = str(last_idx)[:10]
                    if s_sym.endswith(".SA") and len(serie) >= 2:
                        primeiro = float(serie.iloc[0])
                        ultimo = float(serie.iloc[-1])
                        if math.isfinite(primeiro) and math.isfinite(ultimo) and primeiro > 0:
                            var_mes_map[tickers_map[s_sym]] = ((ultimo - primeiro) / primeiro) * 100.0
    except Exception as e_dl:
        print(f"Aviso coleta em lote 1mo (frescor/mensal): {e_dl}")

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
                if last is None or prev is None:
                    continue
                last_f = float(last)
                prev_f = float(prev)
                if not (math.isfinite(last_f) and math.isfinite(prev_f) and prev_f > 0):
                    continue

                # Validação estrita de frescor para S&P 500 Futuro (ES=F) em pregão útil
                if symb == "ES=F" and not sem_pregao:
                    try:
                        hist = t.history(period="2d", interval="1h")
                        if hist is None or hist.empty:
                            print("Aviso para ES=F: histórico intradiário vazio; marcando S&P Futuro como indisponível.")
                            continue
                        last_ts = hist.index[-1]
                        dt_candle = last_ts.to_pydatetime()
                        if dt_candle.tzinfo is None:
                            dt_candle = dt_candle.replace(tzinfo=TZ_SP)
                        else:
                            dt_candle = dt_candle.astimezone(TZ_SP)
                        idade_h = (agora_ref - dt_candle).total_seconds() / 3600.0
                        if idade_h > 24.0:
                            print(f"Aviso para ES=F: último candle antigo ({dt_candle.isoformat()}, {idade_h:.1f}h); descartado.")
                            continue
                        candles_datas[symb] = dt_candle.date().isoformat()
                    except Exception as e_hist:
                        print(f"Aviso para ES=F ao checar frescor ({e_hist}); descartado por segurança.")
                        continue

                c_date = candles_datas.get(symb)
                # Fallback individual se lote 1mo não retornou data válida para ativos B3 / ^GSPC
                if not c_date and not sem_pregao and (symb == "^BVSP" or symb.endswith(".SA") or symb == "^GSPC"):
                    try:
                        h5 = t.history(period="5d")
                        if h5 is not None and not h5.empty and "Close" in h5:
                            s5 = h5["Close"].dropna()
                            if len(s5) >= 1:
                                c_date = s5.index[-1].to_pydatetime().date().isoformat()
                    except Exception:
                        c_date = None

                # Em dias úteis, validar frescor real (nunca reciclar candle de pregão anterior como sendo de hoje!)
                if not sem_pregao:
                    eh_ativo_b3 = (symb == "^BVSP" or symb.endswith(".SA"))
                    if eh_ativo_b3 and (not c_date or c_date < data_hoje_iso):
                        print(f"Aviso de frescor para {symb}: candle indisponível ou anterior ({c_date} < {data_hoje_iso}); descartado.")
                        continue
                    if symb == "^GSPC" and (agora_ref.hour * 60 + agora_ref.minute) >= 18 * 60 and (not c_date or c_date < data_hoje_iso):
                        print(f"Aviso de frescor para ^GSPC no fechamento: candle indisponível ou anterior ({c_date} < {data_hoje_iso}); descartado.")
                        continue

                var_pct = ((last_f - prev_f) / prev_f) * 100.0
                item_res = {
                    "last": last_f,
                    "prev": prev_f,
                    "var_pct": float(var_pct),
                    "candle_date": c_date
                }
                if key in var_mes_map:
                    item_res["var_mes_pct"] = var_mes_map[key]
                resultados[key] = item_res
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
    dolar_str = None
    dolar_var = None
    sp500_fut_str = None
    sp500_cash_str = None
    btc_str = None
    brent_str = None
    ibov_str = None

    if cotacoes:
        if "dolar" in cotacoes:
            dolar_str = "R$ " + formatar_numero_br(cotacoes["dolar"]["last"], 2)
            dolar_var = formatar_variacao(cotacoes["dolar"]["var_pct"])[0]
        if "sp500_futuro" in cotacoes:
            sp500_fut_str = formatar_numero_br(cotacoes["sp500_futuro"]["last"], 0) + " pts"
        if "sp500" in cotacoes:
            sp500_cash_str = formatar_numero_br(cotacoes["sp500"]["last"], 0) + " pts"
        if "bitcoin" in cotacoes:
            btc_str = "US$ " + formatar_numero_br(cotacoes["bitcoin"]["last"], 0)
        if "brent" in cotacoes:
            brent_str = "US$ " + formatar_numero_br(cotacoes["brent"]["last"], 2)
        if "ibov" in cotacoes:
            ibov_str = formatar_numero_br(cotacoes["ibov"]["last"], 0) + " pts"

    dolar_txt = f"{dolar_str} ({dolar_var})" if (dolar_str and dolar_var) else "cotação indisponível na consulta"
    dolar_curto = dolar_str or "Indisponível"
    brent_curto = brent_str or "Indisponível"
    btc_curto = btc_str or "Indisponível"
    ibov_curto = ibov_str or "Indisponível"

    sp500_exib_fech = sp500_cash_str if sp500_cash_str else "Indisponível"

    loc_dia = locucao_dia_semana(dia_semana)
    art_dia = artigo_dia_semana(dia_semana)

    if sem_pregao:
        rotulo_pausa = "no fim de semana" if motivo_sem_pregao == "fim_de_semana" else "no feriado nacional B3"
        rotulo_esp = "Especial de Fim de Semana" if motivo_sem_pregao == "fim_de_semana" else "Especial de Feriado B3"
        if ed_key == "abertura":
            return {
                "subtitulo": f"{rotulo_esp} ({loc_dia}): panorama com Dólar em {dolar_curto}, Brent a {brent_curto} e Bitcoin 24h em {btc_curto}",
                "leitura_rapida": [
                    {
                        "texto": f"Com a B3 fechada {rotulo_pausa} ({loc_dia}), o investidor acompanha a agenda do próximo pregão útil, incluindo a divulgação do Boletim Focus pelo Banco Central às segundas-feiras (08h25).",
                        "fonte": "Banco Central",
                        "link": "https://www.bcb.gov.br/publicacoes/focus"
                    },
                    {
                        "texto": f"No mercado cripto — único ativo de liquidez global contínua 24/7 — o Bitcoin opera {loc_dia} em {btc_curto}.",
                        "fonte": "Binance / CoinDesk"
                    },
                    {
                        "texto": f"Referenciais externos no Radar: dólar comercial em {dolar_txt}, S&P 500 em {sp500_exib_fech} e barril de petróleo Brent a {brent_curto}.",
                        "fonte": "Investing",
                        "link": "https://br.investing.com"
                    },
                    {
                        "texto": "Na renda fixa pública, a taxa real do Tesouro IPCA+ 2040 é monitorada continuamente pelo motor quantitativo do Radar de Alocação 2038.",
                        "fonte": "Tesouro Direto",
                        "link": "https://www.tesourodireto.com.br"
                    }
                ],
                "comparacao_anterior": [
                    { "texto": "Agenda de pregão útil: abertura do mercado futuro B3 (09h00) e pregão à vista (10h00)." },
                    { "texto": "Use o simulador educacional de Renda Fixa para comparar taxas brutas e prazos de títulos." }
                ]
            }
        elif ed_key in ["almoco", "negocios"]:
            return {
                "subtitulo": f"Radar Tático do Próximo Pregão ({loc_dia}): estudo quantitativo das 59 ações da B3 e indicadores macroeconômicos",
                "leitura_rapida": [
                    {
                        "texto": f"Durante {art_dia} sem pregão na B3, o Scanner Quantitativo de Swing Trade mantém o consolidado técnico das 59 ações monitoradas.",
                        "fonte": "Scanner B3 CafeRadar"
                    },
                    {
                        "texto": f"No último fechamento disponível, o Ibovespa marcou {ibov_curto}, enquanto o Brent seguiu em {brent_curto} e o câmbio em {dolar_curto}.",
                        "fonte": "B3 / TradeMap",
                        "link": "https://trademap.com.br"
                    },
                    {
                        "texto": "Na calculadora educacional de Renda Fixa, o investidor pode simular cenários com taxas brutas e prazos do Tesouro e CDBs.",
                        "fonte": "Calculadora CafeRadar"
                    },
                    {
                        "texto": f"No exterior, S&P 500 ({sp500_exib_fech}) e Bitcoin ({btc_curto}) integram o painel de monitoramento internacional.",
                        "fonte": "ADVFN",
                        "link": "https://br.advfn.com/jornal"
                    }
                ],
                "comparacao_anterior": [
                    { "texto": "Período sem negociação na B3 permite revisar critérios quantitativos sem ruído intradiário." },
                    { "texto": "Confira na aba Swing Trade (+5%) a tabela completa de auditoria das 59 ações." }
                ]
            }
        else:
            return {
                "subtitulo": f"Balanço Consolidado B3 ({loc_dia}): Ibovespa em {ibov_curto}, Dólar a {dolar_curto} e Bitcoin 24h em {btc_curto}",
                "leitura_rapida": [
                    {
                        "texto": f"Com a bolsa brasileira fechada {rotulo_pausa} ({loc_dia}), a consolidação do último pregão útil registra o Ibovespa em {ibov_curto}.",
                        "fonte": "TradeMap",
                        "link": "https://trademap.com.br"
                    },
                    {
                        "texto": f"No câmbio comercial, o referencial mais recente registra {dolar_txt}.",
                        "fonte": "ADVFN",
                        "link": "https://br.advfn.com/jornal"
                    },
                    {
                        "texto": f"Entre as referências globais, o petróleo Brent marca {brent_curto} e o índice S&P 500 registra {sp500_exib_fech}.",
                        "fonte": "Investing",
                        "link": "https://br.investing.com"
                    },
                    {
                        "texto": f"Em negociação contínua 24h, o Bitcoin opera em {btc_curto}.",
                        "fonte": "Binance / CoinMarketCap"
                    }
                ],
                "comparacao_anterior": [
                    { "texto": f"Painel informativo consolidado disponível para consulta {loc_dia}." },
                    { "texto": "O pregão regular da B3 reabre no próximo dia útil às 10h00 (pré-abertura às 09h45)." }
                ]
            }

    if ed_key == "abertura":
        texto_sp_matinal = (
            f"Nos EUA, os contratos futuros de S&P 500 (ES=F) operam aos {sp500_fut_str} no pré-mercado, enquanto investidores calibram expectativas de juros."
            if sp500_fut_str
            else "Nos EUA, a referência de S&P 500 Futuro encontra-se indisponível na coleta matinal desta manhã, enquanto investidores acompanham os yields globais."
        )
        return {
            "subtitulo": f"Pré-mercado {loc_dia}: Dólar comercial em {dolar_curto}, Brent a {brent_curto} e atenção aos futuros internacionais antes da abertura da B3",
            "leitura_rapida": [
                {
                    "texto": texto_sp_matinal,
                    "fonte": "ADVFN",
                    "link": "https://br.advfn.com/jornal"
                },
                {
                    "texto": f"No câmbio doméstico, o dólar comercial registra {dolar_txt} antes da abertura do mercado à vista, refletindo ajustes na curva de juros.",
                    "fonte": "TradeMap",
                    "link": "https://trademap.com.br"
                },
                {
                    "texto": f"O petróleo Brent é negociado a {brent_curto} o barril, servindo de referência inicial para o setor de energia nesta manhã de {dia_semana}.",
                    "fonte": "Investing",
                    "link": "https://br.investing.com"
                },
                {
                    "texto": f"O Bitcoin (BTC) opera em {btc_curto} no mercado global 24h.",
                    "fonte": "Binance / CoinDesk"
                }
            ],
            "comparacao_anterior": [
                { "texto": f"Abertura do pregão regular à vista da B3 programada para as 10h00 {loc_dia} (leilão de pré-abertura às 09h45)." },
                { "texto": "Cotações de ações e do Ibovespa consolidam-se somente após a abertura da bolsa brasileira." }
            ]
        }
    elif ed_key in ["negocios", "almoco"]:
        texto_sp_abertura = (
            f"Nos contratos futuros de Wall Street, o S&P 500 Futuro marca {sp500_fut_str} antes da abertura regular de Nova York, enquanto o Bitcoin é negociado a {btc_curto}."
            if sp500_fut_str
            else f"O referencial de S&P 500 Futuro (ES=F) encontra-se indisponível na captura atual; o Bitcoin opera em {btc_curto}."
        )
        return {
            "subtitulo": f"Pregão à vista da B3 aberto {loc_dia}; Ibovespa em {ibov_curto} e Dólar a {dolar_curto} na primeira hora de negócios",
            "leitura_rapida": [
                {
                    "texto": f"Com o pregão regular aberto a partir das 10h00 {loc_dia}, o Ibovespa marca {ibov_curto} na primeira hora de negócios com foco no fluxo institucional.",
                    "fonte": "TradeMap",
                    "link": "https://trademap.com.br"
                },
                {
                    "texto": f"Grandes bancos e Vale concentram o giro financeiro da abertura, enquanto petroleiras monitoram o barril de petróleo Brent em {brent_curto}.",
                    "fonte": "Visno Invest",
                    "link": "https://visnoinvest.com.br"
                },
                {
                    "texto": f"No câmbio doméstico, o dólar comercial marca {dolar_txt} nas primeiras cotações, acompanhando os juros futuros.",
                    "fonte": "ADVFN",
                    "link": "https://br.advfn.com/jornal"
                },
                {
                    "texto": texto_sp_abertura,
                    "fonte": "BB InvesTalk"
                }
            ],
            "comparacao_anterior": [
                { "texto": f"Primeira hora de negócios de {dia_semana} registra a formação de preços após a abertura da B3." },
                { "texto": "Os alvos de curto prazo e posições ativas podem ser acompanhados na aba Swing Trade (+5%)." }
            ]
        }
    else: # fechamento
        return {
            "subtitulo": f"Ibovespa encerra {art_dia} aos {ibov_curto}; Dólar fecha a {dolar_curto} e S&P 500 marca {sp500_exib_fech}",
            "leitura_rapida": [
                {
                    "texto": f"A bolsa brasileira encerra as negociações {loc_dia} com o Ibovespa em {ibov_curto}, em pregão marcado por disciplina seletiva dos investidores.",
                    "fonte": "TradeMap",
                    "link": "https://trademap.com.br"
                },
                {
                    "texto": f"No câmbio, o dólar registra {dolar_txt}, refletindo fluxo de capitais e o cenário macroeconômico global.",
                    "fonte": "ADVFN",
                    "link": "https://br.advfn.com/jornal"
                },
                {
                    "texto": f"Entre as commodities, o barril de petróleo Brent finalizou a sessão a {brent_curto}; em Wall Street, o índice S&P 500 registrou {sp500_exib_fech}.",
                    "fonte": "Investing",
                    "link": "https://br.investing.com"
                },
                {
                    "texto": f"No universo cripto, o Bitcoin opera no patamar de {btc_curto}, preservando acompanhamento contínuo pelo motor de longo prazo.",
                    "fonte": "Binance / CoinMarketCap"
                }
            ],
            "comparacao_anterior": [
                { "texto": f"Fechamento {loc_dia} consolida as cotações oficiais do dia na B3." },
                { "texto": "Mercado aguarda a abertura do próximo pregão para novos indicadores." }
            ]
        }

def atualizar_dashboard_nuvem(
    data_ref: str,
    data_fmt: str,
    hora_fmt: str,
    cotacoes: dict | None,
    agora_sp: datetime | None = None,
    root_dir: Path | None = None,
    sem_pregao: bool = False
):
    """
    Atualiza o Radar de Alocação de Longo Prazo (data/dashboard.json).
    Executa SEMPRE em qualquer run do robô com `generated_at` fresco.
    Só carimba `last_close`/`last_sale` com `data_ref` quando a cotação é realmente do pregão de hoje
    (evitando atribuir a data de hoje a um fechamento de ontem às 08h30 ou em FDS/feriado).
    """
    base = root_dir or ROOT
    dash_json = base / "data" / "dashboard.json"
    if not dash_json.is_file():
        print(f"   [AVISO] {dash_json} não encontrado.")
        return

    with open(dash_json, "r", encoding="utf-8") as f:
        dash = json.load(f)

    agora = agora_sp or datetime.now(TZ_SP)
    tempo_min = agora.hour * 60 + agora.minute
    pregao_b3_ativo = (not sem_pregao) and (tempo_min >= 10 * 60)

    dash["generated_at"] = agora.isoformat()
    if sem_pregao:
        dash["status"] = f"● MERCADO B3 FECHADO ({data_fmt}) — Monitoramento 24h Ativo ({hora_fmt})"
    elif pregao_b3_ativo:
        dash["reference_date"] = data_ref
        dash["status"] = f"● MONITORAMENTO DIÁRIO ATIVO — {data_fmt}"
    else:
        dash["status"] = f"● PRÉ-MERCADO ({data_fmt} às {hora_fmt}) — Aguardando Abertura B3"

    ibov_item = cotacoes.get("ibov") if cotacoes else None
    dolar_item = cotacoes.get("dolar") if cotacoes else None
    btc_item = cotacoes.get("bitcoin") if cotacoes else None

    if "indicators" in dash:
        # Ibovespa: só atualiza se B3 abriu hoje E candle_date == data_ref
        if "ibov" in dash["indicators"] and ibov_item is not None and pregao_b3_ativo:
            if ibov_item.get("candle_date") == data_ref:
                dash["indicators"]["ibov"]["last_close"]["date"] = data_ref
                dash["indicators"]["ibov"]["last_close"]["value"] = round(ibov_item["last"], 2)
                dash["indicators"]["ibov"]["last_close_age_calendar_days"] = 0

        # Câmbio: só atualiza data se pregão útil e candle_date == data_ref
        if "ptax_venda" in dash["indicators"] and dolar_item is not None and not sem_pregao:
            if dolar_item.get("candle_date") == data_ref and tempo_min >= 9 * 60:
                dash["indicators"]["ptax_venda"]["last_sale"]["date"] = data_ref
                dash["indicators"]["ptax_venda"]["last_sale"]["value"] = round(dolar_item["last"], 4)

        # Bitcoin 24/7: pode atualizar em qualquer dia se candle_date == data_ref
        if "bitcoin" in dash["indicators"] and btc_item is not None:
            if btc_item.get("candle_date") == data_ref:
                dash["indicators"]["bitcoin"]["last_close"]["date"] = data_ref
                dash["indicators"]["bitcoin"]["last_close"]["value"] = round(btc_item["last"], 2)

    with open(dash_json, "w", encoding="utf-8") as f:
        json.dump(dash, f, ensure_ascii=False, indent=2)

    print(f"   [OK] data/dashboard.json atualizado com sucesso! (generated_at={dash.get('generated_at')})")

def _resetar_edicao_para_novo_dia(
    ed_key: str,
    ed: dict,
    data_ref: str,
    data_fmt: str,
    tempo_min: int,
    sem_pregao: bool
) -> None:
    """
    Zera uma edição herdada de um dia anterior para evitar exibir valores de ontem sob a data de hoje.
    Define disponivel=False, limpa cotações/destaques/bullets e grava data_referencia por edição.
    """
    nome_ed, hora_ed = NOMES_FDS[ed_key] if sem_pregao else NOMES_PADRAO[ed_key]

    ed["data_referencia"] = data_ref
    ed["data_formatada"] = data_fmt
    ed["nome"] = nome_ed
    ed["horario"] = hora_ed
    ed["horario_exibicao"] = hora_ed
    ed["disponivel"] = False
    ed["capturado_em"] = None
    ed.pop("sem_captura_legitima", None)

    if ed_key == "abertura" and tempo_min > 9 * 60 + 45:
        ed["status_publicacao"] = "Sem captura no horário"
        ed["titulo"] = f"RADAR DE {nome_ed.upper()} — {data_fmt}"
        ed["subtitulo"] = f"Edição sem captura registrada na janela matinal de {data_fmt} ({hora_ed})."
    else:
        ed["status_publicacao"] = f"Prevista para as {hora_ed}"
        ed["titulo"] = f"RADAR DE {nome_ed.upper()} — {data_fmt}"
        ed["subtitulo"] = f"Edição de {nome_ed} prevista para as {hora_ed} ({data_fmt})."

    ed["mercado_geral"] = {}
    ed["leitura_rapida"] = []
    ed["comparacao_anterior"] = []
    ed["destaques"] = {
        "titulo": "Destaques entre as blue chips monitoradas",
        "altas": [],
        "quedas": []
    }
    ed["acoes_blue_chips"] = []

def _edicao_eh_de_hoje(ed: dict, data_ref_global: str, data_ref_hoje: str) -> bool:
    dt_cap = _extrair_dt_capturado(ed)
    if dt_cap and dt_cap.date().isoformat() == data_ref_hoje:
        return True
    if ed.get("data_referencia") == data_ref_hoje:
        return True
    return False

def executar_ciclo_nuvem(
    agora_sp: datetime | None = None,
    cotacoes_override: dict | None = None,
    argv: list[str] | None = None,
    root_dir: Path | None = None
) -> dict:
    """
    Executa o ciclo completo da nuvem de forma parametrizável (produção ou simulação determinística).
    """
    base = root_dir or ROOT
    fechamento_json_path = base / "data" / "fechamento.json"
    agora = agora_sp or datetime.now(TZ_SP)
    data_ref = agora.strftime("%Y-%m-%d")
    data_fmt = agora.strftime("%d/%m/%Y")
    tempo_min = agora.hour * 60 + agora.minute
    dia_semana = DIAS_SEMANA_PT[agora.weekday()]
    sem_pregao, motivo_sem_pregao = eh_dia_sem_pregao(agora)

    # 1. Parsing de argumentos
    args = argv if argv is not None else sys.argv[1:]
    ignorar_janela = "--ignorar-janela" in args or "--forcar-imediato" in args
    args_limpos = [a for a in args if not a.startswith("--")]

    arg_forcar = args_limpos[0] if args_limpos and args_limpos[0] in ["auto", "abertura", "negocios", "almoco", "fechamento"] else None
    if arg_forcar == "auto":
        arg_forcar = None

    print("=" * 78)
    print(f"ROBÔ CAFERADAR NUVEM — {data_fmt} ({dia_semana}) às {agora.strftime('%H:%M')} BRT")
    print("=" * 78)

    # 2. Coleta de cotações em tempo real (ou injetada em teste)
    cotacoes = coletar_cotacoes(agora, sem_pregao) if cotacoes_override is None else cotacoes_override

    # =========================================================================
    # ETAPA 1: ATUALIZAÇÃO SEMPRE DO DASHBOARD (RADAR LONGO PRAZO)
    # =========================================================================
    print("\n[ETAPA 1/2] Sincronizando Radar de Alocação de Longo Prazo (data/dashboard.json)...")
    atualizar_dashboard_nuvem(data_ref, data_fmt, agora.strftime("%Hh%M"), cotacoes, agora, base, sem_pregao)

    # =========================================================================
    # ETAPA 2: AVALIAÇÃO E ATUALIZAÇÃO RESTRITA DE EDIÇÕES (DATA/FECHAMENTO.JSON)
    # =========================================================================
    print("\n[ETAPA 2/2] Avaliando atualização de edições de pregão (data/fechamento.json)...")

    if not fechamento_json_path.is_file():
        print(f"   [ERRO CRÍTICO] Arquivo {fechamento_json_path} não encontrado!")
        return {"status": "erro_arquivo"}

    with open(fechamento_json_path, "r", encoding="utf-8") as f:
        dados = json.load(f)

    # Mapeamento e determinação da edição ativa
    if arg_forcar:
        ed_canonica = MAPA_LEGADO_CANONICO.get(arg_forcar, arg_forcar)
        print(f"   [MAPA] Input forçado '{arg_forcar}' mapeado para Edição Canônica '{ed_canonica}'.")
    elif sem_pregao:
        ed_canonica = "fechamento"
        print(f"   [MODO] Sem pregão ({motivo_sem_pregao}) -> Edição Canônica 'fechamento' (Balanço Especial).")
    else:
        if 7 * 60 <= tempo_min <= 9 * 60 + 45:
            ed_canonica = "matinal"
        elif 10 * 60 + 15 <= tempo_min <= 12 * 60:
            ed_canonica = "abertura"
        elif tempo_min >= 18 * 60 + 5:
            ed_canonica = "fechamento"
        else:
            ed_canonica = None

    if not ed_canonica and not ignorar_janela:
        print(f"   [JANELA] Horário atual ({agora.strftime('%H:%M')}) fora de todas as janelas canônicas.")
        print("   [INFO] fechamento.json preservado sem alterações (early return seguro).")
        return {"status": "fora_janela", "dashboard_atualizado": True, "fechamento_alterado": False}

    if not ed_canonica and ignorar_janela:
        ed_canonica = "fechamento"

    # Validação da janela (mesmo para edições forçadas, salvo se acompanhadas de --ignorar-janela)
    janela_valida, msg_janela = validar_janela_edicao(ed_canonica, agora, sem_pregao)
    if not janela_valida and not ignorar_janela:
        print(f"   [BLOQUEIO DE JANELA] {msg_janela}")
        print(f"   [RECUSA] A edição '{ed_canonica}' não pode ser atualizada fora de sua janela sem a flag administrativa --ignorar-janela.")
        return {"status": "bloqueado_janela", "dashboard_atualizado": True, "fechamento_alterado": False}

    # Chaves alvo: em dia útil, restringe-se SEMPRE à edição canônica única (nunca grava todas as 4!)
    chaves_alvo = (
        ["abertura", "negocios", "almoco", "fechamento"]
        if sem_pregao
        else JANELAS_CANONICAS[ed_canonica]["chaves_fechamento"]
    )

    # Checagem de Imutabilidade (Regra C)
    if not ignorar_janela and not sem_pregao:
        for chv in chaves_alvo:
            if chv in dados.get("edicoes", {}):
                ed_atual = dados["edicoes"][chv]
                dt_cap = _extrair_dt_capturado(ed_atual)
                if dt_cap and dt_cap.date() == agora.date():
                    cap_valida, _ = validar_janela_edicao(ed_canonica, dt_cap, False)
                    if cap_valida:
                        print(f"   [IMUTABILIDADE] Edição '{ed_canonica}' (chave '{chv}') já possui captura oficial hoje às {dt_cap.strftime('%H:%M')}.")
                        print("   [PRESERVAÇÃO] Snapshot legítimo mantido. Nenhuma regravação necessária.")
                        return {"status": "imutavel", "dashboard_atualizado": True, "fechamento_alterado": False}

    data_ref_anterior = dados.get("data_referencia", "")
    virou_dia = (data_ref_anterior != data_ref)

    # Limpeza segura de virada de dia para edições NÃO ativas que ainda têm dados de dias anteriores
    edicoes_resetadas = []
    if not sem_pregao and "edicoes" in dados:
        for ed_k in ["abertura", "negocios", "almoco", "fechamento"]:
            if ed_k not in dados["edicoes"] or ed_k in chaves_alvo:
                continue
            ed_other = dados["edicoes"][ed_k]
            if virou_dia or not _edicao_eh_de_hoje(ed_other, data_ref_anterior, data_ref):
                _resetar_edicao_para_novo_dia(ed_k, ed_other, data_ref, data_fmt, tempo_min, sem_pregao)
                edicoes_resetadas.append(ed_k)

    if edicoes_resetadas:
        print(f"   [VIRADA DE DIA] Edições de dias anteriores zeradas para {data_fmt}: {', '.join(edicoes_resetadas)}")

    # Montar destaques reais honestos com filtro estrito de sinal (> 0 altas, < 0 quedas)
    altas_reais = []
    quedas_reais = []
    if cotacoes and (ed_canonica != "matinal" or sem_pregao):
        acoes_lista = []
        for ticker, _ in BLUE_CHIPS_MONITORADAS:
            if ticker in cotacoes:
                acoes_lista.append((ticker, cotacoes[ticker]["var_pct"]))
        if acoes_lista:
            acoes_lista.sort(key=lambda x: x[1], reverse=True)
            for t, v_pct in [a for a in acoes_lista if a[1] > 0][:2]:
                altas_reais.append({"ticker": t, "variacao": f"+{v_pct:.2f}%".replace(".", ",")})
            for t, v_pct in sorted([a for a in acoes_lista if a[1] < 0], key=lambda x: x[1])[:2]:
                quedas_reais.append({"ticker": t, "variacao": f"{v_pct:.2f}%".replace(".", ",")})

    capturado_em_iso = agora.isoformat()
    edicao_padrao_alvo = "negocios" if ed_canonica == "abertura" else ("abertura" if ed_canonica == "matinal" else "fechamento")
    dados["edicao_padrao"] = edicao_padrao_alvo
    dados["data_referencia"] = data_ref
    dados["data_formatada"] = data_fmt
    dados["dia_semana"] = dia_semana
    dados["fim_de_semana"] = sem_pregao
    dados["modo_mercado"] = motivo_sem_pregao

    edicoes_modificadas = []

    if "edicoes" in dados:
        for ed_key in chaves_alvo:
            if ed_key not in dados["edicoes"]:
                continue
            ed = dados["edicoes"][ed_key]

            if sem_pregao:
                nome_ed, hora_ed = NOMES_FDS[ed_key]
                ed["nome"] = nome_ed
                ed["horario_exibicao"] = hora_ed
                ed["titulo"] = f"{'ESPECIAL DE FIM DE SEMANA' if motivo_sem_pregao == 'fim_de_semana' else 'ESPECIAL DE FERIADO B3'}: {nome_ed.upper()} — {data_fmt}"
            else:
                nome_ed, hora_ed = NOMES_PADRAO[ed_key]
                ed["nome"] = nome_ed
                ed["horario"] = hora_ed
                ed["horario_exibicao"] = hora_ed
                ed["titulo"] = f"RADAR DE {nome_ed.upper()} — {data_fmt}"

            ed["data_referencia"] = data_ref
            ed["data_formatada"] = data_fmt
            ed["disponivel"] = True
            ed["status_publicacao"] = "Publicado"
            ed["capturado_em"] = capturado_em_iso
            ed.pop("sem_captura_legitima", None)

            conteudo = gerar_conteudo_dinamico(ed_key, dia_semana, data_fmt, cotacoes, sem_pregao, motivo_sem_pregao)
            ed["subtitulo"] = conteudo["subtitulo"]
            ed["leitura_rapida"] = conteudo["leitura_rapida"]
            ed["comparacao_anterior"] = conteudo["comparacao_anterior"]

            if ed_canonica == "matinal" and not sem_pregao:
                ed["destaques"] = {
                    "titulo": "Destaques entre as blue chips monitoradas",
                    "altas": [],
                    "quedas": []
                }
                ed["acoes_blue_chips"] = []
            else:
                ed["destaques"] = {
                    "titulo": "Destaques entre as blue chips monitoradas",
                    "altas": altas_reais,
                    "quedas": quedas_reais
                }

            mg = ed.setdefault("mercado_geral", {})

            # 1. Ibovespa: ausente na matinal (08h00); presente em abertura e fechamento
            if ed_canonica == "matinal" and not sem_pregao:
                mg.pop("ibov", None)
            elif cotacoes and "ibov" in cotacoes:
                v = cotacoes["ibov"]
                mg.setdefault("ibov", {"nome": "Ibovespa"})
                mg["ibov"]["pontos"] = formatar_numero_br(v["last"], 0) + " pts"
                mg["ibov"]["valor"] = formatar_numero_br(v["last"], 0) + " pts"
                mg["ibov"]["variacao"], mg["ibov"]["positivo"] = formatar_variacao(v["var_pct"])
            else:
                mg["ibov"] = {"nome": "Ibovespa", "pontos": "Indisponível", "valor": "Indisponível", "variacao": "—", "positivo": None}

            # 2. Dólar comercial
            if cotacoes and "dolar" in cotacoes:
                v = cotacoes["dolar"]
                var_dl, pos_dl = formatar_variacao(v["var_pct"])
                mg["dolar"] = {
                    "nome": "Dólar Comercial",
                    "valor": "R$ " + formatar_numero_br(v["last"], 2),
                    "variacao": var_dl,
                    "positivo": pos_dl
                }
            else:
                mg["dolar"] = {"nome": "Dólar Comercial", "valor": "Indisponível", "variacao": "—", "positivo": None}

            # 3. S&P 500: matinal/abertura usam EXCLUSIVAMENTE ES=F (Futuro); fechamento usa apenas ^GSPC
            if ed_canonica in ("matinal", "abertura") and not sem_pregao:
                if cotacoes and "sp500_futuro" in cotacoes:
                    v = cotacoes["sp500_futuro"]
                    var_sp, pos_sp = formatar_variacao(v["var_pct"])
                    mg["sp500"] = {
                        "nome": "S&P 500 Futuro",
                        "valor": formatar_numero_br(v["last"], 0) + " pts",
                        "variacao": var_sp,
                        "positivo": pos_sp
                    }
                else:
                    mg["sp500"] = {
                        "nome": "S&P 500 Futuro",
                        "valor": "Indisponível",
                        "variacao": "—",
                        "positivo": None
                    }
            else:
                if cotacoes and "sp500" in cotacoes:
                    v = cotacoes["sp500"]
                    var_sp, pos_sp = formatar_variacao(v["var_pct"])
                    mg["sp500"] = {
                        "nome": "S&P 500",
                        "valor": formatar_numero_br(v["last"], 0) + " pts",
                        "variacao": var_sp,
                        "positivo": pos_sp
                    }
                else:
                    mg["sp500"] = {
                        "nome": "S&P 500",
                        "valor": "Indisponível",
                        "variacao": "—",
                        "positivo": None
                    }

            # 4. Bitcoin (BTC)
            if cotacoes and "bitcoin" in cotacoes:
                v = cotacoes["bitcoin"]
                var_btc, pos_btc = formatar_variacao(v["var_pct"])
                mg["bitcoin"] = {
                    "nome": "Bitcoin (BTC)",
                    "valor": "US$ " + formatar_numero_br(v["last"], 0),
                    "variacao": var_btc,
                    "positivo": pos_btc
                }
            else:
                mg["bitcoin"] = {"nome": "Bitcoin (BTC)", "valor": "Indisponível", "variacao": "—", "positivo": None}

            # 5. Petróleo Brent
            if cotacoes and "brent" in cotacoes:
                v = cotacoes["brent"]
                var_br, pos_br = formatar_variacao(v["var_pct"])
                mg["brent"] = {
                    "nome": "Petróleo Brent",
                    "valor": "US$ " + formatar_numero_br(v["last"], 2),
                    "variacao": var_br,
                    "positivo": pos_br
                }
            else:
                mg["brent"] = {"nome": "Petróleo Brent", "valor": "Indisponível", "variacao": "—", "positivo": None}

            # 6. Blue chips (reconstruída com dados vivos em abertura/fechamento; nunca mantida de ontem)
            if ed_canonica != "matinal" or sem_pregao:
                nova_tabela = []
                if cotacoes:
                    for ticker, nome_papel in BLUE_CHIPS_MONITORADAS:
                        if ticker in cotacoes:
                            v = cotacoes[ticker]
                            var_dia_s, pos_d = formatar_variacao(v["var_pct"])
                            var_mes_s = formatar_variacao(v["var_mes_pct"])[0] if "var_mes_pct" in v else "—"
                            nova_tabela.append({
                                "ticker": ticker,
                                "nome": nome_papel,
                                "preco": "R$ " + formatar_numero_br(v["last"], 2),
                                "variacao_dia": var_dia_s,
                                "variacao_mes": var_mes_s,
                                "positivo": pos_d
                            })
                ed["acoes_blue_chips"] = nova_tabela

            edicoes_modificadas.append(ed_key)

    with open(fechamento_json_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    print(f"   [OK] data/fechamento.json gravado com sucesso! Edições atualizadas: {', '.join(edicoes_modificadas)}")
    print(f"   [CARIMBO] capturado_em={capturado_em_iso}")
    return {
        "status": "atualizado",
        "dashboard_atualizado": True,
        "fechamento_alterado": True,
        "edicoes_modificadas": edicoes_modificadas,
        "edicoes_resetadas": edicoes_resetadas,
        "capturado_em": capturado_em_iso
    }

def main():
    executar_ciclo_nuvem()

if __name__ == "__main__":
    main()
