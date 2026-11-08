import numpy as np
import pandas as pd
import pytest
from scipy.optimize import check_grad

from brasileirao import avaliacao
from brasileirao.modelo import dixon_coles as dc


def _liga_sintetica(seed=0, temporadas=4):
    """Liga de 10 clubes com forças conhecidas, placares sorteados pelo próprio modelo."""
    rng = np.random.default_rng(seed)
    times = [f"T{i}" for i in range(10)]
    ataque = np.linspace(-0.4, 0.4, 10)
    defesa = -np.linspace(-0.3, 0.3, 10)
    linhas, dia = [], pd.Timestamp("2020-01-01")
    for _ in range(temporadas):
        for i in range(10):
            for k in range(10):
                if i == k:
                    continue
                lam = np.exp(0.1 + 0.3 + ataque[i] + defesa[k])
                mu = np.exp(0.1 + ataque[k] + defesa[i])
                linhas.append((dia, times[i], times[k], rng.poisson(lam), rng.poisson(mu)))
                dia += pd.Timedelta(days=1)
    df = pd.DataFrame(linhas, columns=["data", "mandante", "visitante",
                                       "gols_mandante", "gols_visitante"])
    return df, ataque - ataque.mean(), defesa - defesa.mean()


def test_gradiente_analitico_confere():
    rng = np.random.default_rng(3)
    n, m = 5, 120
    ih = rng.integers(0, n, m)
    iv = (ih + rng.integers(1, n, m)) % n
    x = rng.poisson(1.3, m).astype(float)
    y = rng.poisson(1.0, m).astype(float)
    w = rng.uniform(0.3, 1, m)
    theta = np.concatenate([rng.normal(0, 0.2, 2 * n), [0.1, 0.3, -0.05]])
    erro = check_grad(lambda t: dc._nll_e_gradiente(t, ih, iv, x, y, w, n, 1.0)[0],
                      lambda t: dc._nll_e_gradiente(t, ih, iv, x, y, w, n, 1.0)[1], theta)
    assert erro < 1e-4


def test_recupera_forcas_conhecidas():
    df, ataque, defesa = _liga_sintetica(temporadas=30)
    p = dc.ajustar(df, df["data"].max() + pd.Timedelta(days=1), xi=0.0, ridge=0.01,
                   janela_dias=10_000)
    assert np.corrcoef(p.ataque, ataque)[0, 1] > 0.9
    assert np.corrcoef(p.defesa, defesa)[0, 1] > 0.9
    assert p.mando == pytest.approx(0.3, abs=0.1)


def test_nao_usa_jogos_futuros():
    df, _, _ = _liga_sintetica()
    corte = df["data"].iloc[200]
    p1 = dc.ajustar(df, corte, xi=0.003)
    alterado = df.copy()
    alterado.loc[alterado["data"] >= corte, "gols_mandante"] = 9
    p2 = dc.ajustar(alterado, corte, xi=0.003)
    assert np.allclose(p1.ataque, p2.ataque)


def test_matriz_soma_um_e_1x2():
    m = dc.matriz_placares(1.5, 1.1, -0.08)
    assert m.sum() == pytest.approx(1.0)
    p = dc.prob_1x2(m)
    assert p.sum() == pytest.approx(1.0) and p[0] > p[2]


def test_metricas_valores_conhecidos():
    probs = np.array([[1.0, 0, 0], [0, 0, 1.0]])
    m = avaliacao.metricas(probs, np.array([0, 2]))
    assert m["rps"] == pytest.approx(0) and m["brier"] == pytest.approx(0)
    ruim = avaliacao.metricas(np.array([[0, 0, 1.0]]), np.array([0]))
    assert ruim["rps"] == pytest.approx(1.0)  # pior erro possível


def test_probs_mercado_remove_margem():
    df = pd.DataFrame({"odd_med_casa": [2.0], "odd_med_empate": [3.2], "odd_med_fora": [3.8]})
    p = avaliacao.probs_mercado(df)
    assert p.sum() == pytest.approx(1.0)
