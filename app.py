"""科技 ETF 進場監控儀表板 — refresh to retrieve publicly available market data.

Run: python -m streamlit run app.py
The app NEVER sends an order or recommends an exact executable price.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_sources import get_price_history, get_fear_greed
from strategy import build_snapshot, first_stage, next_stage, portfolio_percentages, age_days

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / 'my_trade_state.json'
TW_TZ = ZoneInfo('Asia/Taipei')
SYMBOLS = ['QQQM','SMH','00935.TW']
OFFICIAL = 'https://www.nomurafunds.com.tw/'

st.set_page_config(page_title='科技 ETF｜進場訊號儀表板',page_icon='📈',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container {padding-top:1.8rem;padding-bottom:3rem;max-width:1320px}
h1,h2,h3 {letter-spacing:-0.02em}
.top-note {color:#a5b3ca;font-size:0.94rem;margin-top:-8px;margin-bottom:10px}
.hero {background:linear-gradient(125deg,#172842,#112d30 65%,#0d1b2e);border:1px solid #29465b;
 border-radius:18px;padding:26px 27px;margin:8px 0 20px}
.hero h2 {margin:0 0 7px;color:#F0F9FF;font-size:1.6rem}
.hero p{color:#B5C8D4;margin:0;font-size:1rem}
.kv {font-size:.92rem;color:#a8bfd1}
.source {font-size:0.83rem;color:#8799ad}
.pill {background:#153f35;border:1px solid #2d8b74;color:#8af2c6;border-radius:20px;
 padding:5px 12px;display:inline-block;font-size:.84rem;font-weight:700}
.stMetric {background:#131f32;border:1px solid #263853;padding:15px;border-radius:15px}
[data-testid="stMetricValue"] {font-size:1.65rem}
</style>''',unsafe_allow_html=True)

now = datetime.now(timezone.utc)
local_now = now.astimezone(TW_TZ)


def load_trade_state() -> dict:
    try:
        if STATE_PATH.is_file():
            v=json.loads(STATE_PATH.read_text(encoding='utf-8'))
            return v if isinstance(v,dict) else {}
    except Exception:
        pass
    return {}


def save_trade_state(content: dict):
    tmp=STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(content,indent=2,ensure_ascii=False),encoding='utf-8')
    tmp.replace(STATE_PATH)


@st.cache_data(ttl=15*60,show_spinner=False)
def market_snapshot():
    checked=datetime.now(timezone.utc)
    result={}
    for sym in SYMBOLS:
        hist, source, error = get_price_history(sym)
        result[sym]={'history':hist,'source':source,'error':error}
    fear,error=get_fear_greed()
    return checked,result,fear,error

st.markdown('''<div class="hero"><h2>📈 科技 ETF｜進場訊號儀表板</h2>
<p>QQQM · SMH · 00935　｜　主動擇時 × 被動選股 × 15 年不賣出</p></div>''',unsafe_allow_html=True)

with st.sidebar:
    st.title('⚙️ 策略設定')
    profile=st.radio('目標配置',['50／25／25','40／30／30'],index=0)
    allocation=portfolio_percentages(profile)
    capital=st.number_input('年度新增資金（新台幣）',min_value=0,max_value=100000000,value=600000,step=10000)
    st.write('**年度目標買入**')
    for name,pct in allocation.items(): st.caption(f'{name}: {pct:.0%} · NT${capital*pct:,.0f}')
    st.divider()
    st.markdown('**固定進場日期**')
    st.caption('00935 每年 9 月的「除息交易日」，三檔都在台灣同一日買入。美股按該日美股交易時段；如美股休市，改下一個美股交易日。')
    saved_preferences = load_trade_state()
    saved_exdate = saved_preferences.get('exdate')
    try: current_exdate=date.fromisoformat(saved_exdate) if saved_exdate else None
    except ValueError: current_exdate=None
    exdate=st.date_input('00935 官方 9 月除息日（公告後手動填入）',value=current_exdate,
                         help='因 00935 未來除息日需官方公告，不自動猜日期。')
    if st.button('儲存除息日期',use_container_width=True):
        saved_preferences['exdate']=exdate.isoformat() if exdate else None
        save_trade_state(saved_preferences)
        st.success('已儲存在本機，重新整理不會消失（雲端重建除外）。')
    if exdate: st.info(f'已設定：{exdate.isoformat()}（若當年資金未提前完成加碼，在此日完成投入）')
    else: st.warning('尚未設定官方除息日；固定進場提醒待確認。')
    st.link_button('野村投信官方網站',OFFICIAL)
    st.divider()
    if st.button('🔄 強制重新抓取市場資料',use_container_width=True):
        market_snapshot.clear()
        st.rerun()
    st.caption('開啟頁面或重新整理會讀取資料；為避免免費資料來源限流，結果緩存最多 15 分鐘。使用上方按鈕可強制更新。')

with st.spinner('讀取最新可得的市場資料……'):
    checked, raw, fear, fear_error=market_snapshot()

snapshots={}
for sym in SYMBOLS:
    df=raw[sym]['history']
    if df is not None and not df.empty:
        snapshots[sym]=build_snapshot(sym,df,now)
    else:
        snapshots[sym]=build_snapshot(sym,pd.DataFrame(),now)
        snapshots[sym].error=raw[sym]['error'] or snapshots[sym].error

st.caption(f'資料檢查時間（台灣）：{checked.astimezone(TW_TZ).strftime("%Y-%m-%d %H:%M")}　｜　最新股價＝行情來源最近一根日 K 的 Close，可能尚未收盤；非逐筆即時報價')
if now.astimezone(TW_TZ).year < 2027:
    st.info('目前為 **2026 年策略觀察期**；正式 15 年投入計畫預計 2027 年開始。本頁亮燈不代表 2026 年必須下單。')

# Main fear metric
st.subheader('市場情緒')
f1,f2,f3=st.columns([1.25,1.1,1.65],gap='medium')
with f1:
    if fear:
        st.metric('CNN 恐懼與貪婪指數' if fear['source'].startswith('CNN') else '恐懼與貪婪指數（備援）',
                  f"{fear['score']:.1f} / 100",delta=(f"相較上次 {fear['score']-fear['previous']:+.1f}" if fear['previous'] is not None else None),delta_color='off')
    else: st.metric('CNN 恐懼與貪婪指數','無資料')
with f2:
    score=fear['score'] if fear else None
    st.metric('CNN < 25 條件','符合' if (score is not None and score<25) else ('未符合' if score is not None else '待確認'))
with f3:
    if fear:
        fa=age_days(fear['date'],now)
        st.write(f"來源：[{fear['source']}]({fear['url']})")
        st.write(f"資料日期（美國市場）：**{fear['date']}** · 約 {fa} 天前")
        if fa is None or fa>5 or fa<0: st.error('情緒資料過期或日期異常，不用它判斷訊號。')
        if fear.get('warning'): st.warning(fear['warning'])
    else: st.error('恐懼指數暫時無法取得；不能推定市場情緒符合。')

if fear_error and not fear: st.caption(f'來源存取錯誤：{fear_error[:450]}')

st.subheader('三檔 ETF｜最新股價、日 J 與週 J')
cols=st.columns(3,gap='medium')
for c,symbol in zip(cols,SYMBOLS):
    sn=snapshots[symbol]
    with c:
        st.metric(sn.display,f'{sn.currency} {sn.price:,.2f}' if sn.price is not None else '無資料',
                  f'{sn.drawdown_pct:.2f}%（距 52 週高收盤）' if sn.drawdown_pct is not None else None,
                  delta_color='off')
        st.caption(f'最新可得日 K：{sn.last_session or "未知"}｜此價格可能是交易中的未完成日 K，非逐筆即時報價')
        st.metric('日線 J（最新可得日 K）', f'{sn.daily_j:.2f}' if sn.daily_j is not None else '待確認')
        st.caption(f'上一交易日 J：{sn.prior_daily_j:.2f}' if sn.prior_daily_j is not None else '上一交易日 J：無資料')
        st.metric('週線 J（本週最新估算）', f'{sn.week_estimated_j:.2f}' if sn.week_estimated_j is not None else '待確認')
        if sn.week_is_in_progress:
            st.warning(f'本週尚未收線｜估算資料截至 {sn.week_estimated_asof}；可能繼續變動，**不作正式週線觸發**。')
        else:
            st.caption(f'最近可得週線已完成｜資料截至 {sn.week_estimated_asof or "未知"}')
        st.write('完整週線 J（策略確認用）：', f'**{sn.weekly_j:.2f}**' if sn.weekly_j is not None else '**待確認**')
        st.caption(f'完整週截至：{sn.weekly_close_date or "未知"}｜上個完整週 J：{sn.prior_weekly_j:.2f}' if sn.prior_weekly_j is not None else f'完整週截至：{sn.weekly_close_date or "未知"}｜上個完整週 J：無資料')
        if sn.drawdown_pct is not None:
            st.caption('回檔採配息調整後價格' if sn.drawdown_adjusted else '缺調整後價格，原始價可能受除息影響')
        if sn.error: st.error(f'價格來源失敗：{sn.error[:180]}')
        elif age_days(sn.last_session,now) is not None and age_days(sn.last_session,now)>5:
            st.warning('價格已超過 5 天未更新，訊號暫停判定。')

st.divider()
st.subheader('🚦 第一批 30% 進場條件')
st.caption('單檔觸發：①該 ETF 近 52 週高收盤回檔 ≥10%；或 ② CNN <25 且該 ETF 已完成週線 J <25。個別 ETF 觸發**不自動代表整個 50／25／25 組合都應買入**。')
status_rows=[]
first_results={}
for sym in SYMBOLS:
    sn=snapshots[sym]
    out=first_stage(sn,fear['score'] if fear else None,now,fear['date'] if fear else None)
    first_results[sym]=out
    status_rows.append({'標的':sn.display,'最新收盤':f'{sn.price:,.2f} {sn.currency}' if sn.price is not None else '—',
        '52 週回檔':f'{sn.drawdown_pct:.2f}%' if sn.drawdown_pct is not None else '—',
        '日 J':f'{sn.daily_j:.2f}' if sn.daily_j is not None else '—',
        '本週估算 J':f'{sn.week_estimated_j:.2f}' if sn.week_estimated_j is not None else '—',
        '完整週 J':f'{sn.weekly_j:.2f}' if sn.weekly_j is not None else '—',
        '第一批訊號':out['status'],
        '觸發原因':'；'.join(out['reasons']) if out['reasons'] else '—'})
st.dataframe(pd.DataFrame(status_rows),hide_index=True,use_container_width=True)
qtrigger=first_results['QQQM']['triggered']
others=[x for x in ('SMH','00935.TW') if first_results[x]['triggered']]
if qtrigger:
    st.success('QQQM（核心判斷基準）已符合第一批條件。可依預先設定的組合進場規則評估第一批 30%，此頁不代客下單。')
elif others:
    st.warning('僅個別標的 '+ '、'.join(x.replace('.TW','') for x in others) +' 亮燈；QQQM 尚未亮燈。是否啟動**整體**第一批，原策略未明確定義，請勿自動視為整組買進訊號。')
else:
    st.info('QQQM 尚無可確認的第一批觸發訊號；請查看表格內其他資料是否因來源失效而待確認。')

with st.expander('📐 週線 J 值如何計算？',expanded=False):
    st.write('日線 J、完整週線 J、本週估算週 J 都採 RSV(9)、K/D 各 1/3 平滑（初值 50）、J = 3K − 2D。日 J 使用 9 個交易日；週 J 使用 9 週。')
    st.write('**完整週線 J**：僅納入已完成的交易週，用來判斷正式進場訊號。**本週估算 J**：把本週至最新可得交易日的日 OHLC 合成當週未完成週 K；每次更新都可能改變，僅供觀察。')
    st.write('不同券商的週線分組、配息調整方式、初值與價格來源可能使 J 略有差異；應固定使用本網站參數判斷，勿與不同參數的日線 J 混用。')

st.subheader('📌 第二批 40%／第三批 30%')
st.caption('這兩批**必須知道第一批是否已經實際執行**，且以 QQQM 作為此版本的組合級價格基準。不是看見極度恐慌就可以直接跳到第二批。')
state=load_trade_state()
with st.expander('記錄第一批實際買進資訊（儲存在執行程式的電腦）',expanded=bool(state.get('stage1_done',False))):
    with st.form('stageform'):
        done=st.checkbox('我已經執行第一批 30%',value=state.get('stage1_done',False))
        default_date=date.fromisoformat(state['stage1_date']) if state.get('stage1_date') else min(local_now.date(),date(2027,1,1))
        buydate=st.date_input('第一批實際買進日',value=default_date,min_value=date(2020,1,1),max_value=local_now.date())
        buyprice=st.number_input('第一批 QQQM 成交參考價（美元）',value=float(state.get('stage1_qqqm_price',0.0)),min_value=0.0,max_value=100000.0,step=0.01)
        s2done=st.checkbox('第二批 40% 已完成',value=state.get('stage2_done',False))
        s3done=st.checkbox('第三批 30% 已完成',value=state.get('stage3_done',False))
        if st.form_submit_button('💾 儲存紀錄',use_container_width=True):
            if done and buyprice<=0:
                st.error('已執行第一批時，請輸入有效的 QQQM 成交參考價。')
            else:
                updated=load_trade_state()
                updated.update({'stage1_done':done,'stage1_date':buydate.isoformat() if done else None,
                     'stage1_qqqm_price':buyprice if done else None,
                     'stage2_done':s2done if done else False,'stage3_done':s3done if done else False})
                save_trade_state(updated)
                st.success('已儲存於執行程式的本機環境。雲端免費主機重建時資料可能消失，請另存成交紀錄。')
                st.rerun()

has_one=bool(state.get('stage1_done'))
s1date=date.fromisoformat(state['stage1_date']) if has_one and state.get('stage1_date') else None
s1price=state.get('stage1_qqqm_price') if has_one else None
stages=next_stage(snapshots.get('QQQM'),fear['score'] if fear else None,
    fear['previous'] if fear else None,now,s1date,s1price,fear['date'] if fear else None)
a,b=st.columns(2)
with a:
    if not stages['ready']:
        st.metric('第二批 40%','待確認')
    elif state.get('stage2_done'):
        st.metric('第二批 40%','已記錄完成')
    elif stages['stage2']:
        st.metric('第二批 40%','市場條件符合')
        st.success('；'.join(stages['reasons2']))
    else: st.metric('第二批 40%','尚未符合／等待完整週')
with b:
    if not stages['ready']:st.metric('第三批 30%','待確認')
    elif state.get('stage3_done'):st.metric('第三批 30%','已記錄完成')
    elif stages['stage3']:
        st.metric('第三批 30%','市場反轉條件符合')
        st.success('；'.join(stages['reasons3']))
    else:st.metric('第三批 30%','尚未符合／等待反轉')
st.caption(stages['note'])
if stages.get('drop_since_entry') is not None:
    st.caption(f"QQQM 相對第一批記錄價格：{stages['drop_since_entry']:+.2f}%（未針對後續除息作總報酬調整）")

st.divider()
st.subheader('📈 最近 90 個交易日走勢（個別起點＝100）')
chart=go.Figure()
colors={'QQQM':'#68A9FF','SMH':'#71E6BE','00935.TW':'#F5B85D'}
for sym in SYMBOLS:
    sn=snapshots[sym]
    if sn.daily is None or sn.daily.empty: continue
    sub=sn.daily[['Close']].dropna().tail(90)
    if len(sub)<2: continue
    line=100*sub['Close']/float(sub['Close'].iloc[0])
    chart.add_trace(go.Scatter(x=sub.index,y=line,mode='lines',name=sn.display,
                    line={'color':colors[sym],'width':2.5}))
chart.update_layout(height=360,margin=dict(l=5,r=10,t=15,b=15),
    plot_bgcolor='#111B2A',paper_bgcolor='#111B2A',font=dict(color='#DDEBFF'),
    xaxis=dict(gridcolor='#203247'),yaxis=dict(gridcolor='#203247',title='起點=100'),
    legend=dict(orientation='h',y=1.12),hovermode='x unified')
st.plotly_chart(chart,use_container_width=True)
st.caption('此走勢為原始收盤價標準化，**未含股息再投資與匯率**，只適合觀察近期股價變動，不能直接當作投資總報酬比較。')

st.subheader('🎯 每年固定進場與資金表')
if exdate:
    if exdate<local_now.date(): st.warning('指定日期已經過去；請在下一次野村正式公告後更新除息日期。')
    elif exdate==local_now.date():st.success('今天是你設定的 00935 除息交易日：若今年尚有未投入資金，依計畫同步完成三檔買進。請先確認交易所是否開市。')
    else:st.info(f'下一個預設共同買進日：{exdate}。如已依股災規則把年度資金投入完畢，當日不重複買進。')
else:st.info('00935 九月除息日期待野村投信正式公告。除息本身不是折價優惠，也不保證比其他日期報酬高。')
st.dataframe(pd.DataFrame([{'ETF':name,'目標占比':f'{pct:.0%}',
    '年度資金（新台幣）':f'{capital*pct:,.0f}'} for name,pct in allocation.items()]),
    hide_index=True,use_container_width=True)
st.caption('固定日期是年底前的「防踏空」截止規則，不是統計驗證的超額報酬來源。依你的年度計畫，若恐慌訊號提前執行，只在固定日期投入尚未買完的資金。')

with st.expander('資料來源／限制與風險聲明',expanded=False):
    st.markdown('''- **價格**：[Yahoo Finance](https://finance.yahoo.com/) 公開 Chart 資料（QQQM、SMH、00935.TW）。資料可能有交易日延遲、調整價修正或被限制存取。
- **恐懼指數**：[CNN Fear & Greed](https://www.cnn.com/markets/fear-and-greed) 網站使用的非官方資料端點；讀取失敗時才嘗試 [Fear & Greed Graph](https://fearandgreedgraph.com/data) 第三方備援，標明不同來源。
- **日 J／週 J**：本站以日 OHLC、週 OHLC 計算 KDJ（9、3、3；初值 50）。完整週線 J 才用於正式週線進場條件。本週估算 J 只是將本週已取得的日 K 組成未完成週 K，不能當作確認訊號。
- **52 週回檔**：以最近 365 天收盤價為基準；優先使用 Yahoo「Adj Close」避免配息導致假性回檔。ETF 的現價卡片仍顯示原始收盤價。
- **第二／第三批**：需要已執行第一批的實際資料。本版以 QQQM 作為組合級價格基準，若你要改成依各檔 ETF 獨立觸發，需再另行確定規則。
- **資料斷線或超過 5 天**：對相應訊號顯示待確認；不得把空值當 0 或發出錯誤買點。
- **雲端保存**：買進紀錄寫在程式主機本地 JSON，免費雲端環境可能重建，請勿只依賴此功能保存正式交易紀錄；本機使用則可跨日保留。
- 本工具只做市場條件展示，不會替你執行交易，亦不保證策略超額報酬。''')
