"""Métricas de previsão 1X2 e previsões fora da amostra (sem vazamento).

RPS (ranked probability score) é a métrica padrão para 1X2 porque respeita a
ordem casa < empate < fora: errar "casa" quando deu empate é menos grave do que
quando deu vitória do visitante. Menor é melhor em todas as métricas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .modelo import dixon_coles as dc

PROBS = ["p_casa", "p_empate", "p_fora"]


def resultado(df: pd.DataFrame) -> np.ndarray:
    """0 = casa, 1 = empate, 2 = fora."""
    gm, gv = df["gols_mandante"].astype(int), df["gols_visitante"].astype(int)
    return np.select([gm > gv, gm == gv], [0, 1], 2)


def metricas(probs: np.ndarray, res: np.ndarray) -> dict[str, float]:
    probs = np.asarray(probs, dtype=float)
    obs = np.eye(3)[res]
    rps = 0.5 * ((np.cumsum(probs, 1)[:, :2] - np.cumsum(obs, 1)[:, :2]) ** 2).sum(1)
    p_obs = np.clip(probs[np.arange(len(res)), res], 1e-12, 1)
    return {
        "n": len(res),
        "rps": float(rps.mean()),
        "log_loss": float(-np.log(p_obs).mean()),
        "brier": float(((probs - obs) ** 2).sum(1).mean()),
    }


def probs_mercado(df: pd.DataFrame, prefixo: str = "odd_med") -> np.ndarray:
    """Odds decimais -> probabilidades, removendo a margem proporcionalmente."""
    inv = 1 / df[[f"{prefixo}_casa", f"{prefixo}_empate", f"{prefixo}_fora"]].to_numpy(float)
    return inv / inv.sum(1, keepdims=True)


def previsoes_rolantes(jogos: pd.DataFrame, alvo: pd.DataFrame, xi: float,
                       ridge: float) -> pd.DataFrame:
    """Prevê cada jogo de `alvo` com o modelo ajustado só com jogos anteriores à data dele."""
    saidas = []
    for data, grupo in alvo.groupby("data"):
        p = dc.ajustar(jogos, data, xi=xi, ridge=ridge)
        prev = dc.prever(p, grupo)
        saidas.append(prev[PROBS].set_index(grupo.index))
    return alvo.join(pd.concat(saidas))


def alvo_backtest(jogos: pd.DataFrame, temporadas, rodada_min: int = 1,
                  rodada_max: int = 38) -> pd.DataFrame:
    a = jogos[jogos["temporada"].isin(list(temporadas))
              & jogos["gols_mandante"].notna()
              & jogos["rodada"].between(rodada_min, rodada_max)]
    return a.copy()
