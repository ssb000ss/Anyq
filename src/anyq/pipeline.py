from __future__ import annotations

import asyncio

import structlog

from anyq.extractors.tfidf import TFIDFExtractor
from anyq.jobs.storage import JobStatus, RedisJobStorage, Report
from anyq.parsers.factory import ParserFactory
from anyq.query_gen.llm import OllamaQueryGenerator
from anyq.query_gen.rule_based import RuleBasedQueryGenerator
from anyq.search.orchestrator import SearchOrchestrator

log = structlog.get_logger()


async def run_pipeline(
    job_id: str,
    file_content: bytes,
    filename: str,
    storage: RedisJobStorage,
    orchestrator: SearchOrchestrator,
    ollama_gen: OllamaQueryGenerator,
    rule_gen: RuleBasedQueryGenerator,
    max_queries: int = 15,
) -> None:
    async def _update(status: JobStatus, progress: int, step: str) -> None:
        await storage.update_job(
            job_id,
            status=status,
            progress=progress,
            current_step=step,
        )

    try:
        # ── [1/4] Parse ──────────────────────────────────────
        await _update(JobStatus.parsing, 10, "Парсинг документа...")
        parser = ParserFactory.get(filename)

        # Run sync parser in thread to avoid blocking event loop
        doc = await asyncio.to_thread(parser.parse, file_content, filename)
        del file_content  # free memory as soon as parsing is done
        log.info("pipeline.parsed", job_id=job_id, title=doc.title)

        # ── [2/4] Extract + Generate queries ─────────────────
        await _update(JobStatus.generating, 25, "Извлечение ключевых фраз...")
        key_phrases = await asyncio.to_thread(
            TFIDFExtractor.extract_key_phrases, doc.full_text
        )
        samples = await asyncio.to_thread(
            TFIDFExtractor.extract_sample_sentences, doc.full_text
        )

        await _update(JobStatus.generating, 35, "Генерация поисковых запросов...")
        rule_queries = rule_gen.generate(doc, key_phrases, samples, max_queries)
        llm_queries = await ollama_gen.generate(doc, key_phrases)

        # merge: llm first (more intelligent), then rule-based, deduplicate
        seen: set[str] = set()
        all_queries: list[str] = []
        for q in llm_queries + rule_queries:
            if q not in seen:
                seen.add(q)
                all_queries.append(q)
        queries = all_queries[:max_queries]

        log.info("pipeline.queries", job_id=job_id, count=len(queries))

        # ── [3/4] Search ──────────────────────────────────────
        await _update(JobStatus.searching, 45, f"Поиск по {len(queries)} запросам...")

        async def on_progress(done: int, total: int) -> None:
            progress = 45 + int((done / total) * 45)
            await storage.update_job(
                job_id,
                progress=progress,
                current_step=f"Поиск: {done}/{total} запросов...",
            )

        results = await orchestrator.search_all(queries, on_progress=on_progress)

        # ── [4/4] Save report ─────────────────────────────────
        await _update(JobStatus.searching, 95, "Формирование отчёта...")
        report = Report(
            job_id=job_id,
            results=results,
            queries_used=queries,
            total_found=len(results),
        )
        await storage.save_report(job_id, report)
        await storage.update_job(
            job_id,
            status=JobStatus.done,
            progress=100,
            current_step="Готово",
        )
        log.info("pipeline.done", job_id=job_id, results=len(results))

    except asyncio.CancelledError:
        # Server is shutting down — mark job as failed cleanly
        log.warning("pipeline.cancelled", job_id=job_id)
        await storage.update_job(
            job_id,
            status=JobStatus.failed,
            error="Обработка прервана: сервер перезапущен. Попробуйте снова.",
        )
        raise  # must re-raise CancelledError

    except NotImplementedError as exc:
        await storage.update_job(
            job_id,
            status=JobStatus.failed,
            error=str(exc),
        )

    except Exception as exc:
        log.exception("pipeline.failed", job_id=job_id)
        await storage.update_job(
            job_id,
            status=JobStatus.failed,
            error="Внутренняя ошибка при обработке документа.",
        )
