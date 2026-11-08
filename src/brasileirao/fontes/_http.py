"""Download com cache em data/raw (fora do Git)."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

from .. import DADOS

CACHE = DADOS / "raw"
USER_AGENT = "brasileirao-probabilidades (projeto pessoal de estudo)"


def baixar(url: str, *, headers: dict | None = None, max_idade_h: float = 6.0,
           nome: str | None = None) -> bytes:
    """Baixa `url`, reaproveitando a cópia local se tiver menos de `max_idade_h` horas."""
    CACHE.mkdir(parents=True, exist_ok=True)
    nome = nome or hashlib.sha1(url.encode()).hexdigest()[:16]
    caminho: Path = CACHE / nome
    if caminho.exists() and (time.time() - caminho.stat().st_mtime) < max_idade_h * 3600:
        return caminho.read_bytes()
    h = {"User-Agent": USER_AGENT, **(headers or {})}
    resp = requests.get(url, headers=h, timeout=60)
    resp.raise_for_status()
    caminho.write_bytes(resp.content)
    return resp.content
