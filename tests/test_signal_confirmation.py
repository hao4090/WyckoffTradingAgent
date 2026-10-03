from core.signal_confirmation import (
    PendingPool,
    check_confirmation,
    run_confirmation_cycle,
)


def _make_df(dates, closes, volumes=None):
    if volumes is None:
        volumes = [1000000] * len(dates)
    import pandas as pd

    # Full OHLCV for build_today_ohlcv
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    opens = closes  # flat open for simplicity
    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


class TestSurvivedState:
    def test_sos_day1_survived(self):
        snap = dict(snap_low=10.0, snap_close=10.5, snap_volume=1000000)
        today = dict(open=10.5, high=11.0, low=10.4, close=10.9, volume=1200000, ma20=10.2, ma50=9.8)
        status, _ = check_confirmation("sos", snap, today, days_elapsed=1)
        assert status == "survived", f"expected survived, got {status}"

    def test_sos_day0_pending(self):
        snap = dict(snap_low=10.0, snap_close=10.5, snap_volume=1000000)
        today = dict(open=10.5, high=11.0, low=10.4, close=10.9, volume=1200000, ma20=10.2, ma50=9.8)
        status, _ = check_confirmation("sos", snap, today, days_elapsed=0)
        assert status == "pending", f"expected pending, got {status}"

    def test_sos_ttl_expired(self):
        """SOS TTL=2: days_elapsed=3 超过 TTL，应 expired。"""
        snap = dict(snap_low=10.0, snap_close=10.5, snap_volume=1000000)
        today = dict(open=10.5, high=11.0, low=10.4, close=10.9, volume=1200000, ma20=10.2, ma50=9.8)
        status, _ = check_confirmation("sos", snap, today, days_elapsed=3)
        assert status == "expired", f"expected expired, got {status}"

    def test_sos_confirmed(self):
        snap = dict(snap_low=10.0, snap_close=10.5, snap_volume=1000000)
        today = dict(open=10.3, high=10.6, low=10.0, close=10.55, volume=700000, ma20=10.2, ma50=9.8)
        status, _ = check_confirmation("sos", snap, today, days_elapsed=2)
        assert status == "confirmed", f"expected confirmed, got {status}"


class TestRunConfirmationCycle:
    def test_survived_not_in_confirmed_symbols(self):
        # Day 2026-01-05: close=10.9 (>= 97% of snap_close=10.5) BUT volume=900000 (> 80% of snap_vol=1000000)
        # So the "缩量" condition fails, should return survived
        df = _make_df(["2026-01-01", "2026-01-02", "2026-01-05"], [10.0, 10.5, 10.9], [1000000, 1200000, 900000])
        signals = [
            dict(
                id=1,
                code="000001",
                signal_type="sos",
                signal_date="2026-01-01",
                status="pending",
                days_elapsed=1,
                signal_score=1.0,
                snap_low=10.0,
                snap_close=10.5,
                snap_volume=1000000,
                name="TEST",
            )
        ]
        updates, confirmed = run_confirmation_cycle(signals, {"000001": df}, "2026-01-05")
        assert len(confirmed) == 0, "survived should not be in confirmed_symbols"
        assert any(u["status"] == "survived" for u in updates), "should have survived update"


class TestPendingPool:
    def test_survived_stays_in_pool(self):
        pool = PendingPool()
        # Tick 1: 2026-01-05, days_elapsed=1, survives (TTL=2, 1 > 2 is False)
        # Tick 2: 2026-01-06, days_elapsed=2, survives (TTL=2, 2 > 2 is False)
        # Tick 3: 2026-01-07, days_elapsed=3, expires (TTL=2, 3 > 2 is True)
        df_map = {
            "000001": _make_df(
                ["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"],
                [10.0, 10.5, 10.9, 10.9, 10.9],
                [1000000, 1200000, 800000, 800000, 800000],
            )
        }
        pool.write("2026-01-01", {"sos": [("000001", 1.0)]}, df_map)
        confirmed1 = pool.tick(df_map, "2026-01-05")
        assert len(confirmed1) == 0, "tick 1 should not confirm"
        assert len(pool._pool) == 1, "survived should stay in pool"
        confirmed2 = pool.tick(df_map, "2026-01-06")
        assert len(confirmed2) == 0, "tick 2 should not confirm"
        assert len(pool._pool) == 1, "survived should still stay"
        confirmed3 = pool.tick(df_map, "2026-01-07")
        assert len(confirmed3) == 0, "tick 3 should expire"
        assert len(pool._pool) == 0, "expired signal should be removed"
