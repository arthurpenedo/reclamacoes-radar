"""CLI.

    reclamacoes-radar carregar data/amostra_sintetica.csv --db radar.duckdb
    reclamacoes-radar relatorio --db radar.duckdb [--segmento "Bancos, Financeiras e Administradoras de Cartão"]
    reclamacoes-radar resumo --db radar.duckdb [--segmento ...]      # resumo executivo com Claude
    reclamacoes-radar dashboard --db radar.duckdb --saida dashboard.html
"""

import argparse
import json
import sys
from pathlib import Path

from . import indicators as ind
from .ingest import connect, load_csv
from .dashboard import render_dashboard
from .report import build_report


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="reclamacoes-radar")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("carregar", help="carrega um CSV do consumidor.gov.br")
    p_load.add_argument("csv", type=Path)
    p_load.add_argument("--db", type=Path, default=Path("radar.duckdb"))
    p_load.add_argument("--encoding", default="utf-8", help="arquivos oficiais costumam vir em latin-1")

    for name in ("relatorio", "resumo"):
        p = sub.add_parser(name)
        p.add_argument("--db", type=Path, default=Path("radar.duckdb"))
        p.add_argument("--segmento")

    p_dash = sub.add_parser("dashboard", help="gera dashboard HTML com todos os segmentos")
    p_dash.add_argument("--db", type=Path, default=Path("radar.duckdb"))
    p_dash.add_argument("--saida", type=Path, default=Path("dashboard.html"))
    p_dash.add_argument("--fonte", help="texto sobre a origem dos dados, exibido no cabeçalho")

    args = parser.parse_args(argv)
    con = connect(args.db)

    if args.cmd == "carregar":
        total = load_csv(con, args.csv, encoding=args.encoding)
        print(f"{total} reclamações na base {args.db}")
    elif args.cmd == "dashboard":
        kwargs = {"fonte": args.fonte} if args.fonte else {}
        args.saida.write_text(render_dashboard(con, **kwargs), encoding="utf-8")
        print(f"Dashboard salvo em {args.saida}")
    elif args.cmd == "relatorio":
        print(build_report(con, args.segmento))
    else:
        from .insights import summarize

        dados = {
            "visao_geral": ind.visao_geral(con, args.segmento),
            "ranking_empresas": ind.ranking_empresas(con, args.segmento),
            "top_problemas": ind.top_problemas(con, args.segmento),
        }
        print(json.dumps(summarize(dados).model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
