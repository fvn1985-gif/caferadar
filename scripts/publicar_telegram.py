#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/publicar_telegram.py
==========================
Módulo de Disparo Automático para o Canal Oficial do Telegram (Café Radar).

Funcionalidades:
  - Carrega credenciais (TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID) do .env.
  - Envia card PNG de alta resolução acompanhado de legenda formatada com emojis, cashtags e link.
  - Suporta as categorias: fechamento, abertura, swing, longoprazo.
  - Modo seguro (--dry-run).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Tuple

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

if (BASE_DIR / "marketing_output").is_dir():
    DEFAULT_OUTPUT_DIR = BASE_DIR / "marketing_output"
elif (BASE_DIR / "web" / "marketing_output").is_dir():
    DEFAULT_OUTPUT_DIR = BASE_DIR / "web" / "marketing_output"
else:
    DEFAULT_OUTPUT_DIR = BASE_DIR / "marketing_output"


def carregar_credenciais_telegram(caminho: Optional[Path] = None) -> Tuple[bool, dict, str]:
    """
    Carrega as credenciais do Telegram.
    Prioridade 1: Variáveis de ambiente (ex: GitHub Actions Secrets).
    Prioridade 2: Arquivo .env local.
    """
    token_env = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id_env = os.environ.get("TELEGRAM_CHAT_ID")
    if token_env and chat_id_env:
        return True, {"token": token_env.strip(), "chat_id": chat_id_env.strip()}, "OK (Ambiente)"

    p = caminho or ENV_PATH
    if not p.is_file():
        return False, {}, f"Arquivo .env não encontrado em: {p} e variáveis de ambiente não definidas."

    creds = {}
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if "=" in linha:
            k, v = linha.split("=", 1)
            creds[k.strip()] = v.strip()

    token = creds.get("TELEGRAM_BOT_TOKEN")
    chat_id = creds.get("TELEGRAM_CHAT_ID")

    if not token:
        return False, {}, "Variável TELEGRAM_BOT_TOKEN não encontrada no .env nem no ambiente"
    if not chat_id:
        return False, {}, "Variável TELEGRAM_CHAT_ID não encontrada no .env nem no ambiente"

    return True, {"token": token, "chat_id": chat_id}, "OK (.env)"


def enviar_foto_telegram(token: str, chat_id: str, caminho_foto: Path, legenda: str, dry_run: bool = False) -> Tuple[bool, str]:
    """Envia uma foto com legenda para o canal do Telegram via API oficial."""
    if dry_run:
        return True, f"[DRY-RUN] Simulação de envio para o chat {chat_id} com sucesso."

    if not caminho_foto.is_file():
        return False, f"Arquivo de foto não encontrado: {caminho_foto}"

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    # O limite de legenda com foto no Telegram é de 1024 caracteres
    legenda_envio = legenda
    if len(legenda_envio) > 1024:
        legenda_envio = legenda_envio[:1020] + "..."

    try:
        with open(caminho_foto, "rb") as foto:
            dados = {
                "chat_id": chat_id,
                "caption": legenda_envio
            }
            arquivos = {"photo": foto}
            resp = requests.post(url, data=dados, files=arquivos, timeout=30)

        if resp.status_code == 200 and resp.json().get("ok"):
            return True, "Mensagem e foto enviadas com sucesso ao canal do Telegram!"
        else:
            return False, f"Falha no envio (HTTP {resp.status_code}): {resp.text}"
    except Exception as e:
        return False, f"Erro de conexão com a API do Telegram: {e}"


def publicar_material_categoria(
    categoria: str = "fechamento",
    formato: str = "x",
    output_dir: Optional[Path] = None,
    dry_run: bool = False
) -> int:
    """Localiza o material homologado mais recente e dispara para o Telegram."""
    ok, creds, msg = carregar_credenciais_telegram()
    if not ok:
        print(f"AVISO: {msg}", file=sys.stderr)
        return 0

    c_raw = categoria.lower()
    if c_raw in ["swing", "swingtrade", "scanner"]:
        cat = "swingtrade"
    elif c_raw in ["longo", "longoprazo", "alocacao", "radar"]:
        cat = "longoprazo"
    elif c_raw in ["manha", "matinal", "abertura"]:
        cat = "abertura"
    else:
        cat = c_raw

    out = Path(output_dir or DEFAULT_OUTPUT_DIR)

    fmt_escolhido = formato.lower()
    if fmt_escolhido == "x":
        arquivos_img = sorted(out.glob(f"*_{cat}_x.png"))
        if not arquivos_img:
            arquivos_img = sorted(out.glob(f"*_{cat}_feed.png"))
    else:
        arquivos_img = sorted(out.glob(f"*_{cat}_feed.png"))
        if not arquivos_img:
            arquivos_img = sorted(out.glob(f"*_{cat}_x.png"))

    arquivos_txt = sorted(out.glob(f"*_{cat}_legenda.txt"))

    if not arquivos_img or not arquivos_txt:
        print(f"AVISO: Materiais para '{categoria}' não encontrados em {out}")
        return 0

    img_path = arquivos_img[-1]
    txt_path = arquivos_txt[-1]

    legenda = txt_path.read_text(encoding="utf-8")

    print("====================================================================")
    print(f"       CAFÉ RADAR — DISPARO AUTOMÁTICO TELEGRAM [{categoria.upper()} / {fmt_escolhido.upper()}]")
    print("====================================================================")
    print(f"Canal Alvo: {creds['chat_id']}")
    print(f"Imagem: {img_path.name}")
    print(f"Tamanho da Legenda: {len(legenda)} caracteres")

    if dry_run:
        print("Modo --dry-run ativo. Nenhuma mensagem real será enviada.")
        return 0

    print("\nEnviando para o Telegram...")
    sucesso, ret_msg = enviar_foto_telegram(creds["token"], creds["chat_id"], img_path, legenda)
    
    if sucesso:
        print(f"\n[SUCESSO COMPLETO!] {ret_msg}")
        return 0
    else:
        print(f"\n[FALHA NO DISPARO]: {ret_msg}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    args = sys.argv[1:]
    dry = "--dry-run" in args
    
    formato_arg = "x"
    if "--formato" in args:
        idx = args.index("--formato")
        if idx + 1 < len(args):
            formato_arg = args[idx + 1]

    output_arg = None
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            output_arg = Path(args[idx + 1])

    cat_args = [a for a in args if not a.startswith("--") and a not in ["x", "feed"] and (output_arg is None or a != str(output_arg))]
    categoria_escolhida = cat_args[0] if cat_args else "fechamento"
    
    sys.exit(publicar_material_categoria(
        categoria=categoria_escolhida,
        formato=formato_arg,
        output_dir=output_arg,
        dry_run=dry
    ))
