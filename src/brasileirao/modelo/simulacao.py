"""Monte Carlo das rodadas restantes, vetorizado em numpy.

Para cada jogo restante sorteia um PLACAR da matriz Dixon-Coles (λ, μ, ρ), soma
à campanha atual e ordena com os critérios do Brasileirão: pontos, vitórias,
saldo, gols pró, confronto direto (só quando exatamente dois clubes empatam) e,
na falta de dados de cartões, sorteio.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import dixon_coles as dc

MAX_GOLS = 10


@dataclass
class Resultado:
    times: list[str]
    posicoes: np.ndarray          # (n_sim, n_times): posição final (1 = campeão)
    pontos: np.ndarray            # (n_sim, n_times)

    @property
    def n(self) -> int:
        return self.posicoes.shape[0]

    def distribuicao(self) -> pd.DataFrame:
        """P(clube termina em cada posição)."""
        n_t = len(self.times)
        cont = np.stack([(self.posicoes == k).mean(0) for k in range(1, n_t + 1)], axis=1)
        return pd.DataFrame(cont, index=self.times, columns=range(1, n_t + 1))

    def resumo(self, faixas: tuple[int, ...] = (4, 5, 6), z: int = 4) -> pd.DataFrame:
        """Chances de título, de terminar entre os N primeiros (gN) e de rebaixamento."""
        n_t = len(self.times)
        pos = self.posicoes
        colunas = {
            "pts_medio": self.pontos.mean(0),
            "pos_media": pos.mean(0),
            "titulo": (pos == 1).mean(0),
        }
        for g in faixas:
            colunas[f"g{g}"] = (pos <= g).mean(0)
        colunas["rebaixamento"] = (pos > n_t - z).mean(0)
        df = pd.DataFrame(colunas, index=self.times)
        return df.sort_values(["pos_media", "pts_medio"], ascending=[True, False])


def _sortear_placares(lam, mu, rho, n_sim, rng) -> tuple[np.ndarray, np.ndarray]:
    """(n_sim, n_jogos) de gols do mandante e do visitante."""
    n_jogos = len(lam)
    gm = np.empty((n_sim, n_jogos), dtype=np.int16)
    gv = np.empty((n_sim, n_jogos), dtype=np.int16)
    lado = MAX_GOLS + 1
    for k in range(n_jogos):
        cdf = np.cumsum(dc.matriz_placares(lam[k], mu[k], rho, MAX_GOLS).ravel())
        idx = np.searchsorted(cdf, rng.random(n_sim) * cdf[-1], side="right")
        idx = np.minimum(idx, lado * lado - 1)
        gm[:, k], gv[:, k] = np.divmod(idx, lado)
    return gm, gv


def _campanha_atual(jogados: pd.DataFrame, idx: dict[str, int]):
    n_t = len(idx)
    pts, v, gp, gc = (np.zeros(n_t, dtype=np.int32) for _ in range(4))
    for r in jogados.itertuples(index=False):
        m, w = idx[r.mandante], idx[r.visitante]
        a, b = int(r.gols_mandante), int(r.gols_visitante)
        gp[m] += a
        gc[m] += b
        gp[w] += b
        gc[w] += a
        if a > b:
            pts[m] += 3
            v[m] += 1
        elif a < b:
            pts[w] += 3
            v[w] += 1
        else:
            pts[m] += 1
            pts[w] += 1
    return pts, v, gp, gc


def simular(jogados: pd.DataFrame, restantes: pd.DataFrame, rho: float,
            n_sim: int = 100_000, seed: int | None = 0) -> Resultado:
    """`restantes` precisa das colunas mandante, visitante, lambda, mu."""
    rng = np.random.default_rng(seed)
    times = sorted(set(jogados["mandante"]) | set(jogados["visitante"])
                   | set(restantes["mandante"]) | set(restantes["visitante"]))
    idx = {t: i for i, t in enumerate(times)}
    n_t = len(times)
    pts0, v0, gp0, gc0 = _campanha_atual(jogados, idx)

    im = restantes["mandante"].map(idx).to_numpy()
    iv = restantes["visitante"].map(idx).to_numpy()
    gm, gv = _sortear_placares(restantes["lambda"].to_numpy(float),
                               restantes["mu"].to_numpy(float), rho, n_sim, rng)

    pts = np.tile(pts0, (n_sim, 1))
    vit = np.tile(v0, (n_sim, 1))
    gp = np.tile(gp0, (n_sim, 1))
    gc = np.tile(gc0, (n_sim, 1))
    for k in range(len(im)):
        a, b = gm[:, k].astype(np.int32), gv[:, k].astype(np.int32)
        m, w = im[k], iv[k]
        gp[:, m] += a
        gc[:, m] += b
        gp[:, w] += b
        gc[:, w] += a
        vm, vv, em = a > b, a < b, a == b
        pts[:, m] += 3 * vm + em
        pts[:, w] += 3 * vv + em
        vit[:, m] += vm
        vit[:, w] += vv

    # Chave lexicográfica numa só int64: pontos > vitórias > saldo > gols pró.
    sg = gp - gc
    chave = ((pts.astype(np.int64) * 100 + vit) * 1000 + (sg + 500)) * 1000 + gp
    sorteio = rng.random((n_sim, n_t))
    ordem = np.lexsort((sorteio, -chave), axis=1)  # última chave = primária
    _confronto_direto(ordem, chave, jogados, restantes, gm, gv, idx)

    posicoes = np.empty_like(ordem)
    np.put_along_axis(posicoes, ordem, np.arange(1, n_t + 1)[None, :], axis=1)
    return Resultado(times, posicoes, pts)


def _confronto_direto(ordem, chave, jogados, restantes, gm, gv, idx) -> None:
    """Onde exatamente dois clubes empatam em tudo, o confronto direto decide.

    Altera `ordem` no lugar. Empates de 3+ clubes seguem para o sorteio
    (o regulamento usa cartões, que não temos).
    """
    ch_ord = np.take_along_axis(chave, ordem, axis=1)
    igual = ch_ord[:, 1:] == ch_ord[:, :-1]          # posição p empata com p+1
    if not igual.any():
        return
    antes = np.pad(igual[:, :-1], ((0, 0), (1, 0)))   # p-1 empata com p
    depois = np.pad(igual[:, 1:], ((0, 0), (0, 1)))   # p+1 empata com p+2
    so_par = igual & ~antes & ~depois
    sims, ps = np.nonzero(so_par)
    if len(sims) == 0:
        return

    # pontos de confronto direto já disputados (fixos) e jogos restantes entre eles
    fixos: dict[tuple[int, int], int] = {}
    for r in jogados.itertuples(index=False):
        m, w = idx[r.mandante], idx[r.visitante]
        a, b = int(r.gols_mandante), int(r.gols_visitante)
        fixos[(m, w)] = fixos.get((m, w), 0) + (3 if a > b else 1 if a == b else 0)
        fixos[(w, m)] = fixos.get((w, m), 0) + (3 if b > a else 1 if a == b else 0)
    im = restantes["mandante"].map(idx).to_numpy()
    iv = restantes["visitante"].map(idx).to_numpy()

    for s, p in zip(sims, ps):
        x, y = ordem[s, p], ordem[s, p + 1]
        px, py = fixos.get((x, y), 0), fixos.get((y, x), 0)
        for k in np.nonzero(((im == x) & (iv == y)) | ((im == y) & (iv == x)))[0]:
            a, b = int(gm[s, k]), int(gv[s, k])
            pts_casa = 3 if a > b else 1 if a == b else 0
            pts_fora = 3 if b > a else 1 if a == b else 0
            if im[k] == x:
                px, py = px + pts_casa, py + pts_fora
            else:
                px, py = px + pts_fora, py + pts_casa
        if py > px:
            ordem[s, p], ordem[s, p + 1] = y, x
