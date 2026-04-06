import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.runtime.dedupe import MessageDeduplicator


class TestMessageDeduplicator(unittest.TestCase):
    def test_first_seen_message_is_not_duplicate(self) -> None:
        deduplicator = MessageDeduplicator()

        self.assertFalse(deduplicator.is_duplicate("msg-1"))

    def test_second_seen_message_is_duplicate(self) -> None:
        deduplicator = MessageDeduplicator()

        self.assertFalse(deduplicator.is_duplicate("msg-1"))
        self.assertTrue(deduplicator.is_duplicate("msg-1"))

    def test_different_message_ids_are_not_duplicates(self) -> None:
        deduplicator = MessageDeduplicator()

        self.assertFalse(deduplicator.is_duplicate("msg-1"))
        self.assertFalse(deduplicator.is_duplicate("msg-2"))

    def test_clear_resets_tracked_messages(self) -> None:
        deduplicator = MessageDeduplicator()

        self.assertFalse(deduplicator.is_duplicate("msg-1"))
        self.assertTrue(deduplicator.is_duplicate("msg-1"))

        deduplicator.clear()

        self.assertFalse(deduplicator.is_duplicate("msg-1"))

    def test_expired_entries_are_not_considered_duplicates(self) -> None:
        deduplicator = MessageDeduplicator(ttl=5)

        with patch("app.runtime.dedupe.time.time", side_effect=[1000.0, 1006.0]):
            self.assertFalse(deduplicator.is_duplicate("msg-1"))
            self.assertFalse(deduplicator.is_duplicate("msg-1"))

    def test_max_size_evicts_oldest_message_id(self) -> None:
        deduplicator = MessageDeduplicator(ttl=60, max_size=2)

        with patch(
            "app.runtime.dedupe.time.time",
            side_effect=[1000.0, 1001.0, 1002.0, 1003.0],
        ):
            self.assertFalse(deduplicator.is_duplicate("msg-1"))
            self.assertFalse(deduplicator.is_duplicate("msg-2"))
            self.assertFalse(deduplicator.is_duplicate("msg-3"))
            self.assertFalse(deduplicator.is_duplicate("msg-1"))

    def test_concurrent_is_duplicate_calls_are_thread_safe(self) -> None:
        deduplicator = MessageDeduplicator()
        worker_count = 12
        barrier = threading.Barrier(worker_count)

        def worker() -> bool:
            _ = barrier.wait()
            return deduplicator.is_duplicate("shared-message")

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(worker) for _ in range(worker_count)]
            results = [future.result() for future in futures]

        self.assertEqual(results.count(False), 1)
        self.assertEqual(results.count(True), worker_count - 1)


if __name__ == "__main__":
    _ = unittest.main()
