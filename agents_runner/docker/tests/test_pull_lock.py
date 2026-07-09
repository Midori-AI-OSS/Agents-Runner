import threading
import time

from agents_runner.docker.process import _pull_lock


def test_pull_lock_exists_and_is_threading_lock() -> None:
    assert isinstance(_pull_lock, threading.Lock)


def test_pull_lock_serializes_concurrent_access() -> None:
    concurrent_count = 0
    max_concurrent = 0
    count_lock = threading.Lock()

    def locked_work(thread_id: int, results: list[int]) -> None:
        nonlocal concurrent_count, max_concurrent

        with _pull_lock:
            with count_lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            time.sleep(0.08)
            with count_lock:
                concurrent_count -= 1
            results.append(thread_id)

    results: list[int] = []
    threads: list[threading.Thread] = []

    for i in range(4):
        t = threading.Thread(target=locked_work, args=(i, results))
        threads.append(t)

    overall_start = time.monotonic()
    for t in threads:
        t.start()

    for t in threads:
        t.join()
    overall_elapsed = time.monotonic() - overall_start

    assert len(results) == 4
    assert max_concurrent == 1, f"expected max 1 concurrent, got {max_concurrent}"
    assert overall_elapsed >= 0.28, (
        f"expected >= 0.28s (4 * 0.08s sleep), got {overall_elapsed:.3f}s — lock may not be serializing"
    )
