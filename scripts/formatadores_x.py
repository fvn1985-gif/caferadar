"""
Módulo utilitário para formatar textos curtos (<= 280 caracteres) estritamente para o X (Twitter),
garantindo que o usuário consiga colar com 1 clique direto no X sem erro de tamanho.
"""
from typing import Dict, Any, List

def formatar_tweet_negocios(dados_fechamento: Dict[str, Any], data_fmt: str) -> str:
    ed = dados_fechamento.get("edicoes", {}).get("fechamento", {})
    mercados = ed.get("mercado_geral", {})
    blue_chips = ed.get("acoes_blue_chips", [])
    
    ibov = mercados.get("ibov", {})
    dolar = mercados.get("dolar", {})
    
    ibov_txt = f"{ibov.get('pontos', '—')} ({ibov.get('variacao', '—')})"
    dol_txt = f"{dolar.get('valor', '—')} ({dolar.get('variacao', '—')})"
    
    chips_list = []
    for c in blue_chips[:3]:
        if c.get("ticker"):
            chips_list.append(f"${c.get('ticker')}: {c.get('variacao_dia', '')}")
    chips_txt = " | ".join(chips_list) if chips_list else "Acompanhe ao vivo"
    
    tweet = (
        f"🔔 Abertura B3 ({data_fmt})\n\n"
        f"📊 Ibov: {ibov_txt}\n"
        f"💵 Dólar: {dol_txt}\n\n"
        f"Blue chips: {chips_txt}\n\n"
        f"Scanner ao vivo:\n"
        f"🔗 https://caferadar.com.br\n\n"
        f"#B3 #Acoes #CafeRadar"
    )
    return tweet.strip()

def formatar_tweet_calculadora(data_fmt: str) -> str:
    tweet = (
        f"💡 Poupança vs Tesouro Selic?\n\n"
        f"Em 2 anos, R$ 10 mil na poupança perdem quase R$ 2.000 para o Selic e CDB 100% CDI.\n\n"
        f"Simule grátis com desconto automático de IR:\n"
        f"🔗 https://caferadar.com.br/calculadora-rendimento.html\n\n"
        f"#RendaFixa #Investimentos #CafeRadar"
    )
    return tweet.strip()

def formatar_tweet_fechamento(dados_fechamento: Dict[str, Any], data_fmt: str) -> str:
    ed = dados_fechamento.get("edicoes", {}).get("fechamento", {})
    mercados = ed.get("mercado_geral", {})
    destaques = ed.get("destaques", {})
    
    ibov = mercados.get("ibov", {})
    dolar = mercados.get("dolar", {})
    altas = destaques.get("altas", [])
    quedas = destaques.get("quedas", [])
    
    ibov_txt = f"{ibov.get('pontos', '—')} ({ibov.get('variacao', '—')})"
    dol_txt = f"{dolar.get('valor', '—')} ({dolar.get('variacao', '—')})"
    
    altas_txt = ", ".join([f"${a.get('ticker')}" for a in altas[:2]]) if altas else "—"
    quedas_txt = ", ".join([f"${b.get('ticker')}" for b in quedas[:2]]) if quedas else "—"
    
    tweet = (
        f"🌙 Fechamento B3 ({data_fmt})\n\n"
        f"📊 Ibov: {ibov_txt}\n"
        f"💵 Dólar: {dol_txt}\n\n"
        f"🚀 Altas: {altas_txt}\n"
        f"📉 Baixas: {quedas_txt}\n\n"
        f"Dados e scanners completos:\n"
        f"🔗 https://caferadar.com.br\n\n"
        f"#B3 #Ibovespa #CafeRadar"
    )
    return tweet.strip()

def formatar_tweet_longoprazo(dados_dashboard: Dict[str, Any], data_base_br: str) -> str:
    alocacao = dados_dashboard.get("allocation", {})
    ipca = alocacao.get("Tesouro IPCA+ 2040", 60)
    ivvb = alocacao.get("IVVB11", 30)
    btc = alocacao.get("Bitcoin", 10)
    
    tweet = (
        f"🧭 Radar Macro & Alocação ({data_base_br})\n\n"
        f"Ponderação conceitual para aportes:\n"
        f"• IPCA+: {ipca}%\n"
        f"• IVVB11 (S&P 500): {ivvb}%\n"
        f"• Bitcoin: {btc}%\n\n"
        f"Simulador e estudos quantitativos:\n"
        f"🔗 https://caferadar.com.br\n\n"
        f"#LongoPrazo #Investimentos #CafeRadar"
    )
    return tweet.strip()

def formatar_tweet_swingtrade(resumo: Dict[str, Any], data_fmt: str) -> str:
    tweet = (
        f"🎯 Scanner Swing Trade (+5%) — {data_fmt}\n\n"
        f"• Ativação Imediata: {resumo.get('oportunidades', 0)}\n"
        f"• Em Observação: {resumo.get('ressalvas', 0)}\n"
        f"• Filtro Restritivo: {resumo.get('desfavoravel', 0)}\n\n"
        f"Confira a auditoria com 100% dos trades públicos:\n"
        f"🔗 https://caferadar.com.br/historico-swing.html\n\n"
        f"#SwingTrade #B3 #CafeRadar"
    )
    return tweet.strip()
