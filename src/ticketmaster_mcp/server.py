"""Ticketmaster MCP server.

Exposes tools that query the Ticketmaster Discovery API v2 for events,
attractions (artists/teams), and venues. Auth is a single API key passed as
the `apikey` query param (set TICKETMASTER_API_KEY in .env).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
for parent in Path(__file__).resolve().parents:
    env_path = parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)
        break

API_BASE = "https://app.ticketmaster.com/discovery/v2"


def _api_key() -> str:
    key = os.environ.get("TICKETMASTER_API_KEY")
    if not key:
        raise RuntimeError(
            "TICKETMASTER_API_KEY is not set. Copy .env.example to .env and "
            "paste your Ticketmaster Discovery API consumer key."
        )
    return key


def _http() -> httpx.Client:
    return httpx.Client(timeout=20.0)


def _get(path: str, params: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    params = {k: v for k, v in params.items() if v is not None and v != ""}
    params["apikey"] = _api_key()
    resp = client.get(f"{API_BASE}/{path.lstrip('/')}", params=params)
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


def _parse_latlong(s: str) -> str:
    """Accept 'lat,lng' and return Ticketmaster's 'lat,long' format."""
    lat_s, lng_s = s.split(",", 1)
    return f"{float(lat_s.strip())},{float(lng_s.strip())}"


def _strip_event(e: dict[str, Any]) -> dict[str, Any]:
    """Trim a Discovery event into the fields most useful for an LLM."""
    dates = e.get("dates", {})
    start = dates.get("start", {})
    venues = (e.get("_embedded") or {}).get("venues") or []
    attractions = (e.get("_embedded") or {}).get("attractions") or []
    price_ranges = e.get("priceRanges") or []
    classifications = e.get("classifications") or []
    return {
        "id": e.get("id"),
        "name": e.get("name"),
        "url": e.get("url"),
        "start_local": start.get("localDate"),
        "start_local_time": start.get("localTime"),
        "start_datetime": start.get("dateTime"),
        "timezone": dates.get("timezone"),
        "status": dates.get("status", {}).get("code"),
        "sales_public_start": (e.get("sales") or {}).get("public", {}).get("startDateTime"),
        "sales_public_end": (e.get("sales") or {}).get("public", {}).get("endDateTime"),
        "venue": (
            {
                "id": venues[0].get("id"),
                "name": venues[0].get("name"),
                "city": (venues[0].get("city") or {}).get("name"),
                "state": (venues[0].get("state") or {}).get("stateCode"),
                "country": (venues[0].get("country") or {}).get("countryCode"),
                "address": (venues[0].get("address") or {}).get("line1"),
                "postal_code": venues[0].get("postalCode"),
                "lat": (venues[0].get("location") or {}).get("latitude"),
                "lng": (venues[0].get("location") or {}).get("longitude"),
            }
            if venues
            else None
        ),
        "attractions": [
            {"id": a.get("id"), "name": a.get("name"), "type": a.get("type")}
            for a in attractions
        ],
        "classifications": [
            {
                "segment": (c.get("segment") or {}).get("name"),
                "genre": (c.get("genre") or {}).get("name"),
                "subGenre": (c.get("subGenre") or {}).get("name"),
            }
            for c in classifications
        ],
        "price_ranges": [
            {
                "type": pr.get("type"),
                "min": pr.get("min"),
                "max": pr.get("max"),
                "currency": pr.get("currency"),
            }
            for pr in price_ranges
        ],
    }


mcp = FastMCP("ticketmaster")


@mcp.tool()
def search_events(
    keyword: str | None = None,
    location: str | None = None,
    radius_miles: int = 25,
    classification: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    city: str | None = None,
    state_code: str | None = None,
    country_code: str = "US",
    attraction_id: str | None = None,
    venue_id: str | None = None,
    sort: str = "date,asc",
    max_results: int = 20,
) -> dict[str, Any]:
    """Search Ticketmaster Discovery events.

    Args:
        keyword: Free-form search ("Taylor Swift", "Warriors", "Hamilton").
        location: "lat,lng" to geo-filter (uses geoPoint + radius).
        radius_miles: Radius around `location` in miles (default 25).
        classification: Segment/genre name ("music", "sports", "arts & theatre",
            "comedy", "rock", etc.). Case-insensitive.
        start_datetime: ISO-8601 UTC, e.g. "2026-05-26T00:00:00Z". Inclusive.
        end_datetime: ISO-8601 UTC. Inclusive.
        city: City name filter (alternative to lat/lng).
        state_code: 2-letter state code, e.g. "CA".
        country_code: 2-letter ISO country, default "US".
        attraction_id: Filter to events featuring a specific attraction id.
        venue_id: Filter to events at a specific venue id.
        sort: One of "date,asc", "date,desc", "relevance,desc", "name,asc",
            "distance,asc" (requires location), "random".
        max_results: Number of events to return (1-200; default 20).
    """
    params: dict[str, Any] = {
        "keyword": keyword,
        "radius": radius_miles,
        "unit": "miles",
        "classificationName": classification,
        "startDateTime": start_datetime,
        "endDateTime": end_datetime,
        "city": city,
        "stateCode": state_code,
        "countryCode": country_code,
        "attractionId": attraction_id,
        "venueId": venue_id,
        "sort": sort,
        "size": max(1, min(max_results, 200)),
    }
    if location:
        params["geoPoint"] = _parse_latlong(location)

    with _http() as client:
        data = _get("events.json", params, client)
    if "error" in data:
        return data
    events = (data.get("_embedded") or {}).get("events") or []
    page = data.get("page", {})
    return {
        "total": page.get("totalElements"),
        "page": page.get("number"),
        "size": page.get("size"),
        "events": [_strip_event(e) for e in events],
    }


