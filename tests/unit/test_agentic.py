from __future__ import annotations

from dataclasses import dataclass

from konjoai.agent.react import RAGAgent
from konjoai.generate.generator import GenerationResult
from konjoai.retrieve.hybrid import HybridResult
from konjoai.retrieve.reranker import RerankResult


@dataclass
class _SeqGenerator:
    responses: list[str]

    def __post_init__(self) -> None:
        self._i = 0

    def generate(self, question: str, context: str) -> GenerationResult:
        _ = (question, context)
        idx = min(self._i, len(self.responses) - 1)
        self._i += 1
        return GenerationResult(
            answer=self.responses[idx],
            model="stub-agent-model",
            usage={"prompt_tokens": 7, "completion_tokens": 3},
        )


def test_agent_retrieve_then_finish(monkeypatch):
    def _hybrid(query: str, top_k_dense: int, top_k_sparse: int):
        _ = (query, top_k_dense, top_k_sparse)
        return [
            HybridResult(
                rrf_score=0.88,
                content="Refund policy: 30 days with receipt.",
                source="policy.md",
                metadata={},
            )
        ]

    def _rerank(query: str, candidates: list[HybridResult], top_k: int):
        _ = query
        c = candidates[0]
        return [
            RerankResult(
                score=0.95,
                content=c.content,
                source=c.source,
                metadata=c.metadata,
            )
        ][:top_k]

    monkeypatch.setattr("konjoai.agent.react.hybrid_search", _hybrid)
    monkeypatch.setattr("konjoai.agent.react.rerank", _rerank)

    gen = _SeqGenerator(
        responses=[
            '{"thought":"Need docs first","action":"retrieve","action_input":"refund policy","final_answer":""}',
            '{"thought":"Enough evidence","action":"finish","action_input":"","final_answer":"Refunds are accepted within 30 days with receipt."}',
        ]
    )

    result = RAGAgent(max_steps=3, top_k=3).run("What is the refund policy?", generator=gen)

    assert result.answer.startswith("Refunds are accepted")
    assert [s.action for s in result.steps] == ["retrieve", "finish"]
    assert result.sources
    assert result.sources[0].source == "policy.md"


def test_agent_invalid_json_falls_back_to_raw_answer(monkeypatch):
    monkeypatch.setattr("konjoai.agent.react.hybrid_search", lambda *args, **kwargs: [])
    monkeypatch.setattr("konjoai.agent.react.rerank", lambda *args, **kwargs: [])

    gen = _SeqGenerator(responses=["plain text answer without JSON"])
    result = RAGAgent(max_steps=2, top_k=2).run("hello", generator=gen)

    assert result.answer == "plain text answer without JSON"
    assert result.steps
    assert result.steps[0].thought == "parser_fallback"
    assert result.steps[0].action == "finish"


def test_agent_max_steps_guard_triggers_direct_generation(monkeypatch):
    def _hybrid(query: str, top_k_dense: int, top_k_sparse: int):
        _ = (query, top_k_dense, top_k_sparse)
        return [
            HybridResult(
                rrf_score=0.5,
                content="Document content",
                source="doc.txt",
                metadata={},
            )
        ]

    def _rerank(query: str, candidates: list[HybridResult], top_k: int):
        _ = query
        c = candidates[0]
        return [RerankResult(score=0.4, content=c.content, source=c.source, metadata=c.metadata)][:top_k]

    monkeypatch.setattr("konjoai.agent.react.hybrid_search", _hybrid)
    monkeypatch.setattr("konjoai.agent.react.rerank", _rerank)

    gen = _SeqGenerator(
        responses=[
            '{"thought":"retrieve","action":"retrieve","action_input":"doc","final_answer":""}',
            "fallback final answer",
        ]
    )
    result = RAGAgent(max_steps=1, top_k=1).run("Question", generator=gen)

    assert result.answer == "fallback final answer"
    assert result.steps[-1].thought == "max_steps_guard"
    assert result.steps[-1].action == "finish"
