"""A-share quant research dashboard (D1.7, phase 3).

Run from project root: python3 -m streamlit run dashboard_app.py
Read-only: no project data files are modified.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / 'data' / 'clean'
FACTORS = ROOT / 'data' / 'factors'
PAGES = ['Overview', 'Factor Library', 'Strategy', 'Liquidity & Capacity',
         'Risk Control', 'Attribution', 'Holdings & Trades', 'Limitations & Methods']

st.set_page_config(page_title='A-Share Quant Research', page_icon='📈', layout='wide')

@st.cache_data(show_spinner=False, max_entries=4)
def load_panel(path_str, stamp):
    df = pd.read_parquet(path_str)
    df.index = pd.to_datetime(df.index)
    return df.sort_index()

def panel(path):
    if not path.is_file():
        st.warning(f'Missing local data: {path.relative_to(ROOT)}')
        return None
    try:
        return load_panel(str(path), path.stat().st_mtime_ns)
    except Exception as exc:
        st.error(f'Could not read {path.name}: {exc}')
        return None

def valid_fraction(df):
    if df is None or df.empty:
        return float('nan')
    numeric = df.select_dtypes(include='number')
    if numeric.empty:
        return float('nan')
    values = numeric.to_numpy(copy=False)
    return float(np.isfinite(values).mean())

def fmt_pct(x):
    return 'N/A' if not np.isfinite(x) else f'{x:.1%}'

def date_slice(df, start, end):
    return df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]

def plot_series(series, title, yaxis=None):
    fig = px.line(x=series.index, y=series.to_numpy(), labels={'x': 'Date', 'y': yaxis or 'Value'}, title=title)
    fig.update_layout(margin=dict(l=10, r=10, t=45, b=10))
    st.plotly_chart(fig, use_container_width=True)

@st.cache_data(show_spinner=False, max_entries=12)
def load_report(path_str, stamp):
    return pd.read_csv(path_str, low_memory=False)

def report(folder, filename):
    path = ROOT / 'reports' / folder / filename
    if not path.is_file():
        st.warning(f'Missing report: reports/{folder}/{filename}')
        return None
    try:
        return load_report(str(path), path.stat().st_mtime_ns)
    except Exception as exc:
        st.error(f'Unable to load {filename}: {exc}')
        return None

def identify_date(df):
    for col in df.columns:
        if str(col).lower() in ('date', 'trade_date', 'datetime', 'time', 'dt', '日期'):
            parsed = pd.to_datetime(df[col], errors='coerce')
            if parsed.notna().sum() >= max(2, len(df)//2):
                return col, parsed
    return None, None

def numeric_candidates(df):
    result = []
    for col in df.columns:
        values = pd.to_numeric(df[col], errors='coerce')
        if values.notna().sum() >= 2:
            result.append(col)
    return result

def csv_explorer(folder, filenames, key):
    available = [f for f in filenames if (ROOT/'reports'/folder/f).is_file()]
    if not available:
        st.warning(f'No matching CSV reports in reports/{folder}/. The original reports have not been modified.')
        return
    selected = st.selectbox('Report file', available, key=key)
    df = report(folder, selected)
    if df is None:
        return
    st.caption(f'Source: reports/{folder}/{selected} · {len(df):,} rows × {len(df.columns)} columns · read-only')
    if df.empty:
        st.warning('The CSV is empty.')
        return
    date_col, dates = identify_date(df)
    numerics = numeric_candidates(df)
    st.write('Columns:', ', '.join(map(str, df.columns)))
    if numerics:
        chosen = st.selectbox('Numeric field to plot', numerics, key=f'{key}_metric')
        values = pd.to_numeric(df[chosen], errors='coerce').replace([np.inf, -np.inf], np.nan)
        if date_col:
            plot_df = pd.DataFrame({'Date': dates, 'Value': values}).dropna().sort_values('Date')
            if not plot_df.empty:
                fig = px.line(plot_df, x='Date', y='Value', title=f'{selected}: {chosen}')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info('No verified date column detected. Showing numeric distribution rather than inventing a time axis.')
            fig = px.histogram(x=values.dropna(), nbins=45, title=f'{selected}: {chosen}')
            st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df.head(500), use_container_width=True, hide_index=True)
    st.download_button('Export selected source CSV', data=(ROOT/'reports'/folder/selected).read_bytes(),
                       file_name=selected, mime='text/csv', key=f'{key}_download')


st.sidebar.title('Quant Research Dashboard')
page = st.sidebar.radio('Navigation', PAGES)
st.sidebar.caption('Local data only · read-only')
st.title(page)
st.caption('Shanghai & Shenzhen A-shares | local 2018–2024 data where available | D1.7 phase 3')

if page == 'Overview':
    close = panel(CLEAN / 'close_hfq.parquet')
    if close is not None:
        if close.empty:
            st.warning('Close-price panel is empty.')
        else:
            st_date, end_date = close.index.min().date(), close.index.max().date()
            start, end = st.date_input('Date range', (st_date, end_date), min_value=st_date, max_value=end_date)
            if start > end:
                st.error('Start date must not exceed end date.')
                st.stop()
            close = date_slice(close, start, end)
            if close.empty:
                st.info('No trading days in selected range.')
            else:
                numeric = close.select_dtypes(include='number')
                finite = np.isfinite(numeric.to_numpy(copy=False))
                daily_valid = pd.Series(finite.sum(axis=1), index=numeric.index, name='Stocks with valid prices')
                c1, c2, c3, c4 = st.columns(4)
                c1.metric('Stocks in panel', f'{close.shape[1]:,}')
                c2.metric('Trading dates', f'{len(close):,}')
                c3.metric('Valid price cells', fmt_pct(valid_fraction(close)))
                c4.metric('Factor files', len(list(FACTORS.glob('*.parquet'))))
                plot_series(daily_valid, 'Daily valid close-price coverage', 'Number of stocks')
                st.caption('Valid = finite numeric price. This does not imply the stock is tradable on that day.')
    st.subheader('Local dataset inventory')
    inventory = []
    for folder in [CLEAN, FACTORS]:
        for path in sorted(folder.glob('*.parquet')):
            inventory.append({'category': folder.name, 'file': path.name, 'size_MB': round(path.stat().st_size / (1024 ** 2), 2)})
    st.dataframe(pd.DataFrame(inventory), use_container_width=True, hide_index=True)

elif page == 'Factor Library':
    files = sorted(FACTORS.glob('*.parquet'))
    st.metric('Available factor files', len(files))
    if not files:
        st.warning('No factor parquet files found.')
    else:
        name = st.selectbox('Factor', [p.stem for p in files])
        factor = panel(FACTORS / f'{name}.parquet')
        if factor is not None and not factor.empty:
            d0, d1 = factor.index.min().date(), factor.index.max().date()
            dates = st.date_input('Factor date range', (d0, d1), min_value=d0, max_value=d1, key='factor_dates')
            if len(dates) != 2:
                st.info('Select both dates.')
                st.stop()
            sliced = date_slice(factor, *dates)
            if sliced.empty:
                st.info('No factor observations in selected range.')
            else:
                num = sliced.select_dtypes(include='number')
                finite = np.isfinite(num.to_numpy(copy=False))
                c1, c2, c3 = st.columns(3)
                c1.metric('Stock columns', sliced.shape[1])
                c2.metric('Trading dates', len(sliced))
                c3.metric('Valid factor cells', fmt_pct(valid_fraction(sliced)))
                daily_coverage = pd.Series(finite.mean(axis=1), index=num.index)
                plot_series(daily_coverage, f'{name} — daily valid-cell fraction', 'Valid fraction')
                last_row = num.iloc[-1].replace([np.inf, -np.inf], np.nan).dropna()
                if not last_row.empty:
                    fig = px.histogram(x=last_row.to_numpy(), nbins=50, title=f'{name} — distribution on {num.index[-1].date()}', labels={'x': 'Factor value'})
                    st.plotly_chart(fig, use_container_width=True)
                st.dataframe(sliced.iloc[:10, :min(15, sliced.shape[1])], use_container_width=True)
                st.caption('Coverage describes data presence, not predictive validity or factor IC.')

elif page == 'Liquidity & Capacity':
    amount = panel(CLEAN / 'amount.parquet')
    stv = panel(CLEAN / 'is_st.parquet')
    if amount is not None and not amount.empty:
        latest = amount.index.max()
        chosen = st.selectbox('Trading date', list(amount.index[::-1]), format_func=lambda x: x.strftime('%Y-%m-%d'))
        row = pd.to_numeric(amount.loc[chosen], errors='coerce')
        row = row.replace([np.inf, -np.inf], np.nan)
        positive = row[row > 0]
        c1, c2, c3 = st.columns(3)
        c1.metric('Stocks in panel', len(row))
        c2.metric('Positive reported amount', len(positive))
        c3.metric('Positive-amount coverage', fmt_pct(len(positive) / len(row) if len(row) else float('nan')))
        if not positive.empty:
            fig = px.histogram(x=np.log10(positive.to_numpy()), nbins=55,
                               title='Daily trading amount distribution (positive values only)',
                               labels={'x': 'log10(reported amount)'})
            st.plotly_chart(fig, use_container_width=True)
            st.caption('Amount units follow the upstream dataset; no currency conversion or capacity estimate is assumed.')
        lookback = st.slider('Rolling average amount window (trading days)', 5, 60, 20, 5)
        cutoff = st.slider('Exclude bottom percentile of positive rolling average', 0, 50, 20, 5)
        trailing = amount.loc[:chosen].tail(lookback).apply(pd.to_numeric, errors='coerce')
        if len(trailing) < lookback:
            st.warning('Not enough history for a full rolling window; results below are not calculated.')
        else:
            avg = trailing.where(trailing > 0).mean(axis=0)
            eligible = avg.notna() & (avg > 0) & row.gt(0)
            if stv is not None and chosen in stv.index:
                eligible &= ~stv.loc[chosen].reindex(avg.index).fillna(True).astype(bool)
            threshold = avg[eligible].quantile(cutoff / 100) if eligible.any() else np.nan
            passed = eligible & avg.ge(threshold) if np.isfinite(threshold) else eligible & False
            st.metric('Liquidity-screen candidates (not a tradeable universe)', int(passed.sum()))
            st.caption('Screen uses current and trailing values only; it is descriptive, not a point-in-time executable trade list. Suspensions, listing age, limit rules and trade execution constraints require separate checks.')
            table = pd.DataFrame({'stock': avg.index, 'amount_today': row.reindex(avg.index).to_numpy(),
                                  'rolling_mean_amount': avg.to_numpy(), 'screen_pass': passed.to_numpy()})
            st.dataframe(table.sort_values('rolling_mean_amount', ascending=False).head(100), hide_index=True, use_container_width=True)
    else:
        st.info('Trading amount panel is unavailable.')

elif page == 'Strategy':
    st.warning('Historical research results only. Extremely high reported Sharpe ratios have not been independently audited.')
    st.subheader('Portfolio NAV and performance')
    tab1, tab2 = st.tabs(['NAV series', 'Performance / comparisons'])
    with tab1:
        folder = 'week4' if (ROOT/'reports/week4/nav_all.csv').is_file() else 'week3'
        csv_explorer(folder, ['nav_all.csv'], 'strategy_nav')
    with tab2:
        folder = st.selectbox('Report period', ['week4', 'week3'], key='strategy_period')
        csv_explorer(folder, ['bt_compare_FINAL.csv','bt_summary.csv','perf_all.csv','yearly_EW_FINAL2.csv'], 'strategy_perf')

elif page == 'Risk Control':
    st.subheader('Drawdown and tail-risk reports')
    csv_explorer('week4', ['drawdown_episodes_FINAL.csv','tail_stats_FINAL.csv',
                           'cost_sensitivity.csv','variants_eval.csv'], 'risk')
    st.caption('Drawdown episodes and tail summaries are descriptive. A daily drawdown curve requires a verified NAV definition and frequency.')

elif page == 'Attribution':
    st.subheader('Factor and industry attribution')
    csv_explorer('week4', ['factor_attr_FINAL.csv','factor_contrib_period_FINAL.csv',
                           'brinson_industry_FINAL.csv','brinson_period_FINAL.csv',
                           'brinson_summary_FINAL.csv'], 'attrib')
    st.caption('Attribution units, sign conventions and residual reconciliation must be checked against the source methodology.')

elif page == 'Holdings & Trades':
    st.subheader('Portfolio holdings and execution records')
    folder = st.selectbox('Report period', ['week4','week3'], key='holdings_period')
    if folder == 'week4':
        names = ['holdings_FINAL.csv','trades_FINAL.csv','te_shares_FINAL.csv','selection_record.csv']
    else:
        names = ['holdings_EW_FINAL2.csv','holdings_BASE.csv','holdings_EW.csv',
                 'holdings_IC.csv','holdings_IR.csv','holdings_LASSO.csv','holdings_XGB.csv',
                 'trades_IC.csv','rebalance_EW_FINAL2.csv']
    csv_explorer(folder, names, 'holdings')
    st.caption('Displayed trade records are research outputs, not brokerage-confirmed fills.')
else:
    st.caption('Research governance | Methodology, assumptions, validation status and reproducibility')
    st.info('This page documents the research framework and known limitations. It does not certify that every listed control has been implemented or independently audited.')

    st.subheader('1. Research scope & data lineage')
    a, b, c = st.columns(3)
    a.metric('Market', 'China A-shares')
    b.metric('Historical coverage', '2018–2024*')
    c.metric('Online dataset', 'Reduced extract')
    st.caption('*Date availability varies by panel. The online deployment may contain only up to 250 stocks and the latest 500 trading days; it is not the complete historical research universe.')
    st.markdown('''**Universe definition:** Shanghai and Shenzhen A-share panels available in the local research environment. A stock appearing in a panel does not establish its eligibility or tradability on a given date.

**Source format:** Local Parquet matrices indexed by trading date and stock identifier; backtest and analysis outputs are stored as CSV reports. The online app reads these files without altering them.

**Data lineage caution:** Adjustment conventions, corporate actions, publication timestamps, vendor definitions, and point-in-time membership require source-level verification.''')

    st.subheader('2. Research workflow')
    st.markdown('''**Data checks → Factor research → Portfolio construction → Historical backtest → Risk and cost analysis → Interpretation**

- **Data checks:** Inspect missing observations, panel coverage, date alignment and stock identifiers.
- **Factor research:** Examine factor distributions and availability. Coverage is not evidence of predictive power.
- **Portfolio construction:** Interpret weighting and rebalancing assumptions from the corresponding source code and strategy reports.
- **Backtesting:** Compare NAV, performance and yearly outputs where source reports exist; do not treat simulated fills as actual trades.
- **Evaluation:** Review drawdowns, turnover, costs, capacity proxies and attribution residuals where available.''')

    st.subheader('3. Known limitations and possible effects')
    limitations = pd.DataFrame([
        ('Look-ahead / point-in-time bias', 'Fundamental data may be aligned to reporting periods rather than public availability dates.', 'Could overstate historical predictive performance.', 'Verify announcement dates, lags and rolling-window boundaries.'),
        ('Survivorship / universe selection', 'Historical universe membership and delisted securities may be incomplete.', 'Can distort returns and risk estimates.', 'Reconstruct historical eligible universes and delisting treatment.'),
        ('Suspensions, ST and price limits', 'Panel presence does not imply executable buy or sell orders.', 'Simulated trades may be infeasible.', 'Validate daily tradability, ST, suspensions and limit-up/down rules.'),
        ('Transaction costs and slippage', 'Assumed fees and execution prices may differ from actual conditions.', 'Net performance can be overstated.', 'Stress-test cost scenarios and turnover; model realistic execution.'),
        ('Liquidity and capacity', 'Reported trading amount is a screening proxy, not executable capacity.', 'Large orders may face impact and fill constraints.', 'Verify units, participation limits and market impact.'),
        ('Corporate actions and adjustments', 'Price adjustment methodology may vary by source.', 'Can distort returns and signal construction.', 'Audit split/dividend handling and adjustment conventions.'),
        ('Multiple testing / overfitting', 'Factor and parameter selection may reuse the same historical sample.', 'Selected strategies can appear stronger than they generalize.', 'Use independent out-of-sample and walk-forward evaluations.'),
        ('Market regimes and tail events', 'Historical sample covers a finite set of market conditions.', 'Drawdown and tail risk may be underestimated.', 'Assess stress windows, annual stability and downside measures.'),
        ('Reduced online data extract', 'Web display may use a 250-stock / 500-day subset.', 'Coverage and distribution statistics differ from the full universe.', 'Clearly separate demo-panel metrics from original full-sample reports.'),
    ], columns=['Risk area','Current limitation','Potential impact','Recommended validation'])
    st.dataframe(limitations, use_container_width=True, hide_index=True)

    st.subheader('4. Interpretation of key research metrics')
    with st.expander('Factor coverage and data completeness', expanded=True):
        st.markdown('Coverage is the fraction of finite numeric cells in the selected matrix. It measures data availability, **not** factor information coefficient, significance, alpha or executable breadth.')
    with st.expander('NAV, annual return, Sharpe and maximum drawdown'):
        st.markdown('These are descriptive statistics of a historical simulated equity curve. Their meaning depends on return frequency, benchmark, annualization convention, costs and sample window. They do not imply guaranteed future returns.')
    with st.expander('Liquidity screen and capacity'):
        st.markdown('Positive trading amount and rolling-average amount support exploratory filtering only. Units and order-size assumptions must be verified before estimating implementable capacity.')
    with st.expander('Attribution and reconciliation'):
        st.markdown('Factor/industry attribution depends on chosen exposures, grouping conventions and return definitions. Check residuals and accounting consistency against the original reports.')

    st.subheader('5. Validation checklist')
    checks = pd.DataFrame([
        ('Source files are read-only in the dashboard', 'Implemented in dashboard design'),
        ('Missing-file messages are surfaced', 'Implemented in dashboard design'),
        ('Factor data coverage is explicitly distinguished from predictive validity', 'Documented'),
        ('Historical panel membership checked against daily tradability', 'Not independently verified'),
        ('Point-in-time financial disclosures and look-ahead checks', 'Not independently verified'),
        ('Full survivorship-free historical universe', 'Not independently verified'),
        ('Execution feasibility and live brokerage fills', 'Not independently verified'),
        ('Independent out-of-sample performance validation', 'Not established by this dashboard'),
        ('Full-sample equivalence of reduced online extract', 'Not applicable: reduced extract'),
    ], columns=['Control / question', 'Current status'])
    st.dataframe(checks, use_container_width=True, hide_index=True)

    st.subheader('6. Reproducibility & disclosure')
    st.markdown('''To reproduce a displayed result, record the **data version**, **strategy source-code version**, **date range**, **factor list**, **universe definition**, **rebalancing settings**, **cost assumptions**, and **output CSV filename**. Where a source report is unavailable, the dashboard should show a missing-data notice rather than substitute synthetic performance.

**Disclosure:** This application is an educational research demonstration. It is not investment advice. Backtested returns are hypothetical, have not been independently audited, and may not be attainable in live trading.''')
