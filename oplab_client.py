import os
import time
import requests
from typing import Dict, Any, Optional

class OpLabClient:
    def __init__(self, token: Optional[str] = None, base_url: str = "https://api.oplab.com.br/v3", timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.token = token or os.getenv("OPLAB_ACCESS_TOKEN")
        if not self.token:
            raise RuntimeError("Token da OpLab não encontrado. Defina OPLAB_ACCESS_TOKEN nos secrets.")
        self.session = requests.Session()
        self.session.headers.update({"Access-Token": self.token})
        self.timeout = timeout

    def _get(self, path: str, params: Dict[str, Any] = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 429:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                if resp.content:
                    return resp.json()
                return None
            except requests.RequestException as e:
                if attempt == 2:
                    raise e
                time.sleep(1.5 * (attempt + 1))

    def list_stocks(self, page: int = 1, per: int = 200, financial_volume_start: Optional[int] = None):
        params = {"page": page, "per": per}
        if financial_volume_start is not None:
            params["financial_volume_start"] = financial_volume_start
        return self._get("market/stocks/all", params=params)

    def get_stock(self, symbol: str, with_financials: str = "none"):
        return self._get(f"market/stocks/{symbol}", params={"with_financials": with_financials})

    def list_options(self, underlying: str):
        return self._get(f"market/options/{underlying}")

    def option_details(self, option_symbol: str):
        return self._get(f"market/options/details/{option_symbol}")

    def covered_calls(self, underlying: str):
        return self._get("market/options/strategies/covered", params={"underlying": underlying})

    def bs_calc(self, **kwargs):
        return self._get("market/options/bs", params=kwargs)

    def interest_rate(self, rate_id: str = "SELIC"):
        return self._get(f"market/interest_rates/{rate_id}")
