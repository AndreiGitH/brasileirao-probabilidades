"""Odds atuais dos próximos jogos: https://the-odds-api.com (plano grátis: 500 créditos/mês).

Cada atualização gasta 1 crédito (região "eu", mercado "h2h"). A região eu
inclui Pinnacle ("pinnacle") e Betfair Exchange ("betfair_ex_eu"), as duas
referências mais precisas. Coloque a chave em .env: ODDS_API_KEY=...
A lista de campeonatos (/v4/sports) não gasta crédito.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import pandas as pd
import requests

from .. import RAIZ
from ..times import padronizar
from ._http import USER_AGENT

BASE = "https://api.the-odds-api.com/v4"
CHAVE_PADRAO = "soccer_brazil_campeonato"


def _chave_api() -> str:
    chave = os.environ.get("ODDS_API_KEY")
    env = RAIZ / ".env"
    if not chave and env.exists():
        for linha in env.read_text().splitlines():
            if linha.startswith("ODDS_API_KEY="):
                chave = linha.split("=", 1)[1].strip().strip('"')
    if not chave:
        raise RuntimeError("Defina ODDS_API_KEY (chave grátis em the-odds-api.com) no .env")
    return chave


def _get(caminho: str, **params) -> tuple[object, dict]:
    params["apiKey"] = _chave_api()
    r = requests.get(f"{BASE}{caminho}", params=params, timeout=60,
                     headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.json(), r.headers


def chave_brasileirao(esportes: list[dict]) -> str:
    """Acha a chave da Série A na lista de campeonatos (sem gastar crédito)."""
    for e in esportes:
        titulo = f"{e.get('title', '')} {e.get('description', '')}".lower()
        if (e.get("group") == "Soccer" and "brazil" in titulo
                and "rie a" in titulo and "rie b" not in titulo):
            return e["key"]
    return CHAVE_PADRAO


def parse(eventos: list[dict], coletado_em: str) -> pd.DataFrame:
    """Formato longo: uma linha por jogo e por casa de apostas."""
    linhas = []
    for ev in eventos:
        mand, vis = ev["home_team"], ev["away_team"]
        data = (pd.Timestamp(ev["commence_time"]).tz_convert("America/Sao_Paulo")
                .tz_localize(None).normalize())
        for casa in ev.get("bookmakers", []):
            for mercado in casa.get("markets", []):
                if mercado.get("key") != "h2h":
                    continue
                precos = {o["name"]: o["price"] for o in mercado.get("outcomes", [])}
                if not {mand, vis, "Draw"} <= precos.keys():
                    continue
                linhas.append({
                    "data": data,
                    "mandante": padronizar(mand),
                    "visitante": padronizar(vis),
                    "casa_apostas": casa["key"],
                    "odd_casa": float(precos[mand]),
                    "odd_empate": float(precos["Draw"]),
                    "odd_fora": float(precos[vis]),
                    "atualizado": mercado.get("last_update") or casa.get("last_update"),
                    "coletado_em": coletado_em,
                })
    return pd.DataFrame(linhas)


def coletar() -> pd.DataFrame:
    esportes, _ = _get("/sports")
    chave = chave_brasileirao(esportes)
    eventos, headers = _get(f"/sports/{chave}/odds", regions="eu", markets="h2h",
                            oddsFormat="decimal")
    restantes = headers.get("x-requests-remaining")
    if restantes is not None:
        print(f"The Odds API: {restantes} créditos restantes no mês")
    agora = datetime.now(UTC).isoformat(timespec="seconds")
    return parse(eventos, agora)


def parse_arquivo(caminho) -> pd.DataFrame:
    """Para testes e reprocessamento: lê uma resposta salva de /odds."""
    with open(caminho, encoding="utf-8") as f:
        return parse(json.load(f), "arquivo")
