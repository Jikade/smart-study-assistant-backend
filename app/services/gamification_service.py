from __future__ import annotations

import math
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Badge,
    DailyLearningStat,
    FlashcardReview,
    QuizAttempt,
    UserBadge,
    UserGamification,
    XpTransaction,
)


# =========================================================
# GAMIFICATION STATE
# =========================================================


def ensure_gamification(
    db: Session,
    user_id: int,
) -> UserGamification:
    """
    Ensure that the user has one gamification row.
    """

    row = db.get(
        UserGamification,
        user_id,
    )

    if row is None:
        row = UserGamification(
            user_id=user_id,
            xp_total=0,
            level_no=1,
            current_streak=0,
            longest_streak=0,
        )

        db.add(row)
        db.flush()

    return row


# =========================================================
# STREAK
# =========================================================


def touch_streak(
    row: UserGamification,
) -> None:
    """
    Update the user's learning streak.
    """

    today = date.today()

    # Already counted today.
    if row.last_study_date == today:
        return

    yesterday = (
        today
        - timedelta(days=1)
    )

    if row.last_study_date == yesterday:
        row.current_streak = (
            int(row.current_streak or 0)
            + 1
        )

    else:
        row.current_streak = 1

    row.longest_streak = max(
        int(row.longest_streak or 0),
        int(row.current_streak or 0),
    )

    row.last_study_date = today


# =========================================================
# DAILY LEARNING STAT
# =========================================================


def get_or_create_daily_stat(
    db: Session,
    user_id: int,
    activity_date: date | None = None,
) -> DailyLearningStat:
    """
    Return exactly one DailyLearningStat for
    (user_id, activity_date).

    Safe when Session.autoflush is disabled:
    pending ORM objects are checked before querying
    the database, preventing duplicate rows for the
    composite primary key.
    """

    target_date = (
        activity_date
        or date.today()
    )

    # 1) Reuse a matching pending object in this Session.
    for pending in db.new:
        if not isinstance(
            pending,
            DailyLearningStat,
        ):
            continue

        if (
            int(pending.user_id) == int(user_id)
            and pending.activity_date == target_date
        ):
            return pending

    # 2) Query an already-persisted row explicitly by columns.
    stat = db.scalar(
        select(DailyLearningStat)
        .where(
            DailyLearningStat.user_id
            == user_id,
            DailyLearningStat.activity_date
            == target_date,
        )
    )

    if stat is not None:
        return stat

    # 3) Create one canonical row and flush immediately.
    stat = DailyLearningStat(
        user_id=user_id,
        activity_date=target_date,
    )

    db.add(stat)
    db.flush()

    return stat

def add_xp(
    db: Session,
    user_id: int,
    amount: int,
    source_type: str,
    source_id: int | None = None,
    description: str | None = None,
) -> UserGamification:
    """
    Add XP and update:
    - total XP
    - level
    - streak
    - XP transaction
    - daily XP statistic
    """

    row = ensure_gamification(
        db,
        user_id,
    )

    row.xp_total = max(
        0,
        int(row.xp_total or 0)
        + int(amount),
    )

    row.level_no = max(
        1,
        int(
            math.sqrt(
                row.xp_total / 100
            )
        )
        + 1,
    )

    touch_streak(row)

    # -----------------------------------------------------
    # XP transaction
    # -----------------------------------------------------

    db.add(
        XpTransaction(
            user_id=user_id,
            amount=amount,
            source_type=source_type,
            source_id=source_id,
            description=description,
        )
    )

    # -----------------------------------------------------
    # Daily stat
    # -----------------------------------------------------

    stat = get_or_create_daily_stat(
        db,
        user_id,
    )

    stat.xp_earned = (
        int(stat.xp_earned or 0)
        + int(amount)
    )

    return row


# =========================================================
# BADGES
# =========================================================


def grant_badge_if_exists(
    db: Session,
    user_id: int,
    code: str,
) -> bool:
    """
    Grant a badge if:
    - badge exists
    - badge is active
    - user does not already own it
    """

    badge = db.scalar(
        select(Badge)
        .where(
            Badge.code == code,
            Badge.is_active.is_(True),
        )
    )

    if badge is None:
        return False

    # Do NOT use:
    #
    # db.get(UserBadge, (user_id, badge.id))
    #
    # because UserBadge may use a composite primary key
    # whose column order can differ.
    existing_user_badge = db.scalar(
        select(UserBadge)
        .where(
            UserBadge.user_id
            == user_id,
            UserBadge.badge_id
            == badge.id,
        )
    )

    if existing_user_badge is not None:
        return False

    db.add(
        UserBadge(
            user_id=user_id,
            badge_id=badge.id,
            metadata_={},
        )
    )

    # Flush the badge assignment first so another
    # operation in this transaction sees it.
    db.flush()

    if badge.xp_reward:
        add_xp(
            db,
            user_id,
            int(badge.xp_reward),
            "BADGE",
            badge.id,
            f"Badge: {badge.code}",
        )

    return True


# =========================================================
# BADGE EVALUATION
# =========================================================


def evaluate_badges(
    db: Session,
    user_id: int,
    *,
    quiz_percentage: float | None = None,
) -> None:
    """
    Evaluate currently supported achievement rules.
    """

    # -----------------------------------------------------
    # FIRST QUIZ
    # -----------------------------------------------------

    quizzes = (
        db.scalar(
            select(
                func.count(
                    QuizAttempt.id
                )
            )
            .where(
                QuizAttempt.user_id
                == user_id,
                QuizAttempt.status
                == "SUBMITTED",
            )
        )
        or 0
    )

    if quizzes >= 1:
        grant_badge_if_exists(
            db,
            user_id,
            "FIRST_QUIZ",
        )

    # -----------------------------------------------------
    # PERFECT SCORE
    # -----------------------------------------------------

    if (
        quiz_percentage is not None
        and quiz_percentage >= 100
    ):
        grant_badge_if_exists(
            db,
            user_id,
            "PERFECT_SCORE",
        )

    # -----------------------------------------------------
    # STREAK 7
    # -----------------------------------------------------

    gam = ensure_gamification(
        db,
        user_id,
    )

    if (
        int(gam.current_streak or 0)
        >= 7
    ):
        grant_badge_if_exists(
            db,
            user_id,
            "STREAK_7",
        )

    # -----------------------------------------------------
    # FLASHCARD 100
    # -----------------------------------------------------

    reviews = (
        db.scalar(
            select(
                func.count(
                    FlashcardReview.id
                )
            )
            .where(
                FlashcardReview.user_id
                == user_id
            )
        )
        or 0
    )

    if reviews >= 100:
        grant_badge_if_exists(
            db,
            user_id,
            "FLASHCARD_100",
        )