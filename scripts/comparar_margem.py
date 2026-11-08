"""Compara métodos de remoção de margem nas odds de fechamento 2012-2025.

Uso: uv run python scripts/comparar_margem.py
"""

import pandas as pd

from brasileirao import avaliacao, dados
from brasileirao.modelo import mercado

jogos = dados.carregar()
linhas = []
for prefixo, nome in [("odd_med", "média do mercado"), ("odd_pin", "Pinnacle")]:
    cols = [f"{prefixo}_casa", f"{prefixo}_empate", f"{prefixo}_fora"]
    j = jogos[jogos[cols].notna().all(axis=1) & jogos["gols_mandante"].notna()]
    res = avaliacao.resultado(j)
    odds = j[cols].to_numpy(float)
    margem = (1 / odds).sum(1).mean() - 1
    for metodo in mercado.METODOS:
        p = mercado.remover_margem(odds, metodo)
        linhas.append({"odds": nome, "margem_media": round(margem, 4), "metodo": metodo,
                       **avaliacao.metricas(p, res)})
print(pd.DataFrame(linhas).round(5).to_string(index=False))
