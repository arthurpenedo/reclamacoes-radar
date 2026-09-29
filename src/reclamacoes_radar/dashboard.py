"""Dashboard HTML autocontido: um arquivo, sem servidor e sem dependências externas.

Uma seção por segmento (mais "Todos os segmentos"), trocada por um seletor. Cada seção tem
visão geral, evolução mensal, empresas contra a média do segmento e problemas mais frequentes.
Todos os números vêm das funções SQL de `indicators`.
"""

from datetime import datetime
from html import escape

import duckdb

from . import indicators as ind

CSS = """
:root{--bg:#f6f6f3;--card:#fff;--fg:#1c1c1e;--muted:#6b6b70;--line:#e3e3de;--bar:#2f6fed;--bar-bg:#e8eefc;
--good:#1f8a4c;--bad:#c2372e}
@media (prefers-color-scheme:dark){:root{--bg:#121214;--card:#1b1b1f;--fg:#ececf0;--muted:#9a9aa3;--line:#2b2b31;
--bar:#6f96ff;--bar-bg:#252b3d;--good:#4cc38a;--bad:#ff6b61}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:26px;margin:0}h2{font-size:17px;margin:0 0 12px}
.muted{color:var(--muted)}.top{display:flex;flex-wrap:wrap;gap:12px;align-items:end;justify-content:space-between;margin-bottom:20px}
.top label{flex:1 1 260px;max-width:520px;min-width:0}
select{font:inherit;padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);width:100%;text-overflow:ellipsis}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi b{display:block;font-size:26px;font-variant-numeric:tabular-nums}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px}
.grid>*{min-width:0}
@media (max-width:720px){.grid{grid-template-columns:minmax(0,1fr)}}
.wide{grid-column:1/-1}
table{width:100%;border-collapse:collapse}td,th{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.d{font-size:12px;font-weight:600;margin-left:4px}.good{color:var(--good)}.bad{color:var(--bad)}
.hbar{display:grid;grid-template-columns:1fr auto;gap:2px 10px;margin:8px 0}
.hbar .track{grid-column:1/-1;height:8px;border-radius:4px;background:var(--bar-bg);overflow:hidden}
.hbar .track span{display:block;height:100%;background:var(--bar)}
.cols{display:flex;align-items:flex-end;gap:6px;height:160px;padding-top:8px}
.col{flex:1;display:flex;flex-direction:column;align-items:center;height:100%;min-width:0}
.col .area{flex:1;width:100%;display:flex;align-items:flex-end;justify-content:center}
.col i{display:block;width:100%;max-width:44px;background:var(--bar);border-radius:4px 4px 0 0}
.col small{font-size:11px;color:var(--muted);margin-top:4px;white-space:nowrap}
.col em{font-style:normal;font-size:11px;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto}section[hidden]{display:none}footer{margin-top:32px;font-size:13px}
"""

SCRIPT = """
const sel=document.getElementById('seg');
function show(v){document.querySelectorAll('section[data-seg]').forEach(s=>{s.hidden=s.dataset.seg!==v})}
sel.addEventListener('change',()=>{show(sel.value);history.replaceState(null,'','#'+sel.value)});
const h=location.hash.slice(1);if(h&&sel.querySelector('option[value="'+CSS.escape(h)+'"]')){sel.value=h;show(h)}
"""


def _fmt(v, suffix: str = "", dec: int = 1) -> str:
    if v is None:
        return "–"
    return f"{v:.{dec}f}".replace(".", ",") + suffix if isinstance(v, float) else f"{v}{suffix}"


def _delta(v: float | None, higher_is_better: bool = True, suffix: str = "", dec: int = 1) -> str:
    if v is None or round(abs(v), dec) == 0:
        return ""
    good = (v > 0) == higher_is_better
    sign = "+" if v > 0 else "−"
    return f'<span class="d {"good" if good else "bad"}">{sign}{_fmt(abs(v), suffix, dec)}</span>'


def _kpis(g: dict) -> str:
    items = [("Reclamações", g["reclamacoes"]), ("Empresas", g["empresas"]),
             ("Taxa de resposta", _fmt(g["taxa_resposta"], "%")), ("Nota média (1–5)", _fmt(g["nota_media"], dec=2)),
             ("Tempo médio de resposta", _fmt(g["tempo_medio_dias"], " dias"))]
    return '<div class="kpis">' + "".join(
        f'<div class="card kpi"><span class="muted">{k}</span><b>{v}</b></div>' for k, v in items) + "</div>"


def _mensal(rows: list[dict]) -> str:
    if not rows:
        return '<p class="muted">Sem dados.</p>'
    top = max(r["reclamacoes"] for r in rows) or 1
    cols = "".join(
        f'<div class="col" title="{escape(r["mes"])}: {r["reclamacoes"]}"><em>{r["reclamacoes"]}</em>'
        f'<span class="area"><i style="height:{100 * r["reclamacoes"] / top:.0f}%"></i></span><small>{escape(r["mes"][2:])}</small></div>'
        for r in rows)
    return f'<div class="cols">{cols}</div>'


