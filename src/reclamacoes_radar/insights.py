"""Camada opcional de IA: transforma os indicadores em um resumo executivo.

O modelo recebe SOMENTE os números já calculados em SQL. Para evitar números inventados,
`check_numbers` confere se todo número citado no resumo existe nos dados de entrada.
"""

import json
import os
import re
import urllib.request
from typing import Callable

from pydantic import BaseModel, ConfigDict

MODEL = os.getenv("RADAR_MODEL", "claude-opus-5-5")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("RADAR_OLLAMA_MODEL", "qwen2.5:3b")

SYSTEM_PROMPT = """Você é analista de dados de defesa do consumidor. A partir dos indicadores em JSON, \
escreva um resumo executivo em português do Brasil para a diretoria de atendimento de uma empresa.

Regras:
- Use apenas números presentes nos dados. Não calcule novos percentuais nem estime valores.
- Não some nem agrupe categorias (ex.: dois tipos de cobrança): cite cada número como aparece nos dados.
- Destaque no máximo 3 achados e 3 recomendações práticas.
- Seja direto: frases curtas, sem jargão."""


class ExecutiveSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    achados: list[str]
    recomendacoes: list[str]


class RefusalError(RuntimeError):
    pass


class NumerosInventados(ValueError):
    """O resumo citou números fora dos dados. Guarda o resumo rejeitado para auditoria."""

    def __init__(self, invented: list[str], summary: ExecutiveSummary):
        super().__init__(f"O resumo citou números que não estão nos dados: {invented}")
        self.invented, self.summary = invented, summary


def _post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp)


def summarize_ollama(indicadores: dict, model: str = OLLAMA_MODEL, url: str = OLLAMA_URL,
                     post: Callable[[str, dict], dict] = _post_json, tentativas: int = 3) -> ExecutiveSummary:
    """Resumo com modelo aberto (Ollama): grátis, mas erra mais número que o Claude.

    Por isso a trava é mais importante aqui: se o resumo cita número fora dos dados, a rejeição
    volta para o modelo como feedback e ele tenta de novo (até `tentativas`). Se nenhuma tentativa
    passar, levanta `NumerosInventados` com o último resumo, nunca publica número inventado.
    """
    dados = json.dumps(indicadores, ensure_ascii=False, default=str)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"<indicadores>\n{dados}\n</indicadores>"}]
    for tentativa in range(tentativas):
        response = post(f"{url.rstrip('/')}/api/chat", {
            "model": model, "stream": False, "messages": messages,
            "format": ExecutiveSummary.model_json_schema(),
            "options": {"temperature": 0.2 * tentativa, "seed": 7},
        })
        text = response["message"]["content"]
        summary = ExecutiveSummary.model_validate(json.loads(text))
        invented = check_numbers(summary, dados)
        if not invented:
            return summary
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": f"Os números {invented} não estão nos dados. Reescreva sem eles, "
                                                 "citando apenas números exatamente como aparecem nos indicadores."}]
    raise NumerosInventados(invented, summary)


def summarize(indicadores: dict, client=None) -> ExecutiveSummary:
    if client is None:
        import anthropic  # import preguiçoso: o resumo com Ollama não precisa do SDK

        client = anthropic.Anthropic()
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
        raise NumerosInventados(invented, summary)
    return summary


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def check_numbers(summary: ExecutiveSummary, source: str) -> list[str]:
    """Números citados no resumo que não aparecem na fonte (aceita vírgula ou ponto decimal)."""
    source_numbers = {n.replace(",", ".") for n in _NUMBER.findall(source)}
    cited = _NUMBER.findall(" ".join(summary.achados + summary.recomendacoes))
    return [n for n in cited if n.replace(",", ".") not in source_numbers]
