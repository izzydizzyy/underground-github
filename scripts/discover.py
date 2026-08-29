import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN", "")
OUTPUT = Path("data/developers.json")

MAX_STARS = 25
PER_CATEGORY = 6
ACTIVE_DAYS = 180
SEARCH_PAUSE = 5

CATEGORIES = {
    "VR": {
        "search": "vr",
        "terms": ["vr", "virtual reality", "meta quest", "unity xr", "openxr"],
    },
    "Discord": {
        "search": "discord",
        "terms": ["discord", "discord bot", "discord.py", "discord.js"],
    },
    "Python": {
        "search": "python",
        "terms": ["python", "pyqt", "tkinter", "fastapi", "flask"],
    },
    "Web": {
        "search": '"web app"',
        "terms": ["web app", "website", "frontend", "web", "react"],
    },
    "Games": {
        "search": "game",
        "terms": ["game", "pygame", "godot", "unity", "gamedev"],
    },
    "Tools": {
        "search": "cli",
        "terms": ["cli", "tool", "utility", "developer tool", "automation"],
    },
    "APIs": {
        "search": "api",
        "terms": ["api", "rest api", "fastapi", "backend", "endpoint"],
    },
}

BLOCKED_WORDS = {
    "assignment",
    "homework",
    "tutorial",
    "practice",
    "learning",
    "course",
    "leetcode",
    "hello-world",
    "boilerplate",
    "template",
}


def request_json(url, retries=3):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "underground-github",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    for attempt in range(retries):
        request = Request(url, headers=headers)

        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))

        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")

            if error.code == 404:
                return None

            if error.code == 403 and attempt < retries - 1:
                retry_after = error.headers.get("Retry-After")

                if retry_after and retry_after.isdigit():
                    wait = int(retry_after)
                else:
                    wait = 20 * (attempt + 1)

                print(
                    f"[rate limit] waiting {wait}s before retry "
                    f"{attempt + 2}/{retries}"
                )
                time.sleep(wait)
                continue

            raise RuntimeError(
                f"GitHub API error {error.code}: {body}"
            ) from error

    return None


def github_search(category, search_term, cutoff):
    query = (
        f"{search_term} in:name,description,readme "
        f"stars:0..{MAX_STARS} "
        f"pushed:>={cutoff} "
        "fork:false archived:false"
    )

    url = (
        f"{API}/search/repositories"
        f"?q={quote(query)}"
        "&sort=updated"
        "&order=desc"
        "&per_page=30"
    )

    data = request_json(url) or {}
    items = data.get("items", [])

    print(f"[{category}] {len(items)} results")

    return items


def looks_low_quality(repo):
    name = repo["name"].lower()
    description = (repo.get("description") or "").strip()

    if repo.get("fork"):
        return True

    if repo.get("archived") or repo.get("disabled"):
        return True

    if repo["owner"].get("type") != "User":
        return True

    if repo.get("stargazers_count", 0) > MAX_STARS:
        return True

    if len(description) < 18:
        return True

    if repo.get("size", 0) < 8:
        return True

    if any(word in name for word in BLOCKED_WORDS):
        return True

    return False


def match_score(repo, terms):
    name = repo["name"].lower()
    description = (repo.get("description") or "").lower()
    topics = [topic.lower() for topic in repo.get("topics", [])]

    score = 0

    for term in terms:
        term = term.lower()

        if term in name:
            score += 8

        if term in description:
            score += 4

        if any(term in topic for topic in topics):
            score += 5

    stars = repo.get("stargazers_count", 0)

    if 1 <= stars <= 5:
        score += 4
    elif stars <= 12:
        score += 2

    if repo.get("forks_count", 0) > 0:
        score += 1

    pushed = repo.get("pushed_at")

    if pushed:
        pushed_date = datetime.fromisoformat(
            pushed.replace("Z", "+00:00")
        )

        age = datetime.now(timezone.utc) - pushed_date

        if age.days <= 30:
            score += 4
        elif age.days <= 90:
            score += 2

    return score


def normalize(repo, category):
    owner = repo["owner"]["login"]

    return {
        "developer": owner,
        "username": owner,
        "avatar": repo["owner"]["avatar_url"],
        "name": repo["name"],
        "description": repo.get("description") or "",
        "category": category,
        "language": repo.get("language") or "Unknown",
        "stars": repo.get("stargazers_count", 0),
        "topics": repo.get("topics", [])[:4],
        "updated": repo.get("pushed_at") or repo.get("updated_at"),
        "featured": False,
        "profile_url": repo["owner"]["html_url"],
        "repo_url": repo["html_url"],
    }


def discover_category(category, config, cutoff):
    repos = github_search(
        category,
        config["search"],
        cutoff,
    )

    filtered = [
        repo
        for repo in repos
        if not looks_low_quality(repo)
    ]

    ranked = sorted(
        filtered,
        key=lambda repo: (
            -match_score(repo, config["terms"]),
            repo.get("stargazers_count", 0),
            repo["name"].lower(),
        ),
    )

    return [
        normalize(repo, category)
        for repo in ranked[:PER_CATEGORY]
    ]


def mark_featured(repos):
    ranked = sorted(
        repos,
        key=lambda repo: (
            repo["stars"],
            repo["updated"] or "",
        ),
    )

    featured_urls = {
        repo["repo_url"]
        for repo in ranked[: min(8, len(ranked))]
    }

    for repo in repos:
        repo["featured"] = repo["repo_url"] in featured_urls


def main():
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=ACTIVE_DAYS)
    ).date().isoformat()

    all_repos = []
    seen_urls = set()

    for index, (category, config) in enumerate(CATEGORIES.items()):
        print(f"\n--- {category} ---")

        try:
            discovered = discover_category(
                category,
                config,
                cutoff,
            )
        except RuntimeError as error:
            print(f"[warn] skipped {category}: {error}")
            discovered = []

        for repo in discovered:
            if repo["repo_url"] in seen_urls:
                continue

            seen_urls.add(repo["repo_url"])
            all_repos.append(repo)

        if index < len(CATEGORIES) - 1:
            print(f"[pause] waiting {SEARCH_PAUSE}s")
            time.sleep(SEARCH_PAUSE)

    mark_featured(all_repos)

    all_repos.sort(
        key=lambda repo: (
            repo["category"].lower(),
            -int(repo["featured"]),
            repo["stars"],
            repo["name"].lower(),
        )
    )

    if not all_repos:
        raise RuntimeError(
            "No repositories were discovered. "
            "Keeping the current developers.json unchanged."
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(all_repos, indent=2),
        encoding="utf-8",
    )

    print(
        f"\nSaved {len(all_repos)} repos "
        f"to {OUTPUT}"
    )


if __name__ == "__main__":
    main()
