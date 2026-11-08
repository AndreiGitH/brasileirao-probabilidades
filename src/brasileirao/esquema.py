"""Formato único da tabela de jogos usado em todo o projeto."""

from __future__ import annotations

import pandas as pd

from .times import padronizar

COLUNAS = [
    "temporada",       # ano do campeonato (int)
    "rodada",          # 1..38 quando a fonte informa (Int64, pode ser nulo)
    "data",            # data do jogo (datetime64, sem fuso)
    "mandante",        # nome canônico (brasileirao.times)
    "visitante",
    "gols_mandante",   # Int64, nulo se o jogo ainda não aconteceu
    "gols_visitante",
    "fonte",           # de onde veio a linha
]

# Odds decimais opcionais (presentes quando a fonte traz)
COLUNAS_ODDS = [
    "odd_pin_casa", "odd_pin_empate", "odd_pin_fora",  # Pinnacle, fechamento
    "odd_med_casa", "odd_med_empate", "odd_med_fora",  # média do mercado, fechamento
]


def normalizar(df: pd.DataFrame, fonte: str) -> pd.DataFrame:
    """Aplica tipos, nomes canônicos e ordem de colunas."""
    out = df.copy()
    out["mandante"] = out["mandante"].map(padronizar)
    out["visitante"] = out["visitante"].map(padronizar)
    out["temporada"] = out["temporada"].astype(int)
    if "rodada" not in out:
        out["rodada"] = pd.NA
    out["rodada"] = pd.to_numeric(out["rodada"], errors="coerce").astype("Int64")
    out["data"] = pd.to_datetime(out["data"]).dt.tz_localize(None).dt.normalize()
    for c in ("gols_mandante", "gols_visitante"):
        out[c] = pd.to_numeric(out[c], errors="coerce").astype("Int64")
    out["fonte"] = fonte
    for c in COLUNAS_ODDS:
        out[c] = pd.to_numeric(out[c], errors="coerce") if c in out else float("nan")
    return out[COLUNAS + COLUNAS_ODDS].sort_values(["data", "mandante"]).reset_index(drop=True)


def validar(df: pd.DataFrame) -> list[str]:
    """Checagens de sanidade. Devolve a lista de problemas (vazia = ok)."""
    problemas: list[str] = []
    if (df["mandante"] == df["visitante"]).any():
        problemas.append("jogo de um clube contra ele mesmo")
    dup = df.duplicated(["temporada", "mandante", "visitante"], keep=False)
    if dup.any():
        problemas.append(f"{int(dup.sum())} linhas com confronto repetido na mesma temporada")
    gols = df[["gols_mandante", "gols_visitante"]]
    if ((gols < 0) | (gols > 15)).any().any():
        problemas.append("placar fora do intervalo plausível")
    meio = df["gols_mandante"].isna() ^ df["gols_visitante"].isna()
    if meio.any():
        problemas.append("placar com só um dos lados preenchido")
    for temporada, g in df.groupby("temporada"):
        n_times = len(set(g["mandante"]) | set(g["visitante"]))
        if temporada >= 2006 and n_times != 20:
            problemas.append(f"temporada {temporada}: {n_times} clubes (esperado 20)")
        esperado = 379 if temporada == 2016 else 380  # Chape x Atlético-MG não foi jogado
        if temporada >= 2006 and len(g) != esperado:
            problemas.append(f"temporada {temporada}: {len(g)} jogos (esperado {esperado})")
    return problemas
