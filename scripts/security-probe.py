#!/usr/bin/env python3
"""Attacks a deployed Ctrl Academy the way an outsider would, and fails if any attack works.

    STAGING_PASSWORD=... python3 scripts/security-probe.py --base https://staging.ctrlacademy.co.za

Standard library only. It creates a few accounts named probe-<time>-*@example.com and stays well
inside the rate limits, except where it tests them on purpose (about 25 logins, one account).
Running it twice within ten minutes from one address can hit the registration limit; wait.
SE document §14, "Security review".
"""

import argparse
import base64
import concurrent.futures
import statistics
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

UA = "ctrl-academy-security-probe"
results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    results.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


class Site:
    def __init__(self, base: str, gate: str | None) -> None:
        self.base = base.rstrip("/")
        self.gate = gate

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        cookie: str | None = None,
        headers: dict[str, str] | None = None,
        raw: bytes | None = None,
        content_type: str = "application/json",
        gate: bool = True,
        absolute: str | None = None,
    ) -> tuple[int, dict[str, str], str]:
        cookies = [c for c in [self.gate if gate else None, cookie] if c]
        h = {"User-Agent": UA, **({"Cookie": "; ".join(cookies)} if cookies else {})}
        h.update(headers or {})
        data = raw if raw is not None else None if body is None else json.dumps(body).encode()
        if data is not None:
            h["Content-Type"] = content_type
        url = absolute or self.base + path
        req = urllib.request.Request(url, method=method, data=data, headers=h)
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(req, timeout=30) as res:
                return (
                    res.status,
                    {k.lower(): v for k, v in res.headers.items()},
                    res.read().decode(errors="replace"),
                )
        except urllib.error.HTTPError as e:
            return (
                e.code,
                {k.lower(): v for k, v in e.headers.items()},
                e.read().decode(errors="replace"),
            )

    def register(self, email: str, password: str, name: str = "Probe") -> tuple[str, int]:
        status, headers, body = self.request(
            "POST",
            "/api/auth/register",
            {"email": email, "password": password, "displayName": name},
        )
        if status != 201:
            sys.exit(f"setup failed: register returned {status} {body[:200]}")
        return session_cookie(headers), json.loads(body)["id"]

    def login(self, email: str, password: str) -> str:
        status, headers, body = self.request(
            "POST", "/api/auth/login", {"email": email, "password": password}
        )
        if status != 200:
            sys.exit(f"setup failed: login returned {status} {body[:200]}")
        return session_cookie(headers)

    def me(self, cookie: str | None, **kw: Any) -> int:
        return self.request("GET", "/api/auth/me", cookie=cookie, **kw)[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def session_cookie(headers: dict[str, str]) -> str:
    value = headers.get("set-cookie", "")
    assert value.startswith("session="), f"no session cookie in {value[:80]!r}"
    return value.split(";")[0]


def b64(data: dict[str, Any] | bytes) -> str:
    raw = data if isinstance(data, bytes) else json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64(part: str) -> dict[str, Any]:
    decoded: dict[str, Any] = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    return decoded


def hs(
    header: dict[str, Any], claims: dict[str, Any], key: bytes, digest: Any = hashlib.sha256
) -> str:
    signing = f"{b64(header)}.{b64(claims)}"
    return f"{signing}.{b64(hmac.new(key, signing.encode(), digest).digest())}"


def forged_tokens(sample: str, victim_id: int) -> dict[str, str]:
    """Tokens claiming to be the victim, built without the server's key."""
    head, payload, signature = sample.split(".")
    now = int(time.time())
    claims = {"sub": str(victim_id), "ver": 0, "iat": now, "exp": now + 3600}
    mine = unb64(payload)
    return {
        "alg none": f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}.",
        "alg None": f"{b64({'alg': 'None', 'typ': 'JWT'})}.{b64(claims)}.",
        "own token, subject swapped": f"{head}.{b64({**mine, 'sub': str(victim_id)})}.{signature}",
        "own token, version raised": f"{head}.{b64({**mine, 'ver': mine['ver'] + 1})}.{signature}",
        "own token, expiry extended": f"{head}.{b64({**mine, 'exp': now + 10**8})}.{signature}",
        "own token, signature removed": f"{head}.{payload}.",
        "HS256, empty key": hs({"alg": "HS256", "typ": "JWT"}, claims, b""),
        "HS256, key 'secret'": hs({"alg": "HS256", "typ": "JWT"}, claims, b"secret"),
        "HS256, key 'change-me'": hs({"alg": "HS256", "typ": "JWT"}, claims, b"change-me"),
        "HS512, empty key": hs({"alg": "HS512", "typ": "JWT"}, claims, b"", hashlib.sha512),
        "RS256 header, HMAC signature": hs({"alg": "RS256", "typ": "JWT"}, claims, b"secret"),
        "kid pointing at /dev/null": hs(
            {"alg": "HS256", "typ": "JWT", "kid": "../../../../dev/null"}, claims, b""
        ),
        "jku pointing at attacker keys": hs(
            {"alg": "HS256", "typ": "JWT", "jku": "https://evil.example/keys.json"}, claims, b"x"
        ),
        "embedded jwk": hs(
            {"alg": "HS256", "typ": "JWT", "jwk": {"kty": "oct", "k": b64(b"x")}}, claims, b"x"
        ),
    }


