"""Gera painel/index.html: página única, sem internet, com as probabilidades.

Lê os arquivos de data/processed/simulacoes (resumo, posições e jogos de cada
data) e, se existir, a calibração do backtest. Os dados vão embutidos como
JSON e o próprio navegador desenha tabelas e gráficos.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pandas as pd

from . import DADOS, RAIZ, dados
from .tabela import classificacao

SIM = DADOS / "processed" / "simulacoes"
SAIDA = RAIZ / "painel" / "index.html"
REPO = os.environ.get("GITHUB_REPOSITORY", "AndreiGitH/brasileirao-probabilidades")
LINK_ATUALIZAR = f"https://github.com/{REPO}/actions/workflows/atualizar.yml"


def _datas() -> list[str]:
    return sorted(p.stem for p in SIM.glob("*.csv") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem))


def montar_dados(temporada: int) -> dict:
    datas = _datas()
    if not datas:
        raise RuntimeError("Nenhuma simulação encontrada. Rode `brasileirao simular` antes.")
    ultima = datas[-1]
    resumo = pd.read_csv(SIM / f"{ultima}.csv")
    pos = pd.read_csv(SIM / f"{ultima}_posicoes.csv").set_index("time")
    jogos_rest = pd.read_csv(SIM / f"{ultima}_jogos.csv")

    base = dados.carregar()
    temp = base[(base["temporada"] == temporada) & (base["data"] < ultima)]
    tab = classificacao(temp).set_index("time")
    rodada = int(temp["rodada"].max()) if temp["rodada"].notna().any() else None

    clubes = []
    for r in resumo.itertuples(index=False):
        atual = tab.loc[r.time]
        clubes.append({
            "time": r.time, "pts": int(atual["pts"]), "j": int(atual["j"]),
            "sg": int(atual["sg"]), "pos_atual": int(tab.index.get_loc(r.time)) + 1,
            "pts_medio": r.pts_medio, "pos_media": r.pos_media, "titulo": r.titulo,
            "g4": r.g4, "g5": r.g5, "g6": r.g6, "z4": r.rebaixamento,
            "posicoes": pos.loc[r.time].tolist(),
        })

    evolucao = []
    for d in datas:
        df = pd.read_csv(SIM / f"{d}.csv")
        evolucao.append({"data": d, **{r.time: {"titulo": r.titulo, "g6": r.g6,
                                                "z4": r.rebaixamento}
                                       for r in df.itertuples(index=False)}})

    calib_arq = DADOS / "processed" / "backtest" / "calibracao.csv"
    calib = pd.read_csv(calib_arq).to_dict("records") if calib_arq.exists() else []

    return {
        "temporada": temporada, "data": ultima, "rodada": rodada,
        "n_sim": int(resumo["n_sim"].iloc[0]),
        "origem": jogos_rest["origem"].value_counts().to_dict(),
        "clubes": clubes,
        "jogos": jogos_rest.round(4).to_dict("records"),
        "evolucao": evolucao,
        "calibracao": calib,
        "link_atualizar": LINK_ATUALIZAR,
    }


def gerar(temporada: int, saida: Path = SAIDA) -> Path:
    payload = json.dumps(montar_dados(temporada), ensure_ascii=False, default=str)
    payload = payload.replace("</", "<\\/")  # nunca fechar o <script> por acidente
    html = _MODELO.replace("__DADOS__", payload)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(html, encoding="utf-8")
    return saida


_MODELO = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Brasileirão — probabilidades</title>
<style>
:root { --bg:#fbfaf7; --fg:#1d1d1b; --muted:#6b6a65; --line:#e4e1d9; --panel:#ffffff;
  --azul:#2d6fb7; --verde:#2f8f5b; --vermelho:#c2412d; --ouro:#b8860b; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161614; --fg:#ecebe6; --muted:#a3a19a; --line:#34332f; --panel:#1f1f1c;
    --azul:#6aa5e8; --verde:#5cc28a; --vermelho:#ef7a63; --ouro:#e2b84a; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
main { max-width:1080px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:26px; margin:0 0 4px; letter-spacing:-.01em; }
h2 { font-size:18px; margin:36px 0 10px; }
.sub { color:var(--muted); margin:0 0 12px; }
.acoes { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin:0 0 20px; }
.botao { display:inline-block; padding:8px 14px; border-radius:8px; background:var(--azul);
  color:#fff; text-decoration:none; font-weight:600; font-size:14px; }
.botao:hover { filter:brightness(1.08); }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:14px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.card h3 { margin:0 0 10px; font-size:15px; }
.manual h3 { margin:20px 0 6px; font-size:16px; } .manual h3:first-child { margin-top:0; }
.manual li { margin:4px 0; }
.card select { font:inherit; font-size:13px; margin-left:6px; padding:2px 6px; border-radius:6px;
  border:1px solid var(--line); background:var(--panel); color:var(--fg); }
.barra { display:grid; grid-template-columns:110px 1fr 52px; align-items:center; gap:8px;
  margin:5px 0; font-size:14px; }
.trilho { height:12px; background:var(--line); border-radius:6px; overflow:hidden; }
.trilho > div { height:100%; border-radius:6px; }
.num { text-align:right; font-variant-numeric:tabular-nums; }
.tabela-wrap { overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--panel); }
table { border-collapse:collapse; width:100%; font-size:14px; font-variant-numeric:tabular-nums; }
th, td { padding:7px 8px; text-align:right; white-space:nowrap; border-bottom:1px solid var(--line); }
th { color:var(--muted); font-weight:600; font-size:12px; position:sticky; top:0; background:var(--panel); }
td.time, th.time { text-align:left; position:sticky; left:0; background:var(--panel); z-index:1; }
tr:last-child td { border-bottom:none; }
td.p { min-width:58px; }
.heat td.c { padding:0; min-width:26px; height:26px; text-align:center; font-size:10px; }
.legenda { color:var(--muted); font-size:13px; margin-top:8px; }
.jogo { display:grid; grid-template-columns:78px 1fr; gap:4px 10px; padding:9px 0;
  border-bottom:1px solid var(--line); }
.jogo:last-child { border-bottom:none; }
.jogo .quando { color:var(--muted); font-size:13px; grid-row:span 2; }
.empilhada { display:flex; height:16px; border-radius:4px; overflow:hidden; font-size:10px; color:#fff; }
.empilhada div { display:flex; align-items:center; justify-content:center; }
.tag { font-size:11px; color:var(--muted); }
svg text { fill:var(--muted); font-size:11px; }
.dica { position:fixed; pointer-events:none; background:var(--fg); color:var(--bg); padding:4px 8px;
  border-radius:6px; font-size:12px; display:none; z-index:9; }
details { margin-top:8px; }
</style>
</head>
<body>
<main>
<h1 id="titulo">Brasileirão</h1>
<p class="sub" id="sub"></p>
<div class="cards">
  <div class="card"><h3>Título</h3><div id="c-titulo"></div></div>
  <div class="card"><h3>Libertadores
    <select id="sel-g" aria-label="Faixa da Libertadores">
      <option value="4">G4</option><option value="5">G5</option><option value="6" selected>G6</option>
      <option value="7">G7</option><option value="8">G8</option>
    </select></h3><div id="c-g6"></div></div>
  <div class="card"><h3>Rebaixamento (Z4)</h3><div id="c-z4"></div></div>
</div>

<h2>Todos os clubes</h2>
<div class="tabela-wrap"><table id="tab"></table></div>
<p class="legenda">Pts: pontos atuais. Pts proj.: média de pontos ao fim do campeonato nas simulações.
G4/G5/G6: chance de terminar entre os 4, 5 ou 6 primeiros. O número de vagas na Libertadores pode mudar
com os campeões das copas, que o modelo não simula.</p>

<h2>Chance de cada posição final</h2>
<div class="tabela-wrap"><table class="heat" id="heat"></table></div>

<div id="evo-sec"><h2>Evolução das chances</h2><div class="card"><div id="evo"></div></div></div>

<h2>Próximos jogos</h2>
<div class="card" id="jogos"></div>
<p class="legenda">Barra: vitória do mandante · empate · vitória do visitante.
"Mercado" = odds sem a margem da casa (Pinnacle ou Betfair quando disponíveis);
"modelo" = Dixon-Coles, usado quando o jogo ainda não tem odds.</p>

<h2>Manual</h2>
<div class="card manual">
<h3>Visão geral</h3>
<p>O painel mostra, todo dia, a chance de cada clube ser campeão, terminar no G4 a G8 ou ser rebaixado.
O restante do campeonato é simulado <span id="nsim"></span> vezes usando as odds das casas de apostas sem a
margem e, quando um jogo ainda não tem odds, um modelo estatístico próprio (Dixon-Coles).</p>

<h3>Como ler o painel</h3>
<ul>
<li><b>Cartões:</b> título, Libertadores (o seletor escolhe G4 a G8) e rebaixamento.</li>
<li><b>Todos os clubes:</b> pontos atuais, pontos projetados (média nas simulações) e as chances. Cor mais forte = chance maior.</li>
<li><b>Chance de cada posição final:</b> cada linha soma 100%.</li>
<li><b>Evolução:</b> como as chances de título e Z4 mudaram a cada atualização.</li>
<li><b>Próximos jogos:</b> vitória do mandante · empate · vitória do visitante, com a origem (mercado ou modelo).</li>
<li>"—" = menos de 0,05%. "100%" = aconteceu em praticamente todas as simulações, não garantia matemática.</li>
</ul>

<h3>De onde vêm os dados</h3>
<ul>
<li>Placares 2003–2025: bases abertas no GitHub (adaoduque, openfootball).</li>
<li>Placares e calendário de 2026: football-data.org.</li>
<li>Odds de jogos já disputados (2012+): football-data.co.uk.</li>
<li>Odds dos próximos jogos: The Odds API (Pinnacle, Betfair e outras). Mostra só 1–2 semanas à frente.</li>
<li>Se uma fonte falhar e trouxer menos dados que os atuais, o programa mantém os dados antigos.</li>
</ul>

<h3>O modelo, passo a passo</h3>
<ol>
<li><b>Fonte de cada jogo:</b> Pinnacle → Betfair Exchange → média das casas → modelo Dixon-Coles.</li>
<li><b>Odds sem margem:</b> a probabilidade bruta é 1 ÷ odd, mas as três somam mais de 100% (o lucro da casa).
O método da potência usa p = (1/odd)<sup>k</sup>, com k escolhido para a soma dar 100%. Retira mais margem dos
azarões e foi o melhor de três métodos testados em 5.600 jogos.</li>
<li><b>Dixon-Coles:</b> cada clube tem força de ataque e de defesa, mais a vantagem de jogar em casa. Gols
esperados: λ = e<sup>c + h + ataque mandante + defesa visitante</sup> e μ = e<sup>c + ataque visitante + defesa mandante</sup>.
Os gols seguem Poisson, com correção para 0x0, 1x0, 0x1 e 1x1. Um jogo de 230 dias atrás pesa metade de um de hoje.</li>
<li><b>1X2 vira placar:</b> o programa acha os gols esperados que reproduzem as probabilidades do mercado, porque o desempate usa saldo e gols.</li>
<li><b>Monte Carlo:</b> sorteia o placar de cada jogo restante, soma à campanha atual e monta a tabela final, repetindo 100 mil vezes.</li>
<li><b>Desempate:</b> pontos → vitórias → saldo → gols marcados → confronto direto (entre dois clubes) → sorteio (no lugar dos cartões).</li>
<li><b>Resultado:</b> a chance é a fração de simulações em que o evento aconteceu. Erro do sorteio: no máximo ±0,3 ponto percentual.</li>
</ol>
<p>Ficaram de fora de propósito: "fator motivação" manual, notas por jogador e xG. O mercado já embute boa parte disso.</p>

<h3>Quão confiável é</h3>
<p>Testado em 2019–2025, temporadas que o modelo não viu. Por jogo nas rodadas 35–38 (erro RPS, menor = melhor):
mercado 0,2013; mistura 50/50 0,2041; Elo 0,2095; Dixon-Coles 0,2116. As chances finais se mostraram bem
calibradas: quando o modelo disse X%, o evento aconteceu perto de X% das vezes.</p>
<details><summary>Ver a calibração do teste</summary><div class="tabela-wrap" style="margin-top:8px">
<table id="calib"></table></div></details>
<p><b>Limitações:</b> não simula as copas (vagas na Libertadores podem mudar); sem cartões, o último desempate é
sorteio; jogos sem odds usam o modelo, menos preciso; 10% de chance acontece 1 vez em 10.</p>

<h3>Glossário</h3>
<ul>
<li><b>1X2:</b> vitória do mandante, empate, vitória do visitante.</li>
<li><b>Odd / margem:</b> quanto a casa paga; as probabilidades brutas somam mais de 100% por causa do lucro da casa.</li>
<li><b>λ, μ:</b> gols esperados do mandante e do visitante.</li>
<li><b>Monte Carlo:</b> repetir um sorteio muitas vezes e contar a frequência dos resultados.</li>
<li><b>Backtest:</b> testar o método em temporadas passadas sem deixar o modelo ver o futuro.</li>
<li><b>Calibração:</b> se o modelo diz 70%, o evento deve acontecer cerca de 70% das vezes.</li>
<li><b>G4…G8 / Z4:</b> terminar entre os N primeiros / nas 4 últimas posições (rebaixamento).</li>
</ul>
</div>

<div class="acoes" style="margin-top:28px">
  <a class="botao" id="atualizar" target="_blank" rel="noopener">Atualizar agora</a>
  <span class="tag">Atualiza sozinho todo dia às 23:50. O botão só funciona para o dono do
  repositório: abre o GitHub, toque em "Run workflow". Leva ~2 min.</span>
</div>
</main>
<div class="dica" id="dica"></div>
<script id="dados" type="application/json">__DADOS__</script>
<script>
const D = JSON.parse(document.getElementById('dados').textContent);
const pct = (x, casas = 1) => x >= 0.9995 ? '100%' : x < 0.0005 ? '—' :
  (x * 100).toFixed(x < 0.01 ? 1 : casas).replace('.', ',') + '%';
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const el = (tag, attrs = {}, texto) => { const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (texto !== undefined) e.textContent = texto; return e; };
const dataBR = s => { const [a, m, d] = s.split('-'); return `${d}/${m}/${a}`; };

document.getElementById('titulo').textContent = `Brasileirão ${D.temporada} — probabilidades`;
const contagem = {mercado: 0, modelo: 0};
for (const [k, v] of Object.entries(D.origem)) contagem[k.startsWith('mercado') ? 'mercado' : 'modelo'] += v;
const origem = [contagem.mercado && `${contagem.mercado} pelo mercado`,
                contagem.modelo && `${contagem.modelo} pelo modelo`].filter(Boolean).join(', ');
document.getElementById('sub').textContent =
  `Atualizado em ${dataBR(D.data)}` + (D.rodada ? ` · após a rodada ${D.rodada}` : '') +
  ` · ${D.n_sim.toLocaleString('pt-BR')} simulações · ${D.jogos.length} jogos restantes (${origem})`;
document.getElementById('atualizar').href = D.link_atualizar;
document.getElementById('nsim').textContent = D.n_sim.toLocaleString('pt-BR');

const ateG = (c, g) => c.posicoes.slice(0, g).reduce((a, b) => a + b, 0);
for (const c of D.clubes) for (let g = 4; g <= 8; g++) c['G' + g] = ateG(c, g);
function barras(id, campo, cor, filtro, limite) {
  const alvo = document.getElementById(id);
  alvo.innerHTML = '';
  const lista = D.clubes.filter(c => c[campo] >= filtro).sort((a, b) => b[campo] - a[campo]).slice(0, limite);
  if (!lista.length) { alvo.append(el('div', {class: 'tag'}, 'Já definido.')); return; }
  for (const c of lista) {
    const linha = el('div', {class: 'barra'});
    linha.append(el('span', {}, c.time));
    const t = el('div', {class: 'trilho'}); const f = el('div');
    f.style.width = (c[campo] * 100) + '%'; f.style.background = css(cor); t.append(f);
    linha.append(t, el('span', {class: 'num'}, pct(c[campo])));
    alvo.append(linha);
  }
}
barras('c-titulo', 'titulo', '--ouro', 0.0005, 6);
const selG = document.getElementById('sel-g');
const desenhaG = () => barras('c-g6', 'G' + selG.value, '--azul', 0.0005, 12);
selG.addEventListener('change', desenhaG); desenhaG();
barras('c-z4', 'z4', '--vermelho', 0.0005, 10);

function fundo(p, cor) {
  if (p < 0.0005) return '';
  return `color-mix(in srgb, ${css(cor)} ${Math.round(8 + p * 72)}%, transparent)`;
}
(function tabela() {
  const t = document.getElementById('tab');
  const cab = el('tr');
  [['#', ''], ['Clube', 'time'], ['Pts', ''], ['J', ''], ['SG', ''], ['Pts proj.', ''],
   ['Título', ''], ['G4', ''], ['G5', ''], ['G6', ''], ['Z4', '']]
    .forEach(([n, c]) => cab.append(el('th', {class: c}, n)));
  t.append(cab);
  const ordem = [...D.clubes].sort((a, b) => a.pos_atual - b.pos_atual);
  for (const c of ordem) {
    const tr = el('tr');
    tr.append(el('td', {}, c.pos_atual), el('td', {class: 'time'}, c.time), el('td', {}, c.pts),
      el('td', {}, c.j), el('td', {}, c.sg), el('td', {}, c.pts_medio.toFixed(1).replace('.', ',')));
    for (const [campo, cor] of [['titulo', '--ouro'], ['g4', '--azul'], ['g5', '--azul'],
                                ['g6', '--azul'], ['z4', '--vermelho']]) {
      const td = el('td', {class: 'p'}, pct(c[campo])); td.style.background = fundo(c[campo], cor);
      tr.append(td);
    }
    t.append(tr);
  }
})();

(function heat() {
  const t = document.getElementById('heat'); const n = D.clubes.length;
  const cab = el('tr'); cab.append(el('th', {class: 'time'}, 'Clube'));
  for (let i = 1; i <= n; i++) cab.append(el('th', {}, i + 'º'));
  t.append(cab);
  const ordem = [...D.clubes].sort((a, b) => a.pos_media - b.pos_media);
  for (const c of ordem) {
    const tr = el('tr'); tr.append(el('td', {class: 'time'}, c.time));
    c.posicoes.forEach((p, i) => {
      const cor = i < 6 ? '--azul' : i >= n - 4 ? '--vermelho' : '--muted';
      const td = el('td', {class: 'c'}, p >= 0.005 ? Math.round(p * 100) : '');
      td.style.background = fundo(p, cor);
      td.title = `${c.time}: ${pct(p)} de terminar em ${i + 1}º`;
      tr.append(td);
    });
    t.append(tr);
  }
})();

(function evolucao() {
  if (D.evolucao.length < 2) { document.getElementById('evo-sec').style.display = 'none'; return; }
  const alvo = document.getElementById('evo');
  const ns = 'http://www.w3.org/2000/svg';
  const no = (tag, attrs, texto) => { const e = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (texto !== undefined) e.textContent = texto; return e; };
  function grafico(titulo, campo, cor) {
    const datas = D.evolucao.map(e => e.data);
    const clubes = D.clubes.filter(c => D.evolucao.some(e => e[c.time] && e[c.time][campo] > 0.02));
    const caixa = el('div', {style: 'margin-bottom:18px'});
    caixa.append(el('h3', {}, titulo));
    if (!clubes.length) { caixa.append(el('div', {class: 'tag'}, 'Já definido.')); return caixa; }
    const W = alvo.clientWidth || 600, rotuloW = Math.min(150, W * 0.38);
    const H = Math.max(180, clubes.length * 15 + 40), m = {l: 34, r: rotuloW, t: 8, b: 22};
    const svg = no('svg', {viewBox: `0 0 ${W} ${H}`, width: '100%'});
    const x = i => m.l + (W - m.l - m.r) * i / (datas.length - 1);
    const y = p => m.t + (H - m.t - m.b) * (1 - p);
    for (const g of [0, .5, 1]) {
      svg.append(no('text', {x: 0, y: y(g) + 4}, (g * 100) + '%'));
      svg.append(no('line', {x1: m.l, x2: W - m.r, y1: y(g), y2: y(g), stroke: css('--line')}));
    }
    const passo = Math.max(1, Math.ceil(datas.length / Math.max(2, Math.floor((W - m.l - m.r) / 48))));
    datas.forEach((d, i) => { if (i % passo === 0 || i === datas.length - 1)
      svg.append(no('text', {x: x(i), y: H - 5, 'text-anchor': 'middle'}, dataBR(d).slice(0, 5))); });
    const rotulos = [];
    for (const c of clubes) {
      const pts = D.evolucao.map((e, i) => e[c.time] ? [x(i), y(e[c.time][campo])] : null).filter(Boolean);
      svg.append(no('polyline', {points: pts.map(q => q.join(',')).join(' '), fill: 'none',
        stroke: css(cor), 'stroke-width': 2, opacity: .85}));
      const fim = pts[pts.length - 1];
      const ult = D.evolucao[D.evolucao.length - 1][c.time];
      rotulos.push({y0: fim[1], y: fim[1], x: fim[0], txt: `${c.time} ${pct(ult ? ult[campo] : 0)}`});
    }
    // afasta rótulos que se sobrepõem (mínimo 14 px), mantendo a ordem
    rotulos.sort((a, b) => a.y0 - b.y0);
    const gap = 14;
    for (let i = 1; i < rotulos.length; i++) rotulos[i].y = Math.max(rotulos[i].y, rotulos[i - 1].y + gap);
    const excesso = rotulos.length ? rotulos[rotulos.length - 1].y - (H - m.b) : 0;
    if (excesso > 0) for (const r of rotulos) r.y -= excesso;
    for (let i = rotulos.length - 2; i >= 0; i--) rotulos[i].y = Math.min(rotulos[i].y, rotulos[i + 1].y - gap);
    for (const r of rotulos) {
      svg.append(no('line', {x1: r.x, y1: r.y0, x2: r.x + 8, y2: r.y, stroke: css('--line')}));
      svg.append(no('text', {x: r.x + 10, y: r.y + 4}, r.txt));
    }
    caixa.append(svg);
    return caixa;
  }
  const desenha = () => {
    alvo.innerHTML = '';
    alvo.append(grafico('Título', 'titulo', '--ouro'), grafico('Rebaixamento (Z4)', 'z4', '--vermelho'));
  };
  desenha();
  let largura = alvo.clientWidth;
  window.addEventListener('resize', () => { if (alvo.clientWidth !== largura) { largura = alvo.clientWidth; desenha(); } });
})();

(function jogos() {
  const alvo = document.getElementById('jogos');
  for (const j of D.jogos) {
    const linha = el('div', {class: 'jogo'});
    linha.append(el('div', {class: 'quando'}, `${dataBR(j.data).slice(0, 5)}` + (j.rodada ? ` · R${j.rodada}` : '')));
    const nomes = el('div'); nomes.append(el('strong', {}, `${j.mandante} x ${j.visitante}`), ' ',
      el('span', {class: 'tag'}, j.origem.startsWith('mercado') ? 'mercado' : 'modelo'));
    const barra = el('div', {class: 'empilhada'});
    [[j.p_casa, '--azul'], [j.p_empate, '--muted'], [j.p_fora, '--vermelho']].forEach(([p, cor]) => {
      const s = el('div', {}, p >= 0.08 ? Math.round(p * 100) + '%' : ''); s.style.width = (p * 100) + '%';
      s.style.background = css(cor); barra.append(s); });
    linha.append(nomes, barra); alvo.append(linha);
  }
})();

(function calib() {
  const t = document.getElementById('calib');
  if (!D.calibracao.length) { t.closest('details').style.display = 'none'; return; }
  const cab = el('tr');
  ['Faixa prevista', 'Eventos', 'Previsto (média)', 'Aconteceu'].forEach(n => cab.append(el('th', {}, n)));
  t.append(cab);
  for (const r of D.calibracao) {
    const tr = el('tr');
    tr.append(el('td', {}, String(r.faixa).replace(/[(\]]/g, '').replace(', ', ' a ')),
      el('td', {}, r.n), el('td', {}, pct(r.previsto)), el('td', {}, pct(r.observado)));
    t.append(tr);
  }
})();
</script>
</body>
</html>
"""
