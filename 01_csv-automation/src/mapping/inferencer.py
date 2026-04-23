"""Header inferencer (spec §5.9, §6.2). Minimal MVP implementation."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from ..errors import HeaderMappingError
from ..normalize.text import normalize_text
from ..schema.canonical import CANONICAL_COLUMNS, REQUIRED_COLUMNS
from .similarity import similarity_ratio
from .synonyms import SYNONYMS


@dataclass
class HeaderMapping:
    canonical_to_source_index: dict[str, int] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    source_headers: dict[str, str] = field(default_factory=dict)
    via: dict[str, str] = field(default_factory=dict)
    needs_review_columns: list[str] = field(default_factory=list)
    unmapped_columns: list[str] = field(default_factory=list)
    unmapped_source_headers: list[str] = field(default_factory=list)


class HeaderInferencer:
    CONFIRM_THRESHOLD: float = 0.80
    REVIEW_THRESHOLD: float = 0.60

    def __init__(self, synonyms: Optional[dict[str, list[str]]] = None) -> None:
        self.synonyms = synonyms if synonyms is not None else SYNONYMS

    def infer(
        self,
        headers: list[str],
        template: Optional["HeaderMapping"] = None,
    ) -> HeaderMapping:
        if template is not None:
            return self._apply_template(headers, template)

        normalized_headers = [normalize_text(h).lower() for h in headers]

        # Score matrix: canonical -> list[(idx, score, via)]
        per_canonical: dict[str, list[tuple[int, float, str]]] = {}
        for canonical in CANONICAL_COLUMNS:
            syns_norm = [normalize_text(s).lower() for s in self.synonyms[canonical]]
            scored: list[tuple[int, float, str]] = []
            for i, nh in enumerate(normalized_headers):
                if not nh:
                    continue
                if nh in syns_norm:
                    scored.append((i, 1.0, "dict"))
                else:
                    best = max((similarity_ratio(nh, s) for s in syns_norm), default=0.0)
                    scored.append((i, best, "edit"))
            # sort: score desc, via dict-first, leftmost
            scored.sort(key=lambda t: (-t[1], 0 if t[2] == "dict" else 1, t[0]))
            per_canonical[canonical] = scored

        mapping = HeaderMapping()
        used_indices: set[int] = set()

        # Greedy assignment respecting uniqueness; prioritize canonicals with best top scores
        canonical_priority = sorted(
            CANONICAL_COLUMNS,
            key=lambda c: -per_canonical[c][0][1] if per_canonical[c] else 0.0,
        )

        for canonical in canonical_priority:
            candidates = per_canonical[canonical]
            chosen: Optional[tuple[int, float, str]] = None
            for idx, score, via in candidates:
                if idx in used_indices:
                    continue
                chosen = (idx, score, via)
                break
            if chosen is None:
                mapping.unmapped_columns.append(canonical)
                continue
            idx, score, via = chosen
            if score >= self.CONFIRM_THRESHOLD:
                mapping.canonical_to_source_index[canonical] = idx
                mapping.confidence[canonical] = round(score, 2)
                mapping.source_headers[canonical] = headers[idx]
                mapping.via[canonical] = via
                used_indices.add(idx)
            elif score >= self.REVIEW_THRESHOLD:
                mapping.canonical_to_source_index[canonical] = idx
                mapping.confidence[canonical] = round(score, 2)
                mapping.source_headers[canonical] = headers[idx]
                mapping.via[canonical] = via
                mapping.needs_review_columns.append(canonical)
                used_indices.add(idx)
            else:
                mapping.unmapped_columns.append(canonical)

        # Unmapped source headers
        for i, h in enumerate(headers):
            if i not in used_indices:
                mapping.unmapped_source_headers.append(h)

        # REQUIRED check
        missing = REQUIRED_COLUMNS - set(mapping.canonical_to_source_index.keys())
        if missing:
            raise HeaderMappingError(
                message=f"REQUIRED 列が確定できませんでした: {sorted(missing)}",
                hint="同義語辞書外のヘッダーです。--mapping-file で明示してください",
            )
        return mapping

    def _apply_template(
        self, headers: list[str], template: HeaderMapping
    ) -> HeaderMapping:
        mapping = HeaderMapping()
        for canonical in CANONICAL_COLUMNS:
            src = template.source_headers.get(canonical)
            if src is None:
                if canonical in REQUIRED_COLUMNS:
                    mapping.unmapped_columns.append(canonical)
                continue
            if src in headers:
                idx = headers.index(src)
                mapping.canonical_to_source_index[canonical] = idx
                mapping.confidence[canonical] = template.confidence.get(canonical, 1.0)
                mapping.source_headers[canonical] = src
                mapping.via[canonical] = template.via.get(canonical, "manual")
            else:
                mapping.unmapped_columns.append(canonical)

        used = set(mapping.canonical_to_source_index.values())
        for i, h in enumerate(headers):
            if i not in used:
                mapping.unmapped_source_headers.append(h)

        missing = REQUIRED_COLUMNS - set(mapping.canonical_to_source_index.keys())
        if missing:
            raise HeaderMappingError(
                message=f"テンプレート適用後に REQUIRED 列が欠落: {sorted(missing)}",
                hint="入力CSVのヘッダー文字列がテンプレートと一致していません",
            )
        return mapping
