import pandas as pd

from brasileirao.esquema import COLUNAS_ODDS, validar
from brasileirao.tabela import classificacao


def _jogos(linhas):
    df = pd.DataFrame(linhas, columns=["mandante", "visitante", "gols_mandante",
                                       "gols_visitante"])
    df["gols_mandante"] = df["gols_mandante"].astype("Int64")
    df["gols_visitante"] = df["gols_visitante"].astype("Int64")
    return df


def test_criterios_basicos():
    t = classificacao(_jogos([
        ("Bahia", "Vitória", 2, 0),   # Bahia 3 pts, 1 V
        ("Vitória", "Sport", 1, 1),
        ("Sport", "Bahia", 0, 0),
    ]))
    assert t.iloc[0]["time"] == "Bahia" and t.iloc[0]["pts"] == 4


def test_vitorias_antes_do_saldo():
    # A: 1V 2D... montamos A e B com 3 pts; A com 1 vitória, B com 3 empates
    t = classificacao(_jogos([
        ("A", "X", 5, 0), ("A", "Y", 0, 1), ("A", "Z", 0, 1),
        ("B", "X", 0, 0), ("B", "Y", 0, 0), ("B", "Z", 0, 0),
    ]))
    pos = {r["time"]: i for i, r in t.iterrows()}
    assert pos["A"] < pos["B"]


def test_confronto_direto_desempata_par():
    # B e A terminam iguais em pts/V/SG/GP; B venceu o confronto direto.
    t = classificacao(_jogos([
        ("A", "B", 0, 1),
        ("A", "X", 1, 0),
        ("Y", "B", 1, 0),
    ]))
    linhas = t.set_index("time")
    assert linhas.loc["A", "pts"] == linhas.loc["B", "pts"]
    assert list(t["time"]).index("B") < list(t["time"]).index("A")


def test_validar_aponta_confronto_repetido():
    df = _jogos([("A", "B", 1, 0), ("A", "B", 2, 0)])
    df["temporada"] = 2003
    for c in COLUNAS_ODDS:
        df[c] = float("nan")
    assert any("repetido" in p for p in validar(df))
