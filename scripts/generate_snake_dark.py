#!/usr/bin/env python3
"""
generate_snake_dark.py

Fetches the GitHub contributions calendar for a username using GitHub GraphQL API
and generates a dark-theme SVG where a neon snake "eats" contribution squares.
The SVG is written to the file given by --output.

Environment:
  GITHUB_TOKEN  - optional but recommended for higher rate limits (GitHub Actions provides this)

Usage:
  python generate_snake_dark.py --output ../assets/github-snake-dark.svg --username graham218
"""

import os, sys, argparse, math, requests, datetime, json, textwrap

GITHUB_API = "https://api.github.com/graphql"

def query_contributions(username, token=None):
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                color
              }
            }
          }
        }
      }
    }
    """
    variables = {"login": username}
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"bearer {token}"
    resp = requests.post(GITHUB_API, json={"query": query, "variables": variables}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError("GraphQL error: " + json.dumps(data["errors"]))
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    # flatten days into list in calendar order (left-to-right by week)
    days = []
    for week in weeks:
        for d in week["contributionDays"]:
            days.append({"date": d["date"], "count": d["contributionCount"], "color": d["color"]})
    return days

def build_svg(days, username, output_path, cols=53, rows=7, cell_size=12, gap=3, duration=30):
    # Map days to grid positions (columns = weeks)
    cols_actual = math.ceil(len(days) / rows)
    width = cols_actual * (cell_size + gap) + 20
    height = rows * (cell_size + gap) + 60

    # Create list of coordinates in a zigzag snake order so movement is continuous
    coords = []
    for col in range(cols_actual):
        col_days = []
        for row in range(rows):
            idx = col * rows + row
            if idx < len(days):
                x = 10 + col * (cell_size + gap)
                y = 20 + row * (cell_size + gap)
                col_days.append((idx, x, y))
        # for snake-like traversal, alternate column direction
        if col % 2 == 0:
            coords.extend(col_days)
        else:
            coords.extend(list(reversed(col_days)))

    # Build SVG elements
    palette = ["#0d1117","#0f1b17","#0e4429","#006d32","#26a641","#39d353"]
    snake_color = "#00ffcc"
    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg_parts.append(f'<style>.muted{{fill:#8b949e;font-family:monospace;font-size:11px}} .date{{fill:#8b949e;font-family:monospace;font-size:9px}}</style>')
    svg_parts.append(f'<rect width="100%" height="100%" fill="#0d1117"/>')

    # grid base
    for idx, day in enumerate(days):
        col = idx // rows
        row = idx % rows
        x = 10 + col * (cell_size + gap)
        y = 20 + row * (cell_size + gap)
        # use GitHub color if available, otherwise map count to palette
        color = day.get("color") or palette[min(5, math.ceil(day["count"]/5))]
        svg_parts.append(f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="2" ry="2" fill="{color}" />')

    # compute path d for head (through zigzag coords centers)
    points = []
    for (idx, x, y) in coords:
        cx = x + cell_size/2
        cy = y + cell_size/2
        points.append((cx, cy))
    path_d = "M " + " L ".join([f"{x:.1f} {y:.1f}" for x,y in points])

    # times when head reaches each cell
    total_steps = len(points)
    time_per_step = float(duration) / max(1, total_steps)
    reach_times = [i * time_per_step for i in range(total_steps)]

    # head (moving)
    svg_parts.append(f'<path id="snakePath" d="{path_d}" fill="none" stroke="none"/>')
    svg_parts.append(f'<circle r="6" fill="{snake_color}">')
    svg_parts.append(f'<animateMotion dur="{duration}s" repeatCount="indefinite"><mpath xlink:href="#snakePath"/></animateMotion>')
    svg_parts.append('</circle>')

    # body cells: cells with count>0 will light up when eaten (i.e., when head reaches that cell)
    for order_idx, (idx, x, y) in enumerate(coords):
        day = days[idx]
        if day["count"] > 0:
            t = reach_times[order_idx]
            # overlay rectangle to represent snake body grown into that cell
            svg_parts.append(f'<rect x="{x-1}" y="{y-1}" width="{cell_size+2}" height="{cell_size+2}" rx="3" ry="3" fill="{snake_color}" opacity="0">')
            svg_parts.append(f'<title>{day["date"]}: {day["count"]} contributions</title>')
            svg_parts.append(f'<animate attributeName="opacity" from="0" to="0.95" begin="{t:.2f}s" dur="0.1s" fill="freeze" />')
            svg_parts.append('</rect>')

    # caption
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    svg_parts.append(f'<text x="10" y="{height-28}" class="muted">GitHub contributions — {username}</text>')
    svg_parts.append(f'<text x="10" y="{height-12}" class="date">Updated: {now} — snake loops endlessly</text>')
    svg_parts.append('</svg>')

    svg = "\n".join(svg_parts)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote SVG to", output_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, help="Output SVG path (relative to repo root)")
    ap.add_argument("--username", default=os.environ.get("USERNAME", "graham218"))
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    ap.add_argument("--duration", type=float, default=30.0)
    args = ap.parse_args()

    days = query_contributions(args.username, args.token)
    build_svg(days, args.username, args.output, duration=args.duration)


if __name__ == "__main__":
    main()