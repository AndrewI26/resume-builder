"""Entrypoint for the PDF worker: ``uv run python worker.py``.

Not ``arq services.compiler_worker.WorkerSettings``. arq 0.25 builds its
``Worker`` with ``asyncio.get_event_loop()``, which on Python 3.14 raises
rather than creating a loop on demand, so its CLI cannot start a worker on the
version this API runs. Constructing the worker inside a running loop is the
same object by a different route.
"""

import asyncio
from typing import Any, cast

from arq.worker import Worker, get_kwargs

from services.compiler_worker import WorkerSettings


async def main() -> None:
    # arq reads settings off the class __dict__ and accepts that as a plain
    # mapping; its own annotations for both ends of this are wrong, hence the
    # casts rather than a type: ignore that would hide a real mismatch too
    declared = {
        name: value
        for name, value in vars(WorkerSettings).items()
        if not name.startswith("_")
    }
    worker = Worker(**cast(dict[str, Any], get_kwargs(declared)))
    await worker.async_run()


if __name__ == "__main__":
    asyncio.run(main())
