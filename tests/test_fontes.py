"""Parsers testados com amostras no formato real de cada fonte (sem rede)."""

import json

import pandas as pd

from brasileirao.fontes import footballdata_org, footballdata_uk, historico_github, openfootball


def test_historico_github():
    csv = (
        b'"ID","rodata","data","hora","mandante","visitante","formacao_mandante",'
        b'"formacao_visitante","tecnico_mandante","tecnico_visitante","vencedor","arena",'
        b'"mandante_Placar","visitante_Placar","mandante_Estado","visitante_Estado"\n'
        b'"1","38","25/02/2021","21:30","Sao Paulo","Palmeiras","","","","","Sao Paulo",'
        b'" Morumbi","1","0","SP","SP"\n'
    )
    df = historico_github.parse(csv)
    r = df.iloc[0]
    assert r["temporada"] == 2020  # jogo de 2021 pertence à temporada 2020
    assert (r["mandante"], r["visitante"]) == ("São Paulo", "Palmeiras")
    assert (r["gols_mandante"], r["gols_visitante"]) == (1, 0)
    assert r["rodada"] == 38


def test_openfootball_dois_formatos_de_placar():
    dados = {"name": "x", "matches": [
        {"round": "Matchday 1", "date": "2026-01-28", "team1": "CR Flamengo",
         "team2": "SE Palmeiras", "score": {"ht": [0, 0], "ft": [2, 1]}},
        {"round": "Matchday 1", "date": "2026-01-29", "team1": "EC Bahia",
         "team2": "Santos FC", "score": [0, 0]},
        {"round": "Matchday 37", "date": "2026-11-28", "team1": "Mirassol FC",
         "team2": "CA Paranaense"},
    ]}
    df = openfootball.parse(json.dumps(dados).encode(), 2026)
    assert df["gols_mandante"].tolist()[:2] == [2, 0]
    assert pd.isna(df["gols_mandante"].iloc[2])
    assert df["rodada"].tolist() == [1, 1, 37]


def test_footballdata_uk_odds():
    csv = (
        "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA,"
        "MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA\n"
        "Brazil,Serie A,2025,07/12/2025,19:00,Flamengo,Mirassol,3,0,H,1.40,4.9,8.5,"
        "1.45,5.0,9.0,1.38,4.7,8.0\n"
    ).encode("latin-1")
    r = footballdata_uk.parse(csv).iloc[0]
    assert r["temporada"] == 2025 and r["data"] == pd.Timestamp("2025-12-07")
    assert (r["odd_pin_casa"], r["odd_med_fora"]) == (1.40, 8.0)


def test_footballdata_org_fuso_e_status():
    dados = {"matches": [
        {"utcDate": "2026-11-20T01:30:00Z", "status": "FINISHED", "matchday": 35,
         "homeTeam": {"name": "CR Flamengo", "shortName": "Flamengo"},
         "awayTeam": {"name": "Grêmio FBPA", "shortName": "Grêmio"},
         "score": {"fullTime": {"home": 2, "away": 2}}},
        {"utcDate": "2026-11-28T22:00:00Z", "status": "TIMED", "matchday": 37,
         "homeTeam": {"name": "Mirassol FC"}, "awayTeam": {"name": "CA Paranaense"},
         "score": {"fullTime": {"home": None, "away": None}}},
    ]}
    df = footballdata_org.parse(json.dumps(dados).encode(), 2026)
    # 01:30 UTC = 22:30 do dia anterior em Brasília
    assert df["data"].iloc[0] == pd.Timestamp("2026-11-19")
    assert df["gols_mandante"].iloc[0] == 2
    assert pd.isna(df["gols_mandante"].iloc[1])
