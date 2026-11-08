"""Fase 5: backtest completo, 2019-2025.

Parte A (por jogo, rodadas 35-38): Elo, Dixon-Coles, mercado e misturas, por RPS.
  O peso da mistura e o K do Elo são escolhidos em 2015-2018 (todas as rodadas).
Parte B (temporada): a partir do início da rodada 31 e da rodada 35, simula o
  resto do campeonato com cada fonte de probabilidades e mede Brier e log-loss
  dos eventos título, G4, G6 e Z4 contra a classificação final real.
  Fontes:
    - dixon-coles: DC ajustado na data de corte
    - mercado (fechamento): odds de fechamento de TODOS os jogos restantes.
      Otimista: odds de fechamento usam informação posterior ao corte.
    - híbrido realista: odds de fechamento só na rodada seguinte ao corte e DC no
      resto, que é o que temos na prática (a API lista só ~1-2 semanas à frente).

Uso: uv run python scripts/backtest.py   (~3 min)
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from brasileirao import DADOS, avaliacao, dados
from brasileirao.modelo import dixon_coles as dc
from brasileirao.modelo import elo, mercado, simulacao
from brasileirao.tabela import classificacao

HP = json.loads((DADOS / "processed" / "hiperparametros.json").read_text())
TESTE = range(2019, 2026)
AJUSTE = range(2015, 2019)
N_SIM = 20_000
ODDS = ["odd_med_casa", "odd_med_empate", "odd_med_fora"]

jogos = dados.carregar()
jogos = jogos[jogos["temporada"] >= 2006]


def rps_vetor(p, res):
    obs = np.eye(3)[res]
    return 0.5 * ((np.cumsum(p, 1)[:, :2] - np.cumsum(obs, 1)[:, :2]) ** 2).sum(1)


# ---------------------------------------------------------------- Parte A
print("Parte A: previsões por jogo (DC rolante pode levar ~1 min)...", flush=True)
alvo = avaliacao.alvo_backtest(jogos, list(AJUSTE) + list(TESTE))
alvo = alvo[alvo[ODDS].notna().all(axis=1)]
prev = avaliacao.previsoes_rolantes(jogos, alvo, HP["xi"], HP["ridge"])
res = avaliacao.resultado(prev)
p_dc = prev[avaliacao.PROBS].to_numpy()
p_mk = mercado.remover_margem(prev[ODDS].to_numpy(float), "potencia")
em_ajuste = prev["temporada"].isin(AJUSTE).to_numpy()
em_teste = prev["temporada"].isin(TESTE).to_numpy() & prev["rodada"].between(35, 38).to_numpy()

# Elo: K escolhido no ajuste; logit ordenado ajustado só com temporadas < 2019
melhor_k, melhor = None, np.inf
for k in (10, 15, 20, 30, 40):
    dif = elo.historico(jogos, k=k).loc[prev.index, "dif_elo"].to_numpy()
    treino = jogos["temporada"].isin(range(2008, 2015)) & jogos["gols_mandante"].notna()
    d_tr = elo.historico(jogos, k=k).loc[treino[treino].index, "dif_elo"].to_numpy()
    theta = elo.ajustar_logit(d_tr, avaliacao.resultado(jogos[treino]))
    r = rps_vetor(elo.prever(theta, dif[em_ajuste]), res[em_ajuste]).mean()
    if r < melhor:
        melhor_k, melhor, theta_k, dif_k = k, r, theta, dif
p_elo = elo.prever(theta_k, dif_k)

pesos = np.linspace(0, 1, 11)
w_mist = pesos[np.argmin([rps_vetor(w * p_mk + (1 - w) * p_dc, res)[em_ajuste].mean()
                          for w in pesos])]
modelos = {f"Elo (K={melhor_k})": p_elo, "Dixon-Coles": p_dc, "mercado": p_mk,
           f"mistura ({w_mist:.0%} mercado)": w_mist * p_mk + (1 - w_mist) * p_dc,
           "mistura 50/50": 0.5 * p_mk + 0.5 * p_dc}
linhas = []
for nome, p in modelos.items():
    m = avaliacao.metricas(p[em_teste], res[em_teste])
    d = rps_vetor(p, res)[em_teste] - rps_vetor(p_mk, res)[em_teste]
    rng = np.random.default_rng(0)
    boot = [rng.choice(d, len(d)).mean() for _ in range(2000)]
    linhas.append({"modelo": nome, **m, "dif_vs_mercado": d.mean(),
                   "ic95_baixo": np.percentile(boot, 2.5), "ic95_alto": np.percentile(boot, 97.5)})
tab_a = pd.DataFrame(linhas).sort_values("rps")
print("\nParte A: rodadas 35-38 de 2019-2025 (RPS, menor = melhor)")
print(tab_a.round(4).to_string(index=False))

# ---------------------------------------------------------------- Parte B
print("\nParte B: simulação de temporadas...", flush=True)
EVENTOS = {"titulo": lambda pos: pos == 1, "g4": lambda pos: pos <= 4,
           "g6": lambda pos: pos <= 6, "z4": lambda pos: pos >= 17}
registros = []
for temporada in TESTE:
    t = jogos[jogos["temporada"] == temporada]
    final = classificacao(t).reset_index(names="pos").set_index("time")["pos"]
    for rodada_corte in (31, 35):
        corte = t.loc[t["rodada"] >= rodada_corte, "data"].min()
        jogados = t[t["data"] < corte]
        rest = t[t["data"] >= corte].copy()
        params = dc.ajustar(jogos, corte, xi=HP["xi"], ridge=HP["ridge"])
        p_dc_r = dc.prever(params, rest)[avaliacao.PROBS].to_numpy()
        tem_odds = rest[ODDS].notna().all(axis=1).to_numpy()
        p_mk_r = p_dc_r.copy()
        p_mk_r[tem_odds] = mercado.remover_margem(rest.loc[tem_odds, ODDS].to_numpy(float))
        proxima = (rest["rodada"] == rodada_corte).to_numpy() & tem_odds
        p_hib = p_dc_r.copy()
        p_hib[proxima] = p_mk_r[proxima]
        fontes = {"dixon-coles": p_dc_r, "mercado (fechamento)": p_mk_r,
                  "híbrido realista": p_hib}
        lam_dc, mu_dc = dc.taxas(params, rest["mandante"], rest["visitante"])
        for nome, p in fontes.items():
            lam, mu = lam_dc.copy(), mu_dc.copy()
            for i in np.nonzero(~np.isclose(p, p_dc_r).all(axis=1))[0]:
                lam[i], mu[i] = mercado.taxas_do_mercado(p[i], params.rho,
                                                         chute=(lam_dc[i], mu_dc[i]))
            entrada = rest[["mandante", "visitante"]].assign(**{"lambda": lam, "mu": mu})
            sim = simulacao.simular(jogados, entrada, params.rho, n_sim=N_SIM, seed=temporada)
            for time, i in zip(sim.times, range(len(sim.times))):
                pos_sim = sim.posicoes[:, i]
                for ev, f in EVENTOS.items():
                    registros.append({"temporada": temporada, "corte": rodada_corte,
                                      "fonte": nome, "time": time, "evento": ev,
                                      "prob": f(pos_sim).mean(),
                                      "ocorreu": bool(f(final[time]))})
    print(f"  {temporada} ok", flush=True)

reg = pd.DataFrame(registros)
reg["brier"] = (reg["prob"] - reg["ocorreu"]) ** 2
p_cl = reg["prob"].clip(1e-4, 1 - 1e-4)
reg["log_loss"] = -np.where(reg["ocorreu"], np.log(p_cl), np.log(1 - p_cl))
tab_b = (reg.groupby(["corte", "evento", "fonte"])[["brier", "log_loss"]].mean()
         .unstack("fonte").round(4))
print("\nParte B: Brier médio por evento (menor = melhor)")
print(tab_b["brier"].to_string())
print("\nParte B: Brier geral por corte")
print(reg.groupby(["corte", "fonte"])["brier"].mean().unstack().round(4).to_string())

# calibração do híbrido realista (o que usamos na prática), eventos com incerteza
cal = reg[(reg["fonte"] == "híbrido realista") & reg["prob"].between(0.02, 0.98)].copy()
cal["faixa"] = pd.cut(cal["prob"], [0, 0.2, 0.4, 0.6, 0.8, 1.0])
calib = cal.groupby("faixa", observed=True).agg(n=("prob", "size"), previsto=("prob", "mean"),
                                                observado=("ocorreu", "mean")).round(3)
print("\nCalibração do híbrido realista (eventos com prob entre 2% e 98%)")
print(calib.to_string())

saida = DADOS / "processed" / "backtest"
saida.mkdir(parents=True, exist_ok=True)
tab_a.to_csv(saida / "por_jogo.csv", index=False)
reg.to_csv(saida / "eventos.csv", index=False)
calib.to_csv(saida / "calibracao.csv")
print(f"\nArquivos em {saida}")
