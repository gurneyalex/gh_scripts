from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import csv
import os
import sys

from github import Github


@dataclass
class RepositoryInfo:
    """Lightweight representation of a GitHub repository.

    Attributes
    ----------
    name: str
        Technical name of the repository.
    description: Optional[str]
        Description of the repository.
    private: bool
        Value of the "private" attribute from the GitHub API.
    fork: bool
        Value of the "fork" attribute from the GitHub API.
    url: str
        URL of the repository (HTML URL).
    archived: bool
        Value of the "archived" attribute from the GitHub API.
    topics: List[str]
        List of topic names defined on the repository.
    teams: Dict[str, str]
        Mapping of team name to the team's access level on the repository.
    """

    name: str
    description: Optional[str]
    private: bool
    fork: bool
    url: str
    archived: bool
    topics: List[str]
    teams: Dict[str, str]


def _build_github_client() -> Github:
    """Build a Github client using the GITHUB_TOKEN env var when available.

    Falls back to unauthenticated access if no token is configured.
    """

    token = os.getenv("GITHUB_TOKEN")
    if token:
        return Github(token)
    else:
        with open("/home/afayolle/.github_token2") as f:
            token = f.read().strip()
        return Github(token)
    return Github()


def retrieve_github_repositories(organisation: str) -> List[RepositoryInfo]:
    """Retrieve all repositories for a given GitHub organisation.

    This function uses PyGithub's pagination to iterate over all repositories
    of the organisation and returns a list of RepositoryInfo instances.

    Parameters
    ----------
    organisation: str
        The login/name of the GitHub organisation.

    Returns
    -------
    List[RepositoryInfo]
        List of repositories with basic metadata.
    """

    github_client = _build_github_client()

    org = github_client.get_organization(organisation)
    # Use the paginated list returned by PyGithub; this includes archived
    # repositories by default when type="all".
    paginated_repos = org.get_repos(type="all")

    page_index = 0
    while True:
        page = paginated_repos.get_page(page_index)
        if not page:
            break

        for repo in page:
            print(repo.name)
            # Collect topics and team permissions.
            topics = list(repo.get_topics())

            teams: Dict[str, str] = {}
            for team in repo.get_teams():
                # Prefer the "permission" attribute when available.
                permission: Optional[str] = getattr(team, "permission", None)

                # Fallback: derive from the permissions dict if necessary.
                if permission is None and hasattr(team, "permissions"):
                    perms = getattr(team, "permissions") or {}
                    for level in ("admin", "maintain", "push", "triage", "pull"):
                        if perms.get(level):
                            permission = level
                            break

                teams[team.name] = permission or "unknown"

            yield RepositoryInfo(
                name=repo.name,
                description=repo.description,
                private=repo.private,
                fork=repo.fork,
                url=repo.html_url,
                archived=repo.archived,
                topics=topics,
                teams=teams,
            )

        page_index += 1


def make_repositories_csv(organisation: str, csv_filename: str) -> None:
    """Fetch organisation repositories and serialize them into a CSV file.

    The CSV contains one line per repository with the following columns:
    name, description, private, fork, url, archived, topics, teams.

    - ``topics`` is a semicolon-separated list of topic names.
    - ``teams`` is a semicolon-separated list of ``team:permission`` entries.
    """

    repositories = retrieve_github_repositories(organisation)

    fieldnames = [
        "name",
        "description",
        "private",
        "fork",
        "url",
        "archived",
        "topics",
        "teams",
    ]

    with open(csv_filename, "w", newline="", encoding="utf-8", buffering=1) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        count = 0
        for repo in repositories:
            count+= 1
            topics_str = ";".join(repo.topics)
            teams_str = ";".join(
                f"{team}:{permission}" for team, permission in repo.teams.items()
            )

            writer.writerow(
                {
                    "name": repo.name,
                    "description": repo.description or "",
                    "private": repo.private,
                    "fork": repo.fork,
                    "url": repo.url,
                    "archived": repo.archived,
                    "topics": topics_str,
                    "teams": teams_str,
                }
            )


def main() -> None:
    """Entry point for command-line usage.

    Expects two arguments:
    - organisation name (argv[1])
    - output CSV filename (argv[2])
    """

    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <organisation_name> <output_csv>")
        sys.exit(1)

    organisation_name = sys.argv[1]
    csv_filename = sys.argv[2]

    make_repositories_csv(organisation_name, csv_filename)


if __name__ == "__main__":
    main()
