import json
from pathlib import Path

from local_developer_worker.tools import context_route


def test_fixed_retrieval_routing_corpus_is_deterministic_and_bounded():
    corpus = json.loads((Path(__file__).parents[2] / "fixtures" / "context_routing" / "reference_corpus.json").read_text())
    assert corpus["frozen"] is True
    routes = [context_route(case)["data"] for case in corpus["cases"]]
    assert [route["strategy"] for route in routes] == [case["strategy"] for case in corpus["cases"]]
    assert [route["planned_tool_calls"] for route in routes] == [case["planned_tool_calls"] for case in corpus["cases"]]
    assert all(route["repository_content_read"] is False for route in routes)
