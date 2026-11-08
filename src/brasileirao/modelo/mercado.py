"""Odds de mercado -> probabilidades e -> taxas de gols (λ, μ).

Remoção de margem ("devig"):
- proporcional: divide 1/odd pela soma. Simples, mas atribui a margem por igual.
- potência: p_i = (1/odd_i)^k, com k tal que a soma dê 1. Tira mais dos azarões,
  onde as casas costumam embutir mais margem (viés favorito-azarão).
- Shin (1992/1993): modela uma fração z de apostadores com informação privilegiada;
  também corrige o viés favorito-azarão.

Depois, `taxas_do_mercado` encontra λ e μ cujo Dixon-Coles reproduz o 1X2 do
mercado, para que a simulação sorteie placares (necessários no desempate).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq, least_squares

from . import dixon_coles as dc

METODOS = ("proporcional", "potencia", "shin")


def _inversas(odds) -> np.ndarray:
    odds = np.atleast_2d(np.asarray(odds, dtype=float))
    if np.any(odds <= 1):
        raise ValueError("odds decimais precisam ser > 1")
    return 1.0 / odds


def proporcional(odds) -> np.ndarray:
    inv = _inversas(odds)
    return inv / inv.sum(1, keepdims=True)


def potencia(odds) -> np.ndarray:
    inv = _inversas(odds)
    out = np.empty_like(inv)
    for i, linha in enumerate(inv):
        k = brentq(lambda k, x=linha: np.sum(x ** k) - 1, 1e-3, 50)
        out[i] = linha ** k
    return out / out.sum(1, keepdims=True)


def shin(odds) -> np.ndarray:
    inv = _inversas(odds)
    out = np.empty_like(inv)
    for i, linha in enumerate(inv):
        soma = linha.sum()

        def probs(z, x=linha, s=soma):
            return (np.sqrt(z ** 2 + 4 * (1 - z) * x ** 2 / s) - z) / (2 * (1 - z))

        if soma <= 1:  # sem margem (ou exchange): nada a corrigir
            out[i] = linha / soma
            continue
        z = brentq(lambda z: probs(z).sum() - 1, 0.0, 0.5)
        out[i] = probs(z)
    return out / out.sum(1, keepdims=True)


def remover_margem(odds, metodo: str = "potencia") -> np.ndarray:
    funcs = {"proporcional": proporcional, "potencia": potencia, "shin": shin}
    if metodo not in funcs:
        raise ValueError(f"método desconhecido: {metodo}; use um de {METODOS}")
    return funcs[metodo](odds)


def taxas_do_mercado(p_1x2, rho: float, chute: tuple[float, float] = (1.4, 1.0),
                     max_gols: int = 10) -> tuple[float, float]:
    """(λ, μ) tais que o Dixon-Coles com esse ρ reproduza as probabilidades 1X2."""
    alvo = np.asarray(p_1x2, dtype=float)

    def residuos(log_taxas):
        lam, mu = np.exp(log_taxas)
        return dc.prob_1x2(dc.matriz_placares(lam, mu, rho, max_gols)) - alvo

    res = least_squares(residuos, np.log(chute), bounds=(np.log(0.05), np.log(6.0)))
    lam, mu = np.exp(res.x)
    return float(lam), float(mu)