@mcp.tool()
def get_event_details(event_id: str) -> dict[str, Any]:
    """Fetch full details for an event by Ticketmaster id (e.g. 'G5vYZ...').

    Returns the trimmed core fields plus the raw `seatmap`, `info`,
    `pleaseNote`, `ticketLimit`, and accessibility data when present.
    """
    with _http() as client:
        data = _get(f"events/{event_id}.json", {}, client)
    if "error" in data:
        return data
    trimmed = _strip_event(data)
    extras = {
        k: data.get(k)
        for k in ("info", "pleaseNote", "seatmap", "ticketLimit", "accessibility", "images")
        if data.get(k) is not None
    }
    return {**trimmed, **extras}


@mcp.tool()
def search_attractions(
    keyword: str,
    classification: str | None = None,
    country_code: str | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """Search artists, teams, and other attractions by name.

    Args:
        keyword: Name to search ("Beyonce", "Lakers").
        classification: Optional filter ("music", "sports", ...).
        country_code: Optional 2-letter ISO country.
        max_results: 1-200; default 10.
    """
    params: dict[str, Any] = {
        "keyword": keyword,
        "classificationName": classification,
        "countryCode": country_code,
        "size": max(1, min(max_results, 200)),
    }
    with _http() as client:
        data = _get("attractions.json", params, client)
    if "error" in data:
        return data
    items = (data.get("_embedded") or {}).get("attractions") or []
    return {
        "total": data.get("page", {}).get("totalElements"),
        "attractions": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "type": a.get("type"),
                "url": a.get("url"),
                "classifications": [
                    {
                        "segment": (c.get("segment") or {}).get("name"),
                        "genre": (c.get("genre") or {}).get("name"),
                        "subGenre": (c.get("subGenre") or {}).get("name"),
                    }
                    for c in (a.get("classifications") or [])
                ],
                "upcomingEvents_total": (a.get("upcomingEvents") or {}).get("_total"),
            }
            for a in items
        ],
    }


@mcp.tool()
def get_attraction_details(attraction_id: str) -> dict[str, Any]:
    """Fetch full details for an attraction (artist/team) by id."""
    with _http() as client:
        data = _get(f"attractions/{attraction_id}.json", {}, client)
    return data


@mcp.tool()
def search_venues(
    keyword: str | None = None,
    location: str | None = None,
    radius_miles: int = 25,
    city: str | None = None,
    state_code: str | None = None,
    country_code: str = "US",
    max_results: int = 10,
) -> dict[str, Any]:
    """Search venues by name and/or location.

    Args:
        keyword: Venue name filter ("Chase Center").
        location: "lat,lng" to geo-filter.
        radius_miles: Radius around `location` (default 25).
        city: City name filter.
        state_code: 2-letter state, e.g. "CA".
        country_code: 2-letter ISO country, default "US".
        max_results: 1-200; default 10.
    """
    params: dict[str, Any] = {
        "keyword": keyword,
        "radius": radius_miles,
        "unit": "miles",
        "city": city,
        "stateCode": state_code,
        "countryCode": country_code,
        "size": max(1, min(max_results, 200)),
    }
    if location:
        params["geoPoint"] = _parse_latlong(location)

    with _http() as client:
        data = _get("venues.json", params, client)
    if "error" in data:
        return data
    items = (data.get("_embedded") or {}).get("venues") or []
    return {
        "total": data.get("page", {}).get("totalElements"),
        "venues": [
            {
                "id": v.get("id"),
                "name": v.get("name"),
                "url": v.get("url"),
                "city": (v.get("city") or {}).get("name"),
                "state": (v.get("state") or {}).get("stateCode"),
                "country": (v.get("country") or {}).get("countryCode"),
                "address": (v.get("address") or {}).get("line1"),
                "postal_code": v.get("postalCode"),
                "lat": (v.get("location") or {}).get("latitude"),
                "lng": (v.get("location") or {}).get("longitude"),
                "timezone": v.get("timezone"),
            }
            for v in items
        ],
    }


@mcp.tool()
def get_venue_details(venue_id: str) -> dict[str, Any]:
    """Fetch full details for a venue by Ticketmaster id."""
    with _http() as client:
        data = _get(f"venues/{venue_id}.json", {}, client)
    return data


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
