"""Load ICD-10-CM and HCPCS reference codes into the database, with embeddings.

Reads CSV files in the schema documented in docs/datasets.md. The bundled
sample files under backend/data/reference/ are a small curated set suitable
for local development and demos. To load a full official CMS release,
convert the CMS ICD-10-CM and HCPCS release files into the same CSV columns
and point this script at those files instead.

Usage:
    python -m scripts.load_reference_codes \
        --icd10 data/reference/icd10_sample.csv \
        --hcpcs data/reference/hcpcs_sample.csv
"""

import argparse
import csv
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.embeddings.embedder import embed_texts

BATCH_SIZE = 64


def load_icd10(session: Session, csv_path: Path) -> int:
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    count = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        texts = [row["long_description"] for row in batch]
        embeddings = embed_texts(texts)
        for row, embedding in zip(batch, embeddings):
            session.execute(
                text(
                    """
                    INSERT INTO icd10_codes (code, short_description, long_description, chapter, category, embedding)
                    VALUES (:code, :short_description, :long_description, :chapter, :category, :embedding)
                    ON CONFLICT (code) DO UPDATE SET
                        short_description = EXCLUDED.short_description,
                        long_description = EXCLUDED.long_description,
                        chapter = EXCLUDED.chapter,
                        category = EXCLUDED.category,
                        embedding = EXCLUDED.embedding
                    """
                ),
                {
                    "code": row["code"],
                    "short_description": row["short_description"],
                    "long_description": row["long_description"],
                    "chapter": row.get("chapter") or None,
                    "category": row.get("category") or None,
                    "embedding": str(embedding),
                },
            )
            count += 1
        session.commit()
    return count


def load_hcpcs(session: Session, csv_path: Path) -> int:
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    count = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        texts = [row["description"] for row in batch]
        embeddings = embed_texts(texts)
        for row, embedding in zip(batch, embeddings):
            session.execute(
                text(
                    """
                    INSERT INTO procedure_codes (code, description, category, is_sample_only, embedding)
                    VALUES (:code, :description, :category, :is_sample_only, :embedding)
                    ON CONFLICT (code) DO UPDATE SET
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        is_sample_only = EXCLUDED.is_sample_only,
                        embedding = EXCLUDED.embedding
                    """
                ),
                {
                    "code": row["code"],
                    "description": row["description"],
                    "category": row.get("category") or None,
                    "is_sample_only": row.get("is_sample_only", "false").strip().lower() == "true",
                    "embedding": str(embedding),
                },
            )
            count += 1
        session.commit()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icd10", type=Path, default=Path("data/reference/icd10_sample.csv"))
    parser.add_argument("--hcpcs", type=Path, default=Path("data/reference/hcpcs_sample.csv"))
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.sync_database_url)

    with Session(engine) as session:
        icd10_count = load_icd10(session, args.icd10)
        hcpcs_count = load_hcpcs(session, args.hcpcs)

    print(f"Loaded {icd10_count} ICD-10-CM codes from {args.icd10}")
    print(f"Loaded {hcpcs_count} HCPCS codes from {args.hcpcs}")


if __name__ == "__main__":
    main()
