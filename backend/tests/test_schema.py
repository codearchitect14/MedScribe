"""Verifies the Phase 1 data layer against a live database.

Requires the postgres service from docker-compose.yml to be running and
migrated (see README.md). Skips automatically if no database is reachable.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings

settings = get_settings()


def _get_connection():
    engine = create_engine(settings.sync_database_url)
    try:
        conn = engine.connect()
    except OperationalError:
        pytest.skip("database not reachable; start docker compose postgres service first")
    return conn


EXPECTED_TABLES = {
    "organizations",
    "users",
    "patients",
    "encounters",
    "soap_notes",
    "care_plans",
    "code_suggestions",
    "icd10_codes",
    "procedure_codes",
    "note_embeddings",
    "billing_records",
    "audit_logs",
    "llm_usage_logs",
}


def test_all_tables_exist():
    conn = _get_connection()
    with conn:
        rows = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        ).fetchall()
    table_names = {row[0] for row in rows}
    missing = EXPECTED_TABLES - table_names
    assert not missing, f"missing tables: {missing}"


def test_vector_extension_enabled():
    conn = _get_connection()
    with conn:
        row = conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).fetchone()
    assert row is not None, "pgvector extension is not enabled"


def test_icd10_codes_have_embeddings():
    conn = _get_connection()
    with conn:
        total = conn.execute(text("SELECT count(*) FROM icd10_codes")).scalar_one()
        with_embedding = conn.execute(
            text("SELECT count(*) FROM icd10_codes WHERE embedding IS NOT NULL")
        ).scalar_one()
    if total == 0:
        pytest.skip("icd10_codes table is empty; run scripts/load_reference_codes.py first")
    assert with_embedding == total


def test_vector_similarity_search_returns_relevant_code():
    from app.embeddings.embedder import embed_text

    conn = _get_connection()
    with conn:
        total = conn.execute(text("SELECT count(*) FROM icd10_codes")).scalar_one()
        if total == 0:
            pytest.skip("icd10_codes table is empty; run scripts/load_reference_codes.py first")

        query_embedding = embed_text("patient has high blood sugar and type 2 diabetes")
        top_code = conn.execute(
            text(
                """
                SELECT code FROM icd10_codes
                ORDER BY embedding <=> (:q)::vector
                LIMIT 1
                """
            ),
            {"q": str(query_embedding)},
        ).scalar_one()
    assert top_code.startswith("E11")
