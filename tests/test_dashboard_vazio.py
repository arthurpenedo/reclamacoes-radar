from reclamacoes_radar import dashboard
from reclamacoes_radar import indicators as ind


def test_fmt_trata_none_float_e_inteiro():
    assert dashboard._fmt(None) == "–"
    assert dashboard._fmt(3.14159, "%", 2) == "3,14%"
    assert dashboard._fmt(7, " dias") == "7 dias"


def test_secoes_vazias_mostram_aviso_em_vez_de_quebrar():
    assert "Sem dados" in dashboard._mensal([])
    assert "Sem dados" in dashboard._problemas([])
    for secao in (dashboard._comparativo, dashboard._ranking):
        html = secao([])
        assert "Nenhuma empresa" in html
        assert str(ind.MIN_RECLAMACOES) in html
