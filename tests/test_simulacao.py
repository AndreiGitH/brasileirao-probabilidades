import numpy as np
import pandas as pd
import pytest

from brasileirao import dados
from brasileirao.modelo import dixon_coles as dc
from brasileirao.modelo import simulacao
from brasileirao.tabela import classificacao

VAZIO = pd.DataFrame(columns=["mandante", "visitante", "lambda", "mu"])


def _jogos(linhas):
    df = pd.DataFrame(linhas, columns=["mandante", "visitante", "gols_mandante",
                                       "gols_visitante"])
    return df.astype({"gols_mandante": "Int64", "gols_visitante": "Int64"})


def test_sem_jogos_restantes_reproduz_a_tabela_real():
    j = dados.carregar()
    temporada = j[j["temporada"] == 2025]
    r = simulacao.simular(temporada, VAZIO, rho=0.0, n_sim=50, seed=0)
    esperado = list(classificacao(temporada)["time"])
    obtido = [r.times[i] for i in np.argsort(r.posicoes[0])]
    assert obtido == esperado
    assert (r.posicoes == r.posicoes[0]).all()  # nada aleatório


def test_confronto_direto_decide_empate_de_dois():
    # A e B: 3 pts, 1 V, SG 0, GP 1 cada; A venceu B no confronto direto.
    jog = _jogos([("A", "B", 1, 0), ("X", "A", 1, 0), ("B", "Y", 1, 0), ("X", "Y", 0, 0)])
    r = simulacao.simular(jog, VAZIO, rho=0.0, n_sim=200, seed=1)
    i_a, i_b = r.times.index("A"), r.times.index("B")
    assert (r.posicoes[:, i_a] < r.posicoes[:, i_b]).all()


def test_confronto_direto_inclui_jogo_simulado():
    # A e B empatados em tudo antes; o único confronto entre eles é simulado
    # com A muito favorito: quando terminam empatados, A precisa ficar à frente.
    jog = _jogos([("A", "X", 1, 0), ("B", "Y", 1, 0), ("X", "Y", 0, 0)])
    rest = pd.DataFrame({"mandante": ["A"], "visitante": ["B"], "lambda": [1.0], "mu": [1.0]})
    r = simulacao.simular(jog, rest, rho=0.0, n_sim=20_000, seed=2)
    i_a, i_b = r.times.index("A"), r.times.index("B")
    empate = r.pontos[:, i_a] == r.pontos[:, i_b]  # só acontece com empate no jogo
    # empate no jogo => mesmos pts, vitórias, saldo e gols: decide o sorteio (~50%)
    frac = (r.posicoes[empate, i_a] < r.posicoes[empate, i_b]).mean()
    assert 0.45 < frac < 0.55
    # vitória de A => A à frente sempre
    a_vence = r.pontos[:, i_a] > r.pontos[:, i_b]
    assert (r.posicoes[a_vence, i_a] < r.posicoes[a_vence, i_b]).all()


def test_sorteio_de_placares_segue_a_matriz():
    rng = np.random.default_rng(0)
    gm, gv = simulacao._sortear_placares(np.array([1.6]), np.array([1.1]), -0.08,
                                         200_000, rng)
    m = dc.matriz_placares(1.6, 1.1, -0.08, simulacao.MAX_GOLS)
    for a, b in [(0, 0), (1, 0), (1, 1), (2, 1)]:
        freq = ((gm[:, 0] == a) & (gv[:, 0] == b)).mean()
        assert freq == pytest.approx(m[a, b], abs=0.004)


def test_times_iguais_dividem_o_titulo():
    jog = _jogos([("A", "X", 1, 0), ("B", "Y", 1, 0)])
    rest = pd.DataFrame({"mandante": ["A", "B"], "visitante": ["Y", "X"],
                         "lambda": [1.3, 1.3], "mu": [1.0, 1.0]})
    r = simulacao.simular(jog, rest, rho=-0.05, n_sim=40_000, seed=3)
    res = r.resumo()
    # X e Y também podem ser campeões (se A e B perderem); A e B são simétricos
    assert res.loc["A", "titulo"] == pytest.approx(res.loc["B", "titulo"], abs=0.02)
    assert res["titulo"].sum() == pytest.approx(1.0)


def test_somas_das_probabilidades():
    jog = _jogos([("A", "B", 2, 1), ("C", "D", 0, 0), ("E", "F", 1, 3)])
    rest = pd.DataFrame({"mandante": ["B", "D", "F"], "visitante": ["C", "E", "A"],
                         "lambda": [1.2, 1.5, 1.1], "mu": [1.0, 0.9, 1.3]})
    r = simulacao.simular(jog, rest, rho=-0.05, n_sim=5_000, seed=4)
    dist = r.distribuicao()
    assert np.allclose(dist.sum(axis=0), 1) and np.allclose(dist.sum(axis=1), 1)
    assert r.resumo(z=2)["rebaixamento"].sum() == pytest.approx(2.0)
