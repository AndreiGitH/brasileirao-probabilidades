"""Linha de comando: `uv run brasileirao atualizar` e `uv run brasileirao tabela`."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date

import pandas as pd

from . import DADOS, dados, painel
from .fontes import theoddsapi
from .modelo import entradas, simulacao
from .tabela import classificacao

log = logging.getLogger("brasileirao")


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="brasileirao")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("atualizar", help="baixa as fontes e regrava data/processed/jogos.csv")
    a.add_argument("--temporada", type=int, default=date.today().year)
    a.add_argument("--forcar", action="store_true", help="grava mesmo se perder dados")
    t = sub.add_parser("tabela", help="mostra a classificação a partir de jogos.csv")
    t.add_argument("--temporada", type=int, default=date.today().year)
    f = sub.add_parser("proximos", help="forças do Dixon-Coles e probabilidades dos próximos jogos")
    f.add_argument("--temporada", type=int, default=date.today().year)
    f.add_argument("--data", default=str(date.today()), help="data de referência do ajuste")
    sub.add_parser("odds", help="baixa as odds atuais (The Odds API, 1 crédito) e salva")
    pn = sub.add_parser("painel", help="gera painel/index.html com a simulação mais recente")
    pn.add_argument("--temporada", type=int, default=date.today().year)
    for nome, ajuda in [("simular", "simula as rodadas restantes"),
                        ("rodada", "atualiza dados, coleta odds e simula (uso semanal)")]:
        sp = sub.add_parser(nome, help=ajuda)
        sp.add_argument("--temporada", type=int, default=date.today().year)
        sp.add_argument("--data", default=str(date.today()))
        sp.add_argument("--n", type=int, default=100_000, help="número de simulações")
        sp.add_argument("--seed", type=int, default=None)
    args = p.parse_args(argv)

    if args.cmd == "atualizar":
        jogos = dados.montar(args.temporada)
        dados.salvar(jogos, forcar=args.forcar)
        print(dados.relatorio(jogos))
    elif args.cmd == "tabela":
        jogos = dados.carregar()
        print(classificacao(jogos[jogos["temporada"] == args.temporada]).to_string())
    elif args.cmd == "proximos":
        _proximos(args.temporada, args.data)
    elif args.cmd == "simular":
        _simular(args.temporada, args.data, args.n, args.seed)
    elif args.cmd == "rodada":
        jogos = dados.montar(args.temporada)
        if dados.salvar(jogos):
            print(dados.relatorio(jogos), "\n")
        try:
            _coletar_odds()
        except Exception as e:  # noqa: BLE001 - sem chave/rede: segue com o que houver
            log.warning("Odds não coletadas (%s); jogos sem odds usam o Dixon-Coles.", e)
        _simular(args.temporada, args.data, args.n, args.seed)
        print(f"Painel: {painel.gerar(args.temporada)}")
    elif args.cmd == "painel":
        print(f"Painel: {painel.gerar(args.temporada)}")
    elif args.cmd == "odds":
        _coletar_odds()


def _coletar_odds() -> None:
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


def _simular(temporada: int, data: str, n: int, seed: int | None) -> None:
    hp = json.loads((DADOS / "processed" / "hiperparametros.json").read_text())
    jogos = dados.carregar()
    prev, p = entradas.entradas(jogos, temporada, data, hp["xi"], hp["ridge"])
    jogados = jogos[(jogos["temporada"] == temporada) & jogos["gols_mandante"].notna()]
    r = simulacao.simular(jogados, prev, p.rho, n_sim=n, seed=seed)
    res = r.resumo()
    origem = prev["origem"].value_counts().to_dict()

    pasta = DADOS / "processed" / "simulacoes"
    pasta.mkdir(parents=True, exist_ok=True)
    res.assign(data_ref=data, n_sim=n).to_csv(pasta / f"{data}.csv", index_label="time")
    r.distribuicao().to_csv(pasta / f"{data}_posicoes.csv", index_label="time")
    cols = ["data", "rodada", "mandante", "visitante", "lambda", "mu", *entradas.PROBS, "origem"]
    restantes = prev.merge(jogos[jogos["temporada"] == temporada][["mandante", "visitante",
                                                                    "rodada"]],
                           on=["mandante", "visitante"], how="left")
    restantes[cols].to_csv(pasta / f"{data}_jogos.csv", index=False, date_format="%Y-%m-%d")

    pct = res.copy()
    for c in pct.columns[2:]:
        pct[c] = (100 * pct[c]).map(lambda v: f"{v:5.1f}%")
    pct["pts_medio"] = pct["pts_medio"].round(1)
    pct["pos_media"] = pct["pos_media"].round(1)
    print(f"{n:,} simulações · {len(prev)} jogos restantes · origem: {origem}")
    print(f"Erro de Monte Carlo: até ±{100 * 1.96 * (0.25 / n) ** 0.5:.2f} p.p. (IC 95%)\n")
    print(pct.to_string())
    print(f"\nSalvo em {pasta / f'{data}.csv'}")
