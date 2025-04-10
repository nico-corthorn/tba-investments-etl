import json
import sys
import time
import traceback
from datetime import datetime

import pandas as pd
import requests

from tbainvestetl.utils import sql_manager


class NytNewsScraper:
    """NYT news articles download"""

    def __init__(self, table_name: str, api_key: str, db_credentials):
        # Initial parameters
        self.table_name = table_name
        self.api_key = api_key
        self.sql_manager = sql_manager.ManagerSQL(db_credentials)

    def nyt_upload_all_articles(self, year_start=2001, clean_tables=False, verbose=False):
        if clean_tables:
            self.sql_manager.clean_table(self.table_name)
        now = datetime.now()
        for year in range(year_start, now.year + 1):
            month_end = 12
            if year == now.year:
                month_end = now.month - 1
            for month in range(1, month_end + 1):
                self.nyt_upload_one_month_articles(year, month, verbose)

    def nyt_upload_one_month_articles(self, year, month, verbose=False):
        try:
            # Verify data has not been downloaded
            year_month = f"{year}{month:02}"
            db_year_month_list = self.sql_manager.select_distinct_column_list(
                "year_month", "nyt_archive"
            )
            if year_month in db_year_month_list:
                if verbose:
                    print(f"Database already has NYT articles for {year}-{month}")
                return

            # Download
            if verbose:
                print(f"Downloading NYT {year_month}")
            t0 = datetime.now()
            df = self.nyt_api_download_one_month_articles(year, month)
            t1 = datetime.now()
            if verbose:
                if df is None:
                    print(
                        f"No data returned for {year_month} ({(t1 - t0).total_seconds():.2f} sec)"
                    )
                    return
                print(f"Downloaded NYT {year_month} ({(t1 - t0).total_seconds():.2f} sec)")

            # Upload
            if verbose:
                print(f"Uploading NYT {year_month}")
            t0 = datetime.now()
            self.sql_manager.upload_df_chunks("nyt_archive", df)
            t1 = datetime.now()
            if verbose > 0:
                print(f"Uploaded NYT {year_month} ({(t1 - t0).total_seconds():.2f} sec)")

        except Exception:
            t1 = datetime.now()
            print(f"ERROR: Failed to upload NYT {year_month} ({(t1 - t0).total_seconds():.2f} sec)")
            exc_type, exc_value, exc_tb = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_tb)

    def handle_quota_violation(self, data: dict):
        if "fault" in data:
            fault = data.get("fault")
            if isinstance(fault, dict) and "faultstring" in fault:
                if fault["faultstring"].startswith("Rate limit quota violation"):
                    print("Quota violation, sleeping for 60 seconds")
                    time.sleep(60)
                    return True
        return False

    def extract_business_articles(self, data: dict):
        biz_articles = []
        for article in data["response"]["docs"]:
            if article.get("news_desk") == "Business":
                org = [
                    keyword["value"]
                    for keyword in article["keywords"]
                    if keyword["name"] == "organizations"
                ]
                sub = [
                    keyword["value"]
                    for keyword in article["keywords"]
                    if keyword["name"] == "subject"
                ]
                if org:
                    biz_articles.append(
                        {
                            "web_url": article["web_url"],
                            "pub_date": article["pub_date"],
                            "organizations": " | ".join(org),
                            "subjects": " | ".join(sub),
                            "headline": article["headline"]["main"],
                            "snippet": article["snippet"],
                        }
                    )
        return biz_articles

    def nyt_api_download_one_month_articles(self, year, month, attempts=3, lud=None):
        try:
            # Scrape nyt api
            url = (
                f"https://api.nytimes.com/svc/archive/v1/{year}/{month}.json"
                f"?api-key={self.api_key}"
            )
            if lud is None:
                lud = datetime.now()

            for attempt in range(attempts):
                json_data = requests.get(url, timeout=10)
                print(f"attempt {attempt}")
                data = json.loads(json_data.text)
                if "response" in data:
                    break
                if self.handle_quota_violation(data):
                    continue

            if "response" not in data:
                print(data)
                raise ValueError("data has not the expected keys")

            biz_articles = self.extract_business_articles(data)

            # Convert to DataFrame and minimal cleaning
            df = pd.DataFrame(biz_articles)
            if df.empty:
                return None
            cols = [
                "web_url",
                "pub_date",
                "organizations",
                "subjects",
                "headline",
                "snippet",
            ]
            df = df[cols]
            df["pub_date"] = pd.to_datetime(df["pub_date"])
            text_insert_cols = ["organizations", "subjects", "headline", "snippet"]
            df[text_insert_cols] = df[text_insert_cols].mask(df[text_insert_cols].isnull(), "")
            df["year_month"] = f"{year}{month:02}"
            df["lud"] = lud
            final_cols = [
                "web_url",
                "year_month",
                "pub_date",
                "organizations",
                "subjects",
                "headline",
                "snippet",
                "lud",
            ]
            return df[final_cols]

        except Exception:
            exc_type, exc_value, exc_tb = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_tb)
            if "data" in locals():
                print("data:", data)
            return None