def _problemas(rows: list[dict]) -> str:
    if not rows:
        return '<p class="muted">Sem dados.</p>'
    return "".join(
        f'<div class="hbar"><span>{escape(r["problema"])}</span><span class="n">{_fmt(r["percentual"], "%")}</span>'
        f'<div class="track"><span style="width:{r["percentual"]:.0f}%"></span></div></div>'
        for r in rows)


def _comparativo(rows: list[dict]) -> str:
    if not rows:
        return f'<p class="muted">Nenhuma empresa com ao menos {ind.MIN_RECLAMACOES} reclamações.</p>'
    body = "".join(
        f'<tr><td>{escape(r["empresa"])}</td><td class="n">{r["reclamacoes"]}</td>'
        f'<td class="n">{_fmt(r["indice_solucao"], "%")}{_delta(r["delta_solucao"], True, " p.p.")}</td>'
        f'<td class="n">{_fmt(r["nota_media"], dec=2)}{_delta(r["delta_nota"], True, dec=2)}</td>'
        f'<td class="n">{_fmt(r["tempo_medio_dias"], " d")}{_delta(r["delta_tempo"], False, " d")}</td></tr>'
        for r in rows)
    return ('<div class="wrap"><table><thead><tr><th>Empresa</th><th class="n">Reclamações</th>'
            '<th class="n">Índice de solução</th><th class="n">Nota</th><th class="n">Tempo de resposta</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>'
            '<p class="muted" style="font-size:13px;margin:8px 0 0">Em verde/vermelho: diferença para a média do segmento '
            '(melhor/pior). Índice de solução considera só reclamações avaliadas pelo consumidor.</p>')


def _ranking(rows: list[dict]) -> str:
    if not rows:
        return f'<p class="muted">Nenhuma empresa com ao menos {ind.MIN_RECLAMACOES} reclamações.</p>'
    body = "".join(
        f'<tr><td>{escape(r["empresa"])}</td><td class="n">{r["reclamacoes"]}</td>'
        f'<td class="n">{_fmt(r["taxa_resposta"], "%")}</td><td class="n">{_fmt(r["indice_solucao"], "%")}</td>'
        f'<td class="n">{_fmt(r["nota_media"], dec=2)}</td><td class="n">{_fmt(r["tempo_medio_dias"], " d")}</td></tr>'
        for r in rows)
    return ('<div class="wrap"><table><thead><tr><th>Empresa</th><th class="n">Reclamações</th><th class="n">Resposta</th>'
            '<th class="n">Solução</th><th class="n">Nota</th><th class="n">Tempo</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def _section(con: duckdb.DuckDBPyConnection, key: str, segmento: str | None, hidden: bool) -> str:
    empresas = (f'<h2>Empresas × média do segmento</h2>{_comparativo(ind.comparativo_segmento(con, segmento))}'
                if segmento else f'<h2>Empresas com mais reclamações</h2>{_ranking(ind.ranking_empresas(con))}')
    return f"""<section data-seg="{escape(key)}"{' hidden' if hidden else ''}>
{_kpis(ind.visao_geral(con, segmento))}
<div class="grid">
  <div class="card wide">{empresas}</div>
  <div class="card"><h2>Evolução mensal</h2>{_mensal(ind.evolucao_mensal(con, segmento))}</div>
  <div class="card"><h2>Problemas mais frequentes</h2>{_problemas(ind.top_problemas(con, segmento))}</div>
</div></section>"""


def render_dashboard(con: duckdb.DuckDBPyConnection, titulo: str = "Radar de reclamações",
                     fonte: str = "Amostra sintética no layout oficial do consumidor.gov.br (empresas fictícias)") -> str:
    segs = ind.segmentos(con)
    options = ['<option value="todos">Todos os segmentos</option>'] + [
        f'<option value="s{i}">{escape(s)}</option>' for i, s in enumerate(segs)]
    sections = [_section(con, "todos", None, hidden=False)] + [
        _section(con, f"s{i}", s, hidden=True) for i, s in enumerate(segs)]
    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(titulo)}</title><style>{CSS}</style></head>
<body><main>
<div class="top">
  <div><h1>{escape(titulo)}</h1><span class="muted">{escape(fonte)} · gerado em {gerado}</span></div>
  <label><span class="muted" style="display:block;font-size:13px">Segmento</span>
  <select id="seg">{''.join(options)}</select></label>
</div>
{''.join(sections)}
<footer class="muted">Indicadores calculados em SQL (DuckDB) por
<a href="https://github.com/arthurpenedo/reclamacoes-radar">reclamacoes-radar</a>.</footer>
</main><script>{SCRIPT}</script></body></html>
"""
