"""
GitHub Feed Module
==================

GitHub integration via OAuth for notifications, issues, PRs, and activity.
Uses GitHub OAuth App flow for easy "Connect with GitHub" UX.
"""

from typing import List, Dict, Any, Optional
from Feeds.events import EventTypeDefinition, register_event_types, emit_event

# ============================================================================
# OAuth Configuration
# ============================================================================

GITHUB_OAUTH_CONFIG = {
    "provider": "github",
    "client_id_env": "GITHUB_CLIENT_ID",
    "client_secret_env": "GITHUB_CLIENT_SECRET",
    "auth_uri": "https://github.com/login/oauth/authorize",
    "token_uri": "https://github.com/login/oauth/access_token",
    "redirect_uri": "http://localhost:8000/api/feeds/github/oauth/callback",
    "scopes": [
        "repo",
        "notifications",
        "read:user",
    ],
    "api_base": "https://api.github.com",
}


# ============================================================================
# Event Types
# ============================================================================

GITHUB_EVENT_TYPES = [
    EventTypeDefinition(
        name="issue_opened",
        description="A new issue was opened in a watched repository",
        payload_schema={
            "repo": "str",
            "issue_number": "int",
            "title": "str",
            "author": "str",
            "body_preview": "str",
            "labels": "List[str]",
            "url": "str",
        },
        example_payload={
            "repo": "owner/repo",
            "issue_number": 123,
            "title": "Bug: App crashes on startup",
            "author": "username",
            "body_preview": "When I try to start the app...",
            "labels": ["bug", "help wanted"],
            "url": "https://github.com/owner/repo/issues/123",
        },
    ),
    EventTypeDefinition(
        name="pr_opened",
        description="A pull request was opened",
        payload_schema={
            "repo": "str",
            "pr_number": "int",
            "title": "str",
            "author": "str",
            "base_branch": "str",
            "head_branch": "str",
            "url": "str",
        },
        example_payload={
            "repo": "owner/repo",
            "pr_number": 456,
            "title": "feat: Add new feature",
            "author": "contributor",
            "base_branch": "main",
            "head_branch": "feature/new-feature",
            "url": "https://github.com/owner/repo/pull/456",
        },
    ),
    EventTypeDefinition(
        name="review_requested",
        description="You were requested to review a pull request",
        payload_schema={
            "repo": "str",
            "pr_number": "int",
            "title": "str",
            "author": "str",
            "url": "str",
        },
        example_payload={
            "repo": "owner/repo",
            "pr_number": 456,
            "title": "feat: Add new feature",
            "author": "contributor",
            "url": "https://github.com/owner/repo/pull/456",
        },
    ),
    EventTypeDefinition(
        name="mention",
        description="You were mentioned in an issue or PR comment",
        payload_schema={
            "repo": "str",
            "issue_number": "int",
            "comment_author": "str",
            "body_preview": "str",
            "url": "str",
        },
        example_payload={
            "repo": "owner/repo",
            "issue_number": 123,
            "comment_author": "teammate",
            "body_preview": "@you What do you think about this?",
            "url": "https://github.com/owner/repo/issues/123#comment-789",
        },
    ),
    EventTypeDefinition(
        name="push_received",
        description="New commits were pushed to a watched repository",
        payload_schema={
            "repo": "str",
            "branch": "str",
            "pusher": "str",
            "commit_count": "int",
            "head_commit_message": "str",
        },
        example_payload={
            "repo": "owner/repo",
            "branch": "main",
            "pusher": "developer",
            "commit_count": 3,
            "head_commit_message": "fix: resolve merge conflict",
        },
    ),
    EventTypeDefinition(
        name="workflow_failed",
        description="A GitHub Actions workflow failed",
        payload_schema={
            "repo": "str",
            "workflow_name": "str",
            "branch": "str",
            "run_url": "str",
            "failure_reason": "str",
        },
        example_payload={
            "repo": "owner/repo",
            "workflow_name": "CI",
            "branch": "main",
            "run_url": "https://github.com/owner/repo/actions/runs/123",
            "failure_reason": "Test suite failed",
        },
    ),
]

# Register on import
register_event_types("github", GITHUB_EVENT_TYPES)


