"""Registry of official and secondary sources, plus the SSRF guard for every URL.

Reachability of each start URL was checked by hand on 2026-10-16; the result is
recorded in `verified` and `notes`. Unverified sources are skipped at run time
unless TINYFISH_ALLOW_UNVERIFIED_SOURCES=true.
"""
from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlsplit

from app.intel.evidence import AccessMethod, SourceType

Resolver = Callable[[str], list[str]]

STATE_CODES: dict[str, str] = {
    "andhra pradesh": "IN-AP", "arunachal pradesh": "IN-AR", "assam": "IN-AS", "bihar": "IN-BR",
    "chhattisgarh": "IN-CT", "goa": "IN-GA", "gujarat": "IN-GJ", "haryana": "IN-HR",
    "himachal pradesh": "IN-HP", "jharkhand": "IN-JH", "karnataka": "IN-KA", "kerala": "IN-KL",
    "madhya pradesh": "IN-MP", "maharashtra": "IN-MH", "manipur": "IN-MN", "meghalaya": "IN-ML",
    "mizoram": "IN-MZ", "nagaland": "IN-NL", "odisha": "IN-OR", "punjab": "IN-PB",
    "rajasthan": "IN-RJ", "sikkim": "IN-SK", "tamil nadu": "IN-TN", "telangana": "IN-TG",
    "tripura": "IN-TR", "uttar pradesh": "IN-UP", "uttarakhand": "IN-UT", "west bengal": "IN-WB",
    "delhi": "IN-DL", "jammu and kashmir": "IN-JK", "ladakh": "IN-LA", "puducherry": "IN-PY",
}

OFFICIAL_SUFFIXES: tuple[str, ...] = ("gov.in", "nic.in")
NEWS_DOMAINS: tuple[str, ...] = (
    "pib.gov.in", "thehindu.com", "indianexpress.com", "hindustantimes.com",
    "timesofindia.indiatimes.com", "ndtv.com", "newsonair.gov.in", "ddnews.gov.in",
)


def state_code(state: str | None) -> str | None:
    if not state:
        return None
    return STATE_CODES.get(" ".join(state.lower().split()))


@dataclass(frozen=True)
class Season:
    """Inclusive month-day window, e.g. 15 Jun to 15 Oct."""

    start: tuple[int, int]
    end: tuple[int, int]

    def contains(self, day: date) -> bool:
        md = (day.month, day.day)
        if self.start <= self.end:
            return self.start <= md <= self.end
        return md >= self.start or md <= self.end


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    authority: str
    source_type: SourceType
    jurisdictions: frozenset[str]
    domains: tuple[str, ...]
    access: AccessMethod
    start_url: str | None
    freshness_max_age: timedelta
    verified: bool
    notes: str
    season: Season | None = None
    allow_readonly_lookup: bool = False
    requires_setting: str | None = None
    fallback_of: str | None = None

    def covers(self, jurisdiction: str | None) -> bool:
        return "IN" in self.jurisdictions or (jurisdiction is not None and jurisdiction in self.jurisdictions)

    def in_season(self, day: date) -> bool:
        return self.season is None or self.season.contains(day)


def _src(**kw) -> Source:
    kw["jurisdictions"] = frozenset(kw["jurisdictions"])
    kw["domains"] = tuple(kw["domains"])
    return Source(**kw)


_SACHET_NOTE = (
    "RSS 2.0 feed fetched 2026-10-16; items link to CAP 1.2 XML via FetchXMLFile?identifier=. "
    "CWC river advisories appear here with level, warning and danger values."
)

