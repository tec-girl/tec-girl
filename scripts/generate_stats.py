#!/usr/bin/env python3
"""Genera la tarjeta propia de GitHub Stats de Tec Girl (assets/github-stats.svg).

Réplica fiel del sistema de rangos de github-readme-stats (calculateRank.js),
pero generada dentro del propio repositorio con GitHub Actions: sin depender
del servicio público de Vercel, que quedó pausado.

Datos: API REST pública de GitHub con el GITHUB_TOKEN del workflow.
Prueba local: definir STATS_JSON='{"stars":0,"commits":0,"prs":0,"issues":0,
"reviews":0,"followers":0}' para generar el SVG sin llamar a la API.
"""
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

USER = "tec-girl"
API = "https://api.github.com"

# ---------------------------------------------------------------------------
# Réplica de src/calculateRank.js de anuraghazra/github-readme-stats
# (medianas y pesos del algoritmo oficial; commits = último año, mediana 250)
# ---------------------------------------------------------------------------
COMMITS_MEDIAN = 250
COMMITS_WEIGHT = 2
PRS_MEDIAN = 50
PRS_WEIGHT = 3
ISSUES_MEDIAN = 25
ISSUES_WEIGHT = 1
REVIEWS_MEDIAN = 2
REVIEWS_WEIGHT = 1
STARS_MEDIAN = 50
STARS_WEIGHT = 4
FOLLOWERS_MEDIAN = 10
FOLLOWERS_WEIGHT = 1
TOTAL_WEIGHT = (
    COMMITS_WEIGHT + PRS_WEIGHT + ISSUES_WEIGHT
    + REVIEWS_WEIGHT + STARS_WEIGHT + FOLLOWERS_WEIGHT
)  # 12

LEVELS = [
    (1, "S"),
    (12.5, "A+"),
    (25, "A"),
    (37.5, "A-"),
    (50, "B+"),
    (62.5, "B"),
    (75, "B-"),
    (87.5, "C+"),
    (100, "C"),
]


def exponential_cdf(x):
    return 1 - 2 ** (-x)


def log_normal_cdf(x):
    return x / (1 + x)


def calculate_rank(commits, prs, issues, reviews, stars, followers):
    """Devuelve (percentil, nivel). Percentil bajo = mejor (1 = top 1%).

    Asignación de CDF verificada contra el código oficial (2026-11-02):
    exponential_cdf para commits, PRs, issues y reviews;
    log_normal_cdf para stars y followers.
    """
    score = (
        COMMITS_WEIGHT * exponential_cdf(commits / COMMITS_MEDIAN)
        + PRS_WEIGHT * exponential_cdf(prs / PRS_MEDIAN)
        + ISSUES_WEIGHT * exponential_cdf(issues / ISSUES_MEDIAN)
        + REVIEWS_WEIGHT * exponential_cdf(reviews / REVIEWS_MEDIAN)
        + STARS_WEIGHT * log_normal_cdf(stars / STARS_MEDIAN)
        + FOLLOWERS_WEIGHT * log_normal_cdf(followers / FOLLOWERS_MEDIAN)
    ) / TOTAL_WEIGHT
    percentile = (1 - score) * 100
    for threshold, level in LEVELS:
        if percentile <= threshold:
            return percentile, level
    return percentile, "C"


# ---------------------------------------------------------------------------
# Obtención de datos (API REST de GitHub)
# ---------------------------------------------------------------------------
def api_get(path):
    token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("STATS_TOKEN")
        or ""
    )
    req = urllib.request.Request(API + path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "tec-girl-stats-generator")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_count(query):
    q = urllib.parse.quote(query)
    data = api_get(f"/search/issues?q={q}&per_page=1")
    return int(data.get("total_count", 0))


def search_commits_count(query):
    q = urllib.parse.quote(query)
    data = api_get(f"/search/commits?q={q}&per_page=1")
    return int(data.get("total_count", 0))


