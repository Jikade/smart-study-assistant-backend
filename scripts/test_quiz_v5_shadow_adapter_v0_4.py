from __future__ import annotations

from app.services.quiz_v5 import ChunkInput
from app.services.quiz_v5.shadow import (
    SSA_QV5_SHADOW_VERSION,
    report_as_dict,
    shadow_from_chunks,
)


def must(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    print()
    print("=" * 108)
    print(
        "QUIZ V5 REAL-DOCUMENT ADAPTER + "
        "SHADOW PIPELINE V0.4 REGRESSION"
    )
    print("=" * 108)

    chunks = [
        ChunkInput(
            document_id=10,
            chunk_id=1001,
            section_id=101,
            text=(
                "Chiến thắng Bạch Đằng diễn ra năm 938. "
                "Cách mạng tháng Tám diễn ra năm 1945. "
                "Chiến dịch Điện Biên Phủ diễn ra năm 1954. "
                "Chiến dịch Hồ Chí Minh diễn ra năm 1975."
            ),
        ),
        ChunkInput(
            document_id=11,
            chunk_id=1101,
            section_id=111,
            text=(
                "Phân công lao động xã hội là sự phân chia "
                "lao động xã hội thành các ngành và nghề khác nhau. "
                "Thước đo giá trị dùng để đo lường và biểu hiện "
                "giá trị hàng hóa. "
                "Phương tiện lưu thông dùng để làm môi giới "
                "trong trao đổi hàng hóa. "
                "Phương tiện thanh toán dùng để thực hiện "
                "các nghĩa vụ thanh toán."
            ),
        ),
        ChunkInput(
            document_id=12,
            chunk_id=1201,
            section_id=121,
            text=(
                "Đỉnh Phan Xi Păng có độ cao 3143 m.\n"
                "P = A/t\n"
                "C = 2πr"
            ),
        ),
    ]

    report = shadow_from_chunks(
        chunks,
        target=5,
        subject_family="mixed",
        max_per_section=2,
    )

    must(
        "Shadow version exposed",
        SSA_QV5_SHADOW_VERSION
        == "SSA-QV5-SHADOW-V0.4",
    )

    must(
        "Shadow report preserves document IDs",
        report.document_ids == (10, 11, 12),
    )

    must(
        "Shadow report counts source chunks",
        report.chunk_count == 3,
    )

    must(
        "Shadow pipeline extracts knowledge",
        report.knowledge_count > 0,
    )

    must(
        "Shadow pipeline plans candidates",
        report.blueprint_count > 0,
    )

    must(
        "Shadow produces only validated questions",
        0 < report.final_question_count <= report.target,
    )

    must(
        "Exact flag matches final count",
        report.exact
        == (
            report.final_question_count
            == report.target
        ),
    )

    must(
        "Every final question retains chunk lineage",
        all(
            question.source_chunk_id
            in {1001, 1101, 1201}
            for question in report.questions
        ),
    )

    must(
        "Every final question retains evidence",
        all(
            question.evidence
            for question in report.questions
        ),
    )

    plain = report_as_dict(report)

    must(
        "Report serializes to plain dict",
        plain["version"]
        == SSA_QV5_SHADOW_VERSION,
    )

    must(
        "Report exposes extraction coverage",
        report.extraction_coverage_per_1000_chars
        > 0.0,
    )

    must(
        "Shadow report includes diagnostic distributions",
        bool(report.knowledge_by_kind)
        and bool(report.blueprints_by_type),
    )

    print()
    print(
        f"Knowledge objects     : "
        f"{report.knowledge_count}"
    )
    print(
        f"Blueprint candidates  : "
        f"{report.blueprint_count}"
    )
    print(
        f"Final questions       : "
        f"{report.final_question_count}/{report.target}"
    )
    print(
        f"Exact target          : "
        f"{report.exact}"
    )
    print(
        f"Knowledge kinds       : "
        f"{report.knowledge_by_kind}"
    )
    print(
        f"Blueprint types       : "
        f"{report.blueprints_by_type}"
    )

    print("-" * 108)
    print("RESULT: PASS")
    print("=" * 108)


if __name__ == "__main__":
    main()
