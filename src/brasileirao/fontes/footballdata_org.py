"""Temporada corrente (calendário e placares) pela API https://www.football-data.org

Plano gratuito: cadastre-se em football-data.org e coloque o token na variável
de ambiente FOOTBALL_DATA_TOKEN (ou no arquivo .env na raiz do projeto).
Competição Brasileirão Série A = código "BSA".
"""

from __future__ import annotations

import json
import os

import pandas as pd

from .. import RAIZ
from ..esquema import normalizar
from ..times import TimeDesconhecido, padronizar
from ._http import baixar

URL = "https://api.football-data.org/v4/competitions/BSA/matches?season={ano}"


def _token() -> str:
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    env = RAIZ / ".env"
    if not token and env.exists():
        for linha in env.read_text().splitlines():
            if linha.startswith("FOOTBALL_DATA_TOKEN="):
                token = linha.split("=", 1)[1].strip().strip('"')
    if not token:
        raise RuntimeError(
            "Defina FOOTBALL_DATA_TOKEN (token gratuito em football-data.org) "
            "no ambiente ou no arquivo .env"
        )
    return token


def _nome(time: dict) -> str:
    # Tenta o nome completo e depois o curto; o padronizador decide.
    for chave in ("name", "shortName", "tla"):
        valor = time.get(chave)
        if valor:
            try:
                return padronizar(valor)
            except TimeDesconhecido:
                continue
    raise TimeDesconhecido(f"Clube sem nome canônico: {time}")


def parse(conteudo: bytes, ano: int) -> pd.DataFrame:
    linhas = []
    for j in json.loads(conteudo)["matches"]:
        ft = (j.get("score") or {}).get("fullTime") or {}
        terminado = j.get("status") == "FINISHED"
        linhas.append({
            "temporada": ano,
            "rodada": j.get("matchday"),
            "data": j["utcDate"],
            "mandante": _nome(j["homeTeam"]),
            "visitante": _nome(j["awayTeam"]),
            "gols_mandante": ft.get("home") if terminado else None,
            "gols_visitante": ft.get("away") if terminado else None,
        })
    df = pd.DataFrame(linhas)
    # Data UTC -> horário de Brasília antes de descartar a hora (jogo às 22h30 BRT
    # cai no dia seguinte em UTC).
    df["data"] = pd.to_datetime(df["data"], utc=True).dt.tz_convert("America/Sao_Paulo")
    return normalizar(df, fonte="football-data.org")


def coletar(ano: int) -> pd.DataFrame:
    conteudo = baixar(URL.format(ano=ano), headers={"X-Auth-Token": _token()},
                      max_idade_h=1, nome=f"footballdata_org_{ano}.json")
    return parse(conteudo, ano)
