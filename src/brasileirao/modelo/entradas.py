"""Monta as taxas de gols (λ, μ) de cada jogo restante para a simulação.

Ordem de preferência por jogo (decisão 1 do CLAUDE.md):
  1. Pinnacle  2. Betfair Exchange  3. média das demais casas (sem margem)
  4. Dixon-Coles, quando o jogo ainda não tem odds (ex.: rodadas distantes).
O ρ do Dixon-Coles ajustado é usado também para converter o 1X2 do mercado.
"""

from __future__ import annotations

import pandas as pd

from .. import DADOS
from . import dixon_coles as dc
from . import mercado

ARQ_ODDS = DADOS / "processed" / "odds_futuras.csv"
PRIORIDADE = ["pinnacle", "betfair_ex_eu"]
PROBS = ["p_casa", "p_empate", "p_fora"]


def carregar_odds() -> pd.DataFrame:
    if not ARQ_ODDS.exists():
        return pd.DataFrame(columns=["data", "mandante", "visitante", "casa_apostas",
                                     "odd_casa", "odd_empate", "odd_fora", "coletado_em"])
    return pd.read_csv(ARQ_ODDS, parse_dates=["data"])


def salvar_odds(novas: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta a coleta ao histórico (útil para ver o movimento das odds)."""
    todas = pd.concat([carregar_odds(), novas], ignore_index=True)
    todas = todas.drop_duplicates(["mandante", "visitante", "casa_apostas", "coletado_em"])
    ARQ_ODDS.parent.mkdir(parents=True, exist_ok=True)
    todas.to_csv(ARQ_ODDS, index=False, date_format="%Y-%m-%d")
    return todas


def consenso(odds: pd.DataFrame, metodo: str = "potencia") -> pd.DataFrame:
    """Uma probabilidade 1X2 por jogo, a partir da coleta mais recente de cada casa."""
    if odds.empty:
        return pd.DataFrame(columns=["mandante", "visitante", *PROBS, "fonte_odds", "n_casas"])
    recente = (odds.sort_values("coletado_em")
               .drop_duplicates(["mandante", "visitante", "casa_apostas"], keep="last"))
    p = mercado.remover_margem(recente[["odd_casa", "odd_empate", "odd_fora"]], metodo)
    recente = recente.assign(p_casa=p[:, 0], p_empate=p[:, 1], p_fora=p[:, 2])
    linhas = []
    for (m, v), g in recente.groupby(["mandante", "visitante"]):
        escolha = next((g[g["casa_apostas"] == c] for c in PRIORIDADE
                        if (g["casa_apostas"] == c).any()), None)
        if escolha is not None:
            probs, fonte = escolha[PROBS].iloc[0].to_numpy(), escolha["casa_apostas"].iloc[0]
        else:
            probs, fonte = g[PROBS].mean().to_numpy(), "media"
        linhas.append({"mandante": m, "visitante": v, "p_casa": probs[0],
                       "p_empate": probs[1], "p_fora": probs[2],
                       "fonte_odds": fonte, "n_casas": len(g)})
    return pd.DataFrame(linhas)


def entradas(jogos: pd.DataFrame, temporada: int, data_ref, xi: float, ridge: float,
             odds: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dc.Parametros]:
    """Jogos restantes da temporada com λ, μ, probabilidades 1X2 e a origem de cada um."""
    params = dc.ajustar(jogos, data_ref, xi=xi, ridge=ridge)
    rest = jogos[(jogos["temporada"] == temporada) & jogos["gols_mandante"].isna()]
    prev = dc.prever(params, rest)
    prev["origem"] = "dixon-coles"

    cons = consenso(carregar_odds() if odds is None else odds)
    if not cons.empty:
        prev = prev.merge(cons, on=["mandante", "visitante"], how="left",
                          suffixes=("", "_mk"))
        tem = prev["p_casa_mk"].notna()
        for i in prev.index[tem]:
            alvo = prev.loc[i, ["p_casa_mk", "p_empate_mk", "p_fora_mk"]].to_numpy(float)
            lam, mu = mercado.taxas_do_mercado(alvo, params.rho,
                                               chute=(prev.at[i, "lambda"], prev.at[i, "mu"]))
            prev.loc[i, ["lambda", "mu"]] = lam, mu
            prev.loc[i, PROBS] = alvo
            prev.at[i, "origem"] = f"mercado:{prev.at[i, 'fonte_odds']}"
        prev = prev.drop(columns=["p_casa_mk", "p_empate_mk", "p_fora_mk"])
    return prev.reset_index(drop=True), params
