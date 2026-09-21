from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class OTPFetchResult:
    ok: bool
    code: str = ""
    created_at: str = ""
    error: str = ""


class OTPBridgeClient:
    def __init__(self, base_url: str, *, timeout: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def fetch_latest_otp(self) -> OTPFetchResult:
        try:
            res = requests.get(self._url("otp_latest.php"), timeout=self.timeout)
            res.raise_for_status()
            data = res.json()
        except Exception as exc:
            return OTPFetchResult(ok=False, error=str(exc))

        if not data.get("ok"):
            return OTPFetchResult(ok=False)

        code = str(data.get("code", "")).strip()
        if not code:
            return OTPFetchResult(ok=False, error="OTP code missing in response")

        return OTPFetchResult(
            ok=True,
            code=code,
            created_at=str(data.get("created_at", "")).strip(),
        )

    def delete_otp(self) -> bool:
        try:
            res = requests.post(self._url("otp_delete.php"), timeout=self.timeout)
            res.raise_for_status()
            return True
        except Exception:
            return False
