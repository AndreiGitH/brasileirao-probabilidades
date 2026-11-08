"""Resultados e odds de fechamento: https://www.football-data.co.uk/brazil.php

Arquivo único com todas as temporadas desde 2012. Traz as odds de fechamento
da Pinnacle (PSCH/PSCD/PSCA) e a média do mercado (AvgCH/AvgCD/AvgCA), que são
a referência de mercado para calibrar e testar o modelo. Não traz a rodada.
"""

from __future__ import annotations

import io

import pandas as pd

from ..esquema import normalizar
from ._http import baixar

URL = "https://www.football-data.co.uk/new/BRA.csv"

_ODDS = {
    "PSCH": "odd_pin_casa", "PSCD": "odd_pin_empate", "PSCA": "odd_pin_fora",
    "AvgCH": "odd_med_casa", "AvgCD": "odd_med_empate", "AvgCA": "odd_med_fora",
}


def parse(conteudo: bytes) -> pd.DataFrame:
    bruto = pd.read_csv(io.BytesIO(conteudo), encoding="latin-1")
    bruto.columns = [c.strip().lstrip("﻿") for c in bruto.columns]
    if "League" in bruto:
        bruto = bruto[bruto["League"].str.strip() == "Serie A"]
    df = pd.DataFrame({
        "temporada": bruto["Season"],
        "data": pd.to_datetime(bruto["Date"], dayfirst=True),
        "mandante": bruto["Home"].str.strip(),
        "visitante": bruto["Away"].str.strip(),
        "gols_mandante": bruto["HG"],
        "gols_visitante": bruto["AG"],
    })
    for origem, destino in _ODDS.items():
        if origem in bruto:
            df[destino] = bruto[origem].values
    return normalizar(df, fonte="football-data.co.uk")


def coletar() -> pd.DataFrame:
    return parse(baixar(URL, nome="footballdata_uk_BRA.csv"))
