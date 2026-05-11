#!/usr/bin/env python3
"""One-shot import of legacy ``heckler_YYYY-MM-DD.jsonl`` lines into SQLite ``events``.

Each non-empty line must be a single JSON object that :func:`heckle_event_from_json_dict`
accepts (same shape as :func:`serialize_heckle_event` output — no ``audio_chunk`` in the
persisted event body). Each line is written with the same ``payload_json`` contract as live
logging (:func:`~heckler.models.serialize_heckle_event`), plus v2 normalized ``events``
columns and ``event_reactor_results`` when present (see implementation); ``correlation_json``
is always ``NULL`` (legacy files had no LiteLLM correlation).

**Idempotency:** Re-importing the same file inserts duplicate rows by default. Pass
``--skip-existing`` to skip lines whose ``(utterance_id, timestamp_iso)`` pair already
appears in ``events``. Detection uses the same ``$.utterance_id`` / ``$.timestamp_iso``
paths as :func:`~heckler.models.serialize_heckle_event`, preferring v2 normalized
``events`` columns when present (``COALESCE`` with ``json_extract`` on ``payload_json``)
so rows match the live logger / migration shape. Requires JSON1 for the extract arm;
ships with the standard library ``sqlite3`` build on supported platforms.

**Manual verification checklist**

1. From the repo root, with the package importable (e.g. ``pip install -e .``) or after
   ensuring ``sys.path`` includes the repo root (this script prepends the parent of
   ``scripts/``).
2. Create ``tmp/sample.jsonl`` with one line: output of ``json.dumps`` on
   ``serialize_heckle_event`` for any valid :class:`~heckler.models.HeckleEvent` (or a
   hand-written dict matching :func:`~heckler.models.heckle_event_from_json_dict`).
3. ``python scripts/import_legacy_jsonl.py --database /tmp/test-import.db tmp/sample.jsonl``
4. ``sqlite3 /tmp/test-import.db 'SELECT COUNT(*) FROM events;'`` → expect ``1``.
5. Run the same command again; without ``--skip-existing``, count becomes ``2``; with
   ``--skip-existing``, count stays ``1`` and stderr reports one skipped line.

**Automated tests:** ``tests/test_import_legacy_jsonl.py`` (dedupe paths, normalized insert,
reactor child row).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_pkg_path() -> None:
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def _pair_exists(conn: sqlite3.Connection, utterance_id: str, timestamp_iso: str) -> bool:
    """True if ``(utterance_id, timestamp_iso)`` is already stored (normalized and/or JSON).

    Matches :func:`~heckler.event_store.insert_heckle_event_row` / migration semantics:
    v2 columns are authoritative when set; legacy JSON-only rows still dedupe via
    ``json_extract`` on ``payload_json`` using the same ``$`` paths as
    :func:`~heckler.models.serialize_heckle_event`.
    """
    row = conn.execute(
        """
        SELECT 1 FROM events
        WHERE COALESCE(utterance_id, json_extract(payload_json, '$.utterance_id')) = ?
          AND COALESCE(timestamp_iso, json_extract(payload_json, '$.timestamp_iso')) = ?
        LIMIT 1
        """,
        (utterance_id, timestamp_iso),
    ).fetchone()
    return row is not None


def _insert_imported_event(cur: sqlite3.Cursor, event: object, payload_json: str) -> int:
    """Insert one imported row: ``payload_json`` plus v2 analytics columns and reactor child.

    Mirrors :func:`~heckler.event_store.insert_heckle_event_row` SQL shape but leaves the
    surrounding transaction to :func:`import_lines` (single commit per file batch).
    """
    _ensure_pkg_path()
    from heckler.event_store import _EVENT_ANALYTICS_COLUMNS, _heckle_event_analytics_params

    col_names = ", ".join(name for name, _ in _EVENT_ANALYTICS_COLUMNS)
    placeholders = ", ".join("?" for _ in _EVENT_ANALYTICS_COLUMNS)
    sql = (
        f"INSERT INTO events (payload_json, correlation_json, {col_names}) "
        f"VALUES (?, ?, {placeholders})"
    )
    params = (payload_json, None) + _heckle_event_analytics_params(event)
    cur.execute(sql, params)
    event_id = int(cur.lastrowid)
    rr = event.reactor_result
    if rr is not None:
        cur.execute(
            """
            INSERT INTO event_reactor_results (
                event_id, comment, score, comment_type, raw_response
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_id,
                rr.comment,
                rr.score,
                rr.comment_type.value,
                rr.raw_response,
            ),
        )
    return event_id


