"""Base histórica 2003-2024 mantida em https://github.com/adaoduque/Brasileirao_Dataset.

Sem odds. Serve para treinar e testar o modelo em temporadas passadas.
"""

from __future__ import annotations

import io

import pandas as pd

from ..esquema import normalizar
from ._http import baixar

URL = (
    "https://raw.githubusercontent.com/adaoduque/Brasileirao_Dataset/master/"
    "campeonato-brasileiro-full.csv"
)


def _temporada(data: pd.Series) -> pd.Series:
    temporada = data.dt.year
    # A temporada 2020 (pandemia) terminou em fevereiro de 2021.
    fim_2020 = (data >= "2021-01-01") & (data <= "2021-03-31")
    return temporada.where(~fim_2020, 2020)


def parse(conteudo: bytes) -> pd.DataFrame:
    bruto = pd.read_csv(io.BytesIO(conteudo), dtype=str)
    data = pd.to_datetime(bruto["data"], format="%d/%m/%Y")
    df = pd.DataFrame({
        "temporada": _temporada(data),
        "rodada": bruto["rodata"],
        "data": data,
        "mandante": bruto["mandante"].str.strip(),
        "visitante": bruto["visitante"].str.strip(),
        "gols_mandante": bruto["mandante_Placar"],
        "gols_visitante": bruto["visitante_Placar"],
    })
    return normalizar(df, fonte="adaoduque")


def coletar() -> pd.DataFrame:
    return parse(baixar(URL, max_idade_h=24 * 7, nome="adaoduque_full.csv"))
