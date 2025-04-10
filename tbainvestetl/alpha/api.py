import os
import time
from datetime import datetime

import requests

URL_BASE = "https://www.alphavantage.co/query?function="


class AlphaScraper:
    def __init__(self, api_key=None, wait=True, max_api_requests_per_min=75):
        if api_key is None:
            self.api_key = os.environ.get("ALPHAVANTAGE_API_KEY")
        else:
            self.api_key = api_key
        self.wait = wait
        self.max_api_requests_per_min = max_api_requests_per_min
        self.remaining_api_requests = max_api_requests_per_min
        self.last_increase_time = datetime.today()

    def wait_to_hit_api(self):
        # Remaining api requests
        if self.remaining_api_requests > 0:
            self.remaining_api_requests -= 1
            print(f"Remaining api requests: {self.remaining_api_requests}")
            return

        # Reached maximum
        delay = (datetime.today() - self.last_increase_time).total_seconds()
        if delay < 60:
            print(f"Maximum limit reached. Sleeping for {60 - delay} seconds")
            time.sleep(60 - delay)

        print("API limit refreshed after 1 minute")
        self.remaining_api_requests = self.max_api_requests_per_min - 1
        self.last_increase_time = datetime.today()

    def hit_api(self, url, **kwargs):
        kwargs["URL_BASE"] = URL_BASE
        kwargs["api_key"] = self.api_key
        url = url.format(**kwargs)

        if self.wait:
            self.wait_to_hit_api()

        with requests.Session() as s:
            download = s.get(url)

        return download
