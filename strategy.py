"""Pure, testable signal calculations. No trading orders are sent."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import math
import pandas as pd

US_TZ = ZoneInfo('America/New_York')
TW_TZ = ZoneInfo('Asia/Taipei')


@dataclass
class Snapshot:
    symbol: str
    display: str
    price: float | None
    currency: str
    last_session: date | None
    high_52w: float | None
    drawdown_pct: float | None
    drawdown_adjusted: bool
    weekly_j: float | None
    prior_weekly_j: float | None
    weekly_close_date: date | None
    daily: pd.DataFrame | None
    error: str | None = None


def _j_values(weekly: pd.DataFrame, period: int = 9) -> pd.Series:
    """KDJ: RSV(9-week), K = 2/3 prev K + 1/3 RSV, D likewise, J=3K-2D.

    K/D initial=50 at the first fully-defined RSV. Differences from charting
    vendors can arise from initialization, corporate action adjustments, holidays.
    """
    low9 = weekly['Low'].rolling(period, min_periods=period).min()
    high9 = weekly['High'].rolling(period, min_periods=period).max()
    span = high9 - low9
    rsv = (100.0 * (weekly['Close'] - low9) / span.where(span != 0)).clip(0, 100)
    k, d = 50.0, 50.0
    output = []
    for x in rsv:
        if pd.isna(x):
            output.append(float('nan'))
            continue
        k = (2 * k + float(x)) / 3
        d = (2 * d + k) / 3
        output.append(3 * k - 2 * d)
    return pd.Series(output, index=weekly.index, dtype=float)


def most_recent_complete_week_end(now: datetime, exchange: str) -> date:
    tz = TW_TZ if exchange == 'TW' else US_TZ
    local = now.astimezone(tz)
    friday = local.date() - timedelta(days=(local.weekday() - 4) % 7)
    market_close = time(14, 0) if exchange == 'TW' else time(16, 30)
    if local.weekday() == 4 and local.time() < market_close:
        friday -= timedelta(days=7)
    return friday


def build_snapshot(symbol: str, daily: pd.DataFrame, now: datetime) -> Snapshot:
    exchange = 'TW' if symbol == '00935.TW' else 'US'
    currency = 'TWD' if exchange == 'TW' else 'USD'
    label = symbol.replace('.TW', '')
    if daily is None or daily.empty:
        return Snapshot(symbol, label, None, currency, None, None, None, False,
                        None, None, None, daily, '無歷史價格資料')
    df = daily.sort_index().copy()
    df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
    if df.empty:
        return Snapshot(symbol, label, None, currency, None, None, None, False,
                        None, None, None, daily, 'OHLC 資料不完整')
    last_date = df.index[-1].date()
    latest_price = float(df['Close'].iloc[-1])
    adjusted = ('Adj Close' in df.columns and df['Adj Close'].notna().sum() >= 200
                and pd.notna(df['Adj Close'].iloc[-1]))
    source_column = 'Adj Close' if adjusted else 'Close'
    price_series = df[source_column].dropna()
    cutoff = last_date - timedelta(days=364)
    trailing = price_series[price_series.index.date >= cutoff]
    peak = float(trailing.max()) if len(trailing) else None
    close_for_drawdown = float(price_series.iloc[-1]) if len(price_series) else None
    drawdown = 100 * (close_for_drawdown / peak - 1) if peak and close_for_drawdown else None

    # A completed trading week includes the last available exchange session of
    # that week, but the current trading week is excluded until its Fri close.
    end_of_week = most_recent_complete_week_end(now, exchange)
    d = df[df.index.date <= end_of_week]
    weekly = d.resample('W-FRI').agg({
        'Open':'first','High':'max','Low':'min','Close':'last'
    }).dropna()
    j = _j_values(weekly).dropna()
    j_now = float(j.iloc[-1]) if len(j) else None
    j_prev = float(j.iloc[-2]) if len(j) >= 2 else None
    w_date = weekly.index[-1].date() if len(weekly) else None
    return Snapshot(symbol, label, latest_price, currency, last_date, peak,
                    drawdown, bool(adjusted), j_now, j_prev, w_date, df)


def age_days(last_date: date | None, now: datetime) -> int | None:
    return (now.astimezone(TW_TZ).date() - last_date).days if last_date else None


def first_stage(snap: Snapshot, fear: float | None, now: datetime,
                fear_date: date | None = None, allowed_age_days: int = 5) -> dict:
    age = age_days(snap.last_session, now)
    fear_age = age_days(fear_date, now) if fear_date else None
    price_fresh = age is not None and 0 <= age <= allowed_age_days
    fear_fresh = fear is not None and fear_age is not None and 0 <= fear_age <= allowed_age_days
    j_known = (snap.weekly_j is not None and snap.weekly_close_date is not None
               and age_days(snap.weekly_close_date,now) is not None
               and 0 <= age_days(snap.weekly_close_date,now) <= 10)
    price_condition = price_fresh and snap.drawdown_pct is not None and snap.drawdown_pct <= -10
    sentiment_condition = price_fresh and fear_fresh and j_known and fear < 25 and snap.weekly_j < 25
    active = bool(price_condition or sentiment_condition)
    reasons = []
    if price_condition: reasons.append('近 52 週調整後收盤高點回檔 ≥10%' if snap.drawdown_adjusted else '近 52 週原始收盤高點回檔 ≥10%（未調整配息）')
    if sentiment_condition: reasons.append('CNN <25 且完整週線 J <25')
    if active:
        status = '符合第一批條件'
    elif not price_fresh:
        status = '待確認：價格資料過期／缺漏'
    elif not fear_fresh or not j_known:
        status = '未見價格觸發；情緒條件待確認'
    else:
        status = '目前未符合'
    return {'triggered':active,'status':status,'reasons':reasons,
            'price_fresh':price_fresh,'fear_fresh':fear_fresh,'j_known':j_known,
            'age_days':age,'fear_age':fear_age}


def next_stage(qqqm: Snapshot | None, fear: float | None, previous_fear: float | None,
               now: datetime, stage1_date: date | None, stage1_qqqm_price: float | None,
               fear_date: date | None) -> dict:
    """Only inspect stage 2/3 after user recorded an actual stage-1 purchase.

    Entry price baseline here is QQQM. Per-ETF relative fills require a separate
    trade ledger and should not be inferred from other ETF signals.
    """
    if not stage1_date or not stage1_qqqm_price or stage1_qqqm_price <= 0:
        return {'ready':False,'stage2':False,'stage3':False,
                'note':'第二／第三批需先記錄第一批實際成交日期及 QQQM 成交參考價。'}
    if qqqm is None or qqqm.price is None:
        return {'ready':False,'stage2':False,'stage3':False, 'note':'QQQM 價格無法取得。'}
    weeks_elapsed = qqqm.weekly_close_date is not None and qqqm.weekly_close_date > stage1_date
    age = age_days(qqqm.last_session,now)
    quote_fresh = age is not None and 0 <= age <= 5
    fear_age = age_days(fear_date,now)
    sentiment_fresh = fear is not None and fear_age is not None and 0 <= fear_age <= 5
    j = qqqm.weekly_j if qqqm.weekly_close_date and 0 <= age_days(qqqm.weekly_close_date,now) <= 10 else None
    drop_pct = 100 * (qqqm.price / stage1_qqqm_price - 1) if quote_fresh else None
    deep_drop = drop_pct is not None and drop_pct <= -8
    deep_fear = sentiment_fresh and fear < 15 and j is not None and j < 15
    stage2 = bool(weeks_elapsed and (deep_drop or deep_fear))
    j_reversal = (quote_fresh and weeks_elapsed and qqqm.prior_weekly_j is not None and j is not None
                  and qqqm.prior_weekly_j <= 20 < j)
    fear_reversal = (sentiment_fresh and previous_fear is not None
                     and previous_fear <= 30 < fear)
    stage3 = bool(weeks_elapsed and (j_reversal or fear_reversal))
    reasons2 = []
    if deep_drop: reasons2.append('QQQM 相對第一批參考價再跌至少 8%')
    if deep_fear: reasons2.append('CNN <15 且 QQQM 週 J <15')
    reasons3 = []
    if j_reversal: reasons3.append('QQQM 完整週 J 從 ≤20 向上突破 20')
    if fear_reversal: reasons3.append('CNN 由 ≤30 向上突破 30')
    return {'ready':True,'stage2':stage2,'stage3':stage3,'weeks_elapsed':weeks_elapsed,
            'drop_since_entry':drop_pct,'reasons2':reasons2,'reasons3':reasons3,
            'note':'第二／第三批訊號可能互相接近，需依實際已執行批次決定下一步；不得重複使用同一批資金。'}


def portfolio_percentages(option: str) -> dict[str, float]:
    if option == '40／30／30': return {'QQQM':.40,'SMH':.30,'00935':.30}
    return {'QQQM':.50,'SMH':.25,'00935':.25}


def kdj_details(daily: pd.DataFrame, now: datetime, symbol: str) -> dict:
    """Daily J, partial-week J, completed-week J, consistent KDJ(9,3,3)."""
    if daily is None or len(daily) < 80:
        return {'daily_j':None,'partial_j':None,'complete_j':None,'daily_date':None,'completed_date':None}
    df=daily.sort_index().dropna(subset=['Open','High','Low','Close'])
    dj=_j_values(df).dropna()
    cutoff=most_recent_complete_week_end(now,'TW' if symbol.endswith('.TW') else 'US')
    weekly=df.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
    finished=weekly[weekly.index.date <= cutoff]
    finished_j=_j_values(finished).dropna()
    # one bar from current week as if closed at the latest daily close
    partial=_j_values(weekly).dropna()
    return {'daily_j':float(dj.iloc[-1]) if len(dj) else None,
            'partial_j':float(partial.iloc[-1]) if len(partial) else None,
            'complete_j':float(finished_j.iloc[-1]) if len(finished_j) else None,
            'daily_date':df.index[-1].date(),
            'completed_date':finished.index[-1].date() if len(finished) else None,
            'partial_is_complete':df.index[-1].date() <= cutoff}
