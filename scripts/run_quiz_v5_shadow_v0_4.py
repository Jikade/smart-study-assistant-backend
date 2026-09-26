from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.quiz_v5.shadow import (
    SSA_QV5_SHADOW_VERSION,
    list_ready_documents,
    report_as_dict,
    shadow_documents,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Quiz V5 shadow runner. "
            "No Quiz rows are created."
        )
    )

    parser.add_argument(
        "--list-ready",
        action="store_true",
    )
    parser.add_argument(
        "--document-id",
        dest="document_ids",
        action="append",
        type=int,
        default=[],
    )
    parser.add_argument(
        "--owner-id",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--subject-id",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--target",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--subject-family",
        default="general",
    )
    parser.add_argument(
        "--max-per-section",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
    )

    return parser


def _print_ready(rows) -> None:
    print()
    print("=" * 118)
    print(
        "QUIZ V5 READY DOCUMENT INVENTORY — "
        f"{SSA_QV5_SHADOW_VERSION}"
    )
    print("=" * 118)

    if not rows:
        print(
            "No READY documents matched the filters."
        )
        return

    print(
        f"{'DOC':>5}  "
        f"{'OWNER':>5}  "
        f"{'SUBJECT':>7}  "
        f"{'CHUNKS':>6}  "
        f"{'SECTIONED':>9}  "
        f"{'CHARS':>8}  "
        "NAME / SUBJECT"
    )

    for row in rows:
        label = row.original_name
        if row.subject_name:
            label += " / " + row.subject_name

        print(
            f"{row.document_id:>5}  "
            f"{row.owner_id:>5}  "
            f"{str(row.subject_id or '-'):>7}  "
            f"{row.active_chunks:>6}  "
            f"{row.chunks_with_section:>9}  "
            f"{row.active_chars:>8}  "
            f"{label}"
        )


def _print_report(report) -> None:
    print()
    print("=" * 118)
    print(
        "QUIZ V5 REAL-DOCUMENT SHADOW REPORT — "
        f"{report.version}"
    )
    print("=" * 118)

    print(
        f"Documents                    : "
        f"{list(report.document_ids)}"
    )
    print(
        f"Target questions             : "
        f"{report.target}"
    )
    print(
        f"Active chunks                : "
        f"{report.chunk_count}"
    )
    print(
        f"Source characters            : "
        f"{report.source_chars}"
    )
    print(
        f"Knowledge objects            : "
        f"{report.knowledge_count}"
    )
    print(
        f"Knowledge / 1000 chars       : "
        f"{report.extraction_coverage_per_1000_chars}"
    )
    print(
        f"Blueprint candidates         : "
        f"{report.blueprint_count}"
    )
    print(
        f"Validated final questions    : "
        f"{report.final_question_count}/{report.target}"
    )
    print(
        f"Exact target                 : "
        f"{report.exact}"
    )
    print(
        f"Replacement iterations       : "
        f"{report.replacement_iterations}"
    )
    print(
        f"Structured distractors       : "
        f"{report.structured_fallback_count}"
    )
    print(
        f"Rejected blueprint IDs       : "
        f"{list(report.rejected_blueprint_ids)}"
    )
    print(
        f"Knowledge by kind            : "
        f"{report.knowledge_by_kind}"
    )
    print(
        f"Blueprints by type           : "
        f"{report.blueprints_by_type}"
    )

    print()
    print("-" * 118)
    print("FINAL SHADOW QUESTIONS")
    print("-" * 118)

    if not report.questions:
        print(
            "No fully validated questions were produced."
        )

    for question in report.questions:
        print()
        print(
            f"Q{question.order}. "
            f"[{question.blueprint_type}] "
            f"{question.stem}"
        )
        print(
            f"    CORRECT : "
            f"{question.correct_answer}"
        )

        for index, distractor in enumerate(
            question.distractors,
            start=1,
        ):
            origin = (
                question.distractor_origins[index - 1]
                if index - 1
                < len(question.distractor_origins)
                else "unknown"
            )

            print(
                f"    D{index:<2}     : "
                f"{distractor} [{origin}]"
            )

        print(
            "    SOURCE  : "
            f"doc={question.source_document_id} "
            f"chunk={question.source_chunk_id} "
            f"section={question.source_section_id}"
        )
        print(
            f"    SCORES  : "
            f"quality={question.quality_score:.2f} "
            f"validation={question.validation_score:.2f}"
        )
        print(
            f"    EVIDENCE: "
            f"{question.evidence}"
        )

    print()
    print("-" * 118)

    if report.exact:
        print(
            "SHADOW RESULT: EXACT TARGET REACHED"
        )
    else:
        print(
            "SHADOW RESULT: PARTIAL — "
            "this is diagnostic, not an exception."
        )

    print("-" * 118)


def main() -> None:
    args = _parser().parse_args()
    db = SessionLocal()

    try:
        if args.list_ready:
            rows = list_ready_documents(
                db,
                owner_id=args.owner_id,
                subject_id=args.subject_id,
            )
            _print_ready(rows)
            return

        if not args.document_ids:
            raise SystemExit(
                "Use --list-ready first, or provide "
                "one or more --document-id values."
            )

        report = shadow_documents(
            db,
            document_ids=args.document_ids,
            target=args.target,
            owner_id=args.owner_id,
            subject_family=args.subject_family,
            max_per_section=args.max_per_section,
        )

        _print_report(report)

        if args.json_out is not None:
            args.json_out.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            args.json_out.write_text(
                json.dumps(
                    report_as_dict(report),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(
                f"JSON report written: {args.json_out}"
            )
    finally:
        # Explicit read-only exit path.
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
