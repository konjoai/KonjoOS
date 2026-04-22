from __future__ import annotations

import asyncio
import json
import logging
from typing import Generator as IterGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from konjoai.api.schemas import QueryRequest, QueryResponse, SourceDoc
from konjoai.config import get_settings
from konjoai.telemetry import PipelineTelemetry, timed

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


def _parse_bool_header(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@router.post("", response_model=QueryResponse)
async def query(req: QueryRequest, request: Request) -> QueryResponse:  # noqa: C901
    """Run the full RAG pipeline: route → (HyDE) → (decomposition) → hybrid_search → (CRAG) → rerank → generate → (Self-RAG).

    Pipeline steps (each wrapped in timed() when telemetry is enabled):
        1. route         — classify intent; CHAT short-circuits immediately.
        2. hyde          — (optional) replace query embedding with hypothesis embedding.
        2b. embed+cache  — embed once; check semantic cache before hitting Qdrant.
        3. decompose     — (optional) split AGGREGATION question into sub-queries.
        4. hybrid_search — dense + BM25 retrieval with RRF fusion.
        3b. crag         — (optional) relevance grading + corrective filter.
        5. rerank        — cross-encoder reranking.
        5.5 colbert      — (optional) MaxSim late-interaction re-scoring.
        6. generate      — LLM answer synthesis.
        6a. synthesize   — (optional) decomposition-aware final synthesis.
        6b. self_rag     — (optional) reflection critique; retries if unsupported.
    """
    from konjoai.generate.generator import get_generator
    from konjoai.retrieve.hybrid import HybridResult, hybrid_search
    from konjoai.retrieve.hyde import hyde_encode
    from konjoai.retrieve.reranker import rerank
    from konjoai.retrieve.router import QueryIntent, classify_intent

    settings = get_settings()
    timeout_seconds = float(settings.request_timeout_seconds)
    tel = PipelineTelemetry()

    # Optional pipeline component flags (at function scope so _execute closure can access them)
    if settings.use_vectro_retriever:
        from konjoai.retrieve.vectro_retriever import get_vectro_retriever
    if settings.use_colbert:
        from konjoai.retrieve.late_interaction import rerank_with_maxsim

    async def _execute() -> QueryResponse:  # noqa: C901
        """Inner pipeline coroutine — bounded by asyncio.wait_for in the caller."""
        # Hoist generator import unconditionally to avoid UnboundLocalError from
        # the conditional re-import inside the decomposition branch.
        from konjoai.generate.generator import get_generator  # noqa: PLC0415
        # CRAG + Self-RAG metadata (populated only when those features are enabled)
        crag_confidence: float | None = None
        crag_fallback: bool | None = None
        crag_scores: list[float] | None = None
        crag_classification: list[str] | None = None
        crag_refinement_triggered: bool | None = None
        self_rag_support: float | None = None
        self_rag_iterations: int | None = None
        self_rag_iteration_scores: list[dict[str, float]] | None = None
        self_rag_total_tokens: int | None = None
        decomposition_used: bool | None = None
        decomposition_sub_queries: list[str] | None = None
        decomposition_synthesis_hint: str | None = None

        header_use_crag = _parse_bool_header(
            request.headers.get("use_crag")
            or request.headers.get("use-crag")
            or request.headers.get("x-use-crag")
        )
        header_use_self_rag = _parse_bool_header(
            request.headers.get("use_self_rag")
            or request.headers.get("use-self-rag")
            or request.headers.get("x-use-self-rag")
        )
        header_use_decomposition = _parse_bool_header(
            request.headers.get("use_decomposition")
            or request.headers.get("use-decomposition")
            or request.headers.get("x-use-decomposition")
        )
        crag_enabled = bool(settings.enable_crag or req.use_crag or header_use_crag)
        self_rag_enabled = bool(
            settings.enable_self_rag or req.use_self_rag or header_use_self_rag
        )
        decomposition_enabled = bool(
            settings.enable_query_decomposition
            or req.use_decomposition
            or header_use_decomposition
        )

        # ── Step 1: Intent routing ────────────────────────────────────────────────
        intent = QueryIntent.RETRIEVAL
        if settings.enable_query_router:
            with timed(tel, "route"):
                intent = classify_intent(req.question)

        if intent == QueryIntent.CHAT:
            return QueryResponse(
                answer="I'm KonjoOS, a retrieval-augmented generation assistant. "
                       "Ask me a question about your documents!",
                sources=[],
                model="router",
                usage={},
                telemetry=tel.as_dict() if settings.enable_telemetry else None,
                intent=intent.value,
            )

        # ── Step 2: Query embedding (HyDE or raw) ────────────────────────────────
        effective_question = req.question
        hypothesis: str | None = None

        if req.use_hyde or settings.enable_hyde:
            with timed(tel, "hyde"):
                _, hypothesis = await asyncio.to_thread(hyde_encode, req.question)
            effective_question = hypothesis or req.question
            logger.debug("HyDE hypothesis: %r", effective_question[:120])
        # ── Step 2b: Early embed + cache lookup (RETRIEVAL only) ─────────────────
        q_vec = None
        if intent != QueryIntent.AGGREGATION:
            from konjoai.cache import get_semantic_cache
            _cache_chk = get_semantic_cache()
            if _cache_chk is not None:
                from konjoai.embed.encoder import get_encoder
                with timed(tel, "embed"):
                    q_vec = await asyncio.to_thread(
                        get_encoder().encode_query, effective_question
                    )
                _cached = _cache_chk.lookup(effective_question, q_vec)
                if _cached is not None:
                    logger.debug("semantic cache hit — skipping Qdrant")
                    return _cached.model_copy(update={
                        "cache_hit": True,
                        "telemetry": tel.as_dict() if settings.enable_telemetry else None,
                    })
        # ── Step 3: Hybrid retrieval ──────────────────────────────────────────────
        decomposition_batches: list[tuple[str, list[HybridResult]]] = []
        if intent == QueryIntent.AGGREGATION and decomposition_enabled:
            from konjoai.retrieve.decomposition import ParallelRetriever, QueryDecomposer

            generator = get_generator()
            with timed(tel, "decompose"):
                decomposition_plan = await asyncio.to_thread(
                    QueryDecomposer(
                        generator,
                        max_sub_queries=settings.decomposition_max_sub_queries,
                    ).decompose,
                    effective_question,
                )

            decomposition_used = True
            decomposition_sub_queries = decomposition_plan.sub_queries
            decomposition_synthesis_hint = decomposition_plan.synthesis_hint
            logger.debug(
                "Decomposition fan-out: n_sub_queries=%d fallback=%s",
                len(decomposition_plan.sub_queries),
                decomposition_plan.used_fallback,
            )

            def _retrieve_sub_query(sub_query: str) -> list[HybridResult]:
                if settings.use_vectro_retriever:
                    return get_vectro_retriever().search(
                        sub_query,
                        top_k=settings.top_k_dense,
                    )
                return hybrid_search(sub_query)

            with timed(tel, "parallel_retrieve", n_sub_queries=len(decomposition_plan.sub_queries)):
                raw = await ParallelRetriever().retrieve(decomposition_plan.sub_queries, _retrieve_sub_query)

            decomposition_batches = list(zip(decomposition_plan.sub_queries, raw, strict=False))

            all_results: list[HybridResult] = []
            for _, batch in decomposition_batches:
                all_results.extend(batch)

            seen: dict[str, HybridResult] = {}
            for r in all_results:
                if r.content not in seen or r.rrf_score > seen[r.content].rrf_score:
                    seen[r.content] = r
            hybrid_results = sorted(seen.values(), key=lambda x: x.rrf_score, reverse=True)
        else:
            with timed(
                tel,
                "hybrid_search",
                top_k_dense=settings.top_k_dense,
                top_k_sparse=settings.top_k_sparse,
            ):
                if settings.use_vectro_retriever:
                    hybrid_results = get_vectro_retriever().search(
                        effective_question,
                        top_k=settings.top_k_dense,
                    )
                else:
                    hybrid_results = await asyncio.to_thread(
                        hybrid_search, effective_question, q_vec=q_vec
                    )

        # ── Step 3b: CRAG — Corrective RAG relevance grading ─────────────────────
        if crag_enabled and hybrid_results:
            from konjoai.retrieve.crag import get_crag_pipeline

            with timed(tel, "crag", n_docs=len(hybrid_results)):
                crag_result = await asyncio.to_thread(
                    get_crag_pipeline().run, req.question, hybrid_results
                )
            crag_confidence = crag_result.overall_confidence
            crag_fallback = crag_result.needs_fallback
            crag_scores = crag_result.crag_scores
            crag_classification = crag_result.crag_classification
            crag_refinement_triggered = crag_result.refinement_triggered
            # Use the CRAG-filtered document list for downstream steps
            if crag_result.documents:
                hybrid_results = crag_result.documents  # type: ignore[assignment]
            logger.debug(
                "CRAG: kept=%d discarded=%d confidence=%.3f fallback=%s refinement=%s",
                len(crag_result.documents),
                crag_result.discarded_count,
                crag_result.overall_confidence,
                crag_result.needs_fallback,
                crag_result.refinement_triggered,
            )

        # ── Step 4: Cross-encoder reranking ──────────────────────────────────────
        with timed(tel, "rerank", top_k=req.top_k):
            reranked = await asyncio.to_thread(
                rerank, req.question, hybrid_results, top_k=req.top_k
            )

        # ── Step 4.5: MaxSim late-interaction re-scoring (ColBERT-style) ─────────
        if settings.use_colbert:
            with timed(tel, "colbert_maxsim", top_k=req.top_k):
                from konjoai.embed.encoder import get_encoder
                _enc = get_encoder()
                query_emb = await asyncio.to_thread(_enc.encode, req.question)
                reranked = await asyncio.to_thread(rerank_with_maxsim, query_emb, reranked)
                reranked = reranked[: req.top_k]

        # ── Step 5: Generation ───────────────────────────────────────────────────
        context = "\n\n---\n\n".join(r.content for r in reranked)
        generator = get_generator()

        with timed(tel, "generate", model=settings.openai_model):
            result = await asyncio.to_thread(
                generator.generate, question=req.question, context=context
            )

        answer = result.answer

        # ── Step 5a: Decomposed synthesis for AGGREGATION queries ───────────────
        if decomposition_used and decomposition_batches and decomposition_synthesis_hint:
            from konjoai.retrieve.decomposition import AnswerSynthesizer, SubQueryAnswer

            with timed(tel, "decomposition_synthesis", n_sub_queries=len(decomposition_batches)):
                sub_answers: list[SubQueryAnswer] = []
                for sub_query, batch in decomposition_batches:
                    sub_reranked = await asyncio.to_thread(
                        rerank,
                        sub_query,
                        batch,
                        min(req.top_k, 3),
                    )
                    sub_context = "\n\n---\n\n".join(r.content for r in sub_reranked)
                    sub_result = await asyncio.to_thread(
                        generator.generate,
                        sub_query,
                        sub_context,
                    )
                    sub_answers.append(SubQueryAnswer(sub_query=sub_query, answer=sub_result.answer))

                synthesized = await asyncio.to_thread(
                    AnswerSynthesizer(generator).synthesize,
                    req.question,
                    sub_answers,
                    decomposition_synthesis_hint,
                )
                if synthesized.strip():
                    answer = synthesized

        # ── Step 5b: Self-RAG reflection critique ────────────────────────────────
        if self_rag_enabled and reranked:
            from konjoai.retrieve.self_rag import get_self_rag_pipeline

            with timed(tel, "self_rag"):
                def _gen(active_docs=None) -> str:
                    docs = active_docs if active_docs else reranked
                    active_context = "\n\n---\n\n".join(d.content for d in docs)
                    return generator.generate(question=req.question, context=active_context).answer

                def _retrieve_refined(refined_query: str):
                    if settings.use_vectro_retriever:
                        refined_hybrid = get_vectro_retriever().search(
                            refined_query,
                            top_k=settings.top_k_dense,
                        )
                    else:
                        refined_hybrid = hybrid_search(refined_query)
                    return rerank(refined_query, refined_hybrid, top_k=req.top_k)

                sr = await asyncio.to_thread(
                    get_self_rag_pipeline().run,
                    question=req.question,
                    documents=reranked,
                    generate_fn=_gen,
                    retrieve_fn=_retrieve_refined,
                    max_iterations=settings.self_rag_max_iterations,
                )
            answer = sr.answer
            self_rag_support = sr.support_score
            self_rag_iterations = sr.iterations
            self_rag_iteration_scores = sr.iteration_scores
            self_rag_total_tokens = sr.total_tokens
            logger.debug(
                "Self-RAG: support=%.3f usefulness=%s iterations=%d",
                sr.support_score,
                sr.usefulness.name,
                sr.iterations,
            )

        sources = [
            SourceDoc(
                source=r.source,
                content_preview=r.content[:200],
                score=float(r.score),
            )
            for r in reranked
        ]

        telemetry_payload = tel.as_dict() if settings.enable_telemetry else None
        if telemetry_payload is not None and crag_scores is not None:
            telemetry_payload["crag_scores"] = crag_scores
            telemetry_payload["crag_classification"] = crag_classification
            telemetry_payload["crag_refinement_triggered"] = crag_refinement_triggered
        if telemetry_payload is not None and self_rag_iteration_scores is not None:
            telemetry_payload["self_rag_iteration_scores"] = self_rag_iteration_scores
            telemetry_payload["self_rag_total_tokens"] = self_rag_total_tokens
        if telemetry_payload is not None and decomposition_used:
            telemetry_payload["decomposition_sub_queries"] = decomposition_sub_queries
            telemetry_payload["decomposition_synthesis_hint"] = decomposition_synthesis_hint

        response = QueryResponse(
            answer=answer,
            sources=sources,
            model=result.model,
            usage=result.usage,
            telemetry=telemetry_payload,
            intent=intent.value,
            crag_confidence=crag_confidence,
            crag_fallback=crag_fallback,
            crag_scores=crag_scores,
            crag_classification=crag_classification,
            crag_refinement_triggered=crag_refinement_triggered,
            self_rag_support=self_rag_support,
            self_rag_iterations=self_rag_iterations,
            self_rag_iteration_scores=self_rag_iteration_scores,
            self_rag_total_tokens=self_rag_total_tokens,
            decomposition_used=decomposition_used,
            decomposition_sub_queries=decomposition_sub_queries,
            decomposition_synthesis_hint=decomposition_synthesis_hint,
        )
        # Cache store (after full pipeline; K3: no-op when cache_enabled=False)
        if q_vec is not None:
            from konjoai.cache import get_semantic_cache
            _cache_store = get_semantic_cache()
            if _cache_store is not None:
                await asyncio.to_thread(
                    _cache_store.store, effective_question, q_vec, response
                )
        return response

    try:
        return await asyncio.wait_for(_execute(), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        logger.warning("query timed out after %.2fs", timeout_seconds)
        raise HTTPException(
            status_code=504,
            detail=f"query request timed out after {timeout_seconds:.2f}s",
        ) from exc


@router.post("/stream")
async def query_stream(req: QueryRequest) -> StreamingResponse:  # noqa: C901
    """SSE streaming version of the RAG pipeline.

    Emits Server-Sent Events in the format::

        data: {"token": "...", "done": false}\n\n

    Followed by a final frame::

        data: {"token": "", "done": true, "model": "...",
               "sources": [...], "intent": "..."}\n\n

    The pipeline steps (intent → HyDE → hybrid_search → rerank) run
    synchronously before streaming starts so that source metadata is
    available in the final frame.
    """
    from konjoai.generate.generator import get_generator
    from konjoai.retrieve.hybrid import HybridResult, hybrid_search
    from konjoai.retrieve.hyde import hyde_encode
    from konjoai.retrieve.reranker import rerank
    from konjoai.retrieve.router import QueryIntent, classify_intent

    settings = get_settings()
    timeout_seconds = float(settings.request_timeout_seconds)

    async def _stream_execute() -> StreamingResponse:
        """Pre-streaming retrieval pipeline — bounded by asyncio.wait_for in the caller."""
        # ── Intent routing ────────────────────────────────────────────────────
        intent = QueryIntent.RETRIEVAL
        if settings.enable_query_router:
            intent = classify_intent(req.question)

        if intent == QueryIntent.CHAT:

            def _chat_stream() -> IterGenerator[str, None, None]:
                chat_answer = (
                    "I'm KonjoOS, a retrieval-augmented generation assistant. "
                    "Ask me a question about your documents!"
                )
                for token in chat_answer.split():
                    yield f"data: {json.dumps({'token': token + ' ', 'done': False})}\n\n"
                yield f"data: {json.dumps({'token': '', 'done': True, 'model': 'router', 'sources': [], 'intent': intent.value})}\n\n"

            return StreamingResponse(_chat_stream(), media_type="text/event-stream")

        # ── HyDE (optional) ───────────────────────────────────────────────────
        effective_question = req.question
        if req.use_hyde or settings.enable_hyde:
            _, hypothesis = await asyncio.to_thread(hyde_encode, req.question)
            effective_question = hypothesis or req.question

        # ── Hybrid retrieval + rerank ─────────────────────────────────────────
        if settings.use_vectro_retriever:
            from konjoai.retrieve.vectro_retriever import get_vectro_retriever
            hybrid_results = get_vectro_retriever().search(
                effective_question, top_k=settings.top_k_dense
            )
        else:
            hybrid_results = await asyncio.to_thread(hybrid_search, effective_question)
        reranked = await asyncio.to_thread(rerank, req.question, hybrid_results, top_k=req.top_k)

        # ── MaxSim late-interaction re-scoring ────────────────────────────────
        if settings.use_colbert:
            from konjoai.embed.encoder import get_encoder
            from konjoai.retrieve.late_interaction import rerank_with_maxsim
            _query_emb = await asyncio.to_thread(get_encoder().encode, req.question)
            reranked = (await asyncio.to_thread(rerank_with_maxsim, _query_emb, reranked))[: req.top_k]

        context = "\n\n---\n\n".join(r.content for r in reranked)

        sources = [
            SourceDoc(
                source=r.source,
                content_preview=r.content[:200],
                score=float(r.score),
            ).model_dump()
            for r in reranked
        ]

        generator = get_generator()

        def _stream_tokens() -> IterGenerator[str, None, None]:
            model_name = "unknown"
            if hasattr(generator, "generate_stream"):
                for token in generator.generate_stream(question=req.question, context=context):
                    if token:
                        yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                # Try to get model name for final frame
                model_name = getattr(generator, "_model", "unknown")
            else:
                # Fallback: call generate() synchronously and emit all at once
                result = generator.generate(question=req.question, context=context)
                if result.answer:
                    yield f"data: {json.dumps({'token': result.answer, 'done': False})}\n\n"
                model_name = result.model

            yield f"data: {json.dumps({'token': '', 'done': True, 'model': model_name, 'sources': sources, 'intent': intent.value})}\n\n"

        return StreamingResponse(_stream_tokens(), media_type="text/event-stream")

    try:
        return await asyncio.wait_for(_stream_execute(), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        logger.warning("query/stream timed out after %.2fs", timeout_seconds)
        raise HTTPException(
            status_code=504,
            detail=f"query/stream request timed out after {timeout_seconds:.2f}s",
        ) from exc
