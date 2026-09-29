"""Indicadores em SQL sobre a tabela `reclamacoes`.

Definições (as mesmas usadas nos boletins do consumidor.gov.br):
- índice de solução: % de reclamações avaliadas pelo consumidor como "Resolvida";
- taxa de resposta: % respondidas pela empresa;
- nota média: satisfação do consumidor (1 a 5);
- tempo médio de resposta: em dias.
"""

import duckdb

RESOLVIDA = "Finalizada avaliada - Resolvida"
MIN_RECLAMACOES = 5  # empresas com menos reclamações não entram nos rankings


def _where(segmento: str | None) -> tuple[str, list]:
    return ("WHERE segmento_de_mercado = ?", [segmento]) if segmento else ("", [])


def ranking_empresas(con: duckdb.DuckDBPyConnection, segmento: str | None = None, limite: int = 10) -> list[dict]:
    where, params = _where(segmento)
    sql = f"""
        SELECT
            nome_fantasia AS empresa,
            count(*) AS reclamacoes,
            round(100.0 * avg(CASE WHEN respondida THEN 1 ELSE 0 END), 1) AS taxa_resposta,
            round(100.0 * count(*) FILTER (WHERE situacao = '{RESOLVIDA}')
                  / nullif(count(*) FILTER (WHERE situacao LIKE 'Finalizada avaliada%'), 0), 1) AS indice_solucao,
            round(avg(nota_do_consumidor), 2) AS nota_media,
            round(avg(tempo_resposta), 1) AS tempo_medio_dias
        FROM reclamacoes
        {where}
        GROUP BY nome_fantasia
        HAVING count(*) >= {MIN_RECLAMACOES}
        ORDER BY reclamacoes DESC
        LIMIT {int(limite)}
    """
    return _rows(con.execute(sql, params))


def top_problemas(con: duckdb.DuckDBPyConnection, segmento: str | None = None, limite: int = 5) -> list[dict]:
    where, params = _where(segmento)
    sql = f"""
        SELECT problema, count(*) AS reclamacoes,
               round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS percentual
        FROM reclamacoes {where}
        GROUP BY problema ORDER BY reclamacoes DESC LIMIT {int(limite)}
    """
    return _rows(con.execute(sql, params))


def evolucao_mensal(con: duckdb.DuckDBPyConnection, segmento: str | None = None) -> list[dict]:
    where, params = _where(segmento)
    sql = f"""
        SELECT strftime(date_trunc('month', data_abertura), '%Y-%m') AS mes, count(*) AS reclamacoes
        FROM reclamacoes {where}
        GROUP BY mes ORDER BY mes
    """
    return _rows(con.execute(sql, params))


def visao_geral(con: duckdb.DuckDBPyConnection, segmento: str | None = None) -> dict:
    where, params = _where(segmento)
    sql = f"""
        SELECT count(*) AS reclamacoes,
               count(DISTINCT nome_fantasia) AS empresas,
               round(100.0 * avg(CASE WHEN respondida THEN 1 ELSE 0 END), 1) AS taxa_resposta,
               round(avg(nota_do_consumidor), 2) AS nota_media,
               round(avg(tempo_resposta), 1) AS tempo_medio_dias
        FROM reclamacoes {where}
    """
    return _rows(con.execute(sql, params))[0]


def comparativo_segmento(con: duckdb.DuckDBPyConnection, segmento: str) -> list[dict]:
    """Cada empresa do segmento contra a média do próprio segmento (pontos percentuais / dias / nota).

    A "média do segmento" é calculada sobre todas as reclamações do segmento, inclusive de empresas
    abaixo do mínimo — é o patamar que o consumidor encontra no mercado.
    """
    sql = f"""
        WITH base AS (
            SELECT nome_fantasia,
                   CASE WHEN respondida THEN 1 ELSE 0 END AS resp,
                   CASE WHEN situacao = '{RESOLVIDA}' THEN 1 WHEN situacao LIKE 'Finalizada avaliada%' THEN 0 END AS resolvida,
                   nota_do_consumidor AS nota,
                   tempo_resposta AS tempo
            FROM reclamacoes WHERE segmento_de_mercado = ?
        ),
        seg AS (
            SELECT 100.0 * avg(resp) AS taxa_resposta, 100.0 * avg(resolvida) AS indice_solucao,
                   avg(nota) AS nota_media, avg(tempo) AS tempo_medio_dias
            FROM base
        ),
        emp AS (
            SELECT nome_fantasia AS empresa, count(*) AS reclamacoes,
                   100.0 * avg(resp) AS taxa_resposta, 100.0 * avg(resolvida) AS indice_solucao,
                   avg(nota) AS nota_media, avg(tempo) AS tempo_medio_dias
            FROM base GROUP BY nome_fantasia HAVING count(*) >= {MIN_RECLAMACOES}
        )
        SELECT emp.empresa, emp.reclamacoes,
               round(emp.indice_solucao, 1) AS indice_solucao,
               round(emp.indice_solucao - seg.indice_solucao, 1) AS delta_solucao,
               round(emp.nota_media, 2) AS nota_media,
               round(emp.nota_media - seg.nota_media, 2) AS delta_nota,
               round(emp.tempo_medio_dias, 1) AS tempo_medio_dias,
               round(emp.tempo_medio_dias - seg.tempo_medio_dias, 1) AS delta_tempo
        FROM emp, seg
        ORDER BY emp.reclamacoes DESC
    """
    return _rows(con.execute(sql, [segmento]))


def segmentos(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT segmento_de_mercado FROM reclamacoes GROUP BY 1 ORDER BY count(*) DESC").fetchall()]


def _rows(cursor: duckdb.DuckDBPyConnection) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]
