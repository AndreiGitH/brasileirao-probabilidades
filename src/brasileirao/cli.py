"""Linha de comando: `uv run brasileirao atualizar` e `uv run brasileirao tabela`."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date

import pandas as pd

from . import DADOS, dados
from .fontes import theoddsapi
from .modelo import entradas
from .tabela import classificacao


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="brasileirao")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("atualizar", help="baixa as fontes e regrava data/processed/jogos.csv")
    a.add_argument("--temporada", type=int, default=date.today().year)
    t = sub.add_parser("tabela", help="mostra a classificação a partir de jogos.csv")
    t.add_argument("--temporada", type=int, default=date.today().year)
    f = sub.add_parser("proximos", help="forças do Dixon-Coles e probabilidades dos próximos jogos")
    f.add_argument("--temporada", type=int, default=date.today().year)
    f.add_argument("--data", default=str(date.today()), help="data de referência do ajuste")
    sub.add_parser("odds", help="baixa as odds atuais (The Odds API, 1 crédito) e salva")
    args = p.parse_args(argv)

    if args.cmd == "atualizar":
        jogos = dados.montar(args.temporada)
        dados.salvar(jogos)
        print(dados.relatorio(jogos))
    elif args.cmd == "tabela":
        jogos = dados.carregar()
        print(classificacao(jogos[jogos["temporada"] == args.temporada]).to_string())
    elif args.cmd == "proximos":
        _proximos(args.temporada, args.data)
    elif args.cmd == "odds":
        novas = theoddsapi.coletar()
        entradas.salvar_odds(novas)
        n_jogos = novas[["mandante", "visitante"]].drop_duplicates().shape[0] if len(novas) else 0
        casas = sorted(novas["casa_apostas"].unique()) if len(novas) else []
        print(f"{n_jogos} jogos com odds; casas: {', '.join(casas)}")


def _proximos(temporada: int, data: str) -> None:
    hp = json.loads((DADOS / "processed" / "hiperparametros.json").read_text())
    jogos = dados.carregar()
    prev, p = entradas.entradas(jogos, temporada, data, hp["xi"], hp["ridge"])
    print(f"Dixon-Coles em {data}: xi={hp['xi']} ridge={hp['ridge']} "
          f"mando={p.mando:.3f} rho={p.rho:.3f}\n")
    da_temporada = jogos[jogos["temporada"] == temporada]
    clubes = set(da_temporada["mandante"]) | set(da_temporada["visitante"])
    forcas = p.tabela()
    print(forcas[forcas.index.isin(clubes)].round(3).to_string(), "\n")
    cols = ["data", "mandante", "visitante", "lambda", "mu", *entradas.PROBS, "origem"]
    prev = prev.assign(data=prev["data"].dt.date)
    with pd.option_context("display.width", 160):
        print(prev[cols].round(3).to_string(index=False))
    contagem = prev["origem"].value_counts().to_dict()
    print(f"\nOrigem das probabilidades: {contagem}")
