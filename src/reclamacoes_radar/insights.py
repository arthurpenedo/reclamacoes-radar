"""Camada opcional de IA: transforma os indicadores em um resumo executivo.

O modelo recebe SOMENTE os números já calculados em SQL. Para evitar números inventados,
`check_numbers` confere se todo número citado no resumo existe nos dados de entrada.
"""

import json
import os
import re

import anthropic
from pydantic import BaseModel, ConfigDict

MODEL = os.getenv("RADAR_MODEL", "claude-opus-5-5")

SYSTEM_PROMPT = """Você é analista de dados de defesa do consumidor. A partir dos indicadores em JSON, \
escreva um resumo executivo em português do Brasil para a diretoria de atendimento de uma empresa.

Regras:
- Use apenas números presentes nos dados. Não calcule novos percentuais nem estime valores.
- Destaque no máximo 3 achados e 3 recomendações práticas.
- Seja direto: frases curtas, sem jargão."""


class ExecutiveSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    achados: list[str]
    recomendacoes: list[str]


class RefusalError(RuntimeError):
    pass


def summarize(indicadores: dict, client: anthropic.Anthropic | None = None) -> ExecutiveSummary:
    client = client or anthropic.Anthropic()
    dados = json.dumps(indicadores, ensure_ascii=False, default=str)
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM_PROMPT,
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": ExecutiveSummary.model_json_schema()},
        },
        messages=[{"role": "user", "content": f"<indicadores>\n{dados}\n</indicadores>"}],
    )
    if response.stop_reason == "refusal":
        raise RefusalError("O modelo recusou gerar o resumo.")
    text = next(block.text for block in response.content if block.type == "text")
    summary = ExecutiveSummary.model_validate(json.loads(text))
    invented = check_numbers(summary, dados)
    if invented:
        raise ValueError(f"O resumo citou números que não estão nos dados: {invented}")
    return summary


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def check_numbers(summary: ExecutiveSummary, source: str) -> list[str]:
    """Números citados no resumo que não aparecem na fonte (aceita vírgula ou ponto decimal)."""
    source_numbers = {n.replace(",", ".") for n in _NUMBER.findall(source)}
    cited = _NUMBER.findall(" ".join(summary.achados + summary.recomendacoes))
    return [n for n in cited if n.replace(",", ".") not in source_numbers]
