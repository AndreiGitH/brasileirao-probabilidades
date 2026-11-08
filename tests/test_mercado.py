import json

import numpy as np
import pandas as pd
import pytest

from brasileirao.fontes import theoddsapi
from brasileirao.modelo import dixon_coles as dc
from brasileirao.modelo import entradas, mercado
from brasileirao.times import TimeDesconhecido, padronizar

ODDS = np.array([[1.50, 4.20, 7.00], [2.60, 3.10, 2.90], [5.50, 3.80, 1.65]])


@pytest.mark.parametrize("metodo", mercado.METODOS)
def test_probabilidades_somam_um(metodo):
    p = mercado.remover_margem(ODDS, metodo)
    assert np.allclose(p.sum(1), 1) and (p > 0).all()


def test_potencia_e_shin_tiram_mais_do_azarao():
    prop = mercado.proporcional(ODDS[:1])[0]
    for metodo in ("potencia", "shin"):
        p = mercado.remover_margem(ODDS[:1], metodo)[0]
        assert p[2] < prop[2]   # azarão (odd 7.0) perde probabilidade
        assert p[0] > prop[0]   # favorito ganha


def test_odds_sem_margem_ficam_iguais():
    justas = 1 / np.array([[0.5, 0.3, 0.2]])
    for metodo in mercado.METODOS:
        assert np.allclose(mercado.remover_margem(justas, metodo), [[0.5, 0.3, 0.2]], atol=1e-6)


def test_odd_invalida():
    with pytest.raises(ValueError):
        mercado.proporcional([[1.0, 3.0, 4.0]])


@pytest.mark.parametrize("alvo", [[0.62, 0.23, 0.15], [0.35, 0.30, 0.35], [0.18, 0.27, 0.55]])
def test_taxas_reproduzem_o_1x2(alvo):
    lam, mu = mercado.taxas_do_mercado(alvo, rho=-0.07)
    p = dc.prob_1x2(dc.matriz_placares(lam, mu, -0.07))
    assert np.allclose(p, alvo, atol=1e-4)


def test_nome_com_uf():
    assert padronizar("Flamengo-RJ") == "Flamengo"
    assert padronizar("Sao Paulo-SP") == "São Paulo"
    assert padronizar("Vasco da Gama-RJ") == "Vasco"
    with pytest.raises(TimeDesconhecido):
        padronizar("Botafogo-SP")  # outro clube, não o Botafogo carioca


EVENTOS = [{
    "id": "abc", "sport_key": "soccer_brazil_campeonato",
    "commence_time": "2026-11-19T00:30:00Z",
    "home_team": "Flamengo-RJ", "away_team": "Athletico Paranaense",
    "bookmakers": [
        {"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-11-17T12:00:00Z",
         "markets": [{"key": "h2h", "last_update": "2026-11-17T12:00:00Z", "outcomes": [
             {"name": "Flamengo-RJ", "price": 1.45}, {"name": "Athletico Paranaense",
                                                      "price": 7.5},
             {"name": "Draw", "price": 4.6}]}]},
        {"key": "onexbet", "title": "1xBet", "last_update": "2026-11-17T12:00:00Z",
         "markets": [{"key": "h2h", "outcomes": [
             {"name": "Flamengo-RJ", "price": 1.40}, {"name": "Athletico Paranaense",
                                                      "price": 7.0},
             {"name": "Draw", "price": 4.4}]}]},
    ],
}]


def test_parse_theoddsapi():
    df = theoddsapi.parse(json.loads(json.dumps(EVENTOS)), "2026-11-17T13:00:00+00:00")
    assert len(df) == 2
    r = df[df["casa_apostas"] == "pinnacle"].iloc[0]
    assert (r["mandante"], r["visitante"]) == ("Flamengo", "Athletico-PR")
    assert r["data"] == pd.Timestamp("2026-11-18")  # 00:30 UTC = 21:30 de Brasília
    assert (r["odd_casa"], r["odd_empate"], r["odd_fora"]) == (1.45, 4.6, 7.5)


def test_chave_brasileirao():
    esportes = [
        {"key": "soccer_brazil_serie_b", "group": "Soccer", "title": "Brazil Série B"},
        {"key": "soccer_brazil_campeonato", "group": "Soccer", "title": "Brazil Série A"},
    ]
    assert theoddsapi.chave_brasileirao(esportes) == "soccer_brazil_campeonato"


def test_consenso_prefere_pinnacle_e_usa_coleta_mais_recente():
    df = theoddsapi.parse(EVENTOS, "2026-11-17T13:00:00+00:00")
    antiga = df.assign(coletado_em="2026-11-10T00:00:00+00:00", odd_casa=3.0)
    c = entradas.consenso(pd.concat([antiga, df]))
    r = c.iloc[0]
    assert r["fonte_odds"] == "pinnacle"
    esperado = mercado.potencia([[1.45, 4.6, 7.5]])[0]
    assert np.allclose(r[["p_casa", "p_empate", "p_fora"]].to_numpy(float), esperado)


def test_consenso_sem_casa_preferida_usa_media():
    df = theoddsapi.parse(EVENTOS, "x")
    c = entradas.consenso(df[df["casa_apostas"] == "onexbet"])
    assert c.iloc[0]["fonte_odds"] == "media"
