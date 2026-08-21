"""
===============================================================================
Enterprise Commercial Analytics Platform - Local DuckDB Storage Engine
Local In-Memory / File Database for Offline Analytics & Incremental Sync
===============================================================================
"""

import os
import sqlite3
import pandas as pd
import numpy as np
import duckdb

from src.config import BASE_DIR, DATASET_PATH, LOOKBACK_WEEKS, ANOMALY_Z_THRESHOLD
from src.data_preprocessing import preprocess_pharma_dataset
from src.market_share_engine import calculate_market_share
from src.share_shift_engine import calculate_share_shifts
from src.anomaly_engine import detect_statistical_anomalies
from src.alert_engine import generate_market_alerts

DB_PATH = os.path.join(BASE_DIR, "sample_data", "local_warehouse.duckdb")

class LocalWarehouseEngine:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._bootstrap_database()

    def get_connection(self):
        return duckdb.connect(self.db_path)

    def _bootstrap_database(self):
        """
        Initializes DuckDB tables and populates base raw dataset on first run.
        """
        conn = self.get_connection()
        try:
            if os.path.exists(DATASET_PATH):
                # Check if table exists
                tables = conn.execute("SHOW TABLES").fetchdf()
                has_raw = not tables.empty and 'local_prescriptions_raw' in tables['name'].values
                count = conn.execute("SELECT COUNT(*) FROM local_prescriptions_raw").fetchone()[0] if has_raw else 0

                if count == 0:
                    print(f"[Local Storage] Bootstrapping raw data from: {DATASET_PATH}")
                    raw_df = pd.read_csv(DATASET_PATH, dtype=str)
                    if 'source_vendor' not in raw_df.columns:
                        raw_df['source_vendor'] = 'Central Data Feed'
                    conn.register('temp_raw', raw_df)
                    conn.execute("CREATE TABLE local_prescriptions_raw AS SELECT * FROM temp_raw")
                    conn.unregister('temp_raw')

                    # Run initial local pipeline recomputation
                    self.recompute_local_pipeline(conn)
        finally:
            conn.close()

    def recompute_local_pipeline(self, conn=None):
        """
        Recomputes the entire analytics pipeline over complete local raw history (2022-2026).
        This guarantees rolling 3-week baselines and Z-scores are mathematically exact.
        """
        should_close = False
        if conn is None:
            conn = self.get_connection()
            should_close = True

        try:
            raw_df = conn.execute("SELECT * FROM local_prescriptions_raw").fetchdf()
            if raw_df.empty:
                return

            # Step 1: Preprocess
            cleaned_df, dq_report, quarantine_df = preprocess_pharma_dataset(raw_df)

            # Step 2: Market Share
            market_share_df, sum_check_df = calculate_market_share(cleaned_df)

            # Step 3: Share Shifts
            share_shift_df = calculate_share_shifts(market_share_df)

            # Step 4: Anomalies
            anomaly_df = detect_statistical_anomalies(
                share_shift_df,
                lookback_weeks=LOOKBACK_WEEKS,
                z_threshold=ANOMALY_Z_THRESHOLD
            )

            # Step 5: Alerts
            alerts_res = generate_market_alerts(anomaly_df)
            active_alerts_df = alerts_res[1] if isinstance(alerts_res, tuple) else alerts_res

            # Save clean, gold, and alert tables into DuckDB
            conn.execute("DROP TABLE IF EXISTS local_prescriptions_clean")
            conn.execute("DROP TABLE IF EXISTS local_market_share_gold")
            conn.execute("DROP TABLE IF EXISTS local_active_alerts")

            conn.register('temp_clean', cleaned_df)
            conn.execute("CREATE TABLE local_prescriptions_clean AS SELECT * FROM temp_clean")
            conn.unregister('temp_clean')

            conn.register('temp_gold', anomaly_df)
            conn.execute("CREATE TABLE local_market_share_gold AS SELECT * FROM temp_gold")
            conn.unregister('temp_gold')

            if not active_alerts_df.empty:
                conn.register('temp_alerts', active_alerts_df)
                conn.execute("CREATE TABLE local_active_alerts AS SELECT * FROM temp_alerts")
                conn.unregister('temp_alerts')
            else:
                conn.execute("""
                    CREATE TABLE local_active_alerts (
                        year_week VARCHAR,
                        clean_brand VARCHAR,
                        clean_region VARCHAR,
                        share_shift_pp DOUBLE,
                        alert_type VARCHAR,
                        alert_message VARCHAR,
                        severity VARCHAR
                    )
                """)
            print("[Local Storage] Recomputed analytics pipeline over complete history.")
        finally:
            if should_close:
                conn.close()

    def fetch_clean_data_from_local(self):
        """
        Reads analytics data directly from DuckDB Local Storage for UI rendering.
        """
        conn = self.get_connection()
        try:
            cleaned_df = conn.execute("SELECT * FROM local_prescriptions_clean").fetchdf()
            gold_df = conn.execute("SELECT * FROM local_market_share_gold").fetchdf()
            active_alerts_df = conn.execute("SELECT * FROM local_active_alerts").fetchdf()

            return {
                "cleaned_df": cleaned_df,
                "gold_df": gold_df,
                "active_alerts_df": active_alerts_df
            }
        except Exception as e:
            print(f"[Local Storage Fetch Warning] {e}")
            from src.pipeline_runner import run_end_to_end_pipeline
            return run_end_to_end_pipeline()
        finally:
            conn.close()

    def append_incremental_raw_data(self, new_records_df):
        """
        Appends new raw weekly records from central feed into local raw storage
        and triggers a complete local analytics recomputation over full history.
        """
        if new_records_df.empty:
            return

        conn = self.get_connection()
        try:
            if 'source_vendor' not in new_records_df.columns:
                new_records_df['source_vendor'] = 'Central Data Feed'

            # Ensure raw table exists
            tables = conn.execute("SHOW TABLES").fetchdf()
            if tables.empty or 'local_prescriptions_raw' not in tables['name'].values:
                conn.close()
                self._bootstrap_database()
                conn = self.get_connection()

            conn.register('temp_new', new_records_df)
            conn.execute("INSERT INTO local_prescriptions_raw SELECT * FROM temp_new")
            conn.unregister('temp_new')

            # Recompute local analytics layer
            self.recompute_local_pipeline(conn)
        finally:
            conn.close()

local_warehouse = LocalWarehouseEngine()
