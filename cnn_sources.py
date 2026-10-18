"""Optional unofficial CNN page-data integration, with explicit freshness checks.
CNN does not offer a documented or availability-guaranteed public API.
Never synthesize or silently substitute index values.
"""
from datetime import datetime, timezone
import requests

CNN_PAGE = 'https://edition.cnn.com/markets/fear-and-greed'
CNN_ENDPOINT = 'https://production.dataviz.cnn.io/index/fearandgreed/graphdata'


def parse_cnn_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError('CNN 回傳的資料不是 JSON 物件')
    item = payload.get('fear_and_greed')
    if not isinstance(item, dict):
        raise ValueError('CNN 資料缺少 fear_and_greed')
    score = float(item['score'])
    if not (0 <= score <= 100):
        raise ValueError('CNN 指數超出 0～100')
    timestamp = item.get('timestamp')
    if not isinstance(timestamp,str) or not timestamp:
        raise ValueError('CNN 沒有有效資料時間')
    observed = datetime.fromisoformat(timestamp.replace('Z','+00:00'))
    if observed.tzinfo is None:
        raise ValueError('CNN 資料時間缺少時區')
    observed = observed.astimezone(timezone.utc)
    if observed > datetime.now(timezone.utc).replace(microsecond=0):
        raise ValueError('CNN 資料時間超過目前時間')
    def optional_score(name):
        value=item.get(name)
        try:
            number=float(value)
            return number if 0 <= number <= 100 else None
        except (TypeError,ValueError):
            return None
    return {'score':score,'rating':str(item.get('rating','')),
            'observed':observed,'previous_close':optional_score('previous_close'),
            'week_ago':optional_score('previous_1_week'),
            'month_ago':optional_score('previous_1_month'),
            'source':'CNN 網頁使用之未文件化資料端點','url':CNN_PAGE}


def fetch_cnn(timeout=10):
    """May be blocked; caller must display failure, not infer a value."""
    try:
        response=requests.get(CNN_ENDPOINT,timeout=timeout,headers={
            'Accept':'application/json',
            'Referer':CNN_PAGE,
            'User-Agent':'Mozilla/5.0 (compatible; Personal-ETF-Dashboard/2.1)'})
        response.raise_for_status()
        return parse_cnn_payload(response.json()),None
    except (requests.RequestException, ValueError,KeyError,TypeError,OverflowError) as exc:
        return None, f'{type(exc).__name__}: {str(exc)[:220]}'
