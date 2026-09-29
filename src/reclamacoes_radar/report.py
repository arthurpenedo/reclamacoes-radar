"""Relatório em Markdown a partir dos indicadores."""

import duckdb

from . import indicators as ind


def _table(rows: list[dict]) -> str:
    if not rows:
        return "_Sem dados suficientes._\n"
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "|" + "---|" * len(rows[0])
    body = "\n".join("| " + " | ".join("-" if v is None else str(v) for v in r.values()) + " |" for r in rows)
    return f"{header}\n{sep}\n{body}\n"


def build_report(con: duckdb.DuckDBPyConnection, segmento: str | None = None) -> str:
    geral = ind.visao_geral(con, segmento)
    titulo = segmento or "Todos os segmentos"
    return "\n".join([
        f"# Radar de reclamações: {titulo}\n",
        f"- **Reclamações:** {geral['reclamacoes']}",
        f"- **Empresas:** {geral['empresas']}",
        f"- **Taxa de resposta:** {geral['taxa_resposta']}%",
        f"- **Nota média do consumidor:** {geral['nota_media']}",
        f"- **Tempo médio de resposta:** {geral['tempo_medio_dias']} dias\n",
        f"## Empresas com mais reclamações (mínimo de {ind.MIN_RECLAMACOES})\n",
        _table(ind.ranking_empresas(con, segmento)),
        "## Problemas mais frequentes\n",
        _table(ind.top_problemas(con, segmento)),
        "## Evolução mensal\n",
        _table(ind.evolucao_mensal(con, segmento)),
    ])
