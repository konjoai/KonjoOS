from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from konjoai.agent.react import AgentResult, AgentStep
from konjoai.api.routes.agent import router
from konjoai.retrieve.reranker import RerankResult


@dataclass
class _SettingsTelemetryOn:
    enable_telemetry: bool = True
    request_timeout_seconds: float = 30.0


@dataclass
class _SettingsTelemetryOff:
    enable_telemetry: bool = False
    request_timeout_seconds: float = 30.0


@dataclass
class _SettingsTimeout:
    enable_telemetry: bool = True
    request_timeout_seconds: float = 0.01


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _sample_result() -> AgentResult:
    return AgentResult(
        answer="Final answer",
        model="stub-agent-model",
        usage={"prompt_tokens": 11, "completion_tokens": 5},
        steps=[
            AgentStep(
                thought="Need documents",
                action="retrieve",
                action_input="refund policy",
                observation="[]",
            ),
            AgentStep(
                thought="Done",
                action="finish",
                action_input="",
                observation="completed",
            ),
        ],
        sources=[
            RerankResult(
                score=0.91,
                content="Refunds are allowed for 30 days.",
                source="policy.md",
                metadata={},
            )
        ],
    )


def test_agent_query_route_returns_agent_result(monkeypatch):
    for var in (
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "GRPC_PROXY",
        "grpc_proxy",
    ):
        monkeypatch.delenv(var, raising=False)

    app = _make_app()
    client = TestClient(app)

    with (
        patch("konjoai.api.routes.agent.get_settings", return_value=_SettingsTelemetryOn()),
        patch("konjoai.api.routes.agent.RAGAgent.run", return_value=_sample_result()) as run_mock,
    ):
        resp = client.post(
            "/agent/query",
            json={"question": "What is refund policy?", "top_k": 3, "max_steps": 4},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert run_mock.called
    assert body["answer"] == "Final answer"
    assert body["sources"][0]["source"] == "policy.md"
    assert body["steps"][0]["action"] == "retrieve"
    assert body["telemetry"] is not None
    assert body["telemetry"]["steps"]["agent"]["max_steps"] == 4


def test_agent_query_route_disables_telemetry_when_off(monkeypatch):
    for var in (
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "GRPC_PROXY",
        "grpc_proxy",
    ):
        monkeypatch.delenv(var, raising=False)

    app = _make_app()
    client = TestClient(app)

    with (
        patch("konjoai.api.routes.agent.get_settings", return_value=_SettingsTelemetryOff()),
        patch("konjoai.api.routes.agent.RAGAgent.run", return_value=_sample_result()),
    ):
        resp = client.post("/agent/query", json={"question": "Q"})

    assert resp.status_code == 200
    assert resp.json()["telemetry"] is None


def test_agent_query_route_returns_504_on_timeout(monkeypatch):
    for var in (
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "GRPC_PROXY",
        "grpc_proxy",
    ):
        monkeypatch.delenv(var, raising=False)

    app = _make_app()
    client = TestClient(app)

    async def _slow_to_thread(_fn, *_args, **_kwargs):
        import asyncio

        await asyncio.sleep(0.05)
        return _sample_result()

    with (
        patch("konjoai.api.routes.agent.get_settings", return_value=_SettingsTimeout()),
        patch("konjoai.api.routes.agent.asyncio.to_thread", _slow_to_thread),
    ):
        resp = client.post("/agent/query", json={"question": "Q", "max_steps": 2})

    assert resp.status_code == 504
    assert "timed out" in resp.json()["detail"]
