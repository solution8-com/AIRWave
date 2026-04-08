"""GitHub scraper implementation."""

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional
import httpx

from .base import BaseScraper
from ..models import ContentItem, SourceType, GitHubSourceConfig, StarredRepo, StarListState
from ..storage.manager import StorageManager

logger = logging.getLogger(__name__)


class GitHubGraphQLClient:
    """Minimal GraphQL client for the GitHub API."""

    def __init__(self, token: str, http_client: httpx.AsyncClient):
        """Initialize the GraphQL client.

        Args:
            token: GitHub personal access token
            http_client: Shared async HTTP client to reuse
        """
        self.token = token
        self.http_client = http_client
        self.base_url = "https://api.github.com/graphql"

    async def query(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Optional variables dict

        Returns:
            Parsed JSON response dict
        """
        headers = {
            "Authorization": f"bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        response = await self.http_client.post(
            self.base_url,
            json={"query": query, "variables": variables or {}},
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


class GitHubScraper(BaseScraper):
    """Scraper for GitHub events and releases."""

    def __init__(
        self,
        sources: List[GitHubSourceConfig],
        http_client: httpx.AsyncClient,
        storage: Optional[StorageManager] = None,
    ):
        """Initialize GitHub scraper.

        Args:
            sources: List of GitHub source configurations
            http_client: Shared async HTTP client
            storage: Optional storage manager (required for star_list sources)
        """
        super().__init__({"sources": sources}, http_client)
        self.token = os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.storage = storage
        self.graphql_client = (
            GitHubGraphQLClient(self.token, http_client) if self.token else None
        )

    def _get_headers(self) -> dict:
        """Get request headers with optional authentication.

        Returns:
            dict: HTTP headers
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AIRWave-Aggregator"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch GitHub content items.

        Args:
            since: Only fetch items published after this time

        Returns:
            List[ContentItem]: Fetched content items
        """
        items = []
        sources = self.config["sources"]

        for source in sources:
            if not source.enabled:
                continue

            if source.type == "user_events" and source.username:
                user_items = await self._fetch_user_events(source.username, since)
                items.extend(user_items)
            elif source.type == "repo_releases" and source.owner and source.repo:
                release_items = await self._fetch_repo_releases(
                    source.owner, source.repo, since
                )
                items.extend(release_items)
            elif source.type == "star_list" and source.username:
                star_items = await self._fetch_star_list(source.username)
                items.extend(star_items)

        return items

    async def _fetch_user_events(
        self,
        username: str,
        since: datetime
    ) -> List[ContentItem]:
        """Fetch public events for a user.

        Args:
            username: GitHub username
            since: Only fetch events after this time

        Returns:
            List[ContentItem]: Event content items
        """
        url = f"{self.base_url}/users/{username}/events/public"
        items = []

        try:
            response = await self.client.get(url, headers=self._get_headers(), follow_redirects=True)
            response.raise_for_status()
            events = response.json()

            for event in events:
                created_at = datetime.fromisoformat(
                    event["created_at"].replace("Z", "+00:00")
                )

                if created_at < since:
                    continue

                # Filter interesting event types
                event_type = event["type"]
                if event_type not in [
                    "PushEvent", "CreateEvent", "ReleaseEvent",
                    "PublicEvent", "WatchEvent"
                ]:
                    continue

                item = self._parse_event(event, username)
                if item:
                    items.append(item)

        except httpx.HTTPError as e:
            logger.warning("Error fetching GitHub events for %s: %s", username, e)

        return items

    def _parse_event(self, event: dict, username: str) -> Optional[ContentItem]:
        """Parse GitHub event into ContentItem.

        Args:
            event: GitHub event data
            username: GitHub username

        Returns:
            Optional[ContentItem]: Parsed content item or None
        """
        event_type = event["type"]
        event_id = event["id"]
        created_at = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))

        repo_name = event["repo"]["name"]
        repo_url = f"https://github.com/{repo_name}"

        # Generate title and content based on event type
        if event_type == "PushEvent":
            commits = event["payload"].get("commits", [])
            title = f"{username} pushed {len(commits)} commit(s) to {repo_name}"
            content = "\n".join([c.get("message", "") for c in commits[:3]])
        elif event_type == "CreateEvent":
            ref_type = event["payload"].get("ref_type", "repository")
            title = f"{username} created {ref_type} in {repo_name}"
            content = event["payload"].get("description", "")
        elif event_type == "ReleaseEvent":
            release = event["payload"].get("release", {})
            title = f"{username} released {release.get('tag_name', '')} in {repo_name}"
            content = release.get("body", "")
            repo_url = release.get("html_url", repo_url)
        elif event_type == "PublicEvent":
            title = f"{username} made {repo_name} public"
            content = ""
        elif event_type == "WatchEvent":
            title = f"{username} starred {repo_name}"
            content = ""
        else:
            return None

        return ContentItem(
            id=self._generate_id("github", "event", event_id),
            source_type=SourceType.GITHUB,
            title=title,
            url=repo_url,
            content=content,
            author=username,
            published_at=created_at,
            metadata={
                "event_type": event_type,
                "repo": repo_name,
            }
        )

    async def _fetch_repo_releases(
        self,
        owner: str,
        repo: str,
        since: datetime
    ) -> List[ContentItem]:
        """Fetch releases for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            since: Only fetch releases after this time

        Returns:
            List[ContentItem]: Release content items
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/releases"
        items = []

        try:
            response = await self.client.get(url, headers=self._get_headers(), follow_redirects=True)
            response.raise_for_status()
            releases = response.json()

            for release in releases:
                published_at = datetime.fromisoformat(
                    release["published_at"].replace("Z", "+00:00")
                )

                if published_at < since:
                    continue

                item = ContentItem(
                    id=self._generate_id("github", "release", str(release["id"])),
                    source_type=SourceType.GITHUB,
                    title=f"{owner}/{repo} released {release['tag_name']}",
                    url=release["html_url"],
                    content=release.get("body", ""),
                    author=release["author"]["login"],
                    published_at=published_at,
                    metadata={
                        "repo": f"{owner}/{repo}",
                        "tag": release["tag_name"],
                        "prerelease": release.get("prerelease", False),
                    }
                )
                items.append(item)

        except httpx.HTTPError as e:
            logger.warning("Error fetching releases for %s/%s: %s", owner, repo, e)

        return items

    async def _fetch_star_list(self, username: str) -> List[ContentItem]:
        """Fetch updates to a user's global starred repositories via GraphQL.

        On the first run the current state is saved and an empty list is
        returned to avoid flooding the system with historical stars.
        Subsequent runs compare the new state against the saved state and
        emit ContentItems for newly starred and unstarred repositories.

        Args:
            username: GitHub username whose stars to track

        Returns:
            List[ContentItem]: Content items representing star changes
        """
        if not self.graphql_client:
            logger.warning("GITHUB_TOKEN not set – skipping star_list fetch for %s", username)
            return []

        if not self.storage:
            logger.warning("No storage provided – skipping star_list fetch for %s", username)
            return []

        graphql_query = """
        query getUserStars($username: String!, $cursor: String) {
            user(login: $username) {
                starredRepositories(
                    first: 100,
                    after: $cursor,
                    orderBy: {field: STARRED_AT, direction: DESC}
                ) {
                    edges {
                        starredAt
                        node {
                            id
                            nameWithOwner
                            description
                            url
                            primaryLanguage { name }
                            stargazerCount
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        }
        """

        all_repos: List[StarredRepo] = []
        has_next = True
        cursor = None

        try:
            while has_next:
                result = await self.graphql_client.query(
                    graphql_query, {"username": username, "cursor": cursor}
                )
                connection = result["data"]["user"]["starredRepositories"]

                for edge in connection["edges"]:
                    node = edge["node"]
                    lang = node.get("primaryLanguage") or {}
                    all_repos.append(
                        StarredRepo(
                            id=node["id"],
                            name_with_owner=node["nameWithOwner"],
                            description=node.get("description"),
                            url=node["url"],
                            language=lang.get("name"),
                            stars=node["stargazerCount"],
                            starred_at=datetime.fromisoformat(
                                edge["starredAt"].replace("Z", "+00:00")
                            ),
                        )
                    )

                page_info = connection["pageInfo"]
                has_next = page_info["hasNextPage"]
                cursor = page_info["endCursor"]

        except Exception as e:
            logger.warning("Error fetching stars for %s: %s", username, e)
            return []

        list_id = f"stars_{username}"
        prev_state = self.storage.load_star_list_state(list_id)

        current_state = StarListState(
            list_id=list_id,
            username=username,
            repositories=all_repos,
            last_updated=datetime.now(timezone.utc),
            repo_count=len(all_repos),
        )
        self.storage.save_star_list_state(list_id, current_state)

        if prev_state is None:
            logger.info(
                "First run for %s stars – state saved, returning 0 items to prevent flood.",
                username,
            )
            return []

        return self._compare_star_lists(prev_state, current_state)

    def _compare_star_lists(
        self,
        prev_state: StarListState,
        current_state: StarListState,
    ) -> List[ContentItem]:
        """Compare two star list states and generate content items for changes.

        Args:
            prev_state: Previously persisted star list state
            current_state: Freshly fetched star list state

        Returns:
            List[ContentItem]: Items for newly starred and unstarred repos
        """
        items: List[ContentItem] = []

        prev_repos = {repo.id: repo for repo in prev_state.repositories}
        curr_repos = {repo.id: repo for repo in current_state.repositories}

        # New stars
        for repo_id in set(curr_repos.keys()) - set(prev_repos.keys()):
            repo = curr_repos[repo_id]
            items.append(
                ContentItem(
                    id=self._generate_id("github", "star_new", repo.id),
                    source_type=SourceType.GITHUB,
                    title=f"{current_state.username} starred: {repo.name_with_owner}",
                    url=repo.url,
                    content=repo.description or "",
                    author=current_state.username,
                    published_at=repo.starred_at,
                    metadata={
                        "event_type": "star_new",
                        "repo": repo.name_with_owner,
                        "language": repo.language,
                        "stars": repo.stars,
                    },
                )
            )

        # Removed stars
        for repo_id in set(prev_repos.keys()) - set(curr_repos.keys()):
            repo = prev_repos[repo_id]
            items.append(
                ContentItem(
                    id=self._generate_id("github", "star_removed", repo.id),
                    source_type=SourceType.GITHUB,
                    title=f"{current_state.username} unstarred: {repo.name_with_owner}",
                    url=repo.url,
                    content=f"Repository {repo.name_with_owner} was removed from starred list",
                    author=current_state.username,
                    published_at=datetime.now(timezone.utc),
                    metadata={
                        "event_type": "star_removed",
                        "repo": repo.name_with_owner,
                    },
                )
            )

        return items
