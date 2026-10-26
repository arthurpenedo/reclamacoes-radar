import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from reclamacoes_radar import indicators as ind
from reclamacoes_radar.ingest import connect, load_csv, snake
from reclamacoes_radar.insights import (
    ExecutiveSummary,
    NumerosInventados,
    check_comparisons,
    check_numbers,
    summarize,
)
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


def test_summarize_rejects_summed_categories_and_keeps_text():
    # Caso real de 30/09/2026: o modelo somou duas categorias de cobrança (110 + 67 = 177).
    payload = {"achados": ["Cobranças somam 177 reclamações"], "recomendacoes": ["Revisar cobranças"]}
    response = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(payload))])
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response)))
    dados = {"top_problemas": [{"problema": "Cobrança indevida", "reclamacoes": 110},
                               {"problema": "Cobrança não contratada", "reclamacoes": 67}]}
    with pytest.raises(NumerosInventados) as erro:
        summarize(dados, client=client)
    assert erro.value.invented == ["177"]
    assert erro.value.summary.achados == ["Cobranças somam 177 reclamações"]


def _fake_ollama(*contents):
    respostas, calls = iter(contents), []

    def post(url, payload):
        calls.append(payload)
        return {"message": {"content": json.dumps(next(respostas))}}

    return post, calls


def test_ollama_retries_when_numbers_are_invented():
    from reclamacoes_radar.insights import summarize_ollama

    ruim = {"achados": ["Cobranças somam 177"], "recomendacoes": ["Revisar"]}
    bom = {"achados": ["Cobrança indevida: 110"], "recomendacoes": ["Revisar"]}
    post, calls = _fake_ollama(ruim, bom)
    dados = {"top_problemas": [{"reclamacoes": 110}, {"reclamacoes": 67}]}
    result = summarize_ollama(dados, post=post)
    assert result.achados == ["Cobrança indevida: 110"] and len(calls) == 2
    assert "177" in calls[1]["messages"][-1]["content"]  # a rejeição volta para o modelo como feedback


def test_ollama_gives_up_after_attempts_and_keeps_last_summary():
    from reclamacoes_radar.insights import summarize_ollama

    ruim = {"achados": ["Há 999 casos"], "recomendacoes": []}
    post, calls = _fake_ollama(ruim, ruim, ruim)
    with pytest.raises(NumerosInventados) as erro:
        summarize_ollama({"a": 1}, post=post)
    assert erro.value.invented == ["999"] and len(calls) == 3


def test_ollama_logs_how_many_attempts_each_summary_needed():
    from reclamacoes_radar.insights import summarize_ollama

    ruim = {"achados": ["Há 999 casos"], "recomendacoes": []}
    bom = {"achados": ["Cobrança indevida: 110"], "recomendacoes": []}
    dados = {"top_problemas": [{"reclamacoes": 110}, {"reclamacoes": 67}]}
    logs = []
    summarize_ollama(dados, post=_fake_ollama(ruim, bom)[0], log=logs.append)
    assert logs == ["resumo aprovado na tentativa 2 de 3"]
    logs.clear()
    with pytest.raises(NumerosInventados):
        summarize_ollama(dados, post=_fake_ollama(ruim, ruim, ruim)[0], log=logs.append)
    assert logs == ["resumo barrado após 3 tentativas"]


def test_dashboard_renders_summary_and_blocked_notice(tmp_path):
    from reclamacoes_radar.dashboard import render_dashboard

    con = connect()
    load_csv(con, write_csv(tmp_path, ["SP;01/03/2026;Banco A;Bancos;A;G;P;S;Finalizada avaliada - Resolvida;5;2"] * 5))
    resumos = {"todos": ExecutiveSummary(achados=["Achado <b>"], recomendacoes=["Agir"]), "s0": "Resumo barrado"}
    html = render_dashboard(con, resumos=resumos)
    assert "Achado &lt;b&gt;" in html and "Resumo barrado" in html
    assert "Resumo executivo" not in render_dashboard(con)


def test_comparativo_against_segment_average(tmp_path):
    ok = "SP;01/03/2026;Banco A;Bancos;A;G;P;S;Finalizada avaliada - Resolvida;5;2"
    ruim = "SP;01/03/2026;Banco B;Bancos;A;G;P;S;Finalizada avaliada - Não Resolvida;1;6"
    con = connect()
    load_csv(con, write_csv(tmp_path, [ok] * 5 + [ruim] * 5))
    rows = {r["empresa"]: r for r in ind.comparativo_segmento(con, "Bancos")}
    assert rows["Banco A"]["indice_solucao"] == 100.0 and rows["Banco A"]["delta_solucao"] == 50.0
    assert rows["Banco B"]["delta_solucao"] == -50.0
    assert rows["Banco A"]["delta_nota"] == 2.0 and rows["Banco B"]["delta_tempo"] == 2.0


def test_dashboard_has_one_section_per_segment_and_escapes(tmp_path):
    from reclamacoes_radar.dashboard import render_dashboard

    con = connect()
    evil = "SP;01/03/2026;<script>x</script>;Bancos;A;G;P;S;Finalizada avaliada - Resolvida;5;2"
    load_csv(con, write_csv(tmp_path, [evil] * 5))
    html = render_dashboard(con)
    assert html.startswith("<!doctype html>")
    assert html.count("<section data-seg=") == 2  # "todos" + 1 segmento
    assert "<script>x</script>" not in html and "&lt;script&gt;x&lt;/script&gt;" in html


def test_cli_dashboard(tmp_path):
    from reclamacoes_radar.cli import main

    db, out = tmp_path / "r.duckdb", tmp_path / "d.html"
    assert main(["carregar", str(SAMPLE), "--db", str(db)]) == 0
    assert main(["dashboard", "--db", str(db), "--saida", str(out)]) == 0
    html = out.read_text(encoding="utf-8")
    assert "Empresas × média do segmento" in html and "Banco Alfa (fictício)" in html


DADOS_RANKING = {"visao_geral": {"reclamacoes": 600},
                 "top_problemas": [{"problema": "Cobrança", "reclamacoes": 110}, {"problema": "Entrega", "reclamacoes": 67}]}


def test_check_comparisons_flags_wrong_superlative():
    # Achado de 19/10: o número existe nos dados, mas não é o maior.
    ruim = ExecutiveSummary(achados=["Entrega é o maior problema, com 67 reclamações."], recomendacoes=[])
    assert check_comparisons(ruim, DADOS_RANKING) == ["maior com 67"]
    bom = ExecutiveSummary(achados=["Cobrança é o maior problema, com 110 reclamações."], recomendacoes=[])
    assert check_comparisons(bom, DADOS_RANKING) == []


def test_check_comparisons_checks_menor_and_ignores_lone_indicators():
    ruim = ExecutiveSummary(achados=["O menor volume é cobrança, 110."], recomendacoes=[])
    assert check_comparisons(ruim, DADOS_RANKING) == ["menor com 110"]
    solto = ExecutiveSummary(achados=["O maior volume geral é de 600 reclamações."], recomendacoes=[])
    assert check_comparisons(solto, DADOS_RANKING) == []


def test_ollama_retries_when_superlative_is_wrong():
    from reclamacoes_radar.insights import summarize_ollama

    ruim = {"achados": ["Entrega é o maior problema, com 67."], "recomendacoes": []}
    bom = {"achados": ["Cobrança é o maior problema, com 110."], "recomendacoes": []}
    post, calls = _fake_ollama(ruim, bom)
    result = summarize_ollama(DADOS_RANKING, post=post)
    assert result.achados == bom["achados"] and "maior com 67" in calls[1]["messages"][-1]["content"]