_REGISTRY: tuple[Source, ...] = (
    _src(
        id="cwc_ffs", name="CWC Flood Forecast portal", authority="Central Water Commission",
        source_type=SourceType.official, jurisdictions={"IN"},
        domains=["ffs.india-water.gov.in", "india-water.gov.in", "cwc.gov.in"],
        access=AccessMethod.agent, start_url="https://ffs.india-water.gov.in/",
        freshness_max_age=timedelta(hours=6), verified=True,
        notes="Loaded 2026-10-16 (title 'Flood Forecast - Central Water Commision'). No documented API; JS app.",
    ),
    _src(
        id="imd_api", name="IMD district warnings API", authority="India Meteorological Department",
        source_type=SourceType.official, jurisdictions={"IN"}, domains=["api.imd.gov.in"],
        access=AccessMethod.api, start_url="https://api.imd.gov.in/api/v1/districtwarning",
        freshness_max_age=timedelta(hours=24), verified=False, requires_setting="imd_api_key",
        notes="api_reference.html lists /districtwarning fields (Day_1..5, Day1_Color..) but documents no auth "
              "mechanism; registration required. Unverified until a key is issued and the header is confirmed.",
    ),
    _src(
        id="imd_mausam", name="IMD district-wise warnings page", authority="India Meteorological Department",
        source_type=SourceType.official, jurisdictions={"IN"}, domains=["mausam.imd.gov.in"],
        access=AccessMethod.fetch, start_url="https://mausam.imd.gov.in/responsive/districtWiseWarningGIS.php",
        freshness_max_age=timedelta(hours=24), verified=True, fallback_of="imd_api",
        notes="Loaded 2026-10-16 (title 'DW Warnings | India Meteorological Department'). Labelled fallback "
              "for the IMD API; GIS page, so district colours may not be machine-extractable.",
    ),
    _src(
        id="sachet_in", name="NDMA SACHET CAP feed (All India)", authority="National Disaster Management Authority",
        source_type=SourceType.official, jurisdictions={"IN"}, domains=["sachet.ndma.gov.in"],
        access=AccessMethod.rss, start_url="https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml",
        freshness_max_age=timedelta(hours=24), verified=True, notes=_SACHET_NOTE,
    ),
    _src(
        id="sachet_bihar", name="NDMA SACHET CAP feed (Bihar)", authority="National Disaster Management Authority",
        source_type=SourceType.official, jurisdictions={"IN-BR"}, domains=["sachet.ndma.gov.in"],
        access=AccessMethod.rss, start_url="https://sachet.ndma.gov.in/cap_public_website/rss/rss_bihar.xml",
        freshness_max_age=timedelta(hours=24), verified=True, notes=_SACHET_NOTE,
    ),
    _src(
        id="sachet_assam", name="NDMA SACHET CAP feed (Assam)", authority="National Disaster Management Authority",
        source_type=SourceType.official, jurisdictions={"IN-AS"}, domains=["sachet.ndma.gov.in"],
        access=AccessMethod.rss, start_url="https://sachet.ndma.gov.in/cap_public_website/rss/rss_assam.xml",
        freshness_max_age=timedelta(hours=24), verified=True, notes=_SACHET_NOTE,
    ),
    _src(
        id="fmisc_bihar", name="Bihar FMISC daily flood page", authority="Water Resources Department, Bihar",
        source_type=SourceType.official, jurisdictions={"IN-BR"}, domains=["fmiscwrdbihar.gov.in"],
        access=AccessMethod.agent, start_url="https://fmiscwrdbihar.gov.in/fmis/DailyfloodInd.aspx",
        freshness_max_age=timedelta(hours=36), verified=True, season=Season((6, 15), (10, 15)),
        notes="Page loaded 2026-10-16; its 'Daily Flood Bulletin' PDF link returned 404 (season closed 15 Oct).",
    ),
    _src(
        id="asdma_reports", name="ASDMA daily flood reports", authority="Assam State Disaster Management Authority",
        source_type=SourceType.official, jurisdictions={"IN-AS"}, domains=["asdma.gov.in"],
        access=AccessMethod.fetch, start_url="https://asdma.gov.in/",
        freshness_max_age=timedelta(hours=36), verified=False,
        notes="Connection refused on ports 80 and 443 from the test network on 2026-10-16.",
    ),
    _src(
        id="ntes", name="NTES train running status", authority="Indian Railways (CRIS)",
        source_type=SourceType.official, jurisdictions={"IN"}, domains=["enquiry.indianrail.gov.in"],
        access=AccessMethod.agent, start_url="https://enquiry.indianrail.gov.in/mntes/",
        freshness_max_age=timedelta(hours=6), verified=True, allow_readonly_lookup=True,
        notes="/ntes/ redirects to /mntes/ which loaded 2026-10-16 (title 'NTES') with cancelled/diverted/"
              "rescheduled sections. Read-only lookups only; stop on CAPTCHA. IRCTC is out of scope.",
    ),
    _src(
        id="nhai_notices", name="NHAI / MoRTH notices", authority="National Highways Authority of India",
        source_type=SourceType.official, jurisdictions={"IN"},
        domains=["nhai.gov.in", "morth.gov.in", "morth.nic.in"],
        access=AccessMethod.search, start_url=None,
        freshness_max_age=timedelta(hours=48), verified=True,
        notes="nhai.gov.in and morth.nic.in loaded 2026-10-16. Discovered via TinyFish Search restricted to "
              "these domains, then read with Fetch.",
    ),
    _src(
        id="bihar_dmd", name="Bihar Disaster Management Department", authority="Government of Bihar",
        source_type=SourceType.official, jurisdictions={"IN-BR"}, domains=["state.bihar.gov.in"],
        access=AccessMethod.agent, start_url="https://state.bihar.gov.in/disastermgmt/CitizenHome.html",
        freshness_max_age=timedelta(hours=36), verified=False,
        notes="Redirect loop on 2026-10-16 (302 to itself); disastermgmt.bih.nic.in does not resolve.",
    ),
    _src(
        id="ndma_contact", name="NDMA contact page", authority="National Disaster Management Authority",
        source_type=SourceType.official, jurisdictions={"IN"}, domains=["ndma.gov.in"],
        access=AccessMethod.fetch, start_url="https://ndma.gov.in/en/contact-us",
        freshness_max_age=timedelta(days=30), verified=True,
        notes="Loaded 2026-10-16; lists the NDMA Control Room number.",
    ),
    _src(
        id="fmisc_contacts", name="FMISC Bihar home page", authority="Water Resources Department, Bihar",
        source_type=SourceType.official, jurisdictions={"IN-BR"}, domains=["fmiscwrdbihar.gov.in"],
        access=AccessMethod.fetch, start_url="https://fmiscwrdbihar.gov.in/",
        freshness_max_age=timedelta(days=30), verified=True,
        notes="Loaded 2026-10-16; lists the Central Flood Control Room phone number.",
    ),
    _src(
        id="research_brief", name="TinyFish Research (official domains)", authority="TinyFish Research synthesis",
        source_type=SourceType.secondary, jurisdictions={"IN"}, domains=list(OFFICIAL_SUFFIXES),
        access=AccessMethod.research, start_url=None,
        freshness_max_age=timedelta(hours=72), verified=True,
        notes="Synthesised report; citations are checked against the official-domain allowlist.",
    ),
    _src(
        id="news_search", name="News search (district name only)", authority="News media",
        source_type=SourceType.secondary, jurisdictions={"IN"}, domains=list(NEWS_DOMAINS),
        access=AccessMethod.search, start_url=None,
        freshness_max_age=timedelta(hours=24), verified=True,
        notes="TinyFish Search with domain_type=news over an allowlist of news domains. Query is built from the "
              "district name only, never from citizen report text.",
    ),
    _src(
        id="nbpdcl", name="NBPDCL (North Bihar power distribution)", authority="North Bihar Power Distribution Co.",
        source_type=SourceType.official, jurisdictions={"IN-BR"}, domains=["nbpdcl.co.in"],
        access=AccessMethod.agent, start_url="https://nbpdcl.co.in/",
        freshness_max_age=timedelta(hours=12), verified=False,
        notes="Home page returned 200 on 2026-10-16 but with an empty title; no outage notice page located.",
    ),
    _src(
        id="apdcl", name="APDCL (Assam power distribution)", authority="Assam Power Distribution Co. Ltd",
        source_type=SourceType.official, jurisdictions={"IN-AS"}, domains=["apdcl.org"],
        access=AccessMethod.agent, start_url="https://www.apdcl.org/website/",
        freshness_max_age=timedelta(hours=12), verified=True,
        notes="Loaded 2026-10-16 (title 'APDCL | Assam Power Distribution Company Limited').",
    ),
    _src(
        id="bihar_health", name="Bihar Health Department", authority="Government of Bihar",
        source_type=SourceType.official, jurisdictions={"IN-BR"}, domains=["state.bihar.gov.in"],
        access=AccessMethod.agent, start_url="https://state.bihar.gov.in/health/CitizenHome.html",
        freshness_max_age=timedelta(hours=12), verified=False,
        notes="health.bihar.gov.in does not resolve and state.bihar.gov.in looped on 2026-10-16.",
    ),
)

