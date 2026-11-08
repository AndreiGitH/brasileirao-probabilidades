# CLAUDE.md — contexto do projeto

Converse com o usuário em **português**. Ele é dono do repositório (AndreiGitH).

## Objetivo
Estimar as probabilidades de título, G4/Libertadores e rebaixamento do Brasileirão
Série A, com foco nas rodadas finais da temporada 2026 (termina em 02/12/2026).
O projeto nasceu de uma conversa com o Gemini sobre o modelo da UFMG
(mat.ufmg.br/extensao/probabilidade-no-futebol); a avaliação daquela conversa
levou às decisões abaixo.

## Decisões de método (não mudar sem evidência do backtest)
1. **Mercado primeiro.** Com poucas rodadas restantes, as odds sem margem da casa
   (Pinnacle de fechamento quando houver) são a melhor estimativa por jogo.
2. **Modelo próprio = Dixon-Coles** com decaimento temporal (ξ) e correção de
   placares baixos (τ). Gera matriz de placares, não só 1X2.
3. **Simular placares**, não 1X2: o desempate usa vitórias, saldo e gols pró.
4. **Monte Carlo** de ~100 mil temporadas, vetorizado em numpy.
5. **Validação por backtest**: rodadas 35-38 das temporadas 2019-2025, métricas
   RPS, log-loss e calibração. Concorrentes: Elo simples, Dixon-Coles, mercado e
   mistura. Vence quem errar menos.
6. **Fora da v1**: "fator motivação" manual (α não estimável, sobreajuste),
   rating por jogador, xG. O FBref perdeu o xG da Opta em jan/2026.
   Sofascore só como módulo opcional, desligado por padrão, e só entra no modelo
   se o backtest mostrar ganho (endpoints não oficiais, termos de uso incertos).

## Dados (`uv run brasileirao atualizar`)
Base única em `data/processed/jogos.csv` (versionada). Formato em
`src/brasileirao/esquema.py`. Nomes de clubes sempre via `brasileirao.times.padronizar`.

| Temporadas | Placares | Odds |
|---|---|---|
| 2003-2024 | adaoduque/Brasileirao_Dataset (GitHub) | football-data.co.uk (2012+) |
| 2025 | openfootball/football.json (GitHub) | football-data.co.uk |
| corrente | football-data.org (token grátis em `.env`: `FOOTBALL_DATA_TOKEN=...`) | football-data.co.uk |

- Sem token, a temporada corrente vem do openfootball, que costuma ficar
  rodadas atrasado. O relatório do comando mostra quantos jogos estão encerrados.
- 2016 tem 379 jogos (Chapecoense x Atlético-MG não foi disputado).
- 2003-2004 tiveram 24 clubes e 2005 teve 22.
- O ambiente de nuvem do Claude só acessa GitHub e PyPI: odds e temporada
  corrente precisam ser baixadas no PC do usuário e commitadas em `jogos.csv`.

## Comandos
```
uv sync                    # instala dependências
uv run brasileirao atualizar --temporada 2026
uv run brasileirao tabela --temporada 2026
uv run pytest -q
uv run ruff check src tests
```

## Roteiro
- [x] Fase 1: estrutura, coletores, base unificada, classificação com desempate
- [ ] Fase 2: Dixon-Coles (ajuste, decaimento, matriz de placares)
- [ ] Fase 3: odds -> probabilidades (remoção de margem) e ajuste dos λ ao mercado
- [ ] Fase 4: Monte Carlo das rodadas restantes
- [ ] Fase 5: backtest 2019-2025 e escolha da combinação
- [ ] Fase 6: painel com as probabilidades por clube

## Convenções
- Código e comentários em português; nomes canônicos com acento ("Grêmio").
- Fonte que falha é avisada e pulada, nunca preenchida com dado inventado.
- Todo parser novo ganha teste com amostra no formato real da fonte (sem rede).
