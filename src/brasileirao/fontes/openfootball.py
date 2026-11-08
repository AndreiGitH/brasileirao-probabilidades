"""Temporadas em https://github.com/openfootball/football.json (formato football.db).

Fonte aberta e acessível de qualquer lugar, mas atualizada manualmente:
pode ficar algumas rodadas atrasada. Para a temporada corrente, prefira
football-data.org (ver footballdata_org.py).
"""

from __future__ import annotations

import json

import pandas as pd

from ..esquema import normalizar
from ._http import baixar

URL = "https://raw.githubusercontent.com/openfootball/football.json/master/{ano}/br.1.json"


def _placar(score) -> tuple[int | None, int | None]:
    # O arquivo usa dois formatos: {"ft": [a, b], "ht": [...]} ou só [a, b].
    if score is None:
        return None, None
    ft = score.get("ft") if isinstance(score, dict) else score
    if not ft:
        return None, None
    return int(ft[0]), int(ft[1])


def parse(conteudo: bytes, ano: int) -> pd.DataFrame:
    jogos = json.loads(conteudo)["matches"]
    linhas = []
    for j in jogos:
        gm, gv = _placar(j.get("score"))
        linhas.append({
            "temporada": ano,
            "rodada": str(j.get("round", "")).split()[-1],
            "data": j["date"],
            "mandante": j["team1"],
            "visitante": j["team2"],
            "gols_mandante": gm,
            "gols_visitante": gv,
        })
    return normalizar(pd.DataFrame(linhas), fonte="openfootball")


def coletar(ano: int) -> pd.DataFrame:
    return parse(baixar(URL.format(ano=ano), nome=f"openfootball_{ano}.json"), ano)
