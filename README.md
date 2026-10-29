# ticketmaster-mcp

A Python MCP server that lets Claude (or any MCP client) search Ticketmaster events, artists and teams, and venues through the [Ticketmaster Discovery API v2](https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/).

It can answer questions like *"any comedy shows near me this weekend?"* or *"when does the next Warriors game go on sale?"*.

## Tools

| Tool | What it does |
| --- | --- |
| `search_events` | Searches events by keyword, `"lat,lng"` + radius, city or state, classification (e.g. `music`, `comedy`, `nba`), UTC date range, attraction id, or venue id. Supports several sort orders. |
| `get_event_details` | Returns one event's core fields plus sales windows, seat map, ticket limits, accessibility info, notes, and images. |
| `search_attractions` | Finds artists, teams, and shows by name, with genre and upcoming-event count. |
| `get_attraction_details` | Returns the full attraction record for an id. |
| `search_venues` | Finds venues by name and/or `"lat,lng"` + radius, city, or state. |
| `get_venue_details` | Returns the full venue record for an id. |

Event results are trimmed to the fields an LLM needs: date and time, status, sales window, venue with coordinates, performers, genre, and price ranges. This keeps responses small.

## Example

*This is an illustrative example of how Claude uses the tools. It is not a recorded transcript.*

> **You:** What comedy shows are on in San Francisco this weekend?
>
> **Claude:** *(calls `search_events` with `classification="comedy"`, `location="37.7749,-122.4194"`, `radius_miles=10`, and a Friday-to-Sunday UTC `start_datetime`/`end_datetime`)*
> I found several. *[Comedian]* is at Cobb's Comedy Club on Saturday at 7:00 PM, and *[Show]* is at ... Do you want sales details for one of them?
>
> **You:** The first one. Are tickets still on sale?
>
> **Claude:** *(calls `get_event_details` with that event's id)*
> Yes. Public sales are open until the show starts, with a ticket limit of ... Here's the Ticketmaster link: ...

## Requirements

- Python 3.10+
- A free Ticketmaster Discovery API key. Register at <https://developer-acct.ticketmaster.com/user/register> and create an app. The app's **Consumer Key** is your API key. Ticketmaster's portal lists the current rate limits.

## Install

```sh
git clone https://github.com/sourabhmadur/ticketmaster-mcp.git
cd ticketmaster-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # then set TICKETMASTER_API_KEY
```

## Connect to Claude

**Claude Code**

```sh
claude mcp add ticketmaster -e TICKETMASTER_API_KEY=your_key_here \
  -- /absolute/path/to/ticketmaster-mcp/.venv/bin/ticketmaster-mcp
```

**Claude Desktop**: add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ticketmaster": {
      "command": "/absolute/path/to/ticketmaster-mcp/.venv/bin/ticketmaster-mcp",
      "env": { "TICKETMASTER_API_KEY": "your_key_here" }
    }
  }
}
```

## Sanity check

This lists the registered tools. It makes no API calls.

```sh
python -c "import asyncio; from ticketmaster_mcp.server import mcp; print([t.name for t in asyncio.run(mcp.list_tools())])"
```

To check your key with one API call:

```sh
curl "https://app.ticketmaster.com/discovery/v2/events.json?size=1&apikey=$TICKETMASTER_API_KEY" | head -c 200
```

## Notes

- **Dates are UTC ISO-8601 with a `Z` suffix**, e.g. `2026-05-26T00:00:00Z`.
- **`classification` is matched loosely.** Values like `music`, `rock`, `sports`, and `nba` all work. Add `keyword` to narrow results.
- **For "events at venue X"**, look up the `venue_id` with `search_venues` first. Venue names aren't unique.

## Works well with

[google-maps-mcp](https://github.com/sourabhmadur/google-maps-mcp): its `get_my_location` returns the `"lat,lng"` that `search_events` uses for "near me" queries.
