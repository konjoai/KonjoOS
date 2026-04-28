from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from konjoai.agent.react import RAGAgent
from konjoai.api.schemas import SourceDoc
from konjoai.config import get_settings
from konjoai.telemetry import PipelineTelemetry, timed

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentStepResponse(BaseModel):
    thought: str
    action: str
    action_input: str
    observation: str


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)
    max_steps: int = Field(5, ge=1, le=20)


class AgentQueryResponse(BaseModel):
    answer: str
    sources: list[SourceDoc]
    model: str
    usage: dict
    steps: list[AgentStepResponse]
    telemetry: dict | None = None


@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(req: AgentQueryRequest) -> AgentQueryResponse:
    """Run a bounded ReAct loop over Kyro retrieval tools."""
    settings = get_settings()
    tel = PipelineTelemetry()
    timeout_seconds = float(settings.request_timeout_seconds)

    try:
        with timed(tel, "agent", top_k=req.top_k, max_steps=req.max_steps):
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    RAGAgent(top_k=req.top_k, max_steps=req.max_steps).run,
                    req.question,
                ),
                timeout=timeout_seconds,
            )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"agent request timed out after {timeout_seconds:.2f}s",
        ) from exc

    sources = [
        SourceDoc(
            source=s.source,
            content_preview=s.content[:200],
            score=float(s.score),
        )
        for s in result.sources
    ]

    return AgentQueryResponse(
        answer=result.answer,
        sources=sources,
        model=result.model,
        usage=result.usage,
        steps=[
            AgentStepResponse(
                thought=step.thought,
                action=step.action,
                action_input=step.action_input,
                observation=step.observation,
            )
            for step in result.steps
        ],
        telemetry=tel.as_dict() if settings.enable_telemetry else None,
    )
