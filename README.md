# ticketmaster-mcp

An MCP server that gives Claude (or any MCP client) access to the
[Ticketmaster Discovery API](https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/)
so it can answer questions like *"any Taylor Swift shows near me in the next
60 days?"* or *"what's on at Chase Center this weekend?"*.

## Tools

| Tool | Purpose |
| --- | --- |
| `search_events` | Search events by keyword, location, classification, date range, attraction, or venue. |
| `get_event_details` | Full details (sales windows, seatmap, accessibility, info) for one event id. |
| `search_attractions` | Find artists, teams, and other attractions by name. |
| `get_attraction_details` | Profile + upcoming-event count for one attraction id. |
| `search_venues` | Find venues by name and/or location. |
| `get_venue_details` | Full venue profile by id. |

Any tool that takes a `location` accepts `"lat,lng"`. Pair it with the
`google-maps-mcp` server's `get_my_location` for "near me" queries.

## Setup

### 1. Get a Discovery API key

1. Register at https://developer-acct.ticketmaster.com/user/register.
2. Create an app; the "Consumer Key" is your API key.
3. The free tier gives 5,000 calls/day at 5 requests/second — plenty for
   interactive use.

### 2. Install the server

```sh
cd ticketmaster_mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# paste your TICKETMASTER_API_KEY
```

### 3. Register with Claude Code

```sh
claude mcp add ticketmaster \
  --command "/absolute/path/to/ticketmaster_mcp/.venv/bin/ticketmaster-mcp" \
  --env TICKETMASTER_API_KEY=your_key_here
```

Or with `uv`:

```sh
claude mcp add ticketmaster \
  --command "uv" \
  --args "run" "--directory" "/absolute/path/to/ticketmaster_mcp" "ticketmaster-mcp" \
  --env TICKETMASTER_API_KEY=your_key_here
```

## Quick sanity check

```sh
source .venv/bin/activate
python -c "from ticketmaster_mcp.server import mcp; print([t.name for t in mcp._tool_manager.list_tools()])"
```

You should see all six tool names. To smoke-test the API key:

```sh
curl "https://app.ticketmaster.com/discovery/v2/events.json?size=1&apikey=$TICKETMASTER_API_KEY" | head -c 200
```

## Example prompts

- *"Find rock concerts within 25 miles of 37.7749,-122.4194 in the next month."*
- *"Search Ticketmaster for Hamilton, then show me the next 5 shows."*
- *"What events are on at venue KovZpZA7AAEA next weekend?"*
- *"Get sales-window and accessibility info for event G5vYZbpYf-VTk."*

## Notes

- **Date filters are UTC.** Pass ISO-8601 with the `Z` suffix
  (e.g. `2026-05-26T00:00:00Z`). The API rejects unzoned strings.
- **`classificationName` is fuzzy.** "music", "rock", "country", "hip-hop",
  "sports", "nba", etc. all work. Combine with `keyword` for precision.
- **For "events at venue X" queries**, prefer `venue_id` (from
  `search_venues`) over a keyword — venue names collide.
