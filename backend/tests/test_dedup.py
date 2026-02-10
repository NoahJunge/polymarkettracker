"""Tests for snapshot document ID generation and deduplication."""

from datetime import datetime, timezone

from utils.dedup import generate_snapshot_doc_id, parse_snapshot_doc_id


class TestGenerateSnapshotDocId:
    def test_basic_generation(self):
        ts = datetime(2025, 2, 9, 15, 30, 0, tzinfo=timezone.utc)
        doc_id = generate_snapshot_doc_id(ts, "market_123")
        assert doc_id == "2025-02-09T15:30:00Z|market_123"

    def test_deterministic(self):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        id1 = generate_snapshot_doc_id(ts, "abc")
        id2 = generate_snapshot_doc_id(ts, "abc")
        assert id1 == id2

    def test_different_timestamps_differ(self):
        ts1 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2025, 1, 1, 0, 1, 0, tzinfo=timezone.utc)
        assert generate_snapshot_doc_id(ts1, "m") != generate_snapshot_doc_id(ts2, "m")

    def test_different_markets_differ(self):
        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert generate_snapshot_doc_id(ts, "a") != generate_snapshot_doc_id(ts, "b")

    def test_naive_datetime_treated_as_utc(self):
        ts = datetime(2025, 3, 1, 10, 30, 0)
        doc_id = generate_snapshot_doc_id(ts, "m1")
        assert doc_id == "2025-03-01T10:30:00Z|m1"

    def test_second_precision(self):
        ts = datetime(2025, 1, 1, 0, 0, 45, tzinfo=timezone.utc)
        doc_id = generate_snapshot_doc_id(ts, "m1")
        assert "00:00:45Z" in doc_id


class TestParseSnapshotDocId:
    def test_roundtrip(self):
        ts = datetime(2025, 7, 20, 8, 15, 30, tzinfo=timezone.utc)
        market_id = "clob_market_xyz"
        doc_id = generate_snapshot_doc_id(ts, market_id)
        parsed_ts, parsed_mid = parse_snapshot_doc_id(doc_id)
        assert parsed_ts == ts
        assert parsed_mid == market_id

    def test_parse_known_string(self):
        ts, mid = parse_snapshot_doc_id("2025-02-09T15:30:00Z|market_abc")
        assert ts == datetime(2025, 2, 9, 15, 30, 0, tzinfo=timezone.utc)
        assert mid == "market_abc"

    def test_market_id_with_pipe(self):
        """Market IDs shouldn't contain pipes, but handle gracefully."""
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        doc_id = generate_snapshot_doc_id(ts, "has|pipe")
        parsed_ts, parsed_mid = parse_snapshot_doc_id(doc_id)
        assert parsed_mid == "has|pipe"
