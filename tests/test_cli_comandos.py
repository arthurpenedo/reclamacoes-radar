import json
from pathlib import Path

import pytest

from reclamacoes_radar import cli, insights

AMOSTRA = Path(__file__).resolve().parents[1] / "data" / "amostra_sintetica.csv"


@pytest.fixture
def db(tmp_path):
    caminho = tmp_path / "r.duckdb"
    assert cli.main(["carregar", str(AMOSTRA), "--db", str(caminho)]) == 0
    return caminho


class _Resumo:
    def model_dump(self):
        return {"titulo": "resumo falso"}


def test_relatorio_imprime_texto(db, capsys):
    assert cli.main(["relatorio", "--db", str(db)]) == 0
    assert capsys.readouterr().out.strip()


def test_resumo_ollama_imprime_json(db, monkeypatch, capsys):
    vistos = []
    monkeypatch.setattr(insights, "summarize_ollama", lambda dados: vistos.append(set(dados)) or _Resumo())
    assert cli.main(["resumo", "--db", str(db), "--modelo", "ollama"]) == 0
    assert json.loads(capsys.readouterr().out) == {"titulo": "resumo falso"}
    assert vistos == [{"visao_geral", "ranking_empresas", "top_problemas"}]


def test_resumo_claude_e_o_padrao(db, monkeypatch, capsys):
    monkeypatch.setattr(insights, "summarize", lambda dados: _Resumo())
    assert cli.main(["resumo", "--db", str(db)]) == 0
    assert "resumo falso" in capsys.readouterr().out


def test_dashboard_com_resumo_barrado_vira_aviso(db, tmp_path, monkeypatch):
    def barra(dados):
        raise insights.NumerosInventados(["999"], None)

    monkeypatch.setattr(insights, "summarize_ollama", barra)
    saida = tmp_path / "d.html"
    assert cli.main(["dashboard", "--db", str(db), "--saida", str(saida), "--resumo", "ollama",
                     "--fonte", "Dados de teste"]) == 0
    html = saida.read_text(encoding="utf-8")
    assert "Resumo barrado pela trava de números (citou 999" in html
    assert "Dados de teste" in html


@pytest.mark.parametrize("conteudo, encoding", [
    (b"", "utf-8"),
    (b"a;b\n", "utf-8"),
    ("Região;Empresa\n".encode("latin-1"), "utf-8"),
    (b"a;b\n1;2\n", "xyz"),
])
def test_carregar_csv_ruim_devolve_2_sem_traceback(tmp_path, capsys, conteudo, encoding):
    csv = tmp_path / "ruim.csv"
    csv.write_bytes(conteudo)
    assert cli.main(["carregar", str(csv), "--db", str(tmp_path / "r.duckdb"), "--encoding", encoding]) == 2
    assert "Não consegui carregar" in capsys.readouterr().err


def test_dashboard_cria_a_pasta_da_saida(db, tmp_path):
    saida = tmp_path / "site" / "novo" / "index.html"
    assert cli.main(["dashboard", "--db", str(db), "--saida", str(saida)]) == 0
    assert saida.is_file()


def test_comandos_de_consulta_sem_base_devolvem_2_e_nao_criam_arquivo(tmp_path, capsys):
    db = tmp_path / "nao.duckdb"
    for cmd in (["relatorio"], ["resumo"], ["dashboard", "--saida", str(tmp_path / "d.html")]):
        assert cli.main([*cmd, "--db", str(db)]) == 2
        assert "Base não encontrada" in capsys.readouterr().err
    assert not db.exists() and not (tmp_path / "d.html").exists()
