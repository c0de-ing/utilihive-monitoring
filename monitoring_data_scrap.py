#!/usr/bin/env python3
"""
UtiliHive Data Collector V2 - Automatic token management
Run: python script_v2.py
"""

import requests
import csv
import json
import time
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

# ===== CONFIGURATION =====
API_URL = "https://api.ch.utilihive.io/metercloud-integration-insights/api/v1/metrics/oiken-prod"

# Data directory for output files
DATA_DIR = "data"  # CSV files will be saved here

# Output files will be prefixed with date (e.g., data/2026-02-12_utilihive_metrics_hourly.csv)
# This creates a new file for each run, preventing duplicates
OUTPUT_CSV_HOURLY_TEMPLATE = os.path.join(DATA_DIR, "{date}_utilihive_metrics_hourly.csv")
OUTPUT_CSV_DAILY_TEMPLATE = os.path.join(DATA_DIR, "{date}_utilihive_metrics_daily.csv")

TOKEN_FILE = "token.json"

# Date range configuration (modify as needed)
DAYS_BACK = 2  # How many days back to fetch data from today
# Or specify custom date range:
# START_DATE = "2026-02-01"  # Format: YYYY-MM-DD
# END_DATE = "2026-02-12"    # Format: YYYY-MM-DD

# Timezone configuration (Switzerland is UTC+1 in winter, UTC+2 in summer)
TIMEZONE_OFFSET_HOURS = 1  # UTC+1 for CET (winter) or 2 for CEST (summer)

# Rate limiting configuration
REQUEST_DELAY_SECONDS = 0.1  # Delay between API requests to avoid rate limiting


# ===== TOKEN MANAGEMENT =====

def load_token():
    """Load authentication token from file or environment"""
    # Try to load from token file first
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)

            token = token_data.get('token')
            if not token:
                return None

            # Check expiration
            if 'expires_at' in token_data:
                expires_at = datetime.fromisoformat(token_data['expires_at'])
                if datetime.now() >= expires_at:
                    print(f"WARNING Token expired at {expires_at}")
                    print("Please run: python get_token.py")
                    return None
                else:
                    time_left = expires_at - datetime.now()
                    print(f"[Token expires in: {time_left}]")

            print(f"[Token loaded from {TOKEN_FILE}]")
            return token

        except Exception as e:
            print(f"Error loading token from {TOKEN_FILE}: {e}")

    # Try environment variable
    token = os.getenv("API_TOKEN")
    if token:
        print("[Token loaded from environment variable]")
        return token

    return None


# ===== FUNCTIONS =====

def generate_hourly_ranges(start_date, end_date):
    """Generate hour-by-hour date ranges in UTC with timezone offset

    For each hour in the date range, generates:
    - from_date: Start of hour in UTC
    - to_date: End of hour in UTC
    - local_datetime: Local time for this hour
    """
    ranges = []

    # Start at the beginning of the first day
    current_datetime = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # End at the end of the last day
    end_datetime = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    while current_datetime <= end_datetime:
        # Convert local time to UTC
        from_datetime_utc = current_datetime - timedelta(hours=TIMEZONE_OFFSET_HOURS)
        to_datetime_utc = (current_datetime + timedelta(hours=1)) - timedelta(hours=TIMEZONE_OFFSET_HOURS)

        ranges.append((from_datetime_utc, to_datetime_utc, current_datetime))
        current_datetime += timedelta(hours=1)

    return ranges


def fetch_data(from_date, to_date, headers):
    """Fetch data from the API for a specific date range (UTC)"""
    try:
        # Build parameters with new API format (UTC times)
        from_datetime_str = from_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        to_datetime_str = to_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        params = {
            "fromDatetimeInclusive": from_datetime_str,
            "toDatetimeExclusive": to_datetime_str
        }

        print(f"  API call: fromDatetimeInclusive={from_datetime_str}")
        response = requests.get(API_URL, headers=headers, params=params, timeout=30)
        response.raise_for_status()  # Raise exception for HTTP errors

        print(f"[{datetime.now()}] OK Success! Status code: {response.status_code}")
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] ERROR Error fetching data: {e}")
        return None


