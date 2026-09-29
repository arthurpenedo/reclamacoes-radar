# reclamacoes-radar

[![CI](https://github.com/arthurpenedo/reclamacoes-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/arthurpenedo/reclamacoes-radar/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![DuckDB](https://img.shields.io/badge/DuckDB-SQL-yellow)
![License](https://img.shields.io/badge/license-MIT-green)

> Pipeline de dados abertos do **consumidor.gov.br**: ingestão → **DuckDB** → indicadores em **SQL** (índice de solução, taxa de resposta, nota, tempo de resposta) → relatório, com um **resumo executivo gerado por IA** que não pode inventar números.

## O problema

O consumidor.gov.br publica mensalmente milhões de reclamações em dados abertos. Times de CX e ouvidoria querem respostas simples: *como estamos em relação à concorrência? Quais problemas mais geram reclamação? Estamos melhorando?* Os arquivos, porém, são CSVs grandes, com colunas acentuadas, separador `;` e codificações variadas.

O `reclamacoes-radar` resolve o caminho inteiro:

1. **Ingestão robusta:** normaliza os nomes das colunas oficiais, converte datas e tipos e valida o esquema.
2. **Indicadores em SQL puro no DuckDB,** analítico e rápido, sem servidor.
3. **Relatório em Markdown** por segmento de mercado.
4. **Resumo executivo com Claude,** com uma verificação que **rejeita qualquer número citado que não esteja nos dados**.

## Demo (amostra sintética)

```text
$ reclamacoes-radar carregar data/amostra_sintetica.csv --db radar.duckdb
600 reclamações na base radar.duckdb

$ reclamacoes-radar relatorio --db radar.duckdb --segmento "Bancos, Financeiras e Administradoras de Cartão"
```

| empresa | reclamacoes | taxa_resposta | indice_solucao | nota_media | tempo_medio_dias |
|---|---|---|---|---|---|
| Banco Alfa (fictício) | 112 | 99.1 | 66.7 | 3.59 | 6.0 |
| Fintech Beta (fictícia) | 87 | 96.6 | 80.0 | 3.82 | 3.3 |
| Cartões Zeta (fictícia) | 38 | 92.1 | 53.8 | 3.27 | 8.7 |

| problema | reclamacoes | percentual |
|---|---|---|
| Cobrança por serviço/produto não contratado / não reconhecido | 67 | 28.3 |
| Dificuldade de contato / acesso a outros canais | 59 | 24.9 |
| Cobrança indevida / abusiva | 56 | 23.6 |

> As empresas da amostra são **fictícias**. A amostra tem o mesmo layout do arquivo oficial e é gerada por `data/gerar_amostra.py`.

## Arquitetura

```
CSV oficial (;)  ──► ingest.py ──► DuckDB: tabela `reclamacoes` (tipada)
                                          │
                     indicators.py (SQL) ◄┘ ──► report.py ──► Markdown
                                          │
                                          └──► insights.py ──► Claude ──► check_numbers() ──► resumo executivo
```

### Decisões técnicas

- **DuckDB em vez de pandas para as agregações.** Os arquivos mensais oficiais têm centenas de milhares de linhas. O DuckDB lê CSV direto, roda SQL analítico em colunas e cabe num único arquivo `.duckdb`.
- **Definições explícitas dos indicadores.** O índice de solução considera só reclamações **avaliadas** pelo consumidor, como nos boletins oficiais. Empresas com menos de 5 reclamações ficam fora dos rankings.
- **A IA só redige; o SQL calcula.** O modelo recebe os indicadores prontos, e `check_numbers` barra resumos com números que não estão na entrada.

## Como rodar

```bash
git clone https://github.com/arthurpenedo/reclamacoes-radar && cd reclamacoes-radar
pip install -e ".[dev]"

reclamacoes-radar carregar data/amostra_sintetica.csv --db radar.duckdb
reclamacoes-radar relatorio --db radar.duckdb
reclamacoes-radar resumo --db radar.duckdb        # precisa de ANTHROPIC_API_KEY
pytest -q
```

### Com dados reais

Baixe os arquivos mensais em **dados.gov.br**, no conjunto "Reclamações do consumidor.gov.br" (ou na seção de dados abertos do consumidor.gov.br), e carregue quantos meses quiser. A tabela acumula:

```bash
reclamacoes-radar carregar data/raw/2026-07.csv --db radar.duckdb --encoding latin-1
reclamacoes-radar carregar data/raw/2026-08.csv --db radar.duckdb --encoding latin-1
```

## Próximos passos

- [ ] Download automático dos meses pela API do dados.gov.br
- [ ] Dashboard (Streamlit) com filtro por empresa e segmento
- [ ] Comparativo empresa × média do segmento
- [ ] Classificação de temas emergentes com LLM em lote (Batches API)

---

Feito por [Arthur Penedo](https://github.com/arthurpenedo) · [LinkedIn](https://www.linkedin.com/in/arthuralves-penedo)
