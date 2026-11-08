import pytest

from brasileirao.times import TimeDesconhecido, padronizar


@pytest.mark.parametrize("entrada,esperado", [
    ("CR Flamengo", "Flamengo"),
    ("Atletico-MG", "Atlético-MG"),
    ("CA Mineiro", "Atlético-MG"),
    ("CA Paranaense", "Athletico-PR"),
    ("Atletico-PR", "Athletico-PR"),
    ("SC Recife", "Sport"),
    ("Sport Recife", "Sport"),
    ("Botafogo RJ", "Botafogo"),
    ("Grêmio FBPA", "Grêmio"),
    ("gremio", "Grêmio"),
    ("Clube do Remo", "Remo"),
    ("Sao Paulo", "São Paulo"),
])
def test_apelidos(entrada, esperado):
    assert padronizar(entrada) == esperado


def test_desconhecido_gera_erro():
    with pytest.raises(TimeDesconhecido):
        padronizar("Time Inventado FC")
