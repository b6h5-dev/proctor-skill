#!/usr/bin/env python3
"""Generate a proctor quiz summary from ~/.proctor/history.jsonl.

Usage:
    proctor-summary.py [--repo NAME] [--branch NAME] [--html FILE] [--json]

Outputs a text summary to stdout. With --html, also writes a self-contained
HTML report. With --json, outputs raw stats as JSON instead of text.
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HISTORY_FILE = Path.home() / ".proctor" / "history.jsonl"


def load_entries(repo_filter=None, branch_filter=None):
    if not HISTORY_FILE.exists():
        return []
    entries = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if repo_filter and not entry.get("repo", "").endswith("/" + repo_filter):
                continue
            if branch_filter and entry.get("branch") != branch_filter:
                continue
            entries.append(entry)
    return entries


def compute_stats(entries):
    non_trivial = [e for e in entries if not e.get("trivial_skip")]
    trivial = [e for e in entries if e.get("trivial_skip")]
    first_attempts = [e for e in non_trivial if e.get("attempt", 1) == 1]
    first_attempt_passes = [e for e in first_attempts if e.get("failed", 0) == 0]

    category_stats = defaultdict(lambda: {"pass": 0, "fail": 0})
    for entry in non_trivial:
        cats = entry.get("categories", {})
        for cat, result in cats.items():
            key = cat.lower()
            if key.startswith("what"):
                bucket = "what"
            elif key.startswith("why"):
                bucket = "why"
            elif key.startswith("risk"):
                bucket = "risk"
            elif key.startswith("requiz"):
                bucket = "risk"
            else:
                bucket = key
            if result == "pass":
                category_stats[bucket]["pass"] += 1
            else:
                category_stats[bucket]["fail"] += 1

    failed_concepts = defaultdict(list)
    for entry in non_trivial:
        for concept in entry.get("failed_concepts", []):
            if concept:
                failed_concepts[concept].append({
                    "commit": entry.get("commit", "unknown"),
                    "branch": entry.get("branch", "unknown"),
                    "repo": os.path.basename(entry.get("repo", "unknown")),
                    "files": entry.get("files", []),
                    "timestamp": entry.get("timestamp", ""),
                })

    repos = sorted(set(os.path.basename(e.get("repo", "unknown")) for e in entries))
    branches = sorted(set(e.get("branch", "unknown") for e in entries))

    return {
        "total_quizzes": len(non_trivial),
        "trivial_skips": len(trivial),
        "first_attempts": len(first_attempts),
        "first_attempt_passes": len(first_attempt_passes),
        "first_attempt_pass_rate": (
            round(len(first_attempt_passes) / len(first_attempts) * 100)
            if first_attempts else None
        ),
        "categories": {
            cat: {
                "pass": s["pass"],
                "fail": s["fail"],
                "rate": round(s["pass"] / (s["pass"] + s["fail"]) * 100)
                if (s["pass"] + s["fail"]) > 0 else None,
            }
            for cat, s in sorted(category_stats.items())
        },
        "failed_concepts": {
            concept: occurrences
            for concept, occurrences in sorted(
                failed_concepts.items(), key=lambda x: -len(x[1])
            )
        },
        "repos": repos,
        "branches": branches,
        "recent": entries[-10:][::-1],
    }


def format_text(stats):
    lines = []
    lines.append("Proctor Quiz Summary")
    lines.append("=" * 40)
    lines.append("")

    total = stats["total_quizzes"]
    trivial = stats["trivial_skips"]
    rate = stats["first_attempt_pass_rate"]
    lines.append(f"Total quizzes: {total} (+ {trivial} trivial skips)")
    if rate is not None:
        lines.append(f"First-attempt pass rate: {rate}%")
    else:
        lines.append("First-attempt pass rate: N/A")
    lines.append("")

    if stats["categories"]:
        lines.append("Per-category breakdown:")
        for cat, s in stats["categories"].items():
            total_cat = s["pass"] + s["fail"]
            lines.append(f"  {cat.capitalize():8s}  {s['rate']}% ({s['pass']}/{total_cat})")
        lines.append("")

    if stats["failed_concepts"]:
        lines.append("Trouble spots:")
        for concept, occurrences in stats["failed_concepts"].items():
            commits = ", ".join(o["commit"][:7] for o in occurrences)
            lines.append(f"  - {concept} ({len(occurrences)}x, commits: {commits})")
        lines.append("")

    if stats["recent"]:
        lines.append("Recent history:")
        for entry in stats["recent"]:
            ts = entry.get("timestamp", "")[:10]
            repo = os.path.basename(entry.get("repo", ""))
            branch = entry.get("branch", "")
            op = entry.get("operation", "")
            if entry.get("trivial_skip"):
                result = "trivial skip"
            elif entry.get("failed", 0) == 0:
                attempt = entry.get("attempt", 1)
                passed = entry.get("passed", 0)
                qs = entry.get("questions", 0)
                if attempt > 1:
                    result = f"passed (attempt {attempt}, {passed}/{qs})"
                else:
                    result = f"passed ({passed}/{qs})"
            else:
                passed = entry.get("passed", 0)
                qs = entry.get("questions", 0)
                result = f"failed ({passed}/{qs})"
            lines.append(f"  {ts}  {repo:20s} {branch:25s} {op:8s} {result}")
    lines.append("")
    return "\n".join(lines)


def generate_html(stats, repo_filter=None, branch_filter=None):
    title = "Proctor Quiz Summary"
    if repo_filter:
        title += f" — {repo_filter}"
    if branch_filter:
        title += f" ({branch_filter})"

    total = stats["total_quizzes"]
    trivial = stats["trivial_skips"]
    rate = stats["first_attempt_pass_rate"]
    rate_display = f"{rate}%" if rate is not None else "N/A"

    category_rows = ""
    for cat, s in stats["categories"].items():
        total_cat = s["pass"] + s["fail"]
        pct = s["rate"]
        bar_color = "#4caf50" if pct >= 80 else "#ff9800" if pct >= 50 else "#f44336"
        category_rows += f"""
        <tr>
            <td>{cat.capitalize()}</td>
            <td>{s['pass']}/{total_cat}</td>
            <td>
                <div class="bar-bg"><div class="bar" style="width:{pct}%;background:{bar_color}"></div></div>
                {pct}%
            </td>
        </tr>"""

    trouble_rows = ""
    for concept, occurrences in stats["failed_concepts"].items():
        commits = ", ".join(
            f'<code>{o["commit"][:7]}</code>' for o in occurrences
        )
        repos = ", ".join(set(o["repo"] for o in occurrences))
        trouble_rows += f"""
        <tr>
            <td>{concept}</td>
            <td>{len(occurrences)}</td>
            <td>{repos}</td>
            <td>{commits}</td>
        </tr>"""

    recent_rows = ""
    for entry in stats["recent"]:
        ts = entry.get("timestamp", "")[:10]
        repo = os.path.basename(entry.get("repo", ""))
        branch = entry.get("branch", "")
        op = entry.get("operation", "")
        if entry.get("trivial_skip"):
            result = '<span class="badge skip">skip</span>'
        elif entry.get("failed", 0) == 0:
            attempt = entry.get("attempt", 1)
            suffix = f" (attempt {attempt})" if attempt > 1 else ""
            result = f'<span class="badge pass">pass{suffix}</span>'
        else:
            passed = entry.get("passed", 0)
            qs = entry.get("questions", 0)
            result = f'<span class="badge fail">fail ({passed}/{qs})</span>'
        recent_rows += f"""
        <tr>
            <td>{ts}</td>
            <td>{repo}</td>
            <td>{branch}</td>
            <td>{op}</td>
            <td>{result}</td>
        </tr>"""

    trouble_section = ""
    if trouble_rows:
        trouble_section = f"""
    <h2>Trouble Spots</h2>
    <table>
        <thead><tr><th>Concept</th><th>Times Failed</th><th>Repo</th><th>Commits</th></tr></thead>
        <tbody>{trouble_rows}</tbody>
    </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
    :root {{
        --bg: #ffffff; --fg: #1a1a1a; --muted: #666;
        --card-bg: #f8f9fa; --border: #e0e0e0;
        --pass: #4caf50; --fail: #f44336; --skip: #9e9e9e;
    }}
    @media (prefers-color-scheme: dark) {{
        :root {{
            --bg: #1a1a1a; --fg: #e0e0e0; --muted: #999;
            --card-bg: #2a2a2a; --border: #444;
        }}
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           background: var(--bg); color: var(--fg); max-width: 900px; margin: 0 auto;
           padding: 2rem 1rem; line-height: 1.6; }}
    h1 {{ margin-bottom: 0.5rem; }}
    h2 {{ margin: 2rem 0 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
    .subtitle {{ color: var(--muted); margin-bottom: 2rem; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; }}
    .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px;
             padding: 1.25rem; text-align: center; }}
    .card .value {{ font-size: 2rem; font-weight: 700; }}
    .card .label {{ color: var(--muted); font-size: 0.85rem; margin-top: 0.25rem; }}
    table {{ width: 100%; border-collapse: collapse; margin: 0.5rem 0; }}
    th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); font-size: 0.85rem; font-weight: 600; text-transform: uppercase; }}
    .bar-bg {{ display: inline-block; width: 80px; height: 8px; background: var(--border);
               border-radius: 4px; vertical-align: middle; margin-right: 0.5rem; }}
    .bar {{ height: 100%; border-radius: 4px; }}
    .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px;
              font-size: 0.8rem; font-weight: 600; color: #fff; }}
    .badge.pass {{ background: var(--pass); }}
    .badge.fail {{ background: var(--fail); }}
    .badge.skip {{ background: var(--skip); }}
    code {{ background: var(--card-bg); padding: 0.1rem 0.3rem; border-radius: 3px;
            font-size: 0.85rem; }}
    .footer {{ margin-top: 3rem; color: var(--muted); font-size: 0.8rem; text-align: center; }}
    .footer-link {{ color: #4caf50; text-decoration: underline; text-underline-offset: 2px; }}
    .footer-link:hover {{ color: #66bb6a; }}
</style>
</head>
<body>
    <h1>{title}</h1>
    <p class="subtitle">Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>

    <div class="cards">
        <div class="card"><div class="value">{total}</div><div class="label">Quizzes</div></div>
        <div class="card"><div class="value">{trivial}</div><div class="label">Trivial Skips</div></div>
        <div class="card"><div class="value">{rate_display}</div><div class="label">First-Attempt Pass</div></div>
        <div class="card"><div class="value">{len(stats['repos'])}</div><div class="label">Repos</div></div>
    </div>

    <h2>Categories</h2>
    <table>
        <thead><tr><th>Category</th><th>Passed</th><th>Rate</th></tr></thead>
        <tbody>{category_rows if category_rows else '<tr><td colspan="3">No category data yet</td></tr>'}</tbody>
    </table>

    {trouble_section}

    <h2>Recent History</h2>
    <table>
        <thead><tr><th>Date</th><th>Repo</th><th>Branch</th><th>Op</th><th>Result</th></tr></thead>
        <tbody>{recent_rows if recent_rows else '<tr><td colspan="5">No history yet</td></tr>'}</tbody>
    </table>

    <p class="footer">
        <a href="https://b6h5.dev/skills/proctor" class="footer-link">proctor-skill</a> by <a href="https://b6h5.dev" class="footer-link">B6H5</a> &middot; <code>~/.proctor/history.jsonl</code>
    </p>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Proctor quiz summary")
    parser.add_argument("--repo", help="Filter by repo name")
    parser.add_argument("--branch", help="Filter by branch name")
    parser.add_argument("--html", help="Write HTML report to file")
    parser.add_argument("--json", action="store_true", help="Output stats as JSON")
    args = parser.parse_args()

    entries = load_entries(repo_filter=args.repo, branch_filter=args.branch)
    if not entries:
        filters = []
        if args.repo:
            filters.append(f"repo={args.repo}")
        if args.branch:
            filters.append(f"branch={args.branch}")
        filter_msg = f" (filters: {', '.join(filters)})" if filters else ""
        print(f"No quiz history found{filter_msg}.")
        print(f"History file: {HISTORY_FILE}")
        sys.exit(0)

    stats = compute_stats(entries)

    if args.json:
        json.dump(stats, sys.stdout, indent=2, default=str)
        print()
        return

    print(format_text(stats))

    html_path = args.html
    if not html_path:
        html_dir = Path.home() / ".proctor"
        html_dir.mkdir(parents=True, exist_ok=True)
        html_path = str(html_dir / "summary.html")

    html = generate_html(stats, repo_filter=args.repo, branch_filter=args.branch)
    with open(html_path, "w") as f:
        f.write(html)
    print(f"HTML report: {html_path}")


if __name__ == "__main__":
    main()
