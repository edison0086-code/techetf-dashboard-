"""Private personal ETF signal dashboard; informational only, never places orders."""
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_sources import get_price_history
from cnn_sources import fetch_cnn, CNN_PAGE
from strategy import build_snapshot, kdj_details, first_stage, next_stage, portfolio_percentages, age_days

st.set_page_config(page_title='科技ETF｜進場訊號儀表板 v3',page_icon='📈',layout='wide')
TW=ZoneInfo('Asia/Taipei')
now=datetime.now(timezone.utc)
SYMBOLS=['QQQM','SMH','00935.TW']

def secret(name):
    try:return str(st.secrets.get(name,'')).strip()
    except (FileNotFoundError,KeyError):return ''

@st.cache_data(ttl=3600,show_spinner=False)
def fetch_all(massive_key, finmind_key, clear_nonce=0):
    out={}
    for sym in SYMBOLS:
        out[sym]=get_price_history(sym,massive_key,finmind_key,enable_twse=True)
    return out

@st.cache_data(ttl=1800,show_spinner=False)
def cached_cnn():
    return fetch_cnn()

st.title('📈 科技 ETF｜15 年進場監控')
st.caption('主動擇時 × 被動指數選股 × 不賣出｜只供個人研究，不自動下單｜v2.1 Massive + FinMind + TWSE + CNN')
with st.sidebar:
    st.header('策略設定')
    profile=st.radio('目標比例',['50／25／25','40／30／30'])
    allocation=portfolio_percentages(profile)
    budget=st.number_input('年度可投資金額（TWD）',0,100000000,600000,10000)
    st.caption('每年未提前觸發時，三檔於 00935 九月除息交易日買入年度剩餘資金。日期依野村公告，不因除息預期價差。')
    exdate=st.date_input('官方 00935 九月除息日（自行設定）',value=None)
    st.divider()
    st.subheader('CNN 市場情緒')
    st.caption('預設嘗試自動擷取 CNN 網頁所使用的未文件化資料端點；若被封鎖或更新延遲，可切換人工核對。')
    cnn_mode=st.radio('CNN 資料模式',['自動（優先）','手動核對'],horizontal=True)
    manual_fear = None
    manual_fear_date = None
    manual_previous = None
    if cnn_mode == '手動核對':
        st.warning('請依照 CNN 官網實際顯示值填寫；網站無法驗證手動輸入。')
        manual_fear=st.number_input('CNN Fear & Greed',0.0,100.0,25.0,1.0)
        manual_fear_date=st.date_input('CNN 觀測日期',value=now.astimezone(TW).date())
        use_previous=st.checkbox('另外輸入上一期 CNN 數值（第三批反轉條件）',value=False)
        manual_previous=st.number_input('上一期 CNN 數值',0.0,100.0,30.0,1.0) if use_previous else None
    st.link_button('開啟 CNN 官方頁面',CNN_PAGE)
    st.divider()
    st.subheader('實際投入狀態')
    stage1_done=st.checkbox('第一批 30% 已實際買入')
    stage1_date=st.date_input('第一批買進日期',value=None,disabled=not stage1_done)
    stage1_price=st.number_input('第一批 QQQM 參考成交價（USD）',min_value=0.0,value=0.0,step=1.0,disabled=not stage1_done)
    stage2_done=st.checkbox('第二批 40% 已完成')
    stage3_done=st.checkbox('第三批 30% 已完成')
    st.warning('這些側欄輸入不會永久儲存。請保留自己的交易紀錄；不要把私人帳務資料放到公開 App。')
    refresh=st.button('🔄 強制更新日收盤行情',use_container_width=True)

if refresh:
    fetch_all.clear()
    cached_cnn.clear()
keys=(secret('MASSIVE_API_KEY'),secret('FINMIND_TOKEN'))
if not keys[0]:
    st.error('尚未設定 MASSIVE_API_KEY：QQQM／SMH 無法取得完整歷史日K。請到 Streamlit App Settings → Secrets 設定金鑰。')

with st.spinner('讀取最新可得日K與計算 J 值……'):
    data=fetch_all(*keys)

st.caption(f'本頁更新檢查：{now.astimezone(TW):%Y-%m-%d %H:%M}（台灣時間）｜非逐筆即時報價；美股日K可能在美股收盤後數小時才更新')
if now.astimezone(TW).year < 2027:
    st.info('2026 年屬於策略測試與訊號觀察期；原定正式投入從 2027 年起。')