def save_to_csv_hourly(data, csv_file, collection_datetime):
    """Save hourly data to CSV file with flattened structure"""
    if not data:
        print(f"[{datetime.now()}] No data to save")
        return []

    # Handle different data structures
    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = data
    else:
        print(f"[{datetime.now()}] ERROR Unexpected data format: {type(data)}")
        return []

    # Transform data to flattened structure
    flattened_records = []
    for record in records:
        if not isinstance(record, dict):
            continue

        flow_details = record.get('flowDetails', {})
        metrics = record.get('metrics', [])

        # Extract flow information
        flow_id = flow_details.get('flowId', 'unknown')
        flow_name = flow_details.get('flowName', '')
        flow_state = flow_details.get('flowState', '')

        # Extract metrics values
        metrics_dict = {}
        for metric in metrics:
            metric_id = metric.get('metricId', '')
            metric_value = metric.get('value', 0)
            metrics_dict[metric_id] = metric_value

        # Create flattened record with datetime and hour
        flat_record = {
            'datetime': collection_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'date': collection_datetime.strftime('%Y-%m-%d'),
            'hour': collection_datetime.hour,
            'collection_timestamp': datetime.now().isoformat(),
            'flow_id': flow_id,
            'flow_name': flow_name,
            'flow_state': flow_state,
            'total_exchanges': metrics_dict.get('total-exchanges', 0),
            'successful_exchanges': metrics_dict.get('successful-exchanges', 0),
            'failed_exchanges': metrics_dict.get('failed-exchanges', 0),
            'inflight_exchanges': metrics_dict.get('inflight-exchanges', 0),
            'avg_response_time_ms': metrics_dict.get('avg-response-time-millis', 0),
            'avg_processing_time_ms': metrics_dict.get('avg-processing-time-millis', 0)
        }

        flattened_records.append(flat_record)

    # Ensure directory exists
    csv_dir = os.path.dirname(csv_file)
    if csv_dir and not os.path.exists(csv_dir):
        os.makedirs(csv_dir)
        print(f"[{datetime.now()}] Created directory: {csv_dir}")

    # Check if file exists to determine if we need headers
    file_exists = os.path.isfile(csv_file)

    try:
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            if flattened_records:
                fieldnames = [
                    'datetime',
                    'date',
                    'hour',
                    'collection_timestamp',
                    'flow_id',
                    'flow_name',
                    'flow_state',
                    'total_exchanges',
                    'successful_exchanges',
                    'failed_exchanges',
                    'inflight_exchanges',
                    'avg_response_time_ms',
                    'avg_processing_time_ms'
                ]

                writer = csv.DictWriter(f, fieldnames=fieldnames)

                # Write header only if file is new
                if not file_exists:
                    writer.writeheader()

                # Write data rows
                for flat_record in flattened_records:
                    writer.writerow(flat_record)

                print(f"[{datetime.now()}] OK Saved {len(flattened_records)} record(s) to {csv_file}")

    except Exception as e:
        print(f"[{datetime.now()}] ERROR Error saving to CSV: {e}")

    return flattened_records


def aggregate_to_daily(hourly_csv_file, daily_csv_file):
    """Aggregate hourly data to daily summaries"""
    if not os.path.exists(hourly_csv_file):
        print(f"[{datetime.now()}] WARNING Hourly file not found: {hourly_csv_file}")
        return

    print(f"\n[Aggregating hourly data to daily...]")

    try:
        # Read hourly data
        df = pd.read_csv(hourly_csv_file)

        if df.empty:
            print(f"[{datetime.now()}] WARNING No data to aggregate")
            return

        # Group by date and flow_id
        daily_agg = df.groupby(['date', 'flow_id', 'flow_name', 'flow_state']).agg({
            'total_exchanges': 'sum',
            'successful_exchanges': 'sum',
            'failed_exchanges': 'sum',
            'inflight_exchanges': 'mean',  # Average of hourly averages
            'avg_response_time_ms': 'mean',  # Average of hourly averages
            'avg_processing_time_ms': 'mean'  # Average of hourly averages
        }).reset_index()

        # Add collection timestamp
        daily_agg['collection_timestamp'] = datetime.now().isoformat()

        # Reorder columns
        daily_agg = daily_agg[[
            'date',
            'collection_timestamp',
            'flow_id',
            'flow_name',
            'flow_state',
            'total_exchanges',
            'successful_exchanges',
            'failed_exchanges',
            'inflight_exchanges',
            'avg_response_time_ms',
            'avg_processing_time_ms'
        ]]

        # Ensure directory exists
        csv_dir = os.path.dirname(daily_csv_file)
        if csv_dir and not os.path.exists(csv_dir):
            os.makedirs(csv_dir)

        # Save to daily CSV
        daily_agg.to_csv(daily_csv_file, index=False)

        print(f"[{datetime.now()}] OK Daily aggregations saved to {daily_csv_file}")
        print(f"   - {len(daily_agg)} daily records created")

    except Exception as e:
        print(f"[{datetime.now()}] ERROR Error aggregating data: {e}")


