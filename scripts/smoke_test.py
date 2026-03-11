import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

import requests


DEFAULT_EMAIL = "smoke@example.com"
DEFAULT_PASSWORD = "Password123!"

BASE_URLS = {
    "dev": {
        "direct": "http://localhost:8000/api/v1",
        "proxy": "https://dev-b2b-quotation-system.vercel.app/api/v1",
    },
    "prod": {
        "direct": "https://b2b-quotation-system-backend-production.up.railway.app/api/v1",
        "proxy": "https://b2b-quotation-system.vercel.app/api/v1",
    },
}


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"


def cprint(msg: str, color: str = Color.RESET) -> None:
    print(f"{color}{msg}{Color.RESET}")


@dataclass
class CheckResult:
    name: str
    method: str
    endpoint: str
    status: int
    ok: bool
    layer: str
    detail: str = ""


@dataclass
class SmokeReport:
    env: str
    mode: str
    base_url: str
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)

    @property
    def passed(self) -> bool:
        return len(self.checks) > 0 and all(item.ok for item in self.checks)

    def to_json(self) -> dict[str, Any]:
        return {
            "env": self.env,
            "mode": self.mode,
            "base_url": self.base_url,
            "passed": self.passed,
            "checks": [item.__dict__ for item in self.checks],
        }


