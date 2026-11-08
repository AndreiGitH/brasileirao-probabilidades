"""Monta a base única de jogos (data/processed/jogos.csv) a partir das fontes.

Prioridade dos placares por temporada:
  2003-2024  adaoduque (GitHub)
  2025       openfootball (GitHub)
  corrente   football-data.org (precisa de token); sem token, openfootball
Odds de fechamento: football-data.co.uk, juntadas por temporada+mandante+visitante.
Fontes que falham (rede, token) são avisadas e puladas, nunca inventadas.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from . import DADOS
from .esquema import COLUNAS_ODDS, validar
from .fontes import footballdata_org, footballdata_uk, historico_github, openfootball

log = logging.getLogger(__name__)
ARQUIVO = DADOS / "processed" / "jogos.csv"
CHAVE = ["temporada", "mandante", "visitante"]


def _tentar(nome: str, func, *args):
    try:
        return func(*args)
    except Exception as e:  # noqa: BLE001 - rede bloqueada, token ausente, formato mudou...
        log.warning("Fonte %s indisponível: %s", nome, e)
        return None


def _juntar_odds(jogos: pd.DataFrame, odds: pd.DataFrame | None) -> pd.DataFrame:
    if odds is None:
        return jogos
    o = odds[CHAVE + COLUNAS_ODDS + ["gols_mandante", "gols_visitante"]].rename(
        columns={"gols_mandante": "gm_odds", "gols_visitante": "gv_odds"})
    out = jogos.drop(columns=COLUNAS_ODDS).merge(o, on=CHAVE, how="left")
    # Confere os placares entre as duas fontes onde ambas têm o jogo encerrado.
    ambos = out["gols_mandante"].notna() & out["gm_odds"].notna()
    diverge = ambos & ((out["gols_mandante"] != out["gm_odds"])
                       | (out["gols_visitante"] != out["gv_odds"]))
    if diverge.any():
        log.warning("%d placares divergem entre as fontes:\n%s", int(diverge.sum()),
                    out.loc[diverge, CHAVE + ["gols_mandante", "gols_visitante",
                                              "gm_odds", "gv_odds"]].to_string())
    return out.drop(columns=["gm_odds", "gv_odds"])


def montar(temporada_atual: int | None = None) -> pd.DataFrame:
    temporada_atual = temporada_atual or date.today().year
    partes = []

    hist = _tentar("adaoduque", historico_github.coletar)
    if hist is not None:
        partes.append(hist[hist["temporada"] <= 2024])

    for ano in range(2025, temporada_atual):
        p = _tentar(f"openfootball {ano}", openfootball.coletar, ano)
        if p is not None:
            partes.append(p)

    atual = _tentar("football-data.org", footballdata_org.coletar, temporada_atual)
    if atual is None:
        log.warning("Usando openfootball para %d: pode estar rodadas atrasado.",
                    temporada_atual)
        atual = _tentar(f"openfootball {temporada_atual}", openfootball.coletar,
                        temporada_atual)
    if atual is not None:
        partes.append(atual)

    if not partes:
        raise RuntimeError("Nenhuma fonte de dados respondeu.")
    jogos = pd.concat(partes, ignore_index=True)
    jogos = _juntar_odds(jogos, _tentar("football-data.co.uk", footballdata_uk.coletar))
    return jogos.sort_values(["temporada", "data", "mandante"]).reset_index(drop=True)


def salvar(jogos: pd.DataFrame) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    jogos.to_csv(ARQUIVO, index=False, date_format="%Y-%m-%d")


def carregar() -> pd.DataFrame:
    df = pd.read_csv(ARQUIVO, parse_dates=["data"])
    for c in ("rodada", "gols_mandante", "gols_visitante"):
        df[c] = df[c].astype("Int64")
    return df


def relatorio(jogos: pd.DataFrame) -> str:
    linhas = ["temporada  jogos  encerrados  com_odds  fonte"]
    for t, g in jogos.groupby("temporada"):
        linhas.append(f"{t:>9}  {len(g):>5}  {int(g['gols_mandante'].notna().sum()):>10}"
                      f"  {int(g['odd_pin_casa'].notna().sum()):>8}  {g['fonte'].iloc[0]}")
    problemas = validar(jogos)
    linhas.append("Problemas: " + ("; ".join(problemas) if problemas else "nenhum"))
    return "\n".join(linhas)
