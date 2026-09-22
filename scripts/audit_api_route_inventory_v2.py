from __future__ import annotations

from collections import Counter

from app.main import app


HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
    "trace",
}


def group_for(path: str) -> str:
    if path == "/":
        return "root"

    if path == "/api/v1/health":
        return "health"

    prefix = "/api/v1/"

    if path.startswith(prefix):
        rest = path[len(prefix):]
        return rest.split("/", 1)[0] or "api"

    return "other"


def main() -> None:
    schema = app.openapi()
    routes: list[tuple[str, str, str]] = []

    for path, path_item in schema.get("paths", {}).items():
        for method in path_item:
            method_lower = method.lower()

            if method_lower not in HTTP_METHODS:
                continue

            routes.append(
                (
                    group_for(path),
                    method_upper := method_lower.upper(),
                    path,
                )
            )

    routes.sort(
        key=lambda item: (
            item[0],
            item[2],
            item[1],
        )
    )

    counts = Counter(
        group
        for group, _, _ in routes
    )

    api_v1_count = sum(
        1
        for _, _, path in routes
        if path.startswith("/api/v1/")
    )

    print()
    print("=" * 88)
    print("SMART STUDY ASSISTANT - API ROUTE INVENTORY V2")
    print("=" * 88)
    print(f"Application routes total : {len(routes)}")
    print(f"/api/v1 routes total     : {api_v1_count}")
    print(f"Non-/api/v1 routes       : {len(routes) - api_v1_count}")
    print()

    print("Route groups:")

    for group in sorted(counts):
        print(f"  {group:<18} {counts[group]:>3}")

    print()
    print("All application routes:")

    for group, method, path in routes:
        print(
            f"  [{group:<16}] "
            f"{method:<7} {path}"
        )

    expected_groups = {
        "health",
        "auth",
        "users",
        "subjects",
        "documents",
        "chat",
        "quizzes",
        "flashcards",
        "study-plans",
        "analytics",
        "gamification",
        "community",
        "exports",
        "notifications",
    }

    missing = sorted(
        expected_groups - set(counts)
    )

    print()

    if missing:
        print(
            "Result: FAIL - missing groups: "
            + ", ".join(missing)
        )
        raise SystemExit(1)

    print("Result: PASS")
    print("=" * 88)


if __name__ == "__main__":
    main()
