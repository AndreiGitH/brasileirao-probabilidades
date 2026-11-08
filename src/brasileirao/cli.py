"""Linha de comando: `uv run brasileirao atualizar` e `uv run brasileirao tabela`."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date

import pandas as pd

from . import DADOS, avaliacao, dados
from .modelo import dixon_coles as dc
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


def _proximos(temporada: int, data: str) -> None:
    hp = json.loads((DADOS / "processed" / "hiperparametros.json").read_text())
    jogos = dados.carregar()
    p = dc.ajustar(jogos, data, xi=hp["xi"], ridge=hp["ridge"])
    print(f"Dixon-Coles em {data}: xi={hp['xi']} ridge={hp['ridge']} "
          f"mando={p.mando:.3f} rho={p.rho:.3f}\n")
    da_temporada = jogos[jogos["temporada"] == temporada]
    clubes = set(da_temporada["mandante"]) | set(da_temporada["visitante"])
    forcas = p.tabela()
    print(forcas[forcas.index.isin(clubes)].round(3).to_string(), "\n")
    fut = da_temporada[da_temporada["gols_mandante"].isna()]
    prev = dc.prever(p, fut)
    if fut["odd_med_casa"].notna().any():
        mk = avaliacao.probs_mercado(fut)
        prev["mk_casa"], prev["mk_empate"], prev["mk_fora"] = mk.T
    cols = [c for c in prev.columns if c not in ("lambda", "mu")]
    with pd.option_context("display.width", 140):
        prev = prev.assign(data=prev["data"].dt.date)
        print(prev[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
