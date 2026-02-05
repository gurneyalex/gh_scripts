from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple

from github import Github, GithubException

from .utils import _build_github_client, setup_logging


@dataclass
class RepositoryUpdate:
    """Repository update instructions loaded from a CSV file.

    Attributes
    ----------
    department: str
        Value from the "C2C Department" column.
    add_teams: str
        Value from the "Teams to add" column.
    archive: bool
        True if the "Other actions" column contains "to archive".
    """

    department: str
    add_teams: str
    archive: bool


def read_repository_updates(csv_filename: str) -> Dict[str, RepositoryUpdate]:
    """Read a CSV file with repository update instructions.

    The CSV is expected to contain at least the following columns:

    - "name": repository name used as the dictionary key
    - "C2C Department": mapped to RepositoryUpdate.department
    - "Teams to add": mapped to RepositoryUpdate.add_teams
    - "Other actions": used to determine RepositoryUpdate.archive

    Returns a dictionary keyed by URL.
    """

    updates: Dict[str, RepositoryUpdate] = {}

    with open(csv_filename, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if not row:
                continue
            if row["private"].strip().lower() == "false":
                continue

            name = row.get("name")
            if not name:
                raise ValueError(f"Missing 'name' column in row: {row}")

            department = row.get("C2C Department", "") or ""
            add_teams = row.get("Teams to add", "") or ""
            other_actions = row.get("Other actions", "") or ""

            archive = "to archive" in other_actions.lower()

            updates[name] = RepositoryUpdate(
                department=department,
                add_teams=add_teams,
                archive=archive,
            )

    return updates


def apply_repository_updates(
    organisation: str, updates_by_name: Dict[str, RepositoryUpdate]
) -> List[Tuple[str, Exception]]:
    """Apply a set of RepositoryUpdate instructions to repositories.

    Parameters
    ----------
    organisation: str
        GitHub organisation name.
    updates_by_name: Dict[str, RepositoryUpdate]
        Mapping of repository *names* to update instructions.
    """

    logger = setup_logging()
    client = _build_github_client()
    org = client.get_organization(organisation)

    errors: List[Tuple[str, Exception]] = []

    for name, updates in updates_by_name.items():
        logger.info(
            "Updating repository '%s' (department=%s, add_teams=%s, archive=%s)",
            name,
            updates.department,
            updates.add_teams,
            updates.archive,
        )
        try:
            update_repository(org, name, updates)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error while updating repository '%s': %s", name, exc)
            errors.append((name, exc))

    return errors


def update_repository(org, name: str, updates: RepositoryUpdate) -> None:
    """Update a single repository according to RepositoryUpdate.

    - Ensure department topic is present on the repository.
    - Add requested teams with specified access levels.
    - Archive the repository if requested.
    """

    logger = setup_logging()

    department_topic_map = {
        "GS": "geospatial",
        "IS": "infrastructure",
        "BS": "business",
        "c2c": "camptocamp",
    }

    try:
        repo = org.get_repo(name)
    except GithubException as exc:  # type: ignore[attr-defined]
        # UnknownObjectException is raised when the repository is not found
        if getattr(exc, "status", None) == 404:
            logger.warning(
                "Repository '%s' not found in organisation '%s'",
                name,
                getattr(org, "login", "<unknown>"),
            )
            return
        logger.error(
            "Error fetching repository '%s' in organisation '%s': %s",
            name,
            getattr(org, "login", "<unknown>"),
            exc,
        )
        raise

    # Skip updates for already-archived repositories.
    if getattr(repo, "archived", False):
        logger.warning(
            "Repository '%s' in organisation '%s' is archived; skipping updates",
            name,
            getattr(org, "login", "<unknown>"),
        )
        return

    new_topic = []
    # 1. Ensure the department-related topic is set.
    department = (updates.department or "").strip()
    new_topic.append(department_topic_map.get(department))
    if "smartcamp" in updates.add_teams:  # Special case for SmartCamp team
        new_topic.append("smartcamp")
    current_topics = list(repo.get_topics() or [])
    for topic in new_topic:
        if topic not in current_topics:
            current_topics.append(topic)
            repo.replace_topics(current_topics)

    # 2. Add teams with the specified access level.
    add_teams_value = (updates.add_teams or "").strip()
    if add_teams_value:
        for pair in add_teams_value.split(";"):
            pair = pair.strip()
            if not pair:
                continue
            if ":" not in pair:
                continue

            team_name, access = pair.split(":", 1)
            team_name = team_name.strip()
            access = access.strip()
            if not team_name or not access:
                continue

            team = None
            # Try by slug first.
            try:
                team = org.get_team_by_slug(team_name)
            except Exception:
                # Fallback to lookup by display name.
                for t in org.get_teams():
                    if t.name == team_name:
                        team = t
                        break

            if not team:
                continue

            # Grant the team the requested permission level on the repo.
            team.set_repo_permission(repo, access)

    # 3. Archive the repository if requested.
    if updates.archive and not repo.archived:
        repo.edit(archived=True)


def main() -> None:
    """CLI entry point to apply repository updates from a CSV file.

    Expects two arguments:
    - organisation name (argv[1])
    - input CSV filename (argv[2])
    """

    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <organisation_name> <input_csv>")
        sys.exit(1)

    organisation = sys.argv[1]
    csv_filename = sys.argv[2]

    updates_by_name = read_repository_updates(csv_filename)
    errors = apply_repository_updates(organisation, updates_by_name)

    if errors:
        logger = setup_logging()
        logger.error("%d repositories failed to update", len(errors))
        for repo_name, exc in errors:
            logger.error(" - %s: %s", repo_name, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
