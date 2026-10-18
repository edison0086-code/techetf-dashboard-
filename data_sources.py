"""Public market data retrieval, with explicitly attributable sources.

Yahoo Finance chart and CNN Dataviz URLs are public *undocumented* endpoints.
They may fail or change; failure MUST display missing data rather than a value.
No live-trading or brokerage integration is included.
"""
from __future__ import annotations
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import Optional
import requests
import pandas as pd

HEADERS = {
    'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept':'application/json, text/plain, */*',
    'Accept-Language':'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
}
CNN = 'https://production.dataviz.cnn.io/index/fearandgreed/graphdata'
FALLBACK = 'https://fearandgreedgraph.com/api/fear-greed'


def _get_json(url: str, timeout: int = 14, headers: Optional[dict] = None):
    response = requests.get(url,timeout=timeout,headers=headers or HEADERS)
    response.raise_for_status()
    return response.json()


def get_price_history(symbol: str):
    """Returns OHLC + Adj Close indexed by exchange-local calendar date."""
    problems = []
    for host in ('query1.finance.yahoo.com','query2.finance.yahoo.com'):
        try:
            url = f'https://{host}/v8/finance/chart/{symbol}'
            payload = _get_json(url + '?range=2y&interval=1d&events=div%2Csplits', timeout=16)
            chart = payload.get('chart') or {}
            if chart.get('error'):
                raise RuntimeError(str(chart['error']))
            result = (chart.get('result') or [None])[0]
            if not result: raise RuntimeError('查無 chart.result')
            timestamps = result.get('timestamp') or []
            q = ((result.get('indicators') or {}).get('quote') or [None])[0]
            if not q or not timestamps: raise RuntimeError('無交易日或 OHLC')
            adj = ((result.get('indicators') or {}).get('adjclose') or [{}])[0].get('adjclose',[])
            df = pd.DataFrame({'Open':q['open'],'High':q['high'],
                               'Low':q['low'],'Close':q['close']},
                              index=pd.to_datetime(timestamps,unit='s',utc=True))
            if len(adj) == len(df): df['Adj Close'] = adj
            exchange_tz = 'Asia/Taipei' if symbol.endswith('.TW') else 'America/New_York'
            df.index = pd.DatetimeIndex(df.index.tz_convert(exchange_tz).date)
            df = df[~df.index.duplicated(keep='last')].sort_index()
            if df.dropna(subset=['Close']).shape[0] < 50:
                raise RuntimeError('資料少於 50 根日 K')
            return df, f'Yahoo Finance chart ({host})', None
        except Exception as exc:
            problems.append(f'{host}: {str(exc)[:160]}')
    return pd.DataFrame(), 'Yahoo Finance', '；'.join(problems)


def _from_cnn():
    h = HEADERS | {
        'Referer':'https://edition.cnn.com/markets/fear-and-greed',
        'Origin':'https://edition.cnn.com',
    }
    root = _get_json(CNN,headers=h)
    fg = root['fear_and_greed']
    score = float(fg['score'])
    if not 0 <= score <= 100: raise ValueError('CNN 分數超出正常範圍')
    stamp = fg.get('timestamp')
    if isinstance(stamp,(float,int)):
        dt = datetime.fromtimestamp(stamp / (1000 if stamp > 1e11 else 1),tz=timezone.utc)
    elif isinstance(stamp,str):
        dt = datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    else:
        raise ValueError('CNN 未回傳資料時間，不使用無日期的訊號')
    market_date = dt.astimezone(ZoneInfo('America/New_York')).date()
    return {
      'score':score,'previous':float(fg['previous_close']) if fg.get('previous_close') is not None else None,
      'date':market_date,'timestamp':dt.isoformat(),
      'rating':str(fg.get('rating','')),
      'source':'CNN Fear & Greed','url':CNN,
      'warning':None,
    }


def _from_fallback():
    root = _get_json(FALLBACK)
    dates = root.get('dates') or []
    values = root.get('values') or []
    if not dates or not values or len(dates)!=len(values):
        raise ValueError('第三方 API 返回格式不符')
    order = sorted(zip(dates,values),key=lambda x:x[0])
    dateval, scoreval = order[-1]
    score = float(scoreval)
    if not 0 <= score <= 100: raise ValueError('第三方分數範圍錯誤')
    prev = float(order[-2][1]) if len(order)>=2 else None
    return {
      'score':score,'previous':prev,'date':date.fromisoformat(dateval[:10]),
      'timestamp':str(root.get('asOf') or dateval),
      'rating':'','source':'Fear & Greed Graph（第三方備援）',
      'url':FALLBACK,
      'warning':'CNN 原站無法取得；目前使用第三方整理數據，務必再與 CNN 核對。',
    }


def get_fear_greed():
    problems = []
    for fetcher in (_from_cnn,_from_fallback):
        try: return fetcher(), None
        except Exception as exc: problems.append(f'{fetcher.__name__}: {str(exc)[:200]}')
    return None, '；'.join(problems)
