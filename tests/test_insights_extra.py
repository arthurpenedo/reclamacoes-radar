import io
import json
from types import SimpleNamespace

import pytest

from reclamacoes_radar import insights


def test_post_json_envia_json_e_le_resposta(monkeypatch):
    vistos = {}

    def falso_urlopen(req, timeout):
        vistos.update(url=req.full_url, corpo=json.loads(req.data), timeout=timeout)
        return io.StringIO('{"ok": 1}')

    monkeypatch.setattr(insights.urllib.request, "urlopen", falso_urlopen)
    assert insights._post_json("http://x/api", {"a": 2}) == {"ok": 1}
    assert vistos["corpo"] == {"a": 2} and vistos["url"] == "http://x/api"


def test_summarize_recusa_levanta_refusal_error():
    def create(**kwargs):
        return SimpleNamespace(stop_reason="refusal", content=[])

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    with pytest.raises(insights.RefusalError):
        insights.summarize({"visao_geral": {}}, client=client)