class SmokeTester:
    def __init__(self, env: str, mode: str, base_url: str, email: str, password: str):
        self.env = env
        self.mode = mode
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "User-Agent": "B2B-SmokeTester/2.0",
            }
        )
        self.report = SmokeReport(env=env, mode=mode, base_url=self.base_url)

    def _record(
        self,
        *,
        name: str,
        method: str,
        endpoint: str,
        status: int,
        ok: bool,
        layer: str,
        detail: str = "",
    ) -> None:
        self.report.add(
            CheckResult(
                name=name,
                method=method,
                endpoint=endpoint,
                status=status,
                ok=ok,
                layer=layer,
                detail=detail,
            )
        )
        icon = "✅" if ok else "❌"
        color = Color.GREEN if ok else Color.RED
        detail_suffix = f" | {detail}" if detail else ""
        cprint(f"{icon} {method} {endpoint} -> {status} [{layer}]{detail_suffix}", color)

    def _assert_json(self, response: requests.Response, context: str) -> dict[str, Any]:
        text = (response.text or "").strip()
        content_type = response.headers.get("Content-Type", "")
        if text.lower().startswith("<!doctype") or text.lower().startswith("<html"):
            self._record(
                name=context,
                method=response.request.method,
                endpoint=response.request.path_url,
                status=response.status_code,
                ok=False,
                layer="proxy",
                detail="收到 HTML，疑似 rewrite/fallback 問題",
            )
            raise RuntimeError(f"{context}: HTML response detected")

        if "application/json" not in content_type:
            cprint(
                f"⚠️ {context}: Content-Type={content_type}，繼續嘗試 JSON parse",
                Color.YELLOW,
            )

        try:
            return response.json()
        except json.JSONDecodeError as exc:
            self._record(
                name=context,
                method=response.request.method,
                endpoint=response.request.path_url,
                status=response.status_code,
                ok=False,
                layer="backend",
                detail=f"JSON parse failed: {exc}",
            )
            raise RuntimeError(f"{context}: invalid JSON") from exc

    def ensure_csrf(self) -> None:
        endpoint = "/auth/csrf"
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url)

        if response.status_code != 200:
            self._record(
                name="csrf",
                method="GET",
                endpoint=endpoint,
                status=response.status_code,
                ok=False,
                layer="auth",
                detail="無法取得 CSRF token",
            )
            raise RuntimeError("CSRF fetch failed")

        payload = self._assert_json(response, "csrf")
        token = payload.get("csrf_token")
        if token:
            self.session.headers.update({"X-CSRF-Token": token})

        self._record(
            name="csrf",
            method="GET",
            endpoint=endpoint,
            status=response.status_code,
            ok=bool(token),
            layer="auth",
            detail="CSRF token ready" if token else "回應缺少 csrf_token",
        )

        if not token:
            raise RuntimeError("CSRF token missing")

    def login(self) -> None:
        endpoint = "/auth/login"
        url = f"{self.base_url}{endpoint}"
        payload = {
            "email": self.email,
            "password": self.password,
            "remember_me": False,
        }
        response = self.session.post(url, json=payload)

        if response.status_code != 200:
            self._record(
                name="login",
                method="POST",
                endpoint=endpoint,
                status=response.status_code,
                ok=False,
                layer="auth",
                detail=response.text[:160],
            )
            raise RuntimeError("Login failed")

        self._assert_json(response, "login")
        self._record(
            name="login",
            method="POST",
            endpoint=endpoint,
            status=response.status_code,
            ok=True,
            layer="auth",
        )

    def check_auth_me(self) -> None:
        endpoint = "/auth/me"
        response = self.session.get(f"{self.base_url}{endpoint}")
        ok = response.status_code == 200
        detail = ""
        if ok:
            payload = self._assert_json(response, "auth_me")
            detail = payload.get("email", "")
        else:
            detail = response.text[:160]
        self._record(
            name="auth_me",
            method="GET",
            endpoint=endpoint,
            status=response.status_code,
            ok=ok,
            layer="auth",
            detail=detail,
        )
        if not ok:
            raise RuntimeError("Auth me failed")

    def check_customers(self) -> None:
        endpoint = "/customers?page=1&page_size=5"
        response = self.session.get(f"{self.base_url}{endpoint}")
        ok = response.status_code == 200
        detail = ""
        if ok:
            payload = self._assert_json(response, "customers")
            if isinstance(payload, dict) and "items" in payload:
                detail = f"items={len(payload['items'])}"
            else:
                detail = "格式非預期"
        else:
            detail = response.text[:160]
        self._record(
            name="customers",
            method="GET",
            endpoint=endpoint,
            status=response.status_code,
            ok=ok,
            layer="business",
            detail=detail,
        )
        if not ok:
            raise RuntimeError("Customers failed")

    def check_rfqs(self) -> None:
        endpoint = "/rfqs?page=1&page_size=5"
        response = self.session.get(f"{self.base_url}{endpoint}")
        ok = response.status_code == 200
        detail = ""
        if response.history:
            detail = f"redirects={[r.status_code for r in response.history]}"
        if ok:
            payload = self._assert_json(response, "rfqs")
            if isinstance(payload, dict) and "items" in payload:
                detail = f"{detail} items={len(payload['items'])}".strip()
        else:
            detail = response.text[:160]
        self._record(
            name="rfqs",
            method="GET",
            endpoint=endpoint,
            status=response.status_code,
            ok=ok,
            layer="business",
            detail=detail,
        )
        if not ok:
            raise RuntimeError("RFQs failed")

    def run(self) -> SmokeReport:
        cprint(
            f"\n=== Smoke Test env={self.env} mode={self.mode} base={self.base_url} ===",
            Color.CYAN,
        )
        self.ensure_csrf()
        self.login()
        self.check_auth_me()
        self.check_customers()
        self.check_rfqs()
        return self.report


def resolve_base_url(env: str, mode: str, override_url: str | None) -> str:
    if override_url:
        return override_url
    return BASE_URLS[env][mode]


def main() -> int:
    parser = argparse.ArgumentParser(description="B2B API smoke test")
    parser.add_argument("--env", required=True, choices=["dev", "prod"])
    parser.add_argument("--mode", default="direct", choices=["direct", "proxy"])
    parser.add_argument("--base-url", default=None, help="Override resolved base URL")
    parser.add_argument("--email", default=os.getenv("SMOKE_EMAIL", DEFAULT_EMAIL))
    parser.add_argument("--password", default=os.getenv("SMOKE_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument("--json", action="store_true", help="Output final report as JSON")
    args = parser.parse_args()

    base_url = resolve_base_url(args.env, args.mode, args.base_url)
    tester = SmokeTester(
        env=args.env,
        mode=args.mode,
        base_url=base_url,
        email=args.email,
        password=args.password,
    )

    try:
        report = tester.run()
    except Exception as exc:  # noqa: BLE001
        cprint(f"\nSmoke test failed: {exc}", Color.RED)
        report = tester.report
        if args.json:
            print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
        return 1

    if args.json:
        print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))

    cprint("\nSmoke test passed.", Color.GREEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