def import_lines(
    conn: sqlite3.Connection,
    lines: list[str],
    *,
    dry_run: bool,
    skip_existing: bool,
) -> tuple[int, int, int, int]:
    """Parse JSONL lines, validate as HeckleEvent-shaped dicts, insert (or count dry).

    Returns ``(inserted, skipped_duplicate, skipped_blank, errors)``.
    """
    _ensure_pkg_path()
    from heckler.models import heckle_event_from_json_dict, serialize_heckle_event

    inserted = 0
    skipped_duplicate = 0
    skipped_blank = 0
    errors = 0
    cur = conn.cursor()
    try:
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                skipped_blank += 1
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as e:
                print(f"line {lineno}: invalid JSON: {e}", file=sys.stderr)
                errors += 1
                continue
            if not isinstance(raw, dict):
                print(f"line {lineno}: expected JSON object, got {type(raw).__name__}", file=sys.stderr)
                errors += 1
                continue
            try:
                event = heckle_event_from_json_dict(raw)
            except (KeyError, TypeError, ValueError) as e:
                print(f"line {lineno}: not a valid HeckleEvent payload: {e}", file=sys.stderr)
                errors += 1
                continue
            payload_json = json.dumps(
                serialize_heckle_event(event),
                ensure_ascii=False,
            )
            if skip_existing:
                try:
                    if _pair_exists(conn, event.utterance_id, event.timestamp_iso):
                        skipped_duplicate += 1
                        continue
                except sqlite3.OperationalError as e:
                    print(
                        "skip-existing requires SQLite JSON1 (json_extract). "
                        f"Database error: {e}",
                        file=sys.stderr,
                    )
                    raise SystemExit(2) from e
            if dry_run:
                inserted += 1
                continue
            _insert_imported_event(cur, event, payload_json)
            inserted += 1
        if not dry_run:
            conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        cur.close()
    return inserted, skipped_duplicate, skipped_blank, errors


def _collect_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for p in patterns:
        path = Path(p)
        if any(ch in p for ch in "*?[]"):
            paths.extend(sorted(Path().glob(p)))
        else:
            paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import legacy heckler_*.jsonl event lines into SQLite."
    )
    parser.add_argument(
        "--database",
        "-d",
        default=None,
        help="SQLite database path (default: HECKLER_DATABASE_PATH env or logs/heckler.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate only; do not write rows.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip rows whose (utterance_id, timestamp_iso) already exist in events.",
    )
    parser.add_argument(
        "jsonl_files",
        nargs="+",
        metavar="FILE",
        help="JSONL file paths (shell glob accepted, e.g. logs/heckler_*.jsonl)",
    )
    args = parser.parse_args(argv)

    _ensure_pkg_path()
    from heckler.event_store import init_schema, open_store

    if args.database:
        db_path = Path(args.database)
    else:
        import os

        env = (os.environ.get("HECKLER_DATABASE_PATH") or "").strip()
        db_path = Path(env) if env else _repo_root() / "logs" / "heckler.db"

    paths = _collect_paths(args.jsonl_files)
    if not paths:
        print("No input files matched.", file=sys.stderr)
        return 1

    conn = open_store(db_path)
    label = "would import" if args.dry_run else "imported"
    try:
        init_schema(conn)
        total_inserted = 0
        total_skipped_dup = 0
        total_skipped_blank = 0
        total_errors = 0
        for path in paths:
            if not path.is_file():
                print(f"skip: not a file: {path}", file=sys.stderr)
                total_errors += 1
                continue
            text = path.read_text(encoding="utf-8-sig")
            lines = text.splitlines()
            ins, sd, sb, err = import_lines(
                conn,
                lines,
                dry_run=args.dry_run,
                skip_existing=args.skip_existing,
            )
            total_inserted += ins
            total_skipped_dup += sd
            total_skipped_blank += sb
            total_errors += err
            print(
                f"{path}: {label} {ins}, skipped_blank {sb}, "
                f"skipped_existing {sd}, errors {err}"
            )
        print(
            f"total: {label} {total_inserted}, skipped_blank {total_skipped_blank}, "
            f"skipped_existing {total_skipped_dup}, errors {total_errors}"
        )
        return 1 if total_errors else 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
