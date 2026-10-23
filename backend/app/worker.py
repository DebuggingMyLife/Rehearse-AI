"""Single worker thread for GPU-bound work (LLM calls, transcription).

Jobs run one at a time so Whisper and Ollama don't compete for VRAM, and so concurrent
requests on the same session can't race (e.g. two "generate more" clicks).
The event loop stays free, so the API remains responsive while a job runs.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Callable, TypeVar

R = TypeVar("R")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpu-worker")


async def run_job(fn: Callable[..., R], *args, **kwargs) -> R:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, partial(fn, *args, **kwargs))


def shutdown() -> None:
    _executor.shutdown(wait=False, cancel_futures=True)