# ============================================================================
# OAuth Functions
# ============================================================================

def get_oauth_url(state: Optional[str] = None) -> str:
    """Generate GitHub OAuth authorization URL."""
    import os
    from urllib.parse import urlencode
    
    client_id = os.environ.get(GITHUB_OAUTH_CONFIG["client_id_env"], "")
    if not client_id:
        raise ValueError("GITHUB_CLIENT_ID environment variable not set")
    
    params = {
        "client_id": client_id,
        "redirect_uri": GITHUB_OAUTH_CONFIG["redirect_uri"],
        "scope": " ".join(GITHUB_OAUTH_CONFIG["scopes"]),
    }
    if state:
        params["state"] = state
    
    return f"{GITHUB_OAUTH_CONFIG['auth_uri']}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """Exchange authorization code for access token."""
    import os
    import httpx
    
    client_id = os.environ.get(GITHUB_OAUTH_CONFIG["client_id_env"], "")
    client_secret = os.environ.get(GITHUB_OAUTH_CONFIG["client_secret_env"], "")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_OAUTH_CONFIG["token_uri"],
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": GITHUB_OAUTH_CONFIG["redirect_uri"],
            },
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# GitHub Adapter
# ============================================================================

class GitHubAdapter:
    """Adapter for GitHub API interactions."""
    
    def __init__(self):
        self.base_url = GITHUB_OAUTH_CONFIG["api_base"]
    
    def get_access_token(self) -> Optional[str]:
        """Get stored access token."""
        from agent.core.secrets import get_oauth_tokens
        
        tokens = get_oauth_tokens("github")
        if tokens:
            return tokens.get("access_token")
        return None
    
    async def get_user(self) -> Dict[str, Any]:
        """Get authenticated user info."""
        import httpx
        
        token = self.get_access_token()
        if not token:
            raise ValueError("Not authenticated with GitHub")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json()
    
    async def list_notifications(self, all: bool = False) -> List[Dict[str, Any]]:
        """List notifications for authenticated user."""
        import httpx
        
        token = self.get_access_token()
        if not token:
            raise ValueError("Not authenticated with GitHub")
        
        params = {"all": str(all).lower()}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/notifications",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                params=params,
            )
            response.raise_for_status()
            return response.json()
    
    async def list_repos(self, per_page: int = 30) -> List[Dict[str, Any]]:
        """List repositories for authenticated user."""
        import httpx
        
        token = self.get_access_token()
        if not token:
            raise ValueError("Not authenticated with GitHub")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/user/repos",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                params={"per_page": per_page, "sort": "updated"},
            )
            response.raise_for_status()
            return response.json()
    
    async def list_issues(self, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """List issues for a repository."""
        import httpx
        
        token = self.get_access_token()
        if not token:
            raise ValueError("Not authenticated with GitHub")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repos/{repo}/issues",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                params={"state": state},
            )
            response.raise_for_status()
            return response.json()
    
    async def list_prs(self, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """List pull requests for a repository."""
        import httpx
        
        token = self.get_access_token()
        if not token:
            raise ValueError("Not authenticated with GitHub")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repos/{repo}/pulls",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                params={"state": state},
            )
            response.raise_for_status()
            return response.json()
    
    async def create_issue_comment(self, repo: str, issue_number: int, body: str) -> Dict[str, Any]:
        """Post a comment on an issue or PR."""
        import httpx
        
        token = self.get_access_token()
        if not token:
            raise ValueError("Not authenticated with GitHub")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json={"body": body},
            )
            response.raise_for_status()
            return response.json()
    
    async def mark_notification_read(self, thread_id: str) -> None:
        """Mark a notification as read."""
        import httpx
        
        token = self.get_access_token()
        if not token:
            raise ValueError("Not authenticated with GitHub")
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/notifications/threads/{thread_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()


# Singleton adapter instance
_adapter: Optional[GitHubAdapter] = None

def get_adapter() -> GitHubAdapter:
    global _adapter
    if _adapter is None:
        _adapter = GitHubAdapter()
    return _adapter


def is_connected() -> bool:
    """Check if GitHub is connected."""
    from agent.core.secrets import get_oauth_tokens
    return get_oauth_tokens("github") is not None
