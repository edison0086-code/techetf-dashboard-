"""Tiingo (US), FinMind/TWSE (TW); no Yahoo Finance calls.
Returns daily RAW OHLC data. Latest = latest settled daily close (not real-time).
"""
from datetime import date, timedelta
import requests
import pandas as pd

S = requests.Session()
S.headers.update({'User-Agent':'personal-etf-monitor/2.0 (private research dashboard)','Accept':'application/json'})

class DataError(Exception): pass

def request_json(url, *, params=None):
    r = S.get(url, params=params, timeout=18)
    if r.status_code != 200:
        raise DataError(f'HTTP {r.status_code} ({url.split("/")[2]})')
    try: return r.json()
    except ValueError as e: raise DataError('來源非 JSON') from e

def normalize(frame, mapping, source):
    df = pd.DataFrame(frame)
    if df.empty: raise DataError(f'{source}: 沒有交易資料')
    needed = [mapping[x] for x in ('date','Open','High','Low','Close')]
    if any(x not in df.columns for x in needed): raise DataError(f'{source}: OHLC 欄位缺漏')
    out = pd.DataFrame({'Date':pd.to_datetime(df[mapping['date']],errors='coerce').dt.tz_localize(None).dt.normalize()})
    for k in ('Open','High','Low','Close'):
        out[k] = pd.to_numeric(df[mapping[k]], errors='coerce')
    out = out.dropna().set_index('Date').sort_index()
    out = out[~out.index.duplicated(keep='last')]
    out = out[(out[['Open','High','Low','Close']] > 0).all(axis=1)]
    if len(out) < 80: raise DataError(f'{source}: 日K只有 {len(out)} 根，不足計算可靠的週J')
    if (out['Low'] > out['High']).any(): raise DataError(f'{source}: 最高最低價不合理')
    return out

def massive_history(symbol, token):
    """Massive official daily aggregate bars; free Basic uses EOD US stocks."""
    if not token:
        raise DataError('尚未設定 MASSIVE_API_KEY（請到 Streamlit Secrets 設定）')
    end=date.today()
    start=end-timedelta(days=710)  # within free 2-year historical window
    url=(f'https://api.massive.com/v2/aggs/ticker/{symbol}/range/1/day/'
         f'{start.isoformat()}/{end.isoformat()}')
    root=request_json(url,params={'apiKey':token,'adjusted':'false','sort':'asc','limit':5000})
    if not isinstance(root,dict):
        raise DataError('Massive: 回傳格式不正確')
    if root.get('status') not in ('OK','DELAYED'):
        raise DataError('Massive: '+str(root.get('error') or root.get('message') or root.get('status'))[:130])
    records=root.get('results') or []
    if not records:
        raise DataError('Massive: 查無日 K 資料（請檢查股票代碼、免費方案權限）')
    rows=[]
    for row in records:
        try:
            # Daily aggregates are timestamped at midnight in US market timezone.
            session_date=pd.to_datetime(row['t'],unit='ms',utc=True).tz_convert('America/New_York').date()
            rows.append({'date':str(session_date),'open':row['o'],'high':row['h'],
                         'low':row['l'],'close':row['c']})
        except (KeyError,TypeError,ValueError,OverflowError):
            continue
    df=normalize(rows,{'date':'date','Open':'open','High':'high','Low':'low','Close':'close'},'Massive')
    return df,'Massive Stocks EOD（原始 OHLC）','https://massive.com/docs/rest/stocks/aggregates/custom-bars'

def finmind_history(token=''):
    params={'dataset':'TaiwanStockPrice','data_id':'00935','start_date':(date.today()-timedelta(days=900)).isoformat()}
    if token: params['token']=token
    root=request_json('https://api.finmindtrade.com/api/v4/data',params=params)
    if not isinstance(root,dict) or root.get('status') != 200:
        raise DataError('FinMind 回傳異常：'+str(root.get('msg') if isinstance(root,dict) else root)[:160])
    rows=root.get('data') or []
    df=normalize(rows,{'date':'date','Open':'open','High':'max','Low':'min','Close':'close'},'FinMind')
    return df,'FinMind TaiwanStockPrice','https://finmind.github.io/'

def twse_history():
    # Official TWSE STOCK_DAY: a month per request, with ROC date and commas.
    # Fetch 30 monthly files sequentially; reserve this as failover, not on every refresh.
    now=date.today(); first=now.replace(day=1)
    parts=[]
    for months_back in range(30,-1,-1):
        y=first.year; m=first.month-months_back
        while m<=0: m+=12; y-=1
        url='https://www.twse.com.tw/exchangeReport/STOCK_DAY'
        root=request_json(url,params={'response':'json','date':f'{y:04d}{m:02d}01','stockNo':'00935'})
        if not isinstance(root,dict) or root.get('stat')!='OK' or not root.get('data'): continue
        rows=[]
        for values in root['data']:
            try:
                ry,rm,rd=(int(v) for v in str(values[0]).split('/'))
                rows.append({'date':f'{ry+1911:04d}-{rm:02d}-{rd:02d}',
                             'open':str(values[3]).replace(',',''),
                             'high':str(values[4]).replace(',',''),
                             'low':str(values[5]).replace(',',''),
                             'close':str(values[6]).replace(',','')})
            except (ValueError,IndexError): continue
        parts.extend(rows)
    df=normalize(parts,{'date':'date','Open':'open','High':'high','Low':'low','Close':'close'},'TWSE')
    return df,'臺灣證券交易所 STOCK_DAY','https://www.twse.com.tw/'

def get_price_history(symbol,massive_key='',finmind_token='',enable_twse=True):
    errors=[]
    sources=([lambda:massive_history(symbol,massive_key)] if symbol!='00935.TW' else
             [lambda:finmind_history(finmind_token)] + ([twse_history] if enable_twse else []))
    for fn in sources:
        try:
            df,source,url=fn()
            return df,source,url,None
        except (requests.RequestException,DataError,ValueError,KeyError,TypeError) as exc:
            errors.append(str(exc)[:200])
    return pd.DataFrame(),'無可用來源','', '；'.join(errors)
