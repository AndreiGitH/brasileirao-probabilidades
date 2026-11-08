"""Linha de comando: `uv run brasileirao atualizar` e `uv run brasileirao tabela`."""

from __future__ import annotations

import argparse
import logging
from datetime import date

from . import dados
from .tabela import classificacao


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="brasileirao")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("atualizar", help="baixa as fontes e regrava data/processed/jogos.csv")
    a.add_argument("--temporada", type=int, default=date.today().year)
    t = sub.add_parser("tabela", help="mostra a classificação a partir de jogos.csv")
    t.add_argument("--temporada", type=int, default=date.today().year)
    args = p.parse_args(argv)

    if args.cmd == "atualizar":
        jogos = dados.montar(args.temporada)
        dados.salvar(jogos)
        print(dados.relatorio(jogos))
    elif args.cmd == "tabela":
        jogos = dados.carregar()
        print(classificacao(jogos[jogos["temporada"] == args.temporada]).to_string())


if __name__ == "__main__":
    main()
