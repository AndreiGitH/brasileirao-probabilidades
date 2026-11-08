"""Padronização dos nomes dos clubes entre as diferentes fontes de dados.

Cada fonte escreve o mesmo clube de um jeito ("CR Flamengo", "Flamengo",
"Sport Recife", "SC Recife"...). Todo o projeto usa o nome canônico deste
módulo. Um nome desconhecido gera erro em vez de passar em silêncio, porque
um clube duplicado estraga a tabela e o modelo sem dar sinal.
"""

from __future__ import annotations

import unicodedata

# nome canônico -> apelidos conhecidos nas fontes
_ALIASES: dict[str, list[str]] = {
    "América-MG": ["America-MG", "America MG", "América Mineiro", "America Mineiro"],
    "América-RN": ["America-RN", "America RN"],
    "Athletico-PR": [
        "Athletico-PR", "Atletico-PR", "Athletico PR", "Atletico PR", "CA Paranaense",
        "Athletico Paranaense", "Atletico Paranaense",
    ],
    "Atlético-GO": ["Atletico-GO", "Atletico GO", "Atlético Goianiense", "Atletico Goianiense"],
    "Atlético-MG": [
        "Atletico-MG", "Atletico MG", "CA Mineiro", "Atlético Mineiro", "Atletico Mineiro",
    ],
    "Avaí": ["Avai", "Avaí FC"],
    "Bahia": ["EC Bahia"],
    "Barueri": ["Gremio Barueri", "Grêmio Barueri"],
    "Botafogo": ["Botafogo-RJ", "Botafogo RJ", "Botafogo FR"],
    "Bragantino": ["RB Bragantino", "Red Bull Bragantino"],
    "Brasiliense": [],
    "Ceará": ["Ceara", "Ceará SC"],
    "Chapecoense": ["Chapecoense AF", "Chapecoense-SC", "Chapecoense SC"],
    "Corinthians": ["SC Corinthians Paulista"],
    "Coritiba": ["Coritiba FBC"],
    "CSA": [],
    "Criciúma": ["Criciuma", "Criciúma EC"],
    "Cruzeiro": ["Cruzeiro EC"],
    "Cuiabá": ["Cuiaba", "Cuiabá EC"],
    "Figueirense": [],
    "Flamengo": ["CR Flamengo", "Flamengo RJ"],
    "Fluminense": ["Fluminense FC"],
    "Fortaleza": ["Fortaleza EC"],
    "Goiás": ["Goias", "Goiás EC"],
    "Grêmio": ["Gremio", "Grêmio FBPA"],
    "Grêmio Prudente": ["Gremio Prudente"],
    "Guarani": [],
    "Internacional": ["SC Internacional"],
    "Ipatinga": [],
    "Joinville": [],
    "Juventude": ["EC Juventude"],
    "Mirassol": ["Mirassol FC"],
    "Náutico": ["Nautico"],
    "Palmeiras": ["SE Palmeiras"],
    "Paraná": ["Parana"],
    "Paysandu": [],
    "Ponte Preta": [],
    "Portuguesa": [],
    "Remo": ["Clube do Remo"],
    "Santa Cruz": [],
    "Santo André": ["Santo Andre"],
    "Santos": ["Santos FC"],
    "São Caetano": ["Sao Caetano"],
    "São Paulo": ["Sao Paulo", "São Paulo FC"],
    "Sport": ["Sport Recife", "SC Recife"],
    "Vasco": ["CR Vasco da Gama", "Vasco da Gama"],
    "Vitória": ["Vitoria", "EC Vitória"],
}


def _chave(nome: str) -> str:
    """Forma comparável: sem acento, minúscula, hífens e espaços unificados."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().replace("-", " ").split())


_MAPA: dict[str, str] = {}
for _canonico, _apelidos in _ALIASES.items():
    for _nome in [_canonico, *_apelidos]:
        _k = _chave(_nome)
        if _k in _MAPA and _MAPA[_k] != _canonico:
            raise RuntimeError(f"Apelido ambíguo: {_nome!r}")
        _MAPA[_k] = _canonico


class TimeDesconhecido(KeyError):
    pass


def padronizar(nome: str) -> str:
    """Devolve o nome canônico do clube ou levanta TimeDesconhecido."""
    try:
        return _MAPA[_chave(nome)]
    except KeyError:
        raise TimeDesconhecido(
            f"Clube sem nome canônico: {nome!r}. Adicione o apelido em brasileirao/times.py"
        ) from None


def canonicos() -> list[str]:
    return sorted(_ALIASES)
