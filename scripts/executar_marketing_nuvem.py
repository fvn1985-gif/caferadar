#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/executar_marketing_nuvem.py
===================================
Orquestrador de Geração de Cards de Marketing e Disparo para o Telegram na Nuvem (GitHub Actions).

Horários Principais:
  - 10h00 Brasília: Abertura B3 -> Gera e dispara Card 16:9 (X) + Legenda de Abertura para o Telegram.
  - 18h15 Brasília: Fechamento B3 -> Gera e dispara Card 16:9 (X) + Legenda de Fechamento e Swing Trade.
"""

from __future__ import annotations

import os
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

# Garante que scripts/ está no PYTHONPATH para importar os módulos
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    import gerar_marketing
    import publicar_telegram
except ImportError as err:
    print(f"AVISO: Módulos de marketing não puderam ser carregados: {err}")
    sys.exit(0)

TZ_SP = ZoneInfo("America/Sao_Paulo")


def main():
    agora_sp = datetime.now(TZ_SP)
    hora_str = agora_sp.strftime("%Hh%M")
    tempo_min = agora_sp.hour * 60 + agora_sp.minute

    arg_edicao = sys.argv[1] if len(sys.argv) > 1 else "auto"

    if arg_edicao in ["abertura", "fechamento", "swingtrade", "almoco", "longoprazo"]:
        edicao = arg_edicao
    elif tempo_min < 12 * 60:
        edicao = "abertura"
    elif tempo_min < 17 * 60 + 30:
        edicao = "almoco"
    else:
        edicao = "fechamento"

    print("====================================================================")
    print(f"   CAFÉ RADAR — MARKETING ENGINE & TELEGRAM NA NUVEM")
    print(f"   Horário Brasília: {hora_str} | Modo: {edicao.upper()}")
    print("====================================================================")

    # 1. Definir quais categorias serão geradas
    if edicao == "abertura":
        categorias = ["abertura"]
    elif edicao == "fechamento":
        categorias = ["fechamento", "swingtrade"]
    elif edicao == "swingtrade":
        categorias = ["swingtrade"]
    elif edicao == "almoco":
        categorias = ["abertura"]
    else:
        categorias = [edicao]

    print(f"\n[1/2] Gerando cards visuais e legendas estruturadas para: {categorias}...")
    gerar_marketing.main(categorias=categorias, output_dir=OUTPUT_DIR)

    # 2. Verificar credenciais do Telegram
    ok_creds, _, msg_creds = publicar_telegram.carregar_credenciais_telegram()
    if not ok_creds:
        print(f"\n[INFO] {msg_creds}")
        print("       Disparo para o Telegram pulado. O site foi atualizado normalmente.")
        return 0

    print("\n[2/2] Disparando publicações formatadas para o X no Telegram...")
    if edicao == "abertura":
        publicar_telegram.publicar_material_categoria(
            categoria="abertura",
            formato="x",
            output_dir=OUTPUT_DIR
        )
    elif edicao == "fechamento":
        publicar_telegram.publicar_material_categoria(
            categoria="fechamento",
            formato="x",
            output_dir=OUTPUT_DIR
        )
        publicar_telegram.publicar_material_categoria(
            categoria="swingtrade",
            formato="x",
            output_dir=OUTPUT_DIR
        )
    elif edicao == "swingtrade":
        publicar_telegram.publicar_material_categoria(
            categoria="swingtrade",
            formato="x",
            output_dir=OUTPUT_DIR
        )
    else:
        print(f"Nenhum disparo agendado para o modo {edicao}.")

    print("\n[SUCESSO] Processo de marketing na nuvem concluído com êxito!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