def run(site: Site) -> None:
    tag = f"probe-{int(time.time())}"
    victim_email, victim_pw = f"{tag}-victim@example.com", "victim password 1"
    attacker_email, attacker_pw = f"{tag}-attacker@example.com", "attacker password 1"
    victim_cookie, victim_id = site.register(victim_email, victim_pw, "Victim")
    attacker_cookie, _ = site.register(attacker_email, attacker_pw, "Attacker")
    sample = attacker_cookie.split("=", 1)[1]

    print("\nForging a session (becoming the victim without their password)")
    for name, token in forged_tokens(sample, victim_id).items():
        status = site.me(f"session={token}")
        check(status == 401, name, f"/me -> {status}")

    print("\nThe token itself")
    claims = unb64(sample.split(".")[1])
    check(set(claims) == {"sub", "ver", "iat", "exp"}, "carries no personal data", ",".join(claims))
    check(unb64(sample.split(".")[0]).get("alg") == "HS256", "signed with HS256")
    check(
        site.me(None, headers={"Authorization": f"Bearer {sample}"}) == 401,
        "an Authorization header is not a second way in",
    )

    print("\nStolen cookies")
    second_device = site.login(victim_email, victim_pw)
    status = site.request("POST", "/api/auth/logout", cookie=victim_cookie)[0]
    check(status == 204, "victim logs out", str(status))
    check(site.me(victim_cookie) == 401, "replaying the logged-out cookie fails")
    check(site.me(second_device) == 401, "the victim's other device is logged out too")
    victim_cookie = site.login(victim_email, victim_pw)
    check(site.me(victim_cookie) == 200, "the victim can log in again")
    both = f"{victim_cookie}; session=garbage"
    check(site.me(both) in (200, 401), "two session cookies don't crash the API")

    print("\nCross-site requests")
    body = json.dumps({"email": victim_email, "password": victim_pw}).encode()
    for content_type in ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data"]:
        status = site.request("POST", "/api/auth/login", raw=body, content_type=content_type)[0]
        check(
            status == 422,
            f"login as {content_type} (what a form on another site sends)",
            str(status),
        )
    status, headers, _ = site.request(
        "OPTIONS",
        "/api/auth/me",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    check("access-control-allow-origin" not in headers, "no CORS for other origins", str(status))

    print("\nMethods that aren't routes")
    for method, path in [
        ("GET", "/api/auth/logout"),
        ("GET", "/api/auth/login"),
        ("PUT", "/api/auth/me"),
        ("DELETE", "/api/auth/me"),
        ("PATCH", "/api/auth/register"),
    ]:
        status = site.request(method, path, cookie=victim_cookie)[0]
        check(status == 405, f"{method} {path}", str(status))

    print("\nHostile input (must be refused, never a server error)")
    payloads = {
        "SQL in email": {"email": "' OR '1'='1'--@x.com", "password": "x"},
        "SQL in password": {"email": victim_email, "password": "' OR '1'='1"},
        "null byte in password": {"email": victim_email, "password": "abc\u0000def"},
        "null byte in email": {"email": "vic\u0000tim@example.com", "password": "x"},
        "email as a list": {"email": [victim_email], "password": victim_pw},
        "password as an object": {"email": victim_email, "password": {"$ne": ""}},
        "password as true": {"email": victim_email, "password": True},
        "operator in email": {"email": {"$gt": ""}, "password": "x"},
        "missing fields": {},
        "200 kB password": {"email": victim_email, "password": "a" * 200_000},
    }
    for name, payload in payloads.items():
        status, _, text = site.request("POST", "/api/auth/login", payload)
        check(status in (401, 413, 422) and "Traceback" not in text, name, str(status))
    deep = "[" * 5000 + json.dumps(victim_email) + "]" * 5000
    status, _, _ = site.request(
        "POST", "/api/auth/login", raw=f'{{"email":{deep},"password":"x"}}'.encode()
    )
    check(status in (400, 413, 422), "JSON nested 5000 deep", str(status))
    status, _, text = site.request(
        "POST", "/api/auth/login", raw=b'{"email": "x@y.co", "password": '
    )
    check(status == 422 and "Traceback" not in text, "broken JSON", str(status))
    status = site.request("POST", "/api/auth/register", raw=b"{" + b" " * 2_000_000 + b"}")[0]
    check(status in (413, 422), "2 MB request body", str(status))

    print("\nAccount confusion")
    for name, email in [
        ("same email, different case", victim_email.upper()),
        ("same email, spaces around it", f"  {victim_email}  "),
    ]:
        status = site.request(
            "POST",
            "/api/auth/register",
            {"email": email, "password": "another pw 1", "displayName": "Copy"},
        )[0]
        check(status in (409, 422), f"register {name}", str(status))
    status = site.request(
        "POST",
        "/api/auth/register",
        {
            "email": f"{tag}-x@example.com",
            "password": "another pw 1",
            "displayName": "X",
            "id": victim_id,
        },
    )[0]
    check(status == 422, "register choosing your own user ID", str(status))

    print("\nRate limits")
    wrong = {"email": attacker_email, "password": "definitely wrong"}
    statuses = [site.request("POST", "/api/auth/login", wrong)[0] for _ in range(11)]
    check(
        statuses[:10] == [401] * 10 and statuses[10] == 429,
        "11th guess at one account is refused",
        str(statuses),
    )
    for header in [
        "X-Forwarded-For",
        "X-Real-IP",
        "Forwarded",
        "CF-Connecting-IP",
        "True-Client-IP",
    ]:
        statuses = [
            site.request("POST", "/api/auth/login", wrong, headers={header: f"203.0.113.{n}"})[0]
            for n in range(2)
        ]
        # 429: our limit held. 403: Cloudflare refused the forged header before it reached us.
        check(
            all(s in (403, 429) for s in statuses),
            f"a fake {header} doesn't reset it",
            str(statuses),
        )
    status = site.request(
        "POST", "/api/auth/login", {"email": victim_email, "password": "one typo"}
    )[0]
    check(status == 401, "another account from the same address is not locked", str(status))

    print("\nHeaders and files")
    for path in ["/login", "/"]:
        _, headers, _ = site.request("GET", path)
        csp = headers.get("content-security-policy", "")
        check("frame-ancestors 'none'" in csp and "script-src 'self'" in csp, f"CSP on {path}")
        check(headers.get("x-frame-options") == "DENY", f"X-Frame-Options on {path}")
        check("max-age" in headers.get("strict-transport-security", ""), f"HSTS on {path}")
        check(headers.get("x-content-type-options") == "nosniff", f"nosniff on {path}")
    _, headers, _ = site.request("GET", "/api/health")
    check(headers.get("x-content-type-options") == "nosniff", "nosniff on the API")
    for path in [
        "/.env", "/.git/config", "/nginx.conf", "/security-headers.conf", "/etc/passwd",
        "/../../../../etc/passwd", "/assets/..%2f..%2f..%2fetc%2fpasswd", "/staging-gate.sh",
        "/Dockerfile", "/package.json",
    ]:  # fmt: skip
        status, headers, text = site.request("GET", path)
        leaked = any(
            s in text
            for s in [
                "root:x:",
                "[core]",
                "SECRET_KEY",
                "proxy_pass",
                "STAGING_PASSWORD",
                '"devDependencies"',
            ]
        )
        check(not leaked, f"GET {path} reveals nothing", str(status))
    if site.base.startswith("https://"):
        status, headers, _ = site.request(
            "GET", "", absolute="http://" + site.base[len("https://") :] + "/login"
        )
        check(
            status in (301, 302, 307, 308) and headers.get("location", "").startswith("https://"),
            "plain http redirects to https",
            str(status),
        )


def responses_and_races(site: Site, tag: str) -> None:
    print("\nCookies, caching and responses")
    email, password = f"{tag}-cookie@example.com", "cookie test pw 1"
    status, headers, _ = site.request(
        "POST", "/api/auth/register", {"email": email, "password": password, "displayName": "C"}
    )
    cookie = headers.get("set-cookie", "")
    attrs = {a.strip().split("=")[0].lower(): a.strip() for a in cookie.split(";")[1:]}
    check("httponly" in attrs, "session cookie is HttpOnly (scripts can't read it)")
    check("secure" in attrs, "session cookie is Secure (HTTPS only)")
    check(attrs.get("samesite", "").lower() == "samesite=lax", "session cookie is SameSite=Lax")
    check(attrs.get("path") == "Path=/", "session cookie path is /")
    check("domain" not in attrs, "session cookie has no Domain (never sent to other subdomains)")
    check(
        attrs.get("max-age") == "Max-Age=1209600", "session lasts 14 days", attrs.get("max-age", "")
    )
    token = cookie.split(";")[0].split("=", 1)[1]
    claims = unb64(token.split(".")[1])
    check(claims["exp"] - claims["iat"] == 14 * 86400, "token expires 14 days after it was issued")
    session = cookie.split(";")[0]
    for path in ["/api/auth/me", "/api/health"]:
        _, headers, _ = site.request("GET", path, cookie=session)
        check(
            headers.get("cache-control") == "no-store",
            f"{path} is never cached",
            headers.get("cache-control", "(none)"),
        )
    status, headers, _ = site.request(
        "POST", "/api/auth/login", {"email": email, "password": "wrong!"}
    )
    check(
        status == 401 and "set-cookie" not in headers, "a failed login sets no cookie", str(status)
    )
    status, headers, _ = site.request("POST", "/api/auth/logout", cookie=session)
    check(
        "max-age=0" in headers.get("set-cookie", "").lower(),
        "logout deletes the cookie in the browser",
    )
    for method in ["TRACE", "CONNECT"]:
        status = site.request(method, "/api/health")[0]
        check(status in (400, 403, 405, 501), f"{method} is refused", str(status))

    print("\nRaces")
    race = f"{tag}-race@example.com"

    def attempt(_: int) -> int:
        return site.request(
            "POST",
            "/api/auth/register",
            {"email": race, "password": "race pw 1234", "displayName": "R"},
        )[0]

    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        statuses = sorted(pool.map(attempt, range(5)))
    check(
        statuses.count(201) == 1 and statuses.count(409) == 4,
        "5 simultaneous registrations of one email make one account",
        str(statuses),
    )

    print("\nInformation from timing")
    times: dict[str, list[float]] = {"known": [], "unknown": []}
    for _ in range(5):
        for label, address in [("known", email), ("unknown", f"{tag}-nobody@example.com")]:
            start = time.perf_counter()
            site.request("POST", "/api/auth/login", {"email": address, "password": "wrong pw 1"})
            times[label].append(time.perf_counter() - start)
    known, unknown = statistics.median(times["known"]), statistics.median(times["unknown"])
    check(
        abs(known - unknown) < 0.15,
        "a wrong password and an unknown email take the same time",
        f"{known * 1000:.0f} ms vs {unknown * 1000:.0f} ms",
    )

    print("\nLook-alike emails")
    lookalike = "\uff41" + email[1:] if email[0] == "a" else email.replace("e", "\u0435", 1)
    status = site.request(
        "POST",
        "/api/auth/register",
        {"email": lookalike, "password": "lookalike pw 1", "displayName": "L"},
    )[0]
    check(status in (201, 409, 422), "registering a look-alike of an existing email", str(status))
    status = site.request(
        "POST", "/api/auth/login", {"email": email, "password": "lookalike pw 1"}
    )[0]
    check(status == 401, "the look-alike's password does not open the real account", str(status))


def gate_bypass(site: Site) -> None:
    print("\nStaging gate (no team-password cookie)")
    for path in [
        "/api/health", "/api/auth/me", "//api/health", "/API/health", "/%61pi/health",
        "/favicon.svg/../api/health", "/__gate/../api/health", "/__gate/%2e%2e/api/health",
        "/healthz/../api/health", "/api/health?x=/__gate/", "/api/health#/__gate/",
        "/api/health%00", "/./api/health", "/api/./health", "/ui-kit", "/assets/",
    ]:  # fmt: skip
        status, _, text = site.request("GET", path, gate=False)
        exposed = status == 200 and (
            '"status"' in text or "Ctrl Academy UI kit" in text or '<div id="root">' in text
        )
        check(not exposed, f"GET {path}", str(status))
    status, _, text = site.request(
        "POST",
        "/api/auth/register",
        {"email": "x@y.co", "password": "12345678", "displayName": "x"},
        gate=False,
    )
    check(status == 401, "register without the gate cookie", str(status))
    status = site.request("GET", "/api/health", gate=False, cookie="ctrl_staging=" + "0" * 64)[0]
    check(status == 401, "a made-up gate cookie", str(status))
    _, headers, _ = site.request("GET", "/login", gate=False)
    check(
        headers.get("x-frame-options") == "DENY"
        and "frame-ancestors 'none'" in headers.get("content-security-policy", ""),
        "the gate page can't be framed by another site",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="https://staging.ctrlacademy.co.za")
    args = parser.parse_args()
    password = os.environ.get("STAGING_PASSWORD")
    gate = None
    if password:
        gate = (
            "ctrl_staging="
            + hashlib.sha256(f"ctrl-academy-staging:{password}".encode()).hexdigest()
        )
    site = Site(args.base, gate)
    print(f"Probing {site.base}")
    if gate:
        gate_bypass(site)
    run(site)
    responses_and_races(site, f"probe-{int(time.time())}")
    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    for _, name, detail in failed:
        print(f"  FAIL  {name}  ({detail})")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
