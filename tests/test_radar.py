import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from reclamacoes_radar import indicators as ind
from reclamacoes_radar.ingest import connect, load_csv, snake
from reclamacoes_radar.insights import ExecutiveSummary, check_numbers, summarize
from reclamacoes_radar.report import build_report

SAMPLE = Path(__file__).parent.parent / "data" / "amostra_sintetica.csv"
HEADER = ("UF;Data Abertura;Nome Fantasia;Segmento de Mercado;Assunto;Grupo Problema;Problema;"
          "Respondida;Situação;Nota do Consumidor;Tempo Resposta")


def write_csv(tmp_path, rows: list[str]) -> Path:
    path = tmp_path / "mini.csv"
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def mini(tmp_path):
    rows = [f"SP;0{d}/03/2026;Banco X;Bancos;A;G;Cobrança indevida;S;Finalizada avaliada - Resolvida;5;2" for d in range(1, 5)]
    rows += ["RJ;10/04/2026;Banco X;Bancos;A;G;Cartão;N;Finalizada avaliada - Não Resolvida;1;",
             "RJ;11/04/2026;Loja Y;Varejo;A;G;Entrega;S;Finalizada não avaliada;;4"]
    con = connect()
    load_csv(con, write_csv(tmp_path, rows))
    return con


def test_snake_normalizes_official_headers():
    assert snake("Situação") == "situacao"
    assert snake("Nota do Consumidor") == "nota_do_consumidor"


def test_missing_columns_raise(tmp_path):
    path = tmp_path / "ruim.csv"
    path.write_text("UF;Empresa\nSP;X\n", encoding="utf-8")
    with pytest.raises(ValueError, match="colunas esperadas"):
        load_csv(connect(), path)


def test_indicators_on_known_data(mini):
    geral = ind.visao_geral(mini)
    assert geral["reclamacoes"] == 6 and geral["empresas"] == 2
    ranking = ind.ranking_empresas(mini)
    assert [r["empresa"] for r in ranking] == ["Banco X"]  # Loja Y tem < 5 reclamações
    banco = ranking[0]
    assert banco["indice_solucao"] == 80.0  # 4 resolvidas de 5 avaliadas
    assert banco["taxa_resposta"] == 80.0
    assert [m["mes"] for m in ind.evolucao_mensal(mini)] == ["2026-03", "2026-04"]


def test_segment_filter(mini):
    assert ind.visao_geral(mini, "Varejo")["reclamacoes"] == 1


def test_sample_report_renders():
    con = connect()
    assert load_csv(con, SAMPLE) == 600
    report = build_report(con, ind.segmentos(con)[0])
    assert "# Radar de reclamações" in report and "| empresa |" in report


def test_check_numbers_flags_invented_values():
    summary = ExecutiveSummary(achados=["Taxa de resposta de 97.5%", "Nota média 3,1"], recomendacoes=["Cortar 40% do tempo"])
    assert check_numbers(summary, '{"taxa_resposta": 97.5, "nota_media": 3.1}') == ["40"]


def test_summarize_with_fake_client():
    payload = {"achados": ["Taxa de resposta de 97.5%"], "recomendacoes": ["Priorizar cobrança indevida"]}
    response = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(payload))])
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response)))
    result = summarize({"visao_geral": {"taxa_resposta": 97.5}}, client=client)
    assert result.recomendacoes == ["Priorizar cobrança indevida"]
