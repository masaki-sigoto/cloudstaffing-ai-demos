"""Template store (spec §5.19)."""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path

from ..errors import InputValidationError, TemplateExistsError, TemplateSchemaError
from ..io.loader import Dialect
from ..mapping.inferencer import HeaderMapping
from ..schema.canonical import CANONICAL_COLUMNS

NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


class TemplateStore:
    def __init__(self, templates_dir: Path | None = None) -> None:
        self.templates_dir = templates_dir or Path("templates")

    def save(
        self,
        name: str,
        mapping: HeaderMapping,
        encoding: str,
        dialect: Dialect,
        source_hint: str,
        force: bool = False,
    ) -> Path:
        if not NAME_PATTERN.match(name):
            raise TemplateSchemaError(
                message=f"テンプレート名が命名規則違反: {name}",
                hint="半角英数字とアンダースコアのみ使用可能です",
            )
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        path = self.templates_dir / f"{name}.json"
        if path.exists() and not force:
            raise TemplateExistsError(
                message=f"既存テンプレートがあります: {path}",
                hint="--force で上書きするか、別名で保存してください",
            )

        mapping_entries = []
        for canonical in CANONICAL_COLUMNS:
            if canonical not in mapping.canonical_to_source_index:
                continue
            entry = {
                "canonical": canonical,
                "source": mapping.source_headers.get(canonical, ""),
                "source_index": mapping.canonical_to_source_index[canonical],
                "confidence": round(mapping.confidence.get(canonical, 0.0), 2),
                "needs_review": canonical in mapping.needs_review_columns,
                "via": mapping.via.get(canonical, "edit"),
            }
            mapping_entries.append(entry)

        doc = {
            "schema_version": 1,
            "name": name,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source_hint": source_hint,
            "encoding": encoding,
            "dialect": {
                "delimiter": dialect.delimiter,
                "lineterminator": dialect.lineterminator,
            },
            "header_mapping": mapping_entries,
            "unmapped_source_headers": mapping.unmapped_source_headers,
        }
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, name: str) -> HeaderMapping:
        path = self.templates_dir / f"{name}.json"
        if not path.exists():
            raise InputValidationError(
                message=f"テンプレートが存在しません: {path}",
                hint="save-template で作成してください",
            )
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise TemplateSchemaError(
                message=f"テンプレートJSONが壊れています: {e}", hint=""
            ) from e

        mapping = HeaderMapping()
        for entry in doc.get("header_mapping", []):
            canonical = entry["canonical"]
            mapping.canonical_to_source_index[canonical] = entry["source_index"]
            mapping.source_headers[canonical] = entry["source"]
            mapping.confidence[canonical] = entry.get("confidence", 1.0)
            mapping.via[canonical] = entry.get("via", "manual")
            if entry.get("needs_review"):
                mapping.needs_review_columns.append(canonical)
        mapping.unmapped_source_headers = doc.get("unmapped_source_headers", [])
        return mapping
