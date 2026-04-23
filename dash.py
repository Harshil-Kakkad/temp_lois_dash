"""
LOIS Intraday Opportunity Dashboard
Usage:  streamlit run lois_dashboard.py
"""

import streamlit as st
import streamlit.components.v1 as components   # ← proper HTML rendering
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from datetime import timedelta

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LOIS Intraday Opportunity Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE-LEVEL CSS  (not used for the ladder — that lives inside the iframe)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  html, body, [class*="css"] { background:#0d1117; color:#cdd6f4; }
  .stApp { background:#0d1117; }
  [data-testid="stSidebar"]   { background:#161b22; border-right:1px solid #30363d; }
  [data-testid="stSidebar"] * { color:#cdd6f4 !important; }
  [data-testid="stFileUploader"] {
      background:#1c2128 !important; border:1px solid #30363d !important;
      border-radius:8px; padding:8px; }
  input[type="number"] {
      background:#1c2128 !important; color:#cdd6f4 !important;
      border:1px solid #30363d !important; border-radius:6px; }
  .stButton > button {
      background:#1f3a6e; color:#7aa2f7; border:1px solid #3d6ec7;
      border-radius:6px; font-weight:600; padding:4px 14px; }
  .stButton > button:hover { background:#2d52a0; }
  .apply-btn > button {
      background:#1c3a1c !important; color:#a6e3a1 !important;
      border:1px solid #3a7a3a !important; font-size:12px !important;
      padding:2px 10px !important; }
  [data-testid="stMetric"] {
      background:#1c2128; border:1px solid #30363d;
      border-radius:8px; padding:10px 14px; }
  [data-testid="stMetricLabel"] { color:#8b949e !important; }
  [data-testid="stMetricValue"] { color:#7aa2f7 !important; }
  h1  { color:#7aa2f7 !important; letter-spacing:1px; }
  h2, h3 { color:#89b4fa !important; }
  hr  { border-color:#30363d; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# LADDER CSS  (injected into every components.v1.html iframe)
# ─────────────────────────────────────────────────────────────────────────────
LADDER_CSS = """
<style>
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:#0d1117; font-family:'Courier New',monospace; }
  .wrap { display:flex; gap:12px; padding:4px 0; }
  .panel {
      flex:1; border:1px solid #30363d; border-radius:8px;
      background:#13181f; padding:10px; overflow:hidden; }
  .ptitle {
      text-align:center; font-size:13px; font-weight:700;
      padding-bottom:8px; border-bottom:1px solid #1e252e; margin-bottom:6px; }
  .er3-c  { color:#f7768e; }
  .i-c    { color:#7aa2f7; }
  .lois-c { color:#a6e3a1; }
  .fbnote { color:#e0af68; font-size:10px; font-weight:400; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  td    { padding:3px 7px; border:1px solid #1e252e; white-space:nowrap; }
  .lh   { background:#0d1117; color:#8b949e; text-align:center;
          font-size:10px; font-weight:700; letter-spacing:1px; }
  /* bid side */
  .lb   { background:#0e2218; color:#a6e3a1; text-align:right; }
  .lbv  { background:#1a3c28; color:#a6e3a1; text-align:right; font-weight:700; }
  /* ask side */
  .la   { background:#2a0e0e; color:#f7768e; text-align:left; }
  .lav  { background:#3c1a1a; color:#f7768e; text-align:left;  font-weight:700; }
  /* price */
  .lp   { background:#1c2128; color:#cdd6f4; text-align:center; font-weight:600; }
  .lbb  { background:#1a3c28; color:#a6e3a1; text-align:center; font-weight:700; }
  .lba  { background:#3c1a1a; color:#f7768e; text-align:center; font-weight:700; }
  /* empty / traded */
  .lem  { color:#30363d; text-align:center; background:#111620; }
  .ltv  { color:#e0af68; font-size:10px; }
  /* footer */
  .lfoot {
      display:flex; justify-content:space-between;
      padding:6px 4px 0; font-size:11px; color:#8b949e; margin-top:4px;
      border-top:1px solid #1e252e; }
  .gb { color:#a6e3a1; font-weight:700; }
  .gr { color:#f7768e; font-weight:700; }
  .gy { color:#e0af68; font-weight:700; }
  .no-data { color:#565f89; text-align:center; padding:30px 8px; font-size:12px; }
  /* spread separator row */
  .spr { background:#0d1117; color:#565f89; text-align:center;
         font-size:10px; padding:2px 4px; border:1px solid #1e252e; }
  /* arrow indicators */
  .arr-bid   { color:#cba6f7; font-weight:700; font-size:11px; margin-left:4px; }
  .arr-ask   { color:#cba6f7; font-weight:700; font-size:11px; margin-left:4px; }
  .arr-synth { color:#89dceb; font-weight:700; font-size:11px; margin-left:4px; }
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────────────────────

def _is_buy(c):  return isinstance(c, str) and 'b' in c.lower().strip()
def _is_sell(c): return isinstance(c, str) and 's' in c.lower().strip()


@st.cache_data(show_spinner=False)
def load_outright_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    buf = io.BytesIO(file_bytes)
    probe = pd.read_excel(buf, skiprows=8, header=0, engine='calamine', nrows=2)
    buf.seek(0)
    df = (pd.read_excel(buf, skiprows=8, header=0, engine='calamine')
          if 'Timestamp' in probe.columns
          else pd.read_excel(buf, engine='calamine'))
    df = df.rename(columns=lambda c: str(c).strip())
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    for col in ['Last Trade', 'Volume', 'Bid', 'Bid Size', 'Ask', 'Ask Size']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df['Conditions'] = df['Conditions'].astype(str).str.strip()
    df = df.dropna(subset=['Timestamp']).sort_values('Timestamp').reset_index(drop=True)
    df['is_buy']  = df['Conditions'].apply(_is_buy)
    df['is_sell'] = df['Conditions'].apply(_is_sell)
    return df


@st.cache_data(show_spinner=False)
def load_lois_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    buf = io.BytesIO(file_bytes)
    df = pd.read_excel(buf, engine='calamine')
    df = df.rename(columns=lambda c: str(c).strip())
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    for col in ['Last Trade', 'Volume', 'Bid', 'Bid Size', 'Ask', 'Ask Size']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df['Conditions'] = df['Conditions'].astype(str).str.strip()
    df = df.dropna(subset=['Timestamp']).sort_values('Timestamp').reset_index(drop=True)
    df['is_buy']  = df['Conditions'].apply(_is_buy)
    df['is_sell'] = df['Conditions'].apply(_is_sell)
    return df


def slice_window(df, t0, t1):
    return df[(df['Timestamp'] >= t0) & (df['Timestamp'] < t1)]


def compute_hits(df_slice):
    t = df_slice[df_slice['Volume'].notna() & (df_slice['Volume'] > 0)]
    return float(t.loc[t['is_sell'], 'Volume'].sum()), float(t.loc[t['is_buy'], 'Volume'].sum())


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_instances(er3, i_df, window_mins, min_hits, ratio):
    t_start = max(er3['Timestamp'].min(), i_df['Timestamp'].min())
    t_end   = min(er3['Timestamp'].max(), i_df['Timestamp'].max())
    if pd.isna(t_start) or pd.isna(t_end) or t_start >= t_end:
        return []
    wdelta, instances, t = timedelta(minutes=window_mins), [], t_start
    while t + wdelta <= t_end:
        t1 = t + wdelta
        eb, ea = compute_hits(slice_window(er3,  t, t1))
        ib, ia = compute_hits(slice_window(i_df, t, t1))
        if eb >= min_hits and ea >= min_hits and ib >= min_hits and ia >= min_hits:
            sb, sa = eb + ia, ea + ib
            r = max(sb, sa) / min(sb, sa) if min(sb, sa) > 0 else float('inf')
            if r >= ratio:
                es = slice_window(er3,  t, t1).dropna(subset=['Bid', 'Ask'])
                is_ = slice_window(i_df, t, t1).dropna(subset=['Bid', 'Ask'])
                ebp = float(es['Bid'].iloc[-1])  if len(es)  else np.nan
                eap = float(es['Ask'].iloc[-1])  if len(es)  else np.nan
                ibp = float(is_['Bid'].iloc[-1]) if len(is_) else np.nan
                iap = float(is_['Ask'].iloc[-1]) if len(is_) else np.nan
                instances.append(dict(
                    t_start=t, t_end=t1,
                    er3_bid_vol=eb, er3_ask_vol=ea, i_bid_vol=ib, i_ask_vol=ia,
                    synth_bid_vol=sb, synth_ask_vol=sa,
                    ratio=r, direction="BID" if sb >= sa else "ASK",
                    er3_bid_px=ebp, er3_ask_px=eap, i_bid_px=ibp, i_ask_px=iap,
                    synth_bid_px=(ibp - eap) if not any(np.isnan([ibp, eap])) else np.nan,
                    synth_ask_px=(iap - ebp) if not any(np.isnan([iap, ebp])) else np.nan,
                ))
        t = t1
    return instances


def hourly_counts(instances, all_hours):
    c = {h: 0 for h in all_hours}
    for inst in instances:
        h = inst['t_start'].hour
        if h in c: c[h] += 1
    return c


def hourly_volume(df, all_hours):
    vol = {h: 0.0 for h in all_hours}
    if 'Volume' not in df.columns: return vol
    tmp = df[df['Volume'].notna() & (df['Volume'] > 0)].copy()
    tmp['hour'] = tmp['Timestamp'].dt.hour
    for h, v in tmp.groupby('hour')['Volume'].sum().items():
        if h in vol: vol[h] = float(v)
    return vol


# ─────────────────────────────────────────────────────────────────────────────
# LADDER STATE
# ─────────────────────────────────────────────────────────────────────────────

def get_book_state_at(df, t_query, lookback_secs=90):
    """
    Reconstructs top-of-book at t_query.

    Returns a dict with:
      bid, ask, bid_size, ask_size  — current best prices/sizes
      bid_levels  — list of (price, size, traded_vol, is_best)  sorted desc  ← bid side only
      ask_levels  — list of (price, size, traded_vol, is_best)  sorted desc  ← ask side only
      fallback    — True if last data was more than lookback_secs ago
    """
    if df is None or df.empty:
        return None
    hist = df[df['Timestamp'] <= t_query].dropna(subset=['Bid', 'Ask'])
    if hist.empty:
        return None

    latest   = hist.iloc[-1]
    best_bid = float(latest['Bid'])
    best_ask = float(latest['Ask'])
    best_bsz = float(latest['Bid Size']) if pd.notna(latest.get('Bid Size', np.nan)) else 0
    best_asz = float(latest['Ask Size']) if pd.notna(latest.get('Ask Size', np.nan)) else 0
    fallback = (t_query - latest['Timestamp']).total_seconds() > lookback_secs

    t_lb   = t_query - timedelta(seconds=lookback_secs)
    recent = hist[hist['Timestamp'] >= t_lb]
    if len(recent) < 2:
        recent = hist.tail(30)

    # ── Strict separation: bid prices only carry bid sizes, ask prices only ask sizes ──
    # We bucket each historical quote: Bid price → bid size, Ask price → ask size.
    # A price can only belong to ONE side; its position relative to best_bid/best_ask
    # at *that tick* determines which side it is.
    bid_map: dict = {}   # price → latest bid size at that price
    ask_map: dict = {}   # price → latest ask size at that price

    for _, row in recent.iterrows():
        b = float(row['Bid']); a = float(row['Ask'])
        bsz = float(row['Bid Size']) if pd.notna(row.get('Bid Size', np.nan)) else 0
        asz = float(row['Ask Size']) if pd.notna(row.get('Ask Size', np.nan)) else 0
        bid_map[b] = bsz   # always overwrite with latest observation
        ask_map[a] = asz

    # Traded volumes by price
    traded: dict = {}
    for _, row in recent[recent['Volume'].notna() & (recent['Volume'] > 0)].iterrows():
        px = float(row['Last Trade'])
        traded[px] = traded.get(px, 0) + float(row['Volume'])

    band = max((best_ask - best_bid) * 8, 0.006)

    # BID levels: prices ≤ best_bid, within band
    bid_levels = []
    for px, bsz in bid_map.items():
        if px <= best_bid + 1e-8 and abs(px - best_bid) <= band:
            bid_levels.append((px, bsz, traded.get(px, 0), abs(px - best_bid) < 1e-7))
    # Ensure best bid always present
    if not any(abs(lv[0] - best_bid) < 1e-7 for lv in bid_levels):
        bid_levels.append((best_bid, best_bsz, traded.get(best_bid, 0), True))
    bid_levels.sort(key=lambda x: x[0], reverse=True)

    # ASK levels: prices ≥ best_ask, within band
    ask_levels = []
    for px, asz in ask_map.items():
        if px >= best_ask - 1e-8 and abs(px - best_ask) <= band:
            ask_levels.append((px, asz, traded.get(px, 0), abs(px - best_ask) < 1e-7))
    # Ensure best ask always present
    if not any(abs(lv[0] - best_ask) < 1e-7 for lv in ask_levels):
        ask_levels.append((best_ask, best_asz, traded.get(best_ask, 0), True))
    ask_levels.sort(key=lambda x: x[0], reverse=True)

    return dict(
        bid=best_bid, ask=best_ask, bid_size=best_bsz, ask_size=best_asz,
        bid_levels=bid_levels, ask_levels=ask_levels,
        fallback=fallback,
    )


def _ladder_panel_html(state, title: str, color_cls: str,
                       arrow_price: float = None,
                       arrow_side: str = None,
                       arrow_label: str = "◄ target") -> str:
    """
    Renders one contract's order-book ladder as an HTML table.

    Layout (top = highest price):
      ─ ask levels  (price ≥ best ask)  →  empty bid col | price | ask size
      ─ spread gap row
      ─ bid levels  (price ≤ best bid)  →  bid size | price | empty ask col

    arrow_price : if set, that row gets a "◄ <label>" indicator in the price cell
    arrow_side  : 'bid' | 'ask' | 'synth'   (controls arrow colour)
    """
    fb = ' <span class="fbnote">(last known)</span>' if state and state.get('fallback') else ''

    if state is None:
        return (f'<div class="ptitle"><span class="{color_cls}">{title}</span></div>'
                f'<div class="no-data">No data available</div>')

    def _arrow_cls(side):
        return {'bid': 'arr-bid', 'ask': 'arr-ask', 'synth': 'arr-synth'}.get(side or '', 'arr-bid')

    def _is_arrow(px):
        return arrow_price is not None and abs(px - arrow_price) < 1e-7

    rows = ""

    # ── Ask levels (high → low, i.e. best ask last in this sorted-desc slice) ──
    for (px, asz, traded, is_best) in state['ask_levels']:
        px_cls  = "lba" if is_best else "lp"
        av_cls  = "lav" if is_best else ("la" if asz > 0 else "lem")
        av_txt  = f"{asz:,.0f}" if asz > 0 else "—"
        tr_note = f"<br><span class='ltv'>✓ {traded:,.0f}</span>" if traded > 0 else ""
        arr     = (f" <span class='{_arrow_cls(arrow_side)}'>{arrow_label}</span>"
                   if _is_arrow(px) else "")
        rows += (f"<tr>"
                 f"<td class='lem'>—</td>"
                 f"<td class='{px_cls}'>{px:.4f}{tr_note}{arr}</td>"
                 f"<td class='{av_cls}'>{av_txt}</td>"
                 f"</tr>")

    # ── Spread separator ──
    spread = state['ask'] - state['bid']
    rows += (f"<tr>"
             f"<td class='spr' colspan='3'>"
             f"spread&nbsp;<b>{spread:.4f}</b>"
             f"</td></tr>")

    # ── Bid levels (high → low, i.e. best bid first) ──
    for (px, bsz, traded, is_best) in state['bid_levels']:
        px_cls  = "lbb" if is_best else "lp"
        bv_cls  = "lbv" if is_best else ("lb" if bsz > 0 else "lem")
        bv_txt  = f"{bsz:,.0f}" if bsz > 0 else "—"
        tr_note = f"<br><span class='ltv'>✓ {traded:,.0f}</span>" if traded > 0 else ""
        arr     = (f" <span class='{_arrow_cls(arrow_side)}'>{arrow_label}</span>"
                   if _is_arrow(px) else "")
        rows += (f"<tr>"
                 f"<td class='{bv_cls}'>{bv_txt}</td>"
                 f"<td class='{px_cls}'>{px:.4f}{tr_note}{arr}</td>"
                 f"<td class='lem'>—</td>"
                 f"</tr>")

    return f"""
      <div class="ptitle"><span class="{color_cls}">{title}</span>{fb}</div>
      <table>
        <tr>
          <td class="lh" style="width:33%">BID SIZE</td>
          <td class="lh" style="width:34%">PRICE</td>
          <td class="lh" style="width:33%">ASK SIZE</td>
        </tr>
        {rows}
      </table>
      <div class="lfoot">
        <span>Bid: <span class="gb">{state['bid']:.4f}</span></span>
        <span>Spd: <span class="gy">{spread:.4f}</span></span>
        <span>Ask: <span class="gr">{state['ask']:.4f}</span></span>
      </div>"""


def render_ladder_iframe(er3_state, i_state, lois_state, ts_label: str,
                          er3_arrow=None, er3_arrow_side=None,
                          i_arrow=None, i_arrow_side=None,
                          lois_arrow=None, lois_arrow_side=None) -> str:
    """
    Builds a complete self-contained HTML page rendered via components.v1.html().
    Arrow params: (price_float, side_str)  where side ∈ 'bid'|'ask'|'synth'
    """
    er3_html  = _ladder_panel_html(er3_state,  "ER3 (ESTR)",  "er3-c",
                                    arrow_price=er3_arrow,  arrow_side=er3_arrow_side,
                                    arrow_label="◄ hit")
    i_html    = _ladder_panel_html(i_state,    "I (EURIBOR)", "i-c",
                                    arrow_price=i_arrow,    arrow_side=i_arrow_side,
                                    arrow_label="◄ hit")
    lois_html = _ladder_panel_html(lois_state, "LOIS",        "lois-c",
                                    arrow_price=lois_arrow, arrow_side=lois_arrow_side,
                                    arrow_label="◄ synthetic")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{LADDER_CSS}</head>
<body>
  <div style="color:#8b949e;font-size:11px;padding:0 2px 8px 2px;">
    📍 Book state at
    <b style="color:#7aa2f7">{ts_label}</b>
    &nbsp;|&nbsp;
    <span style="color:#a6e3a1">■ BID SIZE</span>
    &nbsp;
    <span style="color:#f7768e">■ ASK SIZE</span>
    &nbsp;
    <span style="color:#e0af68">✓ traded in lookback</span>
    &nbsp;|&nbsp;
    <span style="color:#cba6f7">◄ hit</span> = outright price targeted by signal
    &nbsp;|&nbsp;
    <span style="color:#89dceb">◄ synthetic</span> = implied LOIS price
  </div>
  <div class="wrap">
    <div class="panel">{er3_html}</div>
    <div class="panel">{i_html}</div>
    <div class="panel">{lois_html}</div>
  </div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# OVERVIEW + T&S CHARTS
# ─────────────────────────────────────────────────────────────────────────────

PLOTLY_DARK = dict(paper_bgcolor="#0d1117", plot_bgcolor="#1c2128",
                   font=dict(color="#cdd6f4", family="monospace"))


def make_overview_fig(icounts, er3_vol, i_vol, lois_vol, active_hours):
    labels = [f"{h:02d}:00" for h in active_hours]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                        row_heights=[0.35, 0.22, 0.22, 0.21], vertical_spacing=0.04,
                        subplot_titles=["True Instance Count (per hour)",
                                        "ER3 (ESTR) Volume Density",
                                        "I (EURIBOR) Volume Density",
                                        "LOIS Volume Density"])
    cv = [icounts.get(h, 0) for h in active_hours]
    fig.add_trace(go.Bar(x=labels, y=cv,
        marker_color=['#7aa2f7' if v > 0 else '#30363d' for v in cv],
        hovertemplate="%{x}: %{y} instances<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=labels, y=[er3_vol.get(h,0) for h in active_hours],
        marker_color='#f7768e', hovertemplate="%{x}: %{y:,.0f} lots<extra></extra>"), row=2, col=1)
    fig.add_trace(go.Bar(x=labels, y=[i_vol.get(h,0) for h in active_hours],
        marker_color='#7aa2f7', hovertemplate="%{x}: %{y:,.0f} lots<extra></extra>"), row=3, col=1)
    fig.add_trace(go.Bar(x=labels, y=[lois_vol.get(h,0) for h in active_hours],
        marker_color='#a6e3a1', hovertemplate="%{x}: %{y:,.0f} lots<extra></extra>"), row=4, col=1)
    fig.update_layout(height=520, showlegend=False,
                      margin=dict(l=50, r=20, t=40, b=30), **PLOTLY_DARK)
    for i in range(1, 5):
        fig.update_xaxes(gridcolor="#30363d", row=i, col=1)
        fig.update_yaxes(gridcolor="#30363d", row=i, col=1)
    fig.update_layout(xaxis4=dict(tickangle=-45))
    return fig


def make_ts_fig(er3, i_df, lois, t_center, window_mins):
    half = timedelta(minutes=window_mins)
    t0, t1 = t_center - half, t_center + half
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.34, 0.34, 0.32], vertical_spacing=0.05,
                        subplot_titles=["ER3 (ESTR) — Time & Sales",
                                        "I (EURIBOR) — Time & Sales",
                                        "LOIS — Time & Sales"])

    def ts_panel(df_slice, row):
        t = df_slice.dropna(subset=['Last Trade', 'Volume'])
        t = t[t['Volume'] > 0]
        if t.empty: return
        colors = ['#f7768e' if r.is_buy else '#a6e3a1' if r.is_sell else '#565f89'
                  for _, r in t.iterrows()]
        fig.add_trace(go.Scatter(
            x=t['Timestamp'], y=t['Last Trade'], mode='markers',
            marker=dict(size=np.clip(np.sqrt(t['Volume'].values)*3, 4, 22),
                        color=colors, opacity=0.85, line=dict(width=0)),
            text=[f"{r['Last Trade']:.4f}  vol={int(r['Volume'])}" for _, r in t.iterrows()],
            hovertemplate="%{text}<br>%{x}<extra></extra>",
        ), row=row, col=1)
        bids = df_slice.dropna(subset=['Bid'])
        asks = df_slice.dropna(subset=['Ask'])
        if not bids.empty:
            fig.add_trace(go.Scatter(x=bids['Timestamp'], y=bids['Bid'], mode='lines',
                line=dict(color='#a6e3a1', width=1, dash='dot'), showlegend=False), row=row, col=1)
        if not asks.empty:
            fig.add_trace(go.Scatter(x=asks['Timestamp'], y=asks['Ask'], mode='lines',
                line=dict(color='#f7768e', width=1, dash='dot'), showlegend=False), row=row, col=1)

    for df_s, row in [(slice_window(er3, t0, t1), 1),
                       (slice_window(i_df, t0, t1), 2),
                       (slice_window(lois, t0, t1), 3)]:
        ts_panel(df_s, row)
    fig.add_vline(x=t_center.isoformat(), line_width=1.5, line_dash="dash", line_color="#7aa2f7")
    fig.update_layout(height=530, showlegend=False,
                      margin=dict(l=50, r=20, t=50, b=30), **PLOTLY_DARK)
    for r in [1, 2, 3]:
        fig.update_xaxes(gridcolor="#30363d", row=r, col=1)
        fig.update_yaxes(gridcolor="#30363d", row=r, col=1)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────

for k, v in dict(
    selected_hour=None, selected_instance=None, instances=None,
    er3_df=None, i_df=None, lois_df=None,
    p_window=5.0, p_hits=30.0, p_ratio=2.0,
).items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# SYNCED PARAMETER WIDGET
# ─────────────────────────────────────────────────────────────────────────────
# Design:
#   [──────────── slider ────────────]  [  number input  ] [Apply↩]
#
# • Slider fires on_change → writes directly to st.session_state[skey].
# • "Apply" button reads the number_input widget value and writes to skey,
#   then calls st.rerun() so the slider jumps to match.
# • Both widgets initialise from skey, so they are always consistent after
#   any rerun triggered by either path.
# ─────────────────────────────────────────────────────────────────────────────

def synced_param(label: str, skey: str,
                 smin: float, smax: float, step: float, fmt: str):
    """Renders slider + number_input + Apply button.  Returns canonical value."""

    cur   = float(st.session_state[skey])
    s_val = float(np.clip(cur, smin, smax))

    # Slider — on_change writes directly to the canonical key
    def _on_slide():
        st.session_state[skey] = float(st.session_state[f"__sl_{skey}"])

    col_sl, col_ni, col_btn = st.columns([3, 1, 0.6])

    col_sl.slider(
        label,
        min_value=float(smin), max_value=float(smax),
        value=s_val, step=float(step), format=fmt,
        key=f"__sl_{skey}",
        on_change=_on_slide,
    )

    # Number input — shows current canonical value; user edits then clicks Apply
    new_ni = col_ni.number_input(
        "val",
        value=cur,
        min_value=float(step),
        max_value=float(smax) * 20,
        step=float(step), format=fmt,
        key=f"__ni_{skey}",
        label_visibility="collapsed",
        help="Edit, then click Apply ↩",
    )

    # Apply button — push number-input value into canonical key + rerun to sync slider
    with col_btn:
        st.markdown('<div class="apply-btn">', unsafe_allow_html=True)
        if st.button("↩", key=f"__btn_{skey}",
                     help="Apply this value to the slider"):
            st.session_state[skey] = float(new_ni)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    return float(st.session_state[skey])


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📂 Load Data Files")
    st.markdown('<span style="color:#7aa2f7;font-weight:700">I (EURIBOR)</span> T&S',
                unsafe_allow_html=True)
    i_file = st.file_uploader("i", type=["xlsx"], label_visibility="collapsed", key="i_upload")
    st.markdown('<span style="color:#f7768e;font-weight:700">ER3 (ESTR)</span> T&S',
                unsafe_allow_html=True)
    er3_file = st.file_uploader("er3", type=["xlsx"], label_visibility="collapsed", key="er3_upload")
    st.markdown('<span style="color:#a6e3a1;font-weight:700">LOIS</span> T&S',
                unsafe_allow_html=True)
    lois_file = st.file_uploader("lois", type=["xlsx"], label_visibility="collapsed", key="lois_upload")

    st.markdown("---")
    st.markdown("## ⚙️ Parameters")
    st.caption("Slider auto-syncs on drag. Edit the box then click **↩** to push value to slider.")

    window_mins = synced_param("Time Window (min)", "p_window", 0.5, 60.0, 0.5, "%.1f")
    st.caption(f"Active: **{window_mins:.1f} min**")

    min_hits = synced_param("Min Hits (lots)", "p_hits", 1.0, 500.0, 1.0, "%.0f")
    st.caption(f"Active: **{min_hits:.0f} lots**")

    ratio = synced_param("Bid/Ask Imbalance Ratio", "p_ratio", 1.0, 10.0, 0.1, "%.1f")
    st.caption(f"Active: **{ratio:.1f}×**")

    st.markdown("---")
    run_btn = st.button("▶  Run Analysis", use_container_width=True)

    st.markdown("---")
    st.markdown(
        "**Signal logic**\n\n"
        "Synth **BID** vol = `ER3_bid + I_ask`\n\n"
        "Synth **ASK** vol = `ER3_ask + I_bid`\n\n"
        "LOIS = **I − ER3** (price terms)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# FILE LOADING
# ─────────────────────────────────────────────────────────────────────────────

if er3_file:
    with st.spinner("Loading ER3…"):
        st.session_state.er3_df = load_outright_file(er3_file.read(), er3_file.name)
    er3_file.seek(0)
if i_file:
    with st.spinner("Loading I…"):
        st.session_state.i_df = load_outright_file(i_file.read(), i_file.name)
    i_file.seek(0)
if lois_file:
    with st.spinner("Loading LOIS…"):
        st.session_state.lois_df = load_lois_file(lois_file.read(), lois_file.name)
    lois_file.seek(0)

er3_df  = st.session_state.er3_df
i_df    = st.session_state.i_df
lois_df = st.session_state.lois_df
_EMPTY  = pd.DataFrame(columns=['Timestamp','Last Trade','Volume','Bid','Ask',
                                 'Bid Size','Ask Size','Conditions','is_buy','is_sell'])

# ─────────────────────────────────────────────────────────────────────────────
# HEADER + METRICS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("# LOIS Intraday Opportunity Dashboard")
st.markdown(
    '<span style="color:#f7768e;font-weight:700">ER3</span>'
    ' &nbsp;–&nbsp;<span style="color:#7aa2f7;font-weight:700">I</span>'
    '&nbsp;=&nbsp;<span style="color:#a6e3a1;font-weight:700">LOIS</span>'
    '&emsp;|&emsp;ICE STIR Synthetic Spread Opportunity Finder',
    unsafe_allow_html=True,
)
mc = st.columns(4)
mc[0].metric("ER3 rows",  f"{len(er3_df):,}"  if er3_df  is not None else "–")
mc[1].metric("I rows",    f"{len(i_df):,}"    if i_df    is not None else "–")
mc[2].metric("LOIS rows", f"{len(lois_df):,}" if lois_df is not None else "–")
if er3_df is not None and i_df is not None:
    t0c = max(er3_df['Timestamp'].min(), i_df['Timestamp'].min())
    t1c = min(er3_df['Timestamp'].max(), i_df['Timestamp'].max())
    mc[3].metric("Common range", f"{t0c.strftime('%H:%M')} – {t1c.strftime('%H:%M')}")
else:
    mc[3].metric("Common range", "–")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# RUN ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

if run_btn:
    if er3_df is None or i_df is None:
        st.error("Please upload both ER3 and I files before running.")
    else:
        with st.spinner("Detecting instances…"):
            st.session_state.instances = detect_instances(
                er3_df, i_df, window_mins, min_hits, ratio)
        st.session_state.selected_hour = None
        st.session_state.selected_instance = None

instances = st.session_state.instances
if instances is None:
    st.info("Upload files and click **▶ Run Analysis** to begin.")
    st.stop()

total = len(instances)
st.markdown(f"### 🔍 Found **{total}** true instance{'s' if total != 1 else ''}")
if total == 0:
    st.warning("No instances found. Try lowering Min Hits or Ratio.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# OVERVIEW CHART
# ─────────────────────────────────────────────────────────────────────────────

all_hours = list(range(24))
icounts   = hourly_counts(instances, all_hours)
er3_hv    = hourly_volume(er3_df,  all_hours) if er3_df  is not None else {}
i_hv      = hourly_volume(i_df,    all_hours) if i_df    is not None else {}
lois_hv   = hourly_volume(lois_df, all_hours) if lois_df is not None else {}

active_h = [h for h in all_hours
            if icounts.get(h,0)+er3_hv.get(h,0)+i_hv.get(h,0)+lois_hv.get(h,0) > 0]
if not active_h: active_h = list(range(7, 20))

st.markdown("### 📊 Hourly Overview")
click = st.plotly_chart(
    make_overview_fig(icounts, er3_hv, i_hv, lois_hv, active_h),
    use_container_width=True, on_select="rerun", selection_mode="points",
    key="overview_chart",
)
if click and click.get("selection") and click["selection"].get("points"):
    pt = click["selection"]["points"][0]
    if pt.get("trace_index", -1) == 0:
        try:
            hr = int(str(pt.get("x","")).split(":")[0])
            if st.session_state.selected_hour != hr:
                st.session_state.selected_hour = hr
                st.session_state.selected_instance = None
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────────────────────
# HOUR SELECTOR
# ─────────────────────────────────────────────────────────────────────────────

hours_w = sorted([h for h, c in icounts.items() if c > 0])
if hours_w:
    hr_opts    = [f"{h:02d}:00  ({icounts[h]} instance{'s' if icounts[h]>1 else ''})"
                  for h in hours_w]
    default_i  = (hours_w.index(st.session_state.selected_hour)
                  if st.session_state.selected_hour in hours_w else 0)
    sel_hr_lbl = st.selectbox("🕐 Select Hour", hr_opts, index=default_i, key="hr_sel")
    sel_hr     = int(sel_hr_lbl.split(":")[0])
    if st.session_state.selected_hour != sel_hr:
        st.session_state.selected_hour = sel_hr
        st.session_state.selected_instance = None

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# INSTANCE LIST
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.selected_hour is not None:
    h      = st.session_state.selected_hour
    h_insts = [inst for inst in instances if inst['t_start'].hour == h]
    st.markdown(f"### ⚡ Instances at **{h:02d}:00** — {len(h_insts)} found")

    if h_insts:
        rows = [{
            "#": i+1,
            "Start":    inst['t_start'].strftime("%H:%M:%S"),
            "End":      inst['t_end'].strftime("%H:%M:%S"),
            "Dir":      inst['direction'],
            "ER3 B✓":  f"{inst['er3_bid_vol']:.0f}",
            "ER3 A✓":  f"{inst['er3_ask_vol']:.0f}",
            "I B✓":    f"{inst['i_bid_vol']:.0f}",
            "I A✓":    f"{inst['i_ask_vol']:.0f}",
            "Ratio":   f"{inst['ratio']:.2f}×",
            "Synth B": f"{inst['synth_bid_px']:.4f}" if not np.isnan(inst['synth_bid_px']) else "–",
            "Synth A": f"{inst['synth_ask_px']:.4f}" if not np.isnan(inst['synth_ask_px']) else "–",
        } for i, inst in enumerate(h_insts)]

        labels  = [f"#{r['#']}  {r['Start']}–{r['End']}  {r['Dir']}  {r['Ratio']}"
                   for r in rows]
        prev    = st.session_state.selected_instance or 0
        sel_idx = st.selectbox(
            "Select instance for detail view",
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
            index=min(prev, len(labels)-1),
            key="inst_sel",
        )
        st.session_state.selected_instance = sel_idx
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     height=min(35*len(rows)+45, 260))

    st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# INSTANCE DETAIL
# ─────────────────────────────────────────────────────────────────────────────

if (st.session_state.selected_hour is not None and
        st.session_state.selected_instance is not None and
        er3_df is not None and i_df is not None):

    h       = st.session_state.selected_hour
    h_insts = [inst for inst in instances if inst['t_start'].hour == h]
    si      = st.session_state.selected_instance
    if si >= len(h_insts): st.stop()

    inst     = h_insts[si]
    lois_ref = lois_df if lois_df is not None else _EMPTY
    dir_sym  = "🟢 BID" if inst['direction'] == "BID" else "🔴 ASK"

    st.markdown(
        f"### 🔬 Instance #{si+1} &nbsp; "
        f"`{inst['t_start'].strftime('%H:%M:%S')}` → `{inst['t_end'].strftime('%H:%M:%S')}`"
        f" &nbsp; {dir_sym} &nbsp; Ratio **{inst['ratio']:.2f}×**"
    )
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("ER3 Bid", f"{inst['er3_bid_px']:.4f}" if not np.isnan(inst['er3_bid_px']) else "–")
    m2.metric("ER3 Ask", f"{inst['er3_ask_px']:.4f}" if not np.isnan(inst['er3_ask_px']) else "–")
    m3.metric("I Bid",   f"{inst['i_bid_px']:.4f}"   if not np.isnan(inst['i_bid_px'])   else "–")
    m4.metric("I Ask",   f"{inst['i_ask_px']:.4f}"   if not np.isnan(inst['i_ask_px'])   else "–")
    m5.metric("Synth LOIS B/A",
              f"{inst['synth_bid_px']:.4f} / {inst['synth_ask_px']:.4f}"
              if not any(np.isnan([inst['synth_bid_px'], inst['synth_ask_px']])) else "–")

    # ── LADDER + TIME SLIDER ─────────────────────────────────────────────────
    st.markdown("#### 📟 Ladder Visualizer")
    st.caption(
        "Scrub the slider to replay the book state at any tick in the window. "
        "*(last known)* = no update in window yet, forward-filled from before."
    )

    # Collect all tick timestamps within the window
    win_er3  = slice_window(er3_df,   inst['t_start'], inst['t_end'])
    win_i    = slice_window(i_df,     inst['t_start'], inst['t_end'])
    win_lois = slice_window(lois_ref, inst['t_start'], inst['t_end'])

    ts_pool = (
        pd.concat([win_er3[['Timestamp']], win_i[['Timestamp']], win_lois[['Timestamp']]])
        ['Timestamp'].dropna().drop_duplicates().sort_values().tolist()
    )
    if not ts_pool:
        ts_pool = [inst['t_start'], inst['t_end']]
    else:
        if ts_pool[0]  > inst['t_start']: ts_pool.insert(0, inst['t_start'])
        if ts_pool[-1] < inst['t_end']:   ts_pool.append(inst['t_end'])

    # Build deduplicated string labels
    seen, ts_labels = set(), []
    for ts in ts_pool:
        base = ts.strftime("%H:%M:%S.%f")[:-3]
        lbl, n = base, 0
        while lbl in seen:
            n += 1; lbl = f"{base}+{n}ms"
        seen.add(lbl); ts_labels.append(lbl)
    ts_map = {lbl: ts for lbl, ts in zip(ts_labels, ts_pool)}

    ldr_key = f"ldr_{h}_{si}"
    if ldr_key not in st.session_state or st.session_state[ldr_key] not in ts_map:
        st.session_state[ldr_key] = ts_labels[0]

    chosen = st.select_slider(
        "⏱ Time within window",
        options=ts_labels,
        value=st.session_state[ldr_key],
        key=f"__ldr_{ldr_key}",
    )
    st.session_state[ldr_key] = chosen
    t_sel = ts_map[chosen]

    # Compute states
    er3_st  = get_book_state_at(er3_df,   t_sel)
    i_st    = get_book_state_at(i_df,     t_sel)
    lois_st = get_book_state_at(lois_ref, t_sel)

    # Live synthetic metrics
    if er3_st and i_st:
        sb = i_st['bid']  - er3_st['ask']
        sa = i_st['ask']  - er3_st['bid']
        ab = lois_st['bid'] if lois_st else np.nan
        aa = lois_st['ask'] if lois_st else np.nan
        sc = st.columns(4)
        sc[0].metric("Synth Bid  (I_bid − ER3_ask)", f"{sb:.4f}")
        sc[1].metric("Synth Ask  (I_ask − ER3_bid)", f"{sa:.4f}")
        sc[2].metric("Actual LOIS Bid", f"{ab:.4f}" if not np.isnan(ab) else "–")
        sc[3].metric("Actual LOIS Ask", f"{aa:.4f}" if not np.isnan(aa) else "–")

    # ← KEY FIX: use components.v1.html() instead of st.markdown()
    # ── Compute arrow targets ──
    # BID instance (long synthetic LOIS):
    #   ER3 → selling ER3 at best bid  → arrow on ER3 bid price, side='bid'
    #   I   → buying  I   at best ask  → arrow on I   ask price, side='ask'
    #   LOIS → the synthetic bid price = I_bid − ER3_ask
    # ASK instance (short synthetic LOIS):
    #   ER3 → buying  ER3 at best ask  → arrow on ER3 ask price, side='ask'
    #   I   → selling I   at best bid  → arrow on I   bid price, side='bid'
    #   LOIS → the synthetic ask price = I_ask − ER3_bid
    direction = inst['direction']
    if direction == "BID":
        er3_arrow_px   = er3_st['bid']  if er3_st  else None
        er3_arrow_side = 'bid'
        i_arrow_px     = i_st['ask']    if i_st    else None
        i_arrow_side   = 'ask'
        lois_arrow_px  = inst['synth_bid_px'] if not np.isnan(inst['synth_bid_px']) else None
        lois_arrow_side = 'synth'
    else:
        er3_arrow_px   = er3_st['ask']  if er3_st  else None
        er3_arrow_side = 'ask'
        i_arrow_px     = i_st['bid']    if i_st    else None
        i_arrow_side   = 'bid'
        lois_arrow_px  = inst['synth_ask_px'] if not np.isnan(inst['synth_ask_px']) else None
        lois_arrow_side = 'synth'

    # Estimate iframe height
    max_rows = max(
        (len(er3_st['ask_levels']) + len(er3_st['bid_levels']))  if er3_st  else 2,
        (len(i_st['ask_levels'])   + len(i_st['bid_levels']))    if i_st    else 2,
        (len(lois_st['ask_levels'])+ len(lois_st['bid_levels'])) if lois_st else 2,
    )
    iframe_h = max(200, 95 + 22 * max_rows + 30)

    components.html(
        render_ladder_iframe(
            er3_st, i_st, lois_st, chosen,
            er3_arrow=er3_arrow_px,   er3_arrow_side=er3_arrow_side,
            i_arrow=i_arrow_px,       i_arrow_side=i_arrow_side,
            lois_arrow=lois_arrow_px, lois_arrow_side=lois_arrow_side,
        ),
        height=iframe_h,
        scrolling=False,
    )

    st.info(
        f"ℹ️  **Why this instance? — LOIS book imbalance is not the signal.**\n\n"
        f"The **{ratio:.1f}× ratio** threshold is checked against *trade-flow* on the outrights: "
        f"`synth_BID_vol = ER3_bid_hits + I_ask_lifts = "
        f"{inst['er3_bid_vol']:.0f} + {inst['i_ask_vol']:.0f} = {inst['synth_bid_vol']:.0f}` vs "
        f"`synth_ASK_vol = ER3_ask_lifts + I_bid_hits = "
        f"{inst['er3_ask_vol']:.0f} + {inst['i_bid_vol']:.0f} = {inst['synth_ask_vol']:.0f}` "
        f"→ ratio **{inst['ratio']:.2f}×**. "
        f"The LOIS ladder shows the *resting* order book for reference only — its bid/ask sizes "
        f"are passive liquidity and are independent of the signal condition.",
        icon=None,
    )

    # ── T&S VISUALIZER ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        f"#### 📈 Time & Sales &nbsp;"
        f"<small style='color:#8b949e;'>({2*window_mins:.1f}-min window centred on instance start)</small>",
        unsafe_allow_html=True,
    )
    st.caption("🔴 Ask lift  🟢 Bid hit  ⚪ Other  |  Dot size ∝ lot size  |  dashed = instance start")
    st.plotly_chart(
        make_ts_fig(er3_df, i_df, lois_ref, inst['t_start'], window_mins),
        use_container_width=True, key=f"ts_{h}_{si}",
    )

    # ── Raw data ─────────────────────────────────────────────────────────────
    with st.expander("📋 Raw T&S data for this window"):
        tc1, tc2, tc3 = st.columns(3)
        for df_s, lbl, col in [(win_er3,"ER3",tc1),(win_i,"I",tc2),(win_lois,"LOIS",tc3)]:
            t_df = df_s[df_s['Volume'].notna() & (df_s['Volume'] > 0)]
            show = [c for c in ['Timestamp','Last Trade','Volume','Bid','Ask','Conditions']
                    if c in t_df.columns]
            col.markdown(f"**{lbl}** — {len(t_df)} trades")
            col.dataframe(t_df[show].head(80), hide_index=True,
                          height=240, use_container_width=True)
