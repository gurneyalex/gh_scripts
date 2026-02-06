from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set
import csv
import sys

from .utils import _build_github_client, setup_logging


@dataclass
class UserInfo:
    """Lightweight representation of a GitHub user.

    Attributes
    ----------
    name: str
        Login of the user.
    email: str
        Email of the user.
    internal: bool
        True if the user is a member of the organisation, False otherwise.
    teams: List[str]
        List of team names to which the user belongs.
    repositories: List[str]
        List of repository names to which the user has access.
    """

    name: str
    email: str
    internal: bool
    teams: Set[str]
    repositories: Set[str]


def retrieve_github_users(organisation: str) -> List[UserInfo]:
    """Retrieve all users (members and outside collaborators) for an organisation.

    For each user, a :class:`UserInfo` is created. The ``internal`` field is
    ``True`` for organisation members and ``False`` for outside collaborators.

    For internal users, the ``repositories`` list is left empty as requested.
    For external users, ``repositories`` contains the names of repositories
    within the organisation to which the user has access.
    """

    logger = setup_logging()
    github_client = _build_github_client()
    org = github_client.get_organization(organisation)

    users: Dict[str, UserInfo] = {}

    # Internal members of the organisation.
    for member in org.get_members():
        login = member.login
        email = member.email or ""
        users[login] = UserInfo(
            name=login,
            email=email,
            internal=True,
            teams=set(),
            repositories=set(),  # kept empty for internal users
        )
        logger.info("Created internal user info for '%s'", login)

    # Outside collaborators (external users).
    for collaborator in org.get_outside_collaborators():
        login = collaborator.login
        email = collaborator.email or ""
        users[login] = UserInfo(
            name=login,
            email=email,
            internal=False,
            teams=set(),
            repositories=set(),
        )
        logger.info("Created external user info for '%s'", login)

    # Populate team membership for all known users.
    for team in org.get_teams():
        for member in team.get_members():
            login = member.login
            logger.info("Checking team '%s' for user %s", team.name, login)
            user = users.get(login)
            if user is not None:
                user.teams.add(team.name)

    # Populate repositories for external users only.
    for repo in org.get_repos(type="all"):
        for collaborator in repo.get_collaborators():
            login = collaborator.login
            logger.info("Checking repository '%s' for user %s", repo.name, login)
            user = users.get(login)
            if user is not None and not user.internal:
                user.repositories.add(repo.name)

    return list(users.values())


def make_users_csv(organisation: str, csv_filename: str) -> None:
    """Fetch organisation users and serialize them into a CSV file.

    The CSV contains one line per user with the following columns:
    name, email, internal, teams, repositories.

    - ``teams`` is a semicolon-separated list of team names.
    - ``repositories`` is a semicolon-separated list of repository names.
    """

    users = retrieve_github_users(organisation)

    fieldnames = [
        "name",
        "email",
        "internal",
        "teams",
        "repositories",
    ]

    with open(csv_filename, "w", newline="", encoding="utf-8", buffering=1) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for user in users:
            teams_str = ";".join(sorted(user.teams))
            repos_str = ";".join(sorted(user.repositories))

            writer.writerow(
                {
                    "name": user.name,
                    "email": user.email,
                    "internal": user.internal,
                    "teams": teams_str,
                    "repositories": repos_str,
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

    make_users_csv(organisation_name, csv_filename)


if __name__ == "__main__":
    main()