def main():
    """Main execution function"""
    global API_TOKEN

    print("=" * 70)
    print("UtiliHive Data Collector V2 - Hour by Hour")
    print("=" * 70)

    # Create data directory if it doesn't exist
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"\n[Created data directory: {DATA_DIR}]")

    # Load token
    print("\n[Loading authentication token...]")
    API_TOKEN = load_token()

    if not API_TOKEN:
        print("\n" + "=" * 70)
        print("ERROR: No authentication token found!")
        print("=" * 70)
        print("\nPlease run the token extraction script first:")
        print("  python get_token.py")
        print("\nOr set the API_TOKEN environment variable:")
        print("  set API_TOKEN=your_token_here  (Windows)")
        print("  export API_TOKEN=your_token_here  (Linux/Mac)")
        print("=" * 70)
        sys.exit(1)

    # Set up headers with token
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }

    # Determine date range
    # Priority: 1) Environment variables 2) Code-defined constants 3) DAYS_BACK
    start_date_env = os.getenv('START_DATE')
    end_date_env = os.getenv('END_DATE')

    if start_date_env and end_date_env:
        # Use environment variables (from dashboard or external call)
        start_date = datetime.strptime(start_date_env, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_env, "%Y-%m-%d")
        print(f"Using date range from environment: {start_date_env} to {end_date_env}")
    else:
        # Check if custom date range is defined in code
        try:
            start_date = datetime.strptime(START_DATE, "%Y-%m-%d")
            end_date = datetime.strptime(END_DATE, "%Y-%m-%d")
            print(f"Using custom date range: {START_DATE} to {END_DATE}")
        except (NameError, ValueError):
            # Use DAYS_BACK if custom range not defined
            end_date = datetime.now()
            start_date = end_date - timedelta(days=DAYS_BACK)
            print(f"Fetching last {DAYS_BACK} days: {start_date.date()} to {end_date.date()}")

    # Generate dated output filenames
    collection_date_str = datetime.now().strftime("%Y-%m-%d")
    OUTPUT_CSV_HOURLY = OUTPUT_CSV_HOURLY_TEMPLATE.format(date=collection_date_str)
    OUTPUT_CSV_DAILY = OUTPUT_CSV_DAILY_TEMPLATE.format(date=collection_date_str)

    print(f"\nOutput files for this run:")
    print(f"   - Hourly: {OUTPUT_CSV_HOURLY}")
    print(f"   - Daily:  {OUTPUT_CSV_DAILY}")

    # Generate hourly ranges
    hourly_ranges = generate_hourly_ranges(start_date, end_date)
    total_hours = len(hourly_ranges)
    print(f"Total hours to fetch: {total_hours}")
    print(f"Request delay: {REQUEST_DELAY_SECONDS} seconds between requests")
    print(f"Estimated time: ~{(total_hours * REQUEST_DELAY_SECONDS) / 60:.1f} minutes")
    print("-" * 70)

    # Fetch data for each hour
    total_records = 0
    successful_hours = 0
    all_hourly_records = []

    for i, (from_datetime_utc, to_datetime_utc, local_datetime) in enumerate(hourly_ranges, 1):
        print(f"\n[Hour {i}/{total_hours}] - Local: {local_datetime.strftime('%Y-%m-%d %H:%M')}")
        print(f"  UTC range: {from_datetime_utc.strftime('%Y-%m-%d %H:%M:%S')} to {to_datetime_utc.strftime('%Y-%m-%d %H:%M:%S')}")

        data = fetch_data(from_datetime_utc, to_datetime_utc, headers)

        if data:
            records = save_to_csv_hourly(data, OUTPUT_CSV_HOURLY, local_datetime)
            all_hourly_records.extend(records)

            # Count records if data is a list
            if isinstance(data, list):
                total_records += len(data)
            else:
                total_records += 1
            successful_hours += 1
        else:
            print(f"[{datetime.now()}] WARNING No data retrieved for this hour")

        # Add delay between requests to avoid rate limiting
        if i < total_hours:  # Don't delay after the last request
            time.sleep(REQUEST_DELAY_SECONDS)

    # Aggregate to daily
    print("\n" + "-" * 70)
    aggregate_to_daily(OUTPUT_CSV_HOURLY, OUTPUT_CSV_DAILY)

    # Summary
    print("\n" + "=" * 70)
    print("Collection Summary:")
    print(f"   - Successful hours: {successful_hours}/{total_hours}")
    print(f"   - Total records collected: {total_records}")
    print(f"   - Hourly data saved to: {OUTPUT_CSV_HOURLY}")
    print(f"   - Daily aggregations saved to: {OUTPUT_CSV_DAILY}")
    print("=" * 70)


if __name__ == "__main__":
    main()
