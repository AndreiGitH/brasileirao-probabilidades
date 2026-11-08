"""Escolhe ξ (decaimento) e ridge do Dixon-Coles fora da amostra.

Ajuste: temporadas 2015-2021, rodadas 10-38. Os anos 2022-2025 ficam reservados
para a comparação honesta com o mercado (scripts/comparar_mercado.py).
Uso: uv run python scripts/escolher_xi.py
"""

import itertools
import json
import sys

import pandas as pd

from brasileirao import DADOS, avaliacao, dados

jogos = dados.carregar()
alvo = avaliacao.alvo_backtest(jogos, range(2015, 2022), rodada_min=10)
res = avaliacao.resultado(alvo)
linhas = []
for xi, ridge in itertools.product([0.0, 0.001, 0.002, 0.003, 0.005, 0.008], [0.5, 2.0, 5.0]):
    prev = avaliacao.previsoes_rolantes(jogos, alvo, xi, ridge)
    m = avaliacao.metricas(prev[avaliacao.PROBS].to_numpy(), res)
    linhas.append({"xi": xi, "ridge": ridge, **m})
    print(linhas[-1], file=sys.stderr, flush=True)

tab = pd.DataFrame(linhas).sort_values("rps")
print(tab.to_string(index=False))
melhor = tab.iloc[0]
saida = DADOS / "processed" / "hiperparametros.json"
saida.write_text(json.dumps({"xi": float(melhor.xi), "ridge": float(melhor.ridge),
                             "rps_ajuste": float(melhor.rps)}, indent=2))
print("salvo em", saida)
