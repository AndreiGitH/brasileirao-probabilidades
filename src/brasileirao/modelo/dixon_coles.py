"""Modelo de Dixon & Coles (1997) para placares de futebol.

Gols do mandante ~ Poisson(λ) e do visitante ~ Poisson(μ), com

    log λ = c + h + ataque[mandante] + defesa[visitante]
    log μ = c +     ataque[visitante] + defesa[mandante]

(defesa maior = sofre mais gols). Ataque e defesa são centrados em zero e
`c` é o nível médio de gols. A correção τ(ρ) ajusta 0x0, 1x0, 0x1 e 1x1, que
a Poisson independente erra. Cada jogo pesa exp(-ξ · dias até a data de
referência), dando mais peso à fase recente. Uma penalidade ridge leve puxa
ataque/defesa para a média, o que estabiliza clubes com poucos jogos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

RHO_LIMITE = 0.25


@dataclass
class Parametros:
    times: list[str]
    ataque: np.ndarray
    defesa: np.ndarray
    intercepto: float
    mando: float
    rho: float
    data_ref: pd.Timestamp
    xi: float

    def tabela(self) -> pd.DataFrame:
        return (pd.DataFrame({"ataque": self.ataque, "defesa": self.defesa}, index=self.times)
                .sort_values("ataque", ascending=False))


def _tau(x, y, lam, mu, rho):
    t = np.ones_like(lam)
    t = np.where((x == 0) & (y == 0), 1 - lam * mu * rho, t)
    t = np.where((x == 0) & (y == 1), 1 + lam * rho, t)
    t = np.where((x == 1) & (y == 0), 1 + mu * rho, t)
    t = np.where((x == 1) & (y == 1), 1 - rho, t)
    return t


def _desempacotar(theta, n):
    a = theta[:n] - theta[:n].mean()
    d = theta[n:2 * n] - theta[n:2 * n].mean()
    return a, d, theta[2 * n], theta[2 * n + 1], theta[2 * n + 2]


def _nll_e_gradiente(theta, ih, iv, x, y, w, n, ridge):
    """Log-verossimilhança negativa ponderada e seu gradiente analítico."""
    a, d, c, h, rho = _desempacotar(theta, n)
    log_lam = c + h + a[ih] + d[iv]
    log_mu = c + a[iv] + d[ih]
    lam, mu = np.exp(log_lam), np.exp(log_mu)
    tau = _tau(x, y, lam, mu, rho)
    if np.any(tau <= 0):
        return 1e12, np.zeros_like(theta)

    ll = np.log(tau) + x * log_lam - lam + y * log_mu - mu
    nll = -np.sum(w * ll) + ridge * (np.sum(a ** 2) + np.sum(d ** 2))

    # derivadas de log τ
    z00 = (x == 0) & (y == 0)
    z01 = (x == 0) & (y == 1)
    z10 = (x == 1) & (y == 0)
    z11 = (x == 1) & (y == 1)
    dtau_dlam = np.where(z00, -mu * rho, 0) + np.where(z01, rho, 0)
    dtau_dmu = np.where(z00, -lam * rho, 0) + np.where(z10, rho, 0)
    dtau_drho = (np.where(z00, -lam * mu, 0) + np.where(z01, lam, 0)
                 + np.where(z10, mu, 0) + np.where(z11, -1, 0))
    g_loglam = w * (x - lam + lam * dtau_dlam / tau)   # dℓ/d log λ
    g_logmu = w * (y - mu + mu * dtau_dmu / tau)
    g_rho = np.sum(w * dtau_drho / tau)

    g_a = np.bincount(ih, g_loglam, n) + np.bincount(iv, g_logmu, n)
    g_d = np.bincount(iv, g_loglam, n) + np.bincount(ih, g_logmu, n)
    g_a = -(g_a - g_a.mean()) + 2 * ridge * (a - a.mean())
    g_d = -(g_d - g_d.mean()) + 2 * ridge * (d - d.mean())
    grad = np.concatenate([g_a, g_d, [-(g_loglam.sum() + g_logmu.sum()),
                                      -g_loglam.sum(), -g_rho]])
    return nll, grad


def pesos(datas: pd.Series, data_ref: pd.Timestamp, xi: float) -> np.ndarray:
    dias = (data_ref - pd.to_datetime(datas)).dt.days.to_numpy(dtype=float)
    return np.exp(-xi * np.clip(dias, 0, None))


def ajustar(jogos: pd.DataFrame, data_ref: pd.Timestamp | str, xi: float = 0.003,
            ridge: float = 1.0, janela_dias: int = 730) -> Parametros:
    """Ajusta o modelo usando só jogos encerrados ANTES de `data_ref`."""
    data_ref = pd.Timestamp(data_ref)
    j = jogos[(jogos["data"] < data_ref)
              & (jogos["data"] >= data_ref - pd.Timedelta(days=janela_dias))
              & jogos["gols_mandante"].notna()]
    if len(j) < 50:
        raise ValueError(f"Poucos jogos para ajustar ({len(j)})")
    times = sorted(set(j["mandante"]) | set(j["visitante"]))
    idx = {t: i for i, t in enumerate(times)}
    n = len(times)
    ih = j["mandante"].map(idx).to_numpy()
    iv = j["visitante"].map(idx).to_numpy()
    x = j["gols_mandante"].to_numpy(dtype=float)
    y = j["gols_visitante"].to_numpy(dtype=float)
    w = pesos(j["data"], data_ref, xi)

    media = np.log(max((x * w).sum() + (y * w).sum(), 1e-9) / (2 * w.sum()))
    theta0 = np.concatenate([np.zeros(2 * n), [media, 0.25, -0.05]])
    limites = [(None, None)] * (2 * n + 2) + [(-RHO_LIMITE, RHO_LIMITE)]
    res = minimize(_nll_e_gradiente, theta0, args=(ih, iv, x, y, w, n, ridge),
                   jac=True, method="L-BFGS-B", bounds=limites)
    if not res.success:
        raise RuntimeError(f"Ajuste não convergiu: {res.message}")
    a, d, c, h, rho = _desempacotar(res.x, n)
    return Parametros(times, a, d, float(c), float(h), float(rho), data_ref, xi)


def taxas(p: Parametros, mandantes, visitantes) -> tuple[np.ndarray, np.ndarray]:
    """λ e μ esperados. Clube sem histórico recebe ataque/defesa médios (zero)."""
    idx = {t: i for i, t in enumerate(p.times)}
    a = np.append(p.ataque, 0.0)
    d = np.append(p.defesa, 0.0)
    ih = np.array([idx.get(t, -1) for t in mandantes])
    iv = np.array([idx.get(t, -1) for t in visitantes])
    lam = np.exp(p.intercepto + p.mando + a[ih] + d[iv])
    mu = np.exp(p.intercepto + a[iv] + d[ih])
    return lam, mu


def matriz_placares(lam: float, mu: float, rho: float, max_gols: int = 10) -> np.ndarray:
    """M[i, j] = P(mandante faz i, visitante faz j), já com a correção τ."""
    g = np.arange(max_gols + 1)
    m = np.outer(poisson.pmf(g, lam), poisson.pmf(g, mu))
    m[0, 0] *= 1 - lam * mu * rho
    m[0, 1] *= 1 + lam * rho
    m[1, 0] *= 1 + mu * rho
    m[1, 1] *= 1 - rho
    return m / m.sum()


def prob_1x2(m: np.ndarray) -> np.ndarray:
    return np.array([np.tril(m, -1).sum(), np.trace(m), np.triu(m, 1).sum()])


def prever(p: Parametros, jogos: pd.DataFrame, max_gols: int = 10) -> pd.DataFrame:
    """Probabilidades 1X2 e gols esperados para cada linha de `jogos`."""
    lam, mu = taxas(p, jogos["mandante"], jogos["visitante"])
    probs = np.array([prob_1x2(matriz_placares(a, b, p.rho, max_gols))
                      for a, b in zip(lam, mu)])
    out = jogos[["data", "mandante", "visitante"]].copy()
    out["lambda"], out["mu"] = lam, mu
    out["p_casa"], out["p_empate"], out["p_fora"] = probs.T
    return out
