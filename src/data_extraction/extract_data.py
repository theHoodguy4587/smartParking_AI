
import os
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv


# --------------------------------------------------
# 1. Load database configuration
# --------------------------------------------------

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


# --------------------------------------------------
# 2. SQL query
# --------------------------------------------------

QUERY = """
SELECT
    id AS record_id,
    locationid AS location_id,
    intime AS entry_time,
    outtime AS exit_time,
    vehtype AS vehicle_type,
    totaltime AS recorded_duration,

    CASE
        WHEN seasonrateid IS NOT NULL THEN 1
        ELSE 0
    END AS is_season_vehicle,

    CASE
        WHEN normalrateid IS NOT NULL THEN 1
        ELSE 0
    END AS is_normal_vehicle,

    vehiclestatus AS vehicle_status,
    parkedslot AS parking_slot

FROM tbvehicleentry1

WHERE locationid = 1
  AND intime IS NOT NULL

ORDER BY intime ASC;
"""


# --------------------------------------------------
# 3. Extract data from PostgreSQL
# --------------------------------------------------

def extract_data():

    connection = None

    try:
        print("Connecting to PostgreSQL...")

        connection = psycopg2.connect(**DB_CONFIG)

        print("Database connection successful.")
        print("Executing extraction query...")

        with connection.cursor() as cursor:

            cursor.execute(QUERY)

            records = cursor.fetchall()

            columns = [
                description[0]
                for description in cursor.description
            ]

        df = pd.DataFrame(records, columns=columns)

        print(f"Extracted records: {len(df):,}")

        # --------------------------------------------------
        # 4. Convert timestamps
        # --------------------------------------------------

        df["entry_time"] = pd.to_datetime(df["entry_time"])
        df["exit_time"] = pd.to_datetime(df["exit_time"])

        # --------------------------------------------------
        # 5. Derive parking duration in seconds
        # --------------------------------------------------

        df["duration_seconds"] = (
            df["exit_time"] - df["entry_time"]
        ).dt.total_seconds()

        # --------------------------------------------------
        # 6. Create data quality flags
        # --------------------------------------------------

        df["is_valid_timestamp"] = (
            df["exit_time"].notna()
            & df["exit_time"].ge(df["entry_time"])
        )

        df["is_zero_duration"] = (
            df["duration_seconds"] == 0
        )

        df["is_positive_duration"] = (
            df["duration_seconds"] > 0
        )

        # --------------------------------------------------
        # 7. Export CSV
        # --------------------------------------------------

        output_folder = (
            Path(__file__).resolve().parent
            / "data"
            / "raw"
        )

        output_folder.mkdir(parents=True, exist_ok=True)

        output_file = output_folder / "parking_sessions.csv"

        df.to_csv(output_file, index=False)

        # --------------------------------------------------
        # 8. Display extraction summary
        # --------------------------------------------------

        print("\n========== EXTRACTION SUMMARY ==========")

        print(f"Total records: {len(df):,}")

        print(
            "Invalid timestamps:",
            (~df["is_valid_timestamp"]).sum()
        )

        print(
            "Zero-duration sessions:",
            df["is_zero_duration"].sum()
        )

        print(
            "Positive-duration sessions:",
            df["is_positive_duration"].sum()
        )

        print(
            "Missing exit timestamps:",
            df["exit_time"].isna().sum()
        )

        print(f"\nCSV saved to: {output_file}")

        print("========================================")

    except Exception as error:

        print("Extraction failed!")
        print(f"Error: {error}")

    finally:

        if connection is not None:
            connection.close()
            print("\nDatabase connection closed.")


if __name__ == "__main__":
    extract_data()
