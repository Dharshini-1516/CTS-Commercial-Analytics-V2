"""
===============================================================================
Enterprise Commercial Analytics Platform - Streamlit Dashboard UI
Commercial Analytics Market Share & Share-Shift Tracker
===============================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.config import DATASET_PATH
from src.pipeline_runner import run_end_to_end_pipeline
from src.forecasting_engine import forecast_brand_market_share
from src.market_share_engine import calculate_market_share
from src.share_shift_engine import calculate_share_shifts
from src.anomaly_engine import detect_statistical_anomalies
from src.alert_engine import generate_market_alerts
from src.llm_agent import answer_chatbot_question

# Page Configuration
st.set_page_config(
    page_title="Commercial Market Share & Share-Shift Tracker",
    page_icon="📈",
    layout="wide"
)

import os

# Dynamic cache refresh to fetch market analytics data from local storage
@st.cache_data(ttl=2, show_spinner="Fetching Market Analytics Data from Local Storage...")
def get_initial_pipeline_data():
    from src.local_db import local_warehouse
    return local_warehouse.fetch_clean_data_from_local()

if st.sidebar.button("🔄 Fetch Latest Market Data", help="Fetch latest market feed and recompute local analytics engine"):
    st.cache_data.clear()
    st.rerun()



initial_data = get_initial_pipeline_data()

base_cleaned_df = initial_data['cleaned_df']
base_gold_df = initial_data['gold_df']
base_alerts_df = initial_data['active_alerts_df']

# Sidebar Analytics Controls
st.sidebar.markdown("---")
st.sidebar.title("🎛️ Analytics Controls")
st.sidebar.markdown("---")

# Dynamic Company & Competitor Selection
all_brands = sorted(base_gold_df['clean_brand'].unique().tolist())
company_brand = st.sidebar.selectbox("Selected Company", options=all_brands, index=0)

default_competitors = [b for b in all_brands if b != company_brand][:3]
selected_competitors = st.sidebar.multiselect(
    "Selected Competitors",
    options=[b for b in all_brands if b != company_brand],
    default=default_competitors
)

st.sidebar.markdown("---")
# Market Denominator Mode Toggle
denom_mode = st.sidebar.radio(
    "Market Denominator Mode",
    options=["Full Market Segment", "Selected Competitive Set Only"],
    index=0
)

# Propagate Competitor Selection through ENTIRE Pipeline
if denom_mode == "Selected Competitive Set Only" and len(selected_competitors) > 0:
    active_set = [company_brand] + selected_competitors
    ms_df, _ = calculate_market_share(base_cleaned_df, selected_brands=active_set)
    shift_df = calculate_share_shifts(ms_df)
    gold_df = detect_statistical_anomalies(shift_df)
    _, active_alerts_df = generate_market_alerts(gold_df)
else:
    gold_df = base_gold_df
    active_alerts_df = base_alerts_df

st.sidebar.markdown("---")
# Region & Dynamic TA Filters
all_regions = ["All Regions"] + sorted(gold_df['clean_region'].unique().tolist())
sel_region = st.sidebar.selectbox("Select State / Region", options=all_regions, index=0)

company_tas = sorted(gold_df[gold_df['clean_brand'] == company_brand]['clean_therapeutic_area'].unique().tolist())
all_tas = ["All Therapeutic Areas"] + company_tas
sel_ta = st.sidebar.selectbox("Select Therapeutic Area", options=all_tas, index=0)

st.sidebar.markdown("---")
# Single-Week Input Controls (Dynamic Year & ISO Week Input)
all_weeks = sorted(gold_df['year_week'].unique().tolist())
all_years = sorted(list(set([w.split('-')[0] for w in all_weeks])), reverse=True)
sel_year = st.sidebar.selectbox("Select Year", options=all_years, index=0, key="sb_sel_year")

# Dynamically adapt available ISO weeks to the chosen year (sorted chronologically W01 to W52)
avail_weeks = sorted([w for w in all_weeks if w.startswith(sel_year)], key=lambda x: int(x.split('-W')[1]))

selected_yw = st.sidebar.selectbox(
    f"Select ISO Week in {sel_year}",
    options=avail_weeks,
    index=0,
    key=f"sb_week_picker_{sel_year}"
)

# Apply Region & TA Filters to Gold Dataset
filtered_df = gold_df.copy()
if sel_region != "All Regions":
    filtered_df = filtered_df[filtered_df['clean_region'] == sel_region]
if sel_ta != "All Therapeutic Areas":
    filtered_df = filtered_df[filtered_df['clean_therapeutic_area'] == sel_ta]

# Extract Data for the Specific Input Week
week_df = filtered_df[filtered_df['year_week'] == selected_yw].copy()

# Filter Alert Engine Dataset for the Selected Parameters
company_alerts_df = active_alerts_df[active_alerts_df['clean_brand'] == company_brand].copy()
if sel_region != "All Regions":
    company_alerts_df = company_alerts_df[company_alerts_df['clean_region'] == sel_region]
if sel_ta != "All Therapeutic Areas":
    company_alerts_df = company_alerts_df[company_alerts_df['clean_therapeutic_area'] == sel_ta]

week_alerts_df = company_alerts_df[company_alerts_df['year_week'] == selected_yw].copy()

# Main Dashboard Title
st.title("📈 Commercial Market Share & Share-Shift Tracker")
st.caption(f"Enterprise Weekly Analytics Platform — Viewing Metrics for **{selected_yw}**")

# Top KPI Summary Cards (Specific to the Selected Input Week)
col1, col2, col3, col4 = st.columns(4)

# 1. Selected Week Label
col1.metric("Input Target Week", selected_yw)

# 2. Total Segment Volume TRX for Selected Week
total_market_trx = week_df['clean_trx'].sum() if not week_df.empty else 0.0
col2.metric(f"Total Segment Volume ({selected_yw})", f"{total_market_trx:,.0f} TRX")

# 3. Company Market Share % for Selected Week (TRx-Weighted Aggregation against Total Market TRX)
comp_week = week_df[week_df['clean_brand'] == company_brand].copy()
total_week_market_trx = week_df['brand_trx'].sum() if not week_df.empty else 0.0
if not comp_week.empty and total_week_market_trx > 0:
    curr_share = (comp_week['brand_trx'].sum() / total_week_market_trx) * 100.0
else:
    curr_share = 0.0
col3.metric(f"{company_brand} Share ({selected_yw})", f"{curr_share:.2f}%")

# 4. WoW Share Shift (pp) for Selected Week (TRx-Weighted Shift)
if comp_week.empty or pd.isna(comp_week['share_shift_pp'].mean()):
    curr_shift_pp = 0.0
    shift_str = "0.00 pp"
    delta_str = "Baseline Week"
else:
    curr_shift_pp = float(comp_week['share_shift_pp'].mean())
    shift_str = f"{curr_shift_pp:+.2f} pp"
    delta_str = f"{curr_shift_pp * 100:+.0f} bps"

col4.metric(
    f"WoW Share Shift ({selected_yw})",
    shift_str,
    delta=delta_str,
    delta_color="normal" if curr_shift_pp >= 0 else "inverse"
)

st.markdown("---")

# Main Tabs (4 Distinct Tabs)
tab1, tab2, tab3, tab4 = st.tabs([
    f"📉 Market Trends & Share for {selected_yw}",
    f"🚨 Regional Share Shift & Alert Breakdown ({selected_yw})",
    "🔮 ARIMA Time-Series Forecast",
    "💬 GenAI Commercial Assistant"
])

with tab1:
    st.subheader(f"Weekly Market Trajectory & Share Breakdown (up to {selected_yw})")
    st.caption("Competitive brand share trajectory leading up to the selected week")
    
    view_brands = [company_brand] + selected_competitors
    
    # Take trailing 12 weeks of history up to selected_yw
    all_weeks_sorted = sorted(filtered_df['year_week'].unique())
    if selected_yw in all_weeks_sorted:
        target_idx = all_weeks_sorted.index(selected_yw)
        start_idx = max(0, target_idx - 11)
        trailing_weeks = all_weeks_sorted[start_idx : target_idx + 1]
    else:
        trailing_weeks = [selected_yw]
        
    sub_trend = filtered_df[
        filtered_df['clean_brand'].isin(view_brands) &
        filtered_df['year_week'].isin(trailing_weeks)
    ].copy()
    
    # Fallback to trailing weeks if range is small
    if sub_trend.empty or len(sub_trend['year_week'].unique()) < 2:
        sub_trend = filtered_df[
            filtered_df['clean_brand'].isin(view_brands) &
            (filtered_df['year_week'] <= selected_yw)
        ].copy()
        all_w = sorted(sub_trend['year_week'].unique().tolist())
        if len(all_w) > 26:
            sub_trend = sub_trend[sub_trend['year_week'].isin(all_w[-26:])]
            
    # TRx-Weighted Market Share Aggregation against Total Market TRX in filtered_df
    week_totals_map = filtered_df[filtered_df['year_week'].isin(sub_trend['year_week'].unique())].groupby('year_week')['brand_trx'].sum().to_dict()
    
    trend_agg = (
        sub_trend
        .groupby(['year_week', 'clean_brand'])['brand_trx']
        .sum()
        .reset_index()
    )
    trend_agg['total_market_trx'] = trend_agg['year_week'].map(week_totals_map)
    trend_agg['market_share_trx_pct'] = np.where(
        trend_agg['total_market_trx'] > 0,
        (trend_agg['brand_trx'] / trend_agg['total_market_trx']) * 100.0,
        0.0
    )
    trend_df = trend_agg[['year_week', 'clean_brand', 'market_share_trx_pct']]
    
    ordered_weeks = sorted(trend_df['year_week'].unique().tolist())
    trend_df['year_week'] = pd.Categorical(trend_df['year_week'], categories=ordered_weeks, ordered=True)
    trend_df = trend_df.sort_values('year_week')
    
    color_map = {company_brand: "#6366f1"}
    palette = ["#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"]
    for i, b in enumerate(selected_competitors):
        color_map[b] = palette[i % len(palette)]
        
    fig_trend = px.line(
        trend_df,
        x='year_week',
        y='market_share_trx_pct',
        color='clean_brand',
        color_discrete_map=color_map,
        labels={'year_week': 'ISO Year-Week', 'market_share_trx_pct': 'Market Share %', 'clean_brand': 'Brand'},
        category_orders={'year_week': ordered_weeks}
    )
    
    fig_trend.update_traces(line=dict(width=2))
    if company_brand in trend_df['clean_brand'].values:
        fig_trend.update_traces(selector=dict(name=company_brand), line=dict(width=4))
        
    fig_trend.update_layout(template="plotly_dark", height=450, hovermode="x unified")
    st.plotly_chart(fig_trend, use_container_width=True, key="fig_trend_chart_view")

with tab2:
    st.subheader(f"🚨 Regional Share Shift & Alert Summary for {company_brand} ({selected_yw})")
    st.caption(f"Region-by-region market share breakdown strictly evaluated for your selected week: **{selected_yw}**")
    
    # Filter active alerts for selected week and company brand
    week_alerts = active_alerts_df[
        (active_alerts_df['year_week'] == selected_yw) & 
        (active_alerts_df['clean_brand'] == company_brand)
    ].copy() if not active_alerts_df.empty else pd.DataFrame()
    
    if not week_alerts.empty and 'alert_category' in week_alerts.columns:
        declines_df = week_alerts[
            week_alerts['alert_category'] == 'REGIONAL SHARE DECLINE'
        ].sort_values('share_shift_pp', ascending=True)
        
        gains_df = week_alerts[
            week_alerts['alert_category'] == 'REGIONAL GROWTH SPIKE'
        ].sort_values('share_shift_pp', ascending=False)
    else:
        declines_df = pd.DataFrame()
        gains_df = pd.DataFrame()
    
    decline_region_list = sorted(declines_df['clean_region'].unique().tolist()) if not declines_df.empty and 'clean_region' in declines_df.columns else []
    growth_region_list = sorted(gains_df['clean_region'].unique().tolist()) if not gains_df.empty and 'clean_region' in gains_df.columns else []
    
    t2_summary_col1, t2_summary_col2 = st.columns(2)
    with t2_summary_col1:
        if decline_region_list:
            st.error(f"🔴 **High Alert Decline Regions ({selected_yw}):** {', '.join(decline_region_list)}")
        else:
            st.success(f"🔴 **High Alert Decline Regions ({selected_yw}):** None")
            
    with t2_summary_col2:
        if growth_region_list:
            st.success(f"🟢 **Positive Growth Regions ({selected_yw}):** {', '.join(growth_region_list)}")
        else:
            st.info(f"🟢 **Positive Growth Regions ({selected_yw}):** None")
            
    st.markdown("---")
    
    t2_col1, t2_col2 = st.columns(2)
    
    with t2_col1:
        st.markdown(f"#### 🔴 Regional Share Declines ({selected_yw})")
        st.caption("Regions where your company experienced negative share erosion in this week")
        if not declines_df.empty:
            d_cols = [c for c in ['clean_region', 'clean_therapeutic_area', 'market_share_trx_pct', 'share_shift_pp', 'share_shift_bps', 'clean_trx'] if c in declines_df.columns]
            st.dataframe(
                declines_df[d_cols],
                use_container_width=True
            )
        else:
            st.info(f"No regional share declines recorded for {selected_yw}.")
            
    with t2_col2:
        st.markdown(f"#### 🟢 Regional Growth Spikes ({selected_yw})")
        st.caption("Regions where your company achieved positive share growth in this week")
        if not gains_df.empty:
            g_cols = [c for c in ['clean_region', 'clean_therapeutic_area', 'market_share_trx_pct', 'share_shift_pp', 'share_shift_bps', 'clean_trx'] if c in gains_df.columns]
            st.dataframe(
                gains_df[g_cols],
                use_container_width=True
            )
        else:
            st.info(f"No regional growth spikes recorded for {selected_yw}.")

with tab3:
    selected_reg = sel_region
    st.subheader(f"ARIMA Time-Series Future Forecast for {company_brand} & Competitive Set ({selected_reg})")
    
    h_col1, _ = st.columns([1, 2])
    with h_col1:
        forecast_horizon = st.slider("Select Forecast Horizon (Weeks Ahead)", min_value=2, max_value=26, value=8, step=2)
        
    st.caption(f"{forecast_horizon}-Week future market share projection for competitive set starting from trajectory up to {selected_yw}")
    
    view_brands = [company_brand] + selected_competitors
    fig_forecast = go.Figure()
    
    color_map = {company_brand: "#6366f1"}
    palette = ["#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"]
    for i, b in enumerate(selected_competitors):
        color_map[b] = palette[i % len(palette)]
        
    def yw_key(yw):
        try:
            parts = str(yw).split('-W')
            return (int(parts[0]), int(parts[1]))
        except Exception:
            return (0, 0)

    all_y = []
    all_weeks_set = set()
    
    for brand in view_brands:
        f_df = forecast_brand_market_share(gold_df, brand, selected_reg, forecast_horizon=forecast_horizon)
        
        if selected_reg == "All Regions":
            tot_w = gold_df[gold_df['clean_brand'] == brand].groupby('year_week')['brand_trx'].sum().reset_index()
            tot_m = gold_df.groupby('year_week')['brand_trx'].sum().to_dict()
            tot_w['total_m'] = tot_w['year_week'].map(tot_m)
            tot_w['market_share_trx_pct'] = np.where(
                tot_w['total_m'] > 0,
                (tot_w['brand_trx'] / tot_w['total_m']) * 100.0,
                0.0
            )
            tot_w['yw_sort'] = tot_w['year_week'].apply(yw_key)
            h_sub = tot_w[['year_week', 'market_share_trx_pct', 'yw_sort']].sort_values('yw_sort').tail(16)
        else:
            sub_df = gold_df[(gold_df['clean_brand'] == brand) & (gold_df['clean_region'] == selected_reg)].copy()
            sub_df['yw_sort'] = sub_df['year_week'].apply(yw_key)
            h_sub = sub_df.sort_values('yw_sort').tail(16)
            
        b_color = color_map.get(brand, "#6366f1")
        l_width = 4 if brand == company_brand else 2
        
        all_weeks_set.update(h_sub['year_week'].tolist())

        # Historical Trace
        fig_forecast.add_trace(go.Scatter(
            x=h_sub['year_week'],
            y=h_sub['market_share_trx_pct'],
            mode='lines+markers',
            name=f"{brand} (Hist)",
            line=dict(color=b_color, width=l_width)
        ))
        all_y += h_sub['market_share_trx_pct'].dropna().tolist()
        
        # Forecast Trace
        if not f_df['forecast_market_share_pp'].isna().all():
            f_df['yw_sort'] = f_df['year_week'].apply(yw_key)
            f_df = f_df.sort_values('yw_sort')
            all_weeks_set.update(f_df['year_week'].tolist())

            fig_forecast.add_trace(go.Scatter(
                x=f_df['year_week'],
                y=f_df['forecast_market_share_pp'],
                mode='lines+markers',
                name=f"{brand} ({forecast_horizon}-Wk Forecast)",
                line=dict(color=b_color, width=l_width, dash='dash')
            ))
            all_y += f_df['forecast_market_share_pp'].dropna().tolist()
            
            # Add Confidence Interval for Company Brand
            if brand == company_brand and 'upper_ci_95' in f_df and not f_df['upper_ci_95'].isna().all():
                fig_forecast.add_trace(go.Scatter(x=f_df['year_week'], y=f_df['upper_ci_95'], mode='lines', name='Company Upper 95% CI', line=dict(width=0), showlegend=False))
                fig_forecast.add_trace(go.Scatter(x=f_df['year_week'], y=f_df['lower_ci_95'], mode='lines', name='Company Lower 95% CI', fill='tonexty', fillcolor='rgba(99, 102, 241, 0.15)', line=dict(width=0)))
                all_y += f_df['upper_ci_95'].dropna().tolist() + f_df['lower_ci_95'].dropna().tolist()

    combined_weeks_list = sorted(list(all_weeks_set), key=yw_key)

    if all_y:
        min_y = max(0.0, float(min(all_y)) - 2.0)
        max_y = min(100.0, float(max(all_y)) + 2.0)
        y_range = [min_y, max_y]
    else:
        y_range = None

    fig_forecast.update_layout(
        template="plotly_dark", 
        title=f"ARIMA {forecast_horizon}-Week Market Share Forecast for Competitive Set ({selected_reg})", 
        height=450,
        yaxis=dict(range=y_range, title="Market Share %", autorange=False if y_range else True),
        xaxis=dict(categoryorder='array', categoryarray=combined_weeks_list)
    )
    st.plotly_chart(fig_forecast, use_container_width=True, key="fig_forecast_chart_view")

with tab4:
    st.subheader("💬 Commercial Intelligence GenAI Assistant")
    st.caption("Ask questions about regional share declines, competitive growth, or commercial strategy!")
    
    # Dynamic chat message greeting matching active sidebar selections
    greeting_text = f"Hello! I am your Commercial Analytics AI Agent. Ask me anything about **{company_brand}** performance in week **{selected_yw}**!"
    if "chat_messages" not in st.session_state or len(st.session_state.chat_messages) == 1:
        st.session_state.chat_messages = [
            {"role": "assistant", "content": greeting_text}
        ]
        
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if user_prompt := st.chat_input(f"Ask a question about {company_brand} in week {selected_yw}..."):
        st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)
            
        week_company_df = week_df[week_df['clean_brand'] == company_brand].copy()
        declines_df = week_company_df[week_company_df['share_shift_pp'] < 0].sort_values('share_shift_pp', ascending=True)
        gains_df = week_company_df[week_company_df['share_shift_pp'] > 0].sort_values('share_shift_pp', ascending=False)
        decline_region_list = sorted(declines_df['clean_region'].unique().tolist())
        growth_region_list = sorted(gains_df['clean_region'].unique().tolist())
        
        context_str = f"Selected Company Brand: {company_brand}\n"
        context_str += f"Target Input Week: {selected_yw}\n"
        context_str += f"Selected Region Filter: {sel_region}\n"
        context_str += f"Selected Therapeutic Area Filter: {sel_ta}\n"
        context_str += f"Current Share for {company_brand} in {selected_yw}: {curr_share:.2f}%\n"
        context_str += f"WoW Shift in {selected_yw}: {curr_shift_pp:+.2f} pp\n"
        context_str += f"Decline Region Names ({selected_yw}): {', '.join(decline_region_list)}\n"
        context_str += f"Growth Region Names ({selected_yw}): {', '.join(growth_region_list)}\n"
        context_str += f"Selected Competitors: {', '.join(selected_competitors)}\n\n"
        
        selected_reg = sel_region if sel_region != "All Regions" else all_regions[1] if len(all_regions) > 1 else "Tamil Nadu"
        forecast_summaries = []
        for b in [company_brand] + selected_competitors:
            f_df = forecast_brand_market_share(base_gold_df, b, selected_reg, forecast_horizon=4)
            if not f_df.empty and not f_df['forecast_market_share_pp'].isna().all():
                avg_f = f_df['forecast_market_share_pp'].mean()
                f_weeks = ", ".join(f_df['year_week'].tolist())
                forecast_summaries.append(f"- {b} in {selected_reg}: ARIMA Forecasted Share = {avg_f:.2f}% across {f_weeks}")
                
        context_str += "ARIMA TIME-SERIES FUTURE FORECAST PROJECTIONS:\n" + "\n".join(forecast_summaries) + "\n\n"
        context_str += f"Regional Share Declines in {selected_yw}:\n" + declines_df[['clean_region', 'share_shift_pp', 'clean_trx']].head(5).to_string() + "\n\n"
        context_str += f"Regional Growth Spikes in {selected_yw}:\n" + gains_df[['clean_region', 'share_shift_pp', 'clean_trx']].head(5).to_string()
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing regional dataset & commercial shifts..."):
                bot_reply = answer_chatbot_question(user_prompt, context_str)
                st.markdown(bot_reply)
                st.session_state.chat_messages.append({"role": "assistant", "content": bot_reply})
