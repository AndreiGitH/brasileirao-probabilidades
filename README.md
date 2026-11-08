# brasileirao-probabilidades

Probabilidades de título, G4/Libertadores e rebaixamento do Brasileirão Série A,
com odds de mercado, modelo Dixon-Coles e simulação de Monte Carlo.

## Como usar

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run brasileirao atualizar --temporada 2026   # baixa e une as fontes
uv run brasileirao tabela --temporada 2026      # classificação atual
uv run pytest -q
```

Para a temporada em andamento, crie um token gratuito em
[football-data.org](https://www.football-data.org/client/register) e salve em `.env`:

```
FOOTBALL_DATA_TOKEN=seu_token_aqui
ODDS_API_KEY=sua_chave_aqui
```

A chave da [The Odds API](https://the-odds-api.com) (grátis, 500 créditos/mês) traz as
odds dos próximos jogos: `uv run brasileirao odds`.

## Fontes

- Placares 2003-2024: [adaoduque/Brasileirao_Dataset](https://github.com/adaoduque/Brasileirao_Dataset)
- Placares 2025 em diante: [openfootball/football.json](https://github.com/openfootball/football.json) e [football-data.org](https://www.football-data.org)
- Odds de fechamento: [football-data.co.uk](https://www.football-data.co.uk/brazil.php)
- Odds dos próximos jogos: [The Odds API](https://the-odds-api.com)

Detalhes do método e roteiro em [CLAUDE.md](CLAUDE.md).
