import json
import re

import numpy as np
import pandas as pd

from brasileirao import painel
from brasileirao.modelo import elo


def test_painel_gera_html_com_dados_validos(tmp_path):
    saida = painel.gerar(2026, tmp_path / "index.html")
    html = saida.read_text(encoding="utf-8")
    bruto = re.search(r'<script id="dados" type="application/json">(.*?)</script>', html, re.DOTALL)
    d = json.loads(bruto.group(1).replace("<\\/", "</"))
    assert len(d["clubes"]) == 20
    assert abs(sum(c["titulo"] for c in d["clubes"]) - 1) < 1e-6
    assert abs(sum(c["z4"] for c in d["clubes"]) - 4) < 1e-6
    for c in d["clubes"]:
        assert abs(sum(c["posicoes"]) - 1) < 1e-6


def test_elo_vencedor_sobe_e_logit_soma_um():
    jogos = pd.DataFrame({"temporada": [2020] * 3,
                          "data": pd.to_datetime(["2020-01-01", "2020-01-08", "2020-01-15"]),
                          "mandante": ["A", "A", "B"], "visitante": ["B", "B", "A"],
                          "gols_mandante": pd.array([2, 3, 0], dtype="Int64"),
                          "gols_visitante": pd.array([0, 0, 1], dtype="Int64")})
    h = elo.historico(jogos, k=20, mando=0)["dif_elo"].to_numpy()
    assert h[0] == 0 and h[1] > 0  # A venceu o 1º jogo, chega ao 2º com rating maior
    p = elo.prever(np.array([0.005, -1.0, 0.0]), [-200, 0, 200])
    assert np.allclose(p.sum(1), 1) and p[2, 0] > p[0, 0]
