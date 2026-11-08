"""Compara Dixon-Coles e mercado fora da amostra (temporadas 2022-2025).

Uso: uv run python scripts/comparar_mercado.py
"""

import json

import numpy as np
import pandas as pd

from brasileirao import DADOS, avaliacao, dados

hp = json.loads((DADOS / "processed" / "hiperparametros.json").read_text())
jogos = dados.carregar()
alvo = avaliacao.alvo_backtest(jogos, range(2022, 2026))
alvo = alvo[alvo["odd_med_casa"].notna()]
prev = avaliacao.previsoes_rolantes(jogos, alvo, hp["xi"], hp["ridge"])

res = avaliacao.resultado(prev)
p_dc = prev[avaliacao.PROBS].to_numpy()
p_mk = avaliacao.probs_mercado(prev, "odd_med")
treino = jogos[(jogos["temporada"] < 2022) & jogos["gols_mandante"].notna()]
base = np.bincount(avaliacao.resultado(treino), minlength=3) / len(treino)

modelos = {
    "frequência histórica": np.tile(base, (len(prev), 1)),
    "Dixon-Coles": p_dc,
    "mercado (média, sem margem)": p_mk,
    "mistura 50/50": 0.5 * p_dc + 0.5 * p_mk,
}
recortes = {"todas as rodadas": np.ones(len(prev), bool),
            "rodadas 35-38": prev["rodada"].between(35, 38).to_numpy()}
linhas = []
for nome_r, mask in recortes.items():
    for nome_m, p in modelos.items():
        linhas.append({"recorte": nome_r, "modelo": nome_m,
                       **avaliacao.metricas(p[mask], res[mask])})
print(f"xi={hp['xi']} ridge={hp['ridge']}")
print(pd.DataFrame(linhas).round(4).to_string(index=False))