def fetch_stats():
    user = api_get(f"/users/{USER}")
    followers = int(user.get("followers", 0))

    stars = 0
    page = 1
    while True:
        repos = api_get(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        if not repos:
            break
        stars += sum(int(r.get("stargazers_count", 0)) for r in repos)
        if len(repos) < 100:
            break
        page += 1

    since = (date.today() - timedelta(days=365)).isoformat()
    commits = search_commits_count(f"author:{USER} author-date:>={since}")
    prs = search_count(f"author:{USER} type:pr")
    issues = search_count(f"author:{USER} type:issue")
    # Aproximación al totalReviews oficial: PRs revisados por la usuaria
    # que no son suyos (la API de búsqueda cuenta PRs distintos revisados).
    reviews = search_count(f"reviewed-by:{USER} type:pr -author:{USER}")

    return {
        "stars": stars,
        "commits": commits,
        "prs": prs,
        "issues": issues,
        "reviews": reviews,
        "followers": followers,
    }


# ---------------------------------------------------------------------------
# Dibujo del SVG (paleta Tec Girl: turquesa/rosa/morado sobre negro)
# ---------------------------------------------------------------------------
BG = "0a0a14"
TITLE = "00e5ff"
ICON = "ff2e88"
TEXT = "c9b8ff"
BORDER = "7b2ff7"


def fmt(n):
    return f"{n:,}"


def icon_star(cx, cy):
    pts = "0,-6.5 1.9,-2 6.8,-2 2.9,1.3 4.2,6 0,3.1 -4.2,6 -2.9,1.3 -6.8,-2 -1.9,-2"
    return f'<polygon transform="translate({cx},{cy})" points="{pts}" fill="#{ICON}"/>'


def icon_commit(cx, cy):
    return (
        f'<g transform="translate({cx},{cy})" stroke="#{ICON}" stroke-width="1.8" fill="none">'
        f'<circle r="3.4" fill="#{BG}"/><line x1="-9" y1="0" x2="-3.4" y2="0"/>'
        f'<line x1="3.4" y1="0" x2="9" y2="0"/></g>'
    )


def icon_pr(cx, cy):
    return (
        f'<g transform="translate({cx},{cy})" stroke="#{ICON}" stroke-width="1.7" fill="none">'
        f'<circle cx="-4.5" cy="-5" r="2.4"/><circle cx="-4.5" cy="5" r="2.4"/>'
        f'<circle cx="4.5" cy="5" r="2.4"/>'
        f'<path d="M -4.5 -2.6 V 2.6 M -4.5 5 H 2.1 M 4.5 2.6 V -2 C 4.5 -4.4 3 -5 -4.5 -5" stroke-linecap="round"/></g>'
    )


def icon_issue(cx, cy):
    return (
        f'<g transform="translate({cx},{cy})" stroke="#{ICON}" stroke-width="1.7" fill="none">'
        f'<circle r="6.8"/><line x1="0" y1="-3.4" x2="0" y2="1.2" stroke-linecap="round"/>'
        f'<circle cy="4" r="0.4" fill="#{ICON}"/></g>'
    )


def icon_review(cx, cy):
    return (
        f'<g transform="translate({cx},{cy})" stroke="#{ICON}" stroke-width="1.7" fill="none">'
        f'<path d="M -7.5 0 C -4 -5 4 -5 7.5 0 C 4 5 -4 5 -7.5 0 Z"/>'
        f'<circle r="2.3"/></g>'
    )


def icon_followers(cx, cy):
    return (
        f'<g transform="translate({cx},{cy})" stroke="#{ICON}" stroke-width="1.7" fill="none">'
        f'<circle cx="-2" cy="-2.8" r="2.8"/>'
        f'<path d="M -8 6.5 C -8 1.8 -4.9 0.4 -2 0.4 C 0.9 0.4 4 1.8 4 6.5" stroke-linecap="round"/>'
        f'<path d="M 3.4 -5.2 C 5.9 -5 7.4 -3.3 7.4 -1.2 C 7.4 0.6 6.2 2 4.6 2.5 M 5.6 3.4 C 7 4.2 7.8 5.2 7.8 6.5" stroke-linecap="round"/></g>'
    )


def build_svg(stats):
    percentile, level = calculate_rank(
        stats["commits"], stats["prs"], stats["issues"],
        stats["reviews"], stats["stars"], stats["followers"],
    )
    rows = [
        (icon_star, "Total Stars", stats["stars"]),
        (icon_commit, "Total Commits (last year)", stats["commits"]),
        (icon_pr, "Total PRs", stats["prs"]),
        (icon_issue, "Total Issues", stats["issues"]),
        (icon_review, "Total PR Reviews", stats["reviews"]),
        (icon_followers, "Followers", stats["followers"]),
    ]
    width, height = 495, 220
    y0, step = 66, 25
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Tec Girl\'s GitHub Stats — rank {level}">',
        "<defs>",
        '<linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        f'<stop offset="0%" stop-color="#{TITLE}"/>',
        f'<stop offset="100%" stop-color="#{ICON}"/>',
        "</linearGradient>",
        "</defs>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" '
        f'fill="#{BG}" stroke="#{BORDER}"/>',
        f'<text x="25" y="36" font-family="\'Segoe UI\', Ubuntu, sans-serif" '
        f'font-size="16" font-weight="700" fill="#{TITLE}">'
        "Tec Girl's GitHub Stats</text>",
    ]
    for i, (icon_fn, label, value) in enumerate(rows):
        cy = y0 + i * step
        parts.append(icon_fn(33, cy - 4))
        parts.append(
            f'<text x="50" y="{cy}" font-family="\'Segoe UI\', Ubuntu, sans-serif" '
            f'font-size="13" fill="#{TEXT}">{label}:</text>'
        )
        parts.append(
            f'<text x="345" y="{cy}" text-anchor="end" '
            f'font-family="\'Segoe UI\', Ubuntu, sans-serif" font-size="13" '
            f'font-weight="700" fill="#{TEXT}">{fmt(value)}</text>'
        )
    # Anillo de rango
    cx, cy, r = 415, 122, 42
    circ = 2 * math.pi * r
    progress = (100 - percentile) / 100
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#26263a" stroke-width="7"/>'
    )
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#ringGrad)" '
        f'stroke-width="7" stroke-linecap="round" '
        f'stroke-dasharray="{circ * progress:.1f} {circ:.1f}" '
        f'transform="rotate(-90 {cx} {cy})"/>'
    )
    parts.append(
        f'<text x="{cx}" y="{cy + 9}" text-anchor="middle" '
        f'font-family="\'Segoe UI\', Ubuntu, sans-serif" font-size="27" '
        f'font-weight="800" fill="#{TITLE}">{level}</text>'
    )
    parts.append(
        f'<text x="{cx}" y="{cy + r + 22}" text-anchor="middle" '
        f'font-family="\'Segoe UI\', Ubuntu, sans-serif" font-size="11" '
        f'fill="#{TEXT}">Top {percentile:.1f}%</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts), percentile, level


def main():
    preview = os.environ.get("STATS_JSON")
    if preview:
        stats = json.loads(preview)
    else:
        stats = fetch_stats()
    svg, percentile, level = build_svg(stats)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "assets", "github-stats.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg + "\n")
    print(
        "Stats:", stats,
        f"| Percentile: {percentile:.2f} | Rank: {level}",
        f"| SVG -> {out}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
