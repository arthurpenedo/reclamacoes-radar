"""Ingestão dos dados abertos do consumidor.gov.br para o DuckDB.

Os arquivos oficiais (dados.gov.br, conjunto "Reclamações do consumidor.gov.br") vêm em CSV
separado por ";" e com nomes de coluna em português com acentos. Aqui as colunas são
normalizadas para snake_case e os tipos são ajustados em SQL.
"""

import re
import unicodedata
from pathlib import Path

import duckdb

# Colunas usadas nos indicadores (nome normalizado).
REQUIRED_COLUMNS = {
    "uf", "data_abertura", "nome_fantasia", "segmento_de_mercado", "assunto",
    "grupo_problema", "problema", "respondida", "situacao", "nota_do_consumidor", "tempo_resposta",
}


def snake(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch)).lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def connect(db_path: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path))


def load_csv(con: duckdb.DuckDBPyConnection, csv_path: str | Path, encoding: str = "utf-8") -> int:
    """Carrega (ou acrescenta) um CSV na tabela `reclamacoes`. Retorna o total de linhas da tabela."""
    raw = con.read_csv(str(csv_path), delimiter=";", header=True, encoding=encoding, all_varchar=True)
    mapping = {col: snake(col) for col in raw.columns}
    missing = REQUIRED_COLUMNS - set(mapping.values())
    if missing:
        raise ValueError(f"CSV sem as colunas esperadas: {sorted(missing)}")

    select = ", ".join(f'"{orig}" AS {new}' for orig, new in mapping.items())
    con.register("raw_csv", raw)
    con.execute(f"CREATE OR REPLACE TEMP VIEW staged AS SELECT {select} FROM raw_csv")
    con.execute("""
        CREATE TABLE IF NOT EXISTS reclamacoes (
            uf VARCHAR, data_abertura DATE, nome_fantasia VARCHAR, segmento_de_mercado VARCHAR,
            assunto VARCHAR, grupo_problema VARCHAR, problema VARCHAR, respondida BOOLEAN,
            situacao VARCHAR, nota_do_consumidor INTEGER, tempo_resposta INTEGER
        )
    """)
    con.execute("""
        INSERT INTO reclamacoes
        SELECT
            upper(trim(uf)),
            COALESCE(try_strptime(data_abertura, '%d/%m/%Y'), try_strptime(data_abertura, '%Y-%m-%d'))::DATE,
            trim(nome_fantasia),
            trim(segmento_de_mercado),
            trim(assunto),
            trim(grupo_problema),
            trim(problema),
            upper(trim(respondida)) IN ('S', 'SIM'),
            trim(situacao),
            try_cast(nullif(trim(nota_do_consumidor), '') AS INTEGER),
            try_cast(nullif(trim(tempo_resposta), '') AS INTEGER)
        FROM staged
    """)
    con.unregister("raw_csv")
    return con.execute("SELECT count(*) FROM reclamacoes").fetchone()[0]