SOURCES: dict[str, Source] = {s.id: s for s in _REGISTRY}


def host_matches(host: str, domains: Iterable[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in domains)


def is_official_url(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host_matches(host, OFFICIAL_SUFFIXES)


def default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def is_public_ip(raw: str) -> bool:
    ip = ipaddress.ip_address(raw.split("%", 1)[0])
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
    )


def url_rejection(url: str, domains: Iterable[str], resolver: Resolver | None = None) -> str | None:
    """Return why `url` is unsafe to request, or None when it is allowed.

    With `resolver=None` DNS is not consulted (used for URLs TinyFish fetches on
    its own infrastructure); pass a resolver for any request Aegis makes itself.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "unparseable"
    if parts.scheme not in ("http", "https"):
        return "scheme"
    host = (parts.hostname or "").lower()
    if not host:
        return "no_host"
    if parts.username or parts.password:
        return "userinfo"
    try:
        ipaddress.ip_address(host)
        return "ip_literal"
    except ValueError:
        pass
    if host == "localhost" or host.endswith(".localhost") or "." not in host:
        return "local_host"
    if not host_matches(host, domains):
        return "host_not_allowlisted"
    if resolver is not None:
        try:
            addresses = resolver(host)
        except OSError:
            return "dns_failure"
        if not addresses:
            return "dns_failure"
        if not all(is_public_ip(a) for a in addresses):
            return "private_address"
    return None


def is_allowed_url(url: str, source: Source, resolver: Resolver | None = default_resolver) -> bool:
    return url_rejection(url, source.domains, resolver) is None
