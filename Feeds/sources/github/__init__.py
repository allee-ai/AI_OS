"""
GitHub Feed Module
==================

GitHub integration via Device Flow for easy "Connect with GitHub" UX.
No redirect URIs needed - user enters code at github.com/login/device.
"""

from typing import List, Dict, Any, Optional
from Feeds.events import EventTypeDefinition, register_event_types, emit_event

# ============================================================================
# OAuth Configuration (Device Flow - no redirect needed)
# ============================================================================

GITHUB_OAUTH_CONFIG = {
    "provider": "github",
    "client_id_env": "GITHUB_CLIENT_ID",
    # Device flow endpoints
    "device_code_uri": "https://github.com/login/device/code",
    "token_uri": "https://github.com/login/oauth/access_token",
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
# Device Flow OAuth Functions
# ============================================================================

async def start_device_flow() -> Dict[str, Any]:
    """
    Start GitHub Device Flow - returns user_code and verification_uri.
    
    Returns:
        {
            "device_code": "xxx",      # Used to poll for token
            "user_code": "ABCD-1234",  # User enters this at GitHub
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
            "interval": 5              # Poll interval in seconds
        }
    """
    import os
    import httpx
    
    client_id = os.environ.get(GITHUB_OAUTH_CONFIG["client_id_env"], "")
    if not client_id:
        raise ValueError("GITHUB_CLIENT_ID not set. Create a GitHub OAuth App and add it to .env")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_OAUTH_CONFIG["device_code_uri"],
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "scope": " ".join(GITHUB_OAUTH_CONFIG["scopes"]),
            },
        )
        response.raise_for_status()
        return response.json()


async def poll_for_token(device_code: str) -> Dict[str, Any]:
    """
    Poll GitHub for access token (call this on interval until success).
    
    Returns:
        On success: {"access_token": "xxx", "token_type": "bearer", "scope": "..."}
        On pending: {"error": "authorization_pending"}
        On slow_down: {"error": "slow_down", "interval": 10}
        On expired: {"error": "expired_token"}
        On denied: {"error": "access_denied"}
    """
    import os
    import httpx
    
    client_id = os.environ.get(GITHUB_OAUTH_CONFIG["client_id_env"], "")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_OAUTH_CONFIG["token_uri"],
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        return response.json()


# Legacy function for backwards compatibility
def get_oauth_url(state: Optional[str] = None) -> str:
    """Legacy - use start_device_flow() instead."""
    raise ValueError("GitHub now uses Device Flow. Use the 'Login with GitHub' button which will show a code to enter at github.com")


async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """Legacy - use poll_for_token() instead."""
    raise ValueError("GitHub now uses Device Flow - no code exchange needed")


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
