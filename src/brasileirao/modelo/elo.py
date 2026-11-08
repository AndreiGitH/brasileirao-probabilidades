"""Elo simples como concorrente de referência (decisão 5 do CLAUDE.md).

Rating atualizado jogo a jogo (vitória=1, empate=0,5), com vantagem de mando
H em pontos de rating. Entre temporadas, o rating regride 1/3 para a média;
clube que entra na Série A começa abaixo da média (promovidos são mais fracos).
O 1X2 sai de um logit ordenado na diferença de rating, ajustado em temporadas
anteriores às avaliadas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

MEDIA = 1500.0
NOVATO = 1450.0


def historico(jogos: pd.DataFrame, k: float = 20.0, mando: float = 60.0,
              regressao: float = 1 / 3) -> pd.DataFrame:
    """Diferença de rating (mandante + mando - visitante) ANTES de cada jogo."""
    j = jogos.sort_values(["data", "mandante"])
    rating: dict[str, float] = {}
    temporada_atual = None
    difs = np.full(len(j), np.nan)
    for n, r in enumerate(j.itertuples(index=False)):
        if r.temporada != temporada_atual:
            temporada_atual = r.temporada
            rating = {t: MEDIA + (1 - regressao) * (v - MEDIA) for t, v in rating.items()}
        rm = rating.setdefault(r.mandante, NOVATO)
        rv = rating.setdefault(r.visitante, NOVATO)
        d = rm + mando - rv
        difs[n] = d
        if pd.isna(r.gols_mandante):
            continue
        esperado = 1 / (1 + 10 ** (-d / 400))
        real = 1.0 if r.gols_mandante > r.gols_visitante else (
            0.5 if r.gols_mandante == r.gols_visitante else 0.0)
        rating[r.mandante] = rm + k * (real - esperado)
        rating[r.visitante] = rv - k * (real - esperado)
    return pd.Series(difs, index=j.index, name="dif_elo").reindex(jogos.index).to_frame()


def _probs(theta, d):
    beta, c1, gap = theta
    c2 = c1 + np.exp(gap)
    p_fora = expit(c1 - beta * d)
    p_nao_casa = expit(c2 - beta * d)
    return np.column_stack([1 - p_nao_casa, p_nao_casa - p_fora, p_fora])


def ajustar_logit(d: np.ndarray, res: np.ndarray) -> np.ndarray:
    """Logit ordenado: res 0=casa, 1=empate, 2=fora."""
    def nll(theta):
        p = np.clip(_probs(theta, d), 1e-12, 1)
        return -np.log(p[np.arange(len(res)), res]).sum()
    return minimize(nll, np.array([0.005, -1.0, 0.0]), method="Nelder-Mead",
                    options={"xatol": 1e-8, "fatol": 1e-8, "maxiter": 5000}).x


def prever(theta, d) -> np.ndarray:
    return _probs(theta, np.asarray(d, dtype=float))
