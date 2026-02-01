"""
Discord Feed Module
===================

Event types, OAuth setup, and adapter for Discord integration.
"""

from typing import List, Dict, Any, Optional
from Feeds.events import EventTypeDefinition, register_event_types, emit_event, EventPriority

# ============================================================================
# Event Types
# ============================================================================

DISCORD_EVENT_TYPES = [
    EventTypeDefinition(
        name="message_received",
        description="A new message was received in a channel",
        payload_schema={
            "message_id": "str",
            "channel_id": "str",
            "guild_id": "str?",
            "author_id": "str",
            "author_name": "str",
            "content": "str",
            "timestamp": "str",
        },
        example_payload={
            "message_id": "123456789",
            "channel_id": "987654321",
            "guild_id": "111222333",
            "author_id": "444555666",
            "author_name": "JohnDoe#1234",
            "content": "Hello everyone!",
            "timestamp": "2026-02-01T10:30:00Z",
        },
    ),
    EventTypeDefinition(
        name="mention_received",
        description="The bot/user was mentioned in a message",
        payload_schema={
            "message_id": "str",
            "channel_id": "str",
            "author_name": "str",
            "content": "str",
        },
        example_payload={
            "message_id": "123456789",
            "channel_id": "987654321",
            "author_name": "JohnDoe#1234",
            "content": "@Bot check this out",
        },
    ),
    EventTypeDefinition(
        name="dm_received",
        description="A direct message was received",
        payload_schema={
            "message_id": "str",
            "author_id": "str",
            "author_name": "str",
            "content": "str",
        },
        example_payload={
            "message_id": "123456789",
            "author_id": "444555666",
            "author_name": "JohnDoe#1234",
            "content": "Hey, can you help me?",
        },
    ),
    EventTypeDefinition(
        name="reaction_added",
        description="A reaction was added to a message",
        payload_schema={
            "message_id": "str",
            "channel_id": "str",
            "user_id": "str",
            "emoji": "str",
        },
        example_payload={
            "message_id": "123456789",
            "channel_id": "987654321",
            "user_id": "444555666",
            "emoji": "👍",
        },
    ),
    EventTypeDefinition(
        name="member_joined",
        description="A new member joined the server",
        payload_schema={
            "guild_id": "str",
            "user_id": "str",
            "username": "str",
        },
        example_payload={
            "guild_id": "111222333",
            "user_id": "777888999",
            "username": "NewUser#5678",
        },
    ),
]

# Register on import
register_event_types("discord", DISCORD_EVENT_TYPES)


# ============================================================================
# Bot Token Configuration (Discord uses bot tokens, not OAuth for bots)
# ============================================================================

DISCORD_CONFIG = {
    "bot_token_env": "DISCORD_BOT_TOKEN",
    "base_url": "https://discord.com/api/v10",
    "gateway_url": "wss://gateway.discord.gg",
}


def get_bot_token() -> Optional[str]:
    """Get Discord bot token from secrets or env."""
    from agent.core.secrets import get_secret
    import os
    
    # Try secrets first
    token = get_secret("bot_token", "discord")
    if token:
        return token
    
    # Fall back to env
    return os.environ.get(DISCORD_CONFIG["bot_token_env"])


# ============================================================================
# Discord API Adapter
# ============================================================================

class DiscordAdapter:
    """Adapter for Discord API interactions."""
    
    def __init__(self):
        self.base_url = DISCORD_CONFIG["base_url"]
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        token = get_bot_token()
        if not token:
            raise ValueError("Discord bot token not configured")
        return {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }
    
    async def get_current_user(self) -> Dict[str, Any]:
        """Get current bot user info."""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/users/@me",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()
    
    async def get_guilds(self) -> List[Dict[str, Any]]:
        """Get all guilds the bot is in."""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/users/@me/guilds",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()
    
    async def get_channels(self, guild_id: str) -> List[Dict[str, Any]]:
        """Get channels in a guild."""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/guilds/{guild_id}/channels",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()
    
    async def get_messages(
        self,
        channel_id: str,
        limit: int = 50,
        before: Optional[str] = None,
        after: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get messages from a channel."""
        import httpx
        
        params = {"limit": limit}
        if before:
            params["before"] = before
        if after:
            params["after"] = after
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/channels/{channel_id}/messages",
                headers=self._get_headers(),
                params=params,
            )
            response.raise_for_status()
            return response.json()
    
    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message to a channel."""
        import httpx
        
        payload = {"content": content}
        if reply_to:
            payload["message_reference"] = {"message_id": reply_to}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/channels/{channel_id}/messages",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            
            # Emit event
            emit_event(
                "discord",
                "message_sent",
                {
                    "message_id": result.get("id"),
                    "channel_id": channel_id,
                    "content": content,
                },
            )
            
            return result
    
    async def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> None:
        """Add a reaction to a message."""
        import httpx
        from urllib.parse import quote
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/channels/{channel_id}/messages/{message_id}/reactions/{quote(emoji)}/@me",
                headers=self._get_headers(),
            )
            response.raise_for_status()


# Singleton adapter instance
_adapter: Optional[DiscordAdapter] = None

def get_adapter() -> DiscordAdapter:
    global _adapter
    if _adapter is None:
        _adapter = DiscordAdapter()
    return _adapter
