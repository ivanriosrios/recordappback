"""Tests del lifecycle admin de Subscription (sync helpers)."""
from datetime import datetime, timedelta

from tests.conftest import make_business

from app.models.subscription import Subscription, SubscriptionStatus
from app.services.subscription import (
    admin_grant_free_month,
    admin_reactivate,
    admin_suspend,
)


def _make_sub(session, biz, status=SubscriptionStatus.TRIALING, current_period_end=None):
    sub = Subscription(
        business_id=biz.id,
        status=status,
        plan_name="Pro",
        price_usd=12,
        currency="USD",
        current_period_end=current_period_end,
    )
    session.add(sub)
    session.flush()
    return sub


def test_grant_free_extends_period(db_session):
    biz = make_business(db_session)
    sub = _make_sub(db_session, biz, status=SubscriptionStatus.CANCELED)
    db_session.commit()
    admin_grant_free_month(db_session, sub, months=2)
    db_session.commit()
    assert sub.granted_free_months == 2
    assert sub.status == SubscriptionStatus.FREE
    assert sub.current_period_end > datetime.utcnow() + timedelta(days=50)


def test_suspend_marks_canceled(db_session):
    biz = make_business(db_session)
    sub = _make_sub(db_session, biz, status=SubscriptionStatus.ACTIVE)
    db_session.commit()
    admin_suspend(db_session, sub)
    db_session.commit()
    assert sub.status == SubscriptionStatus.CANCELED
    assert sub.canceled_at is not None


def test_reactivate_canceled_goes_to_trialing(db_session):
    biz = make_business(db_session)
    sub = _make_sub(db_session, biz, status=SubscriptionStatus.CANCELED)
    db_session.commit()
    admin_reactivate(db_session, sub)
    db_session.commit()
    assert sub.status == SubscriptionStatus.TRIALING
    assert sub.canceled_at is None
    assert sub.trial_ends_at and sub.trial_ends_at > datetime.utcnow()


def test_reactivate_with_granted_months_goes_to_free(db_session):
    biz = make_business(db_session)
    sub = _make_sub(
        db_session,
        biz,
        status=SubscriptionStatus.PAST_DUE,
        current_period_end=datetime.utcnow() + timedelta(days=20),
    )
    sub.granted_free_months = 1
    db_session.commit()
    admin_reactivate(db_session, sub)
    db_session.commit()
    assert sub.status == SubscriptionStatus.FREE


def test_has_access_property(db_session):
    biz = make_business(db_session)
    future = datetime.utcnow() + timedelta(days=5)
    past = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    s1 = _make_sub(db_session, biz, status=SubscriptionStatus.ACTIVE, current_period_end=future)
    assert s1.has_access is True

    s1.current_period_end = past
    assert s1.has_access is False

    s1.status = SubscriptionStatus.CANCELED
    assert s1.has_access is False