st.subheader('三檔 ETF｜最近收盤＋日 J＋本週暫估／完整週 J')
snaps={}; details={}
for sym in SYMBOLS:
    df,source,url,error=data[sym]
    if df.empty:
        with st.container(border=True):
            st.error(f'{sym}｜無法取得資料：{error or "未知錯誤"}')
            st.caption('檢查 API 權限、網路與伺服器日誌；無數據時不判斷進場。')
        continue
    snap=build_snapshot(sym,df,now)
    extra=kdj_details(df,now,sym)
    snaps[sym]=snap; details[sym]=extra
    label=sym.replace('.TW','')
    with st.container(border=True):
        st.markdown(f'### {label}')
        c1,c2,c3,c4=st.columns(4)
        c1.metric('最近收盤價',f'{snap.price:,.2f} {snap.currency}' if snap.price is not None else '待確認')
        c2.metric('日 J（最新日K）',f'{extra["daily_j"]:.2f}' if extra['daily_j'] is not None else '待確認')
        c3.metric('本週暫估週 J',f'{extra["partial_j"]:.2f}' if extra['partial_j'] is not None else '待確認')
        c4.metric('已完成週 J',f'{extra["complete_j"]:.2f}' if extra['complete_j'] is not None else '待確認')
        e1,e2,e3=st.columns(3)
        e1.metric('52 週最高收盤回檔',f'{snap.drawdown_pct:+.2f}%' if snap.drawdown_pct is not None else '待確認')
        e2.metric('近期最高收盤',f'{snap.high_52w:.2f}' if snap.high_52w is not None else '待確認')
        e3.metric('資料距今（曆日）',str(age_days(snap.last_session,now)))
        st.caption(f'行情日期：{snap.last_session}｜完整週 J 截至：{extra["completed_date"]}｜來源：[{source}]({url})')
        if extra['partial_is_complete']:
            st.info('最新日K落在已完成週，暫估週 J 與完整週 J 可能相同。')
        else:
            st.info('本週週 J 是截至最新日K的暫估值，週 K 尚未收盤，**不直接作為正式的週 J 觸發**。')
        if age_days(snap.last_session,now) is not None and age_days(snap.last_session,now)>5:
            st.warning('行情可能過期；不應用過期資料發出正式訊號。')
        with st.expander(f'{label} 最近 120 個交易日走勢與原始資料'):
            graph=df.tail(120).reset_index()
            fig=go.Figure(go.Scatter(x=graph['Date'],y=graph['Close'],mode='lines',name='每日收盤'))
            fig.update_layout(height=260,margin=dict(t=15,b=20,l=12,r=12),xaxis_title='交易日期',yaxis_title=snap.currency)
            st.plotly_chart(fig,use_container_width=True)
            st.dataframe(df.tail(15).sort_index(ascending=False),use_container_width=True)

st.subheader('市場情緒與分批進場條件')
cnn_data,cnn_error=cached_cnn() if cnn_mode=='自動（優先）' else (None,None)
fear=None
fear_date=None
previous_fear=None
if cnn_mode == '手動核對':
    fear=float(manual_fear)
    fear_date=manual_fear_date
    previous_fear=manual_previous
    st.metric('CNN 恐懼與貪婪（人工輸入）',f'{fear:.1f}')
    st.caption(f'人工觀測日期：{fear_date}。僅供輔助分析，請自行核對 CNN 原始數值。')
elif cnn_data is not None:
    observed=cnn_data['observed']
    fear=cnn_data['score']
    fear_date=observed.astimezone(ZoneInfo('America/New_York')).date()
    previous_fear=cnn_data['previous_close']
    st.metric('CNN 恐懼與貪婪（自動）',f'{fear:.1f}',help=cnn_data['rating'])
    st.caption(f"CNN 時間：{observed.astimezone(TW):%Y-%m-%d %H:%M} 台灣時間｜類別：{cnn_data['rating']}｜來源：[CNN 官方頁面]({CNN_PAGE})，未文件化資料端點")
    if age_days(fear_date,now)>5 or age_days(fear_date,now)<0:
        st.warning('CNN 資料可能過期：不使用它觸發新的情緒買進訊號。請到側欄切換「手動核對」。')
else:
    st.warning(f'CNN 自動讀取失敗：{cnn_error or "未知錯誤"}。價格回檔訊號仍會獨立計算；情緒複合訊號待確認。請到側欄切換「手動核對」並從 CNN 官方頁面查證。')
rows=[]
for sym in SYMBOLS:
    snap=snaps.get(sym)
    if snap is None:
        rows.append({'標的':sym,'第一批 30%':'待確認：行情缺失','條件':'無法計算'})
        continue
    res=first_stage(snap,fear,now,fear_date)
    rows.append({'標的':sym.replace('.TW',''),'第一批 30%':res['status'], '條件':'；'.join(res['reasons']) or '未見已核實觸發'})
st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
st.caption('價格回檔 ≥10% 為個別 ETF 訊號，不能擅自當成整個三檔組合全部觸發；須先決定採個別標的還是 QQQM 組合基準。')

qq=snaps.get('QQQM')
next_sig=next_stage(qq,fear,previous_fear,now,stage1_date if stage1_done else None,stage1_price if stage1_done else None,fear_date)
with st.container(border=True):
    st.markdown('#### 第二批 40%／第三批 30%')
    if not next_sig['ready']:
        st.warning(next_sig['note'])
    else:
        st.write('第二批：', '已完成' if stage2_done else ('符合候選條件（請人工核對）' if next_sig['stage2'] else '未符合'))
        st.write('第三批：', '已完成' if stage3_done else ('符合候選條件（請人工核對）' if next_sig['stage3'] else '未符合'))
        st.caption('；'.join(next_sig.get('reasons2',[])+next_sig.get('reasons3',[])) or next_sig['note'])

st.subheader('年度資金配置與固定日')
a,b,c=st.columns(3)
for col,name in zip([a,b,c],['QQQM','SMH','00935']):
    col.metric(f'{name} 目標',f'{allocation[name]:.0%}',f'NT$ {budget*allocation[name]:,.0f}',delta_color='off')
st.write('00935 官方九月除息日期：',str(exdate) if exdate else '尚未設定；請依野村公告填入。')
st.caption('規則：若未提前觸發，三檔於 00935 九月除息日的各自市場交易時段買進當年尚未投入資金；若美股休市須順延。')
st.divider()
st.caption('⚠️ 本工具僅供個人研究；無券商連線、不自動下單。行情可能延遲或因資料端點故障而缺失。所有數據應於實際交易前向交易所／券商核對。')
