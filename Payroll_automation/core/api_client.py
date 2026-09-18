"""
HTTP connector used by every processor.
Adds: API-key auth, timeouts, retry with back-off on network/5xx errors.
Swapping to a real ERP/HRIS/mail system = change base_url + api_key (+ endpoint paths).
"""
import time
import requests


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


class Api:
    def __init__(self, cfg):
        a = cfg["api"]
        self.base = a["base_url"].rstrip("/")
        self.timeout = a.get("timeout_sec", 10)
        self.retries = a.get("retries", 3)
        self.s = requests.Session()
        self.s.headers.update({"X-API-Key": a["api_key"]})
        self.calls = 0

    def _request(self, method, path, **kw):
        last = None
        for attempt in range(1, self.retries + 1):
            try:
                self.calls += 1
                r = self.s.request(method, self.base + path, timeout=self.timeout, **kw)
                if r.status_code >= 500:
                    raise ApiError(r.status_code, r.text[:200])
                return r
            except (requests.ConnectionError, requests.Timeout, ApiError) as e:
                last = e
                time.sleep(0.3 * attempt)
        raise last

    def get(self, url, allow_404=False, **params):
        r = self._request("GET", url, params=params or None)
        if r.status_code == 404 and allow_404:
            return None
        if r.status_code >= 400:
            raise ApiError(r.status_code, r.text[:200])
        return r.json()

    def post(self, path, body, allow_conflict=False):
        """POST json. With allow_conflict=True a 409 is returned as {"conflict": True, "message": ...}."""
        r = self._request("POST", path, json=body)
        if r.status_code == 409 and allow_conflict:
            return {"conflict": True, "message": r.json().get("detail")}
        if r.status_code >= 400:
            raise ApiError(r.status_code, r.text[:200])
        return r.json()

    # ---- document store helpers -------------------------------------------------
    def list_files(self, prefix):
        return self.get("/files/list", prefix=prefix)

    def get_file(self, path):
        """Download a file from the document store. Returns bytes, or None if it does not exist."""
        import base64
        r = self.get("/files/download", allow_404=True, path=path)
        return base64.b64decode(r["content_b64"]) if r else None

    def put_file(self, path, text):
        return self.post("/files/upload", {"path": path, "text": text})

    def healthy(self):
        try:
            return self.s.get(self.base + "/health", timeout=2).status_code == 200
        except requests.RequestException:
            return False
