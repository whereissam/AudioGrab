"""Named custom extraction-schema accessors (P17).

A saved schema is a reusable ``{"fields": [{name, type, description}]}``
definition for the CUSTOM extraction preset, addressable by ``schema_id``
(stable hash) or unique human name.
"""

import hashlib
import json
from datetime import datetime
from typing import Optional


def compute_schema_id(name: str) -> str:
    digest = hashlib.sha256(name.strip().lower().encode()).hexdigest()[:8]
    return f"xs_{digest}"


class _ExtractionSchemasMixin:
    """Extraction-schema CRUD used by the extract routes."""

    def create_extraction_schema(
        self, *, name: str, fields: list[dict], description: Optional[str] = None
    ) -> dict:
        """Insert a schema. Raises ValueError on a duplicate name."""
        row = {
            "schema_id": compute_schema_id(name),
            "name": name.strip(),
            "description": description,
            "fields": fields,
            "created_at": datetime.utcnow().isoformat(),
        }
        import sqlite3

        with self._get_conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO extraction_schemas
                        (schema_id, name, description, fields, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row["schema_id"],
                        row["name"],
                        row["description"],
                        json.dumps(fields),
                        row["created_at"],
                    ),
                )
            except sqlite3.IntegrityError as e:
                raise ValueError(f"Schema name '{name}' already exists") from e
        return row

    def get_extraction_schema(self, id_or_name: str) -> Optional[dict]:
        with self._get_conn() as conn:
            r = conn.execute(
                "SELECT * FROM extraction_schemas "
                "WHERE schema_id = ? OR name = ?",
                (id_or_name, id_or_name),
            ).fetchone()
        return self._schema_row_to_dict(r) if r else None

    def list_extraction_schemas(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM extraction_schemas ORDER BY created_at DESC"
            ).fetchall()
        return [self._schema_row_to_dict(r) for r in rows]

    def delete_extraction_schema(self, id_or_name: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM extraction_schemas "
                "WHERE schema_id = ? OR name = ?",
                (id_or_name, id_or_name),
            )
            return cur.rowcount > 0

    @staticmethod
    def _schema_row_to_dict(row) -> dict:
        d = dict(row)
        try:
            d["fields"] = json.loads(d.get("fields") or "[]")
        except (TypeError, ValueError):
            d["fields"] = []
        return d
