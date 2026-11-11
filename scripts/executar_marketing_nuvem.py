#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/executar_marketing_nuvem.py
===================================
Orquestrador de Geração de Cards PNG do Portal na Nuvem (GitHub Actions).
Gera automaticamente os cards *_x.png das edições disponíveis em data/fechamento.json
para manter o portal caferadar.com.br com imagens atualizadas sem depender do PC local.
Não realiza disparo automático para Telegram/X.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
OUTPUT_DIR = BASE_DIR / "marketing_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SCRIPTS_DIR))

try:
    import gerar_marketing
except ImportError as err:
    print(f"AVISO: Módulo gerar_marketing não pôde ser carregado: {err}")
    sys.exit(1)

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _coletar_categorias_disponiveis(fechamento_path: Path) -> list[str]:
    """Identifica todas as edições disponíveis hoje em data/fechamento.json."""
    if not fechamento_path.is_file():
        return []
    try:
        dados = json.loads(fechamento_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    edicoes = dados.get("edicoes", {})
    mapa = [
        ("abertura", "abertura"),
        ("negocios", "negocios"),
        ("almoco", "negocios"),
        ("fechamento", "fechamento"),
    ]
    cats: list[str] = []
    for chave_json, cat in mapa:
        ed = edicoes.get(chave_json)
        if not isinstance(ed, dict):
            continue
        if ed.get("disponivel") is True and ed.get("sem_captura_legitima") is not True:
            if cat not in cats:
                cats.append(cat)
    return cats


def main() -> int:
    agora_sp = datetime.now(TZ_SP)
    hora_str = agora_sp.strftime("%Hh%M")
    tempo_min = agora_sp.hour * 60 + agora_sp.minute

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arg_edicao = args[0] if args else "auto"

    if arg_edicao in ["abertura", "negocios", "fechamento", "swing", "longoprazo", "calculadora"]:
        edicao = arg_edicao
    elif arg_edicao == "swingtrade":
        edicao = "swing"
    elif arg_edicao == "almoco":
        edicao = "negocios"
    elif tempo_min < 10 * 60:
        edicao = "abertura"
    elif tempo_min < 18 * 60:
        edicao = "negocios"
    else:
        edicao = "fechamento"

    categorias: list[str] = []
    if edicao in ("abertura", "negocios", "fechamento", "calculadora", "swing", "longoprazo"):
        if arg_edicao != "auto" or not _coletar_categorias_disponiveis(BASE_DIR / "data" / "fechamento.json"):
            categorias.append(edicao)

    # Garante cards para todas as edições do dia já marcadas como disponíveis no JSON
    for cat_disp in _coletar_categorias_disponiveis(BASE_DIR / "data" / "fechamento.json"):
        if cat_disp not in categorias:
            categorias.append(cat_disp)

    print("====================================================================")
    print("   CAFÉ RADAR — GERAÇÃO DE CARDS DO PORTAL NA NUVEM")
    print(f"   Horário Brasília: {hora_str} | Modo: {edicao.upper()} | Categorias: {categorias}")
    print("====================================================================")

    rc = gerar_marketing.main(categorias=categorias, output_dir=OUTPUT_DIR)
    if rc != 0:
        print(f"AVISO: gerar_marketing retornou código {rc}")
        return rc

    print("\n[SUCESSO] Cards PNG do portal atualizados em marketing_output/ (sem envio ao Telegram).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
