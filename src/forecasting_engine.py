"""
===============================================================================
Cognizant (CTS) Nurture Placement Hackathon - Advanced ARIMA Forecasting Engine
Commercial Analytics Market Share & Share-Shift Tracker
===============================================================================
"""

import datetime
import pandas as pd
import numpy as np

try:
    from statsmodels.tsa.arima.model import ARIMA
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False

def get_next_year_weeks(latest_week_str, horizon=4):
    """
    Dynamically generates the next N year-week strings using ISO calendar arithmetic.
    Supports 52-week and 53-week ISO calendar years accurately.
    Example: 2025-W52 -> 2026-W01, 2026-W02, 2026-W03, 2026-W04
    """
    if not latest_week_str or pd.isna(latest_week_str) or '-' not in str(latest_week_str):
        return [None] * horizon
        
    try:
        parts = str(latest_week_str).split('-W')
        year = int(parts[0])
        week = int(parts[1])
        base_date = datetime.date.fromisocalendar(year, week, 1)
    except Exception:
        return [None] * horizon
        
    next_weeks = []
    curr_date = base_date
    for _ in range(horizon):
        curr_date += datetime.timedelta(days=7)
        iso_y, iso_w, _ = curr_date.isocalendar()
        next_weeks.append(f"{iso_y}-W{iso_w:02d}")
    return next_weeks

import warnings

def evaluate_arima_models(ts_data):
    """
    Evaluates candidate ARIMA orders with trend/drift parameters by AIC and returns the best model fit.
    Suppresses candidate convergence warnings silently.
    """
    candidate_configs = [
        ((1, 1, 1), 't'),
        ((1, 1, 0), 't'),
        ((2, 1, 1), 't'),
        ((1, 1, 1), 'c'),
        ((1, 1, 0), None),
        ((1, 1, 1), None)
    ]
    best_aic = float('inf')
    best_fit = None
    best_order = (1, 1, 1)
    
    for order, tr in candidate_configs:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ARIMA(ts_data, order=order, trend=tr)
                fit = model.fit()
                if fit.aic < best_aic:
                    best_aic = fit.aic
                    best_fit = fit
                    best_order = order
        except Exception:
            continue
            
    return best_fit, best_order, best_aic

def calculate_backtest_metrics(ts_data, holdout=4):
    """
    Performs backtesting on historical data and calculates MAE (Mean Absolute Error) and RMSE (Root Mean Squared Error).
    """
    if len(ts_data) < (holdout + 6):
        return None, None
        
    train = ts_data[:-holdout]
    test = ts_data[-holdout:]
    
    try:
        fit, _, _ = evaluate_arima_models(train)
        if fit:
            preds = fit.forecast(steps=holdout)
            mae = np.mean(np.abs(preds - test))
            rmse = np.sqrt(np.mean((preds - test) ** 2))
            return round(mae, 3), round(rmse, 3)
    except Exception:
        pass
        
    return None, None

def forecast_brand_market_share(gold_df, brand_name, region_name, forecast_horizon=4):
    """
    Fits ARIMA model with dynamic model selection by AIC and backtested accuracy validation (MAE/RMSE).
    Dynamically generates future year-week dates using ISO calendar arithmetic with momentum drift projection.
    """
    if region_name == "All Regions":
        tot_w = gold_df[gold_df['clean_brand'] == brand_name].groupby('year_week')['brand_trx'].sum().reset_index()
        tot_m = gold_df.groupby('year_week')['brand_trx'].sum().to_dict()
        tot_w['total_m'] = tot_w['year_week'].map(tot_m)
        tot_w['market_share_trx_pct'] = np.where(
            tot_w['total_m'] > 0,
            (tot_w['brand_trx'] / tot_w['total_m']) * 100.0,
            0.0
        )
        sub_df = tot_w[['year_week', 'market_share_trx_pct']].sort_values('year_week').reset_index(drop=True)
    else:
        sub_df = gold_df[
            (gold_df['clean_brand'] == brand_name) &
            (gold_df['clean_region'] == region_name)
        ].sort_values('year_week').reset_index(drop=True)
    
    if sub_df.empty:
        return pd.DataFrame({
            'year_week': [None] * forecast_horizon,
            'forecast_market_share_pp': [np.nan] * forecast_horizon,
            'lower_ci_95': [np.nan] * forecast_horizon,
            'upper_ci_95': [np.nan] * forecast_horizon,
            'is_forecast': True,
            'status': 'Forecast unavailable — no historical data for selected brand/region.',
            'best_model_order': 'None',
            'mae': np.nan,
            'rmse': np.nan
        })
        
    latest_actual_week = sub_df['year_week'].iloc[-1]
    future_weeks = get_next_year_weeks(latest_actual_week, horizon=forecast_horizon)
    
    if len(sub_df) < 6:
        return pd.DataFrame({
            'year_week': future_weeks,
            'forecast_market_share_pp': [np.nan] * forecast_horizon,
            'lower_ci_95': [np.nan] * forecast_horizon,
            'upper_ci_95': [np.nan] * forecast_horizon,
            'is_forecast': True,
            'status': 'Forecast unavailable — insufficient historical data.',
            'best_model_order': 'None',
            'mae': np.nan,
            'rmse': np.nan
        })
        
    ts_data = sub_df['market_share_trx_pct'].values
    mae, rmse = calculate_backtest_metrics(ts_data, holdout=4)
    
    if STATSMODELS_AVAILABLE:
        best_fit, best_order, best_aic = evaluate_arima_models(ts_data)
        if best_fit:
            try:
                forecast_res = best_fit.get_forecast(steps=forecast_horizon)
                mean_forecast = np.array(forecast_res.predicted_mean)
                ci = np.array(forecast_res.conf_int(alpha=0.05))
                
                # Pure Statistical ARIMA Forecast & 95% Confidence Intervals
                return pd.DataFrame({
                    'year_week': future_weeks,
                    'forecast_market_share_pp': np.clip(mean_forecast, 0, 100),
                    'lower_ci_95': np.clip(ci[:, 0], 0, 100),
                    'upper_ci_95': np.clip(ci[:, 1], 0, 100),
                    'is_forecast': True,
                    'status': f"Successfully fitted ARIMA{best_order} model via AIC minimization.",
                    'best_model_order': str(best_order),
                    'mae': mae,
                    'rmse': rmse
                })
            except Exception as e:
                print(f"[Forecasting Engine Warning] Forecast generation error: {e}")
                
    return pd.DataFrame({
        'year_week': future_weeks,
        'forecast_market_share_pp': [np.nan] * forecast_horizon,
        'lower_ci_95': [np.nan] * forecast_horizon,
        'upper_ci_95': [np.nan] * forecast_horizon,
        'is_forecast': True,
        'status': 'Forecast unavailable — statistical fit error.',
        'best_model_order': 'None',
        'mae': np.nan,
        'rmse': np.nan
    })
