"""Classificação com os critérios de desempate do Brasileirão.

Critérios (regulamento CBF): pontos, vitórias, saldo de gols, gols marcados,
confronto direto (só entre dois clubes), menos cartões vermelhos, menos
amarelos, sorteio. Sem dados de cartões, o desempate termina no confronto
direto e, depois, na ordem alfabética (aproximação documentada).
"""

from __future__ import annotations

import pandas as pd


def classificacao(jogos: pd.DataFrame) -> pd.DataFrame:
    j = jogos.dropna(subset=["gols_mandante", "gols_visitante"])
    gm = j["gols_mandante"].astype(int)
    gv = j["gols_visitante"].astype(int)
    casa = pd.DataFrame({"time": j["mandante"], "gp": gm, "gc": gv})
    fora = pd.DataFrame({"time": j["visitante"], "gp": gv, "gc": gm})
    linhas = pd.concat([casa, fora], ignore_index=True)
    linhas["v"] = (linhas["gp"] > linhas["gc"]).astype(int)
    linhas["e"] = (linhas["gp"] == linhas["gc"]).astype(int)
    linhas["d"] = (linhas["gp"] < linhas["gc"]).astype(int)
    t = linhas.groupby("time").agg(j=("gp", "size"), v=("v", "sum"), e=("e", "sum"),
                                   d=("d", "sum"), gp=("gp", "sum"), gc=("gc", "sum"))
    todos = sorted(set(jogos["mandante"]) | set(jogos["visitante"]))
    t = t.reindex(todos, fill_value=0)
    t["sg"] = t["gp"] - t["gc"]
    t["pts"] = 3 * t["v"] + t["e"]
    t = t.reset_index().rename(columns={"index": "time"})
    t = t.sort_values(["pts", "v", "sg", "gp", "time"],
                      ascending=[False, False, False, False, True]).reset_index(drop=True)
    t = _confronto_direto(t, j)
    t.index = range(1, len(t) + 1)
    return t[["time", "pts", "j", "v", "e", "d", "gp", "gc", "sg"]]


def _confronto_direto(t: pd.DataFrame, j: pd.DataFrame) -> pd.DataFrame:
    """Troca a ordem de pares empatados em tudo se o confronto direto decidir."""
    chave = ["pts", "v", "sg", "gp"]
    ordem = list(t.index)
    grupos = t.groupby(chave, sort=False).groups
    for idx in grupos.values():
        if len(idx) != 2:
            continue
        a, b = t.loc[idx[0], "time"], t.loc[idx[1], "time"]
        pts = {a: 0, b: 0}
        for _, r in j[j["mandante"].isin([a, b]) & j["visitante"].isin([a, b])].iterrows():
            m, v = r["mandante"], r["visitante"]
            if r["gols_mandante"] > r["gols_visitante"]:
                pts[m] += 3
            elif r["gols_mandante"] < r["gols_visitante"]:
                pts[v] += 3
            else:
                pts[m] += 1
                pts[v] += 1
        if pts[b] > pts[a]:
            i, k = ordem.index(idx[0]), ordem.index(idx[1])
            ordem[i], ordem[k] = ordem[k], ordem[i]
    return t.loc[ordem].reset_index(drop=True)
