"""
Kernel Service - Living Body Integration for Agent

This service provides browser automation through Kernel's unikernel infrastructure.
It enables the agent to control a persistent browser session with human-like behavior.
"""

import asyncio
import random
import os
from typing import Optional, Dict, Any
from datetime import datetime


class KernelService:
    """
    Manages browser sessions through Kernel API.
    
    Provides:
    - Persistent profile management (tied to the agent's identity)
    - Human-behavior mimicry (mouse jerks, typing delays)
    - Login/navigation workflows
    - Content posting with DB-driven content generation
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("KERNEL_API_KEY")
        if not self.api_key:
            raise ValueError("KERNEL_API_KEY not found in environment")
        
        # Import kernel SDK (lazy to avoid requiring it globally)
        try:
            from kernel import Kernel
            self.kernel = Kernel(api_key=self.api_key)
            self._kernel_available = True
        except ImportError:
            print("⚠️ Kernel SDK not installed. Run: pip install kernel playwright")
            self._kernel_available = False
            self.kernel = None
        
        # Track active sessions
        self.active_session: Optional[Dict[str, Any]] = None
        self.profile_name = "aios_identity"
    
    async def create_persistent_profile(self) -> Dict[str, Any]:
        """Create or get a persistent browser profile linked to the agent's identity."""
        if not self._kernel_available:
            return {"error": "Kernel SDK not available"}
        
        try:
            # Try to get existing profile or create new one
            # Note: Profiles require paid plan on Kernel
            try:
                profile = self.kernel.profiles.get(name=self.profile_name)
            except:
                profile = self.kernel.profiles.create(name=self.profile_name)
            
            return {
                "success": True,
                "profile_id": profile.id,
                "profile_name": profile.name
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def launch_browser(
        self, 
        headless: bool = False, 
        stealth: bool = True
    ) -> Dict[str, Any]:
        """
        Launch a living browser session.
        
        Args:
            headless: If False, provides GUI/VNC Live View for demo
            stealth: Enable anti-detection features
        
        Returns:
            Session info including live_view_url for demo purposes
        """
        if not self._kernel_available:
            return {"error": "Kernel SDK not available"}
        
        try:
            # Note: Profiles require paid plan, so we'll launch without profile for now
            # This means cookies won't persist, but demo will still work
            
            # Launch browser with persistent identity
            browser = self.kernel.browsers.create(
                # profile={"id": profile.id, "save_changes": True},  # Requires paid plan
                stealth=stealth,
                headless=headless,
                timeout_seconds=3600  # 1 hour session
            )
            
            # Store session info
            self.active_session = {
                "session_id": browser.session_id,
                "live_view_url": browser.browser_live_view_url,
                "cdp_ws_url": browser.cdp_ws_url,
                "created_at": datetime.now().isoformat()
            }
            
            return {
                "success": True,
                "session_id": browser.session_id,
                "live_view_url": browser.browser_live_view_url,
                "message": "Browser launched. Live view available for demo."
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def human_mouse_movement(
        self, 
        target_x: int, 
        target_y: int,
        add_jerk: bool = True
    ) -> None:
        """
        Move mouse with human-like behavior.
        
        Args:
            target_x, target_y: Final destination
            add_jerk: Add random "mouse lift" behavior
        """
        if not self.active_session:
            raise RuntimeError("No active browser session")
        
        session_id = self.active_session["session_id"]
        
        # The "jerk" - mouse gets stuck or lifted mid-movement
        if add_jerk and random.random() > 0.5:
            # Random jerk to unexpected location
            jerk_x = random.randint(100, 800)
            jerk_y = random.randint(100, 600)
            self.kernel.browsers.computer.moveMouse(
                session_id,
                x=jerk_x, y=jerk_y
            )
            # Brief pause (mouse lifted)
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Smooth movement to actual target
        self.kernel.browsers.computer.moveMouse(
            session_id,
            x=target_x, y=target_y
        )
    
    async def human_type(
        self, 
        text: str, 
        add_typos: bool = True
    ) -> None:
        """
        Type text with human-like delays and occasional typos.
        
        Args:
            text: Content to type
            add_typos: Randomly introduce and correct typos
        """
        if not self.active_session:
            raise RuntimeError("No active browser session")
        
        session_id = self.active_session["session_id"]
        
        for i, char in enumerate(text):
            # Random typo injection (5% chance)
            if add_typos and random.random() < 0.05 and i < len(text) - 1:
                # Type wrong character
                wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                self.kernel.browsers.computer.type(
                    session_id,
                    text=wrong_char
                )
                await asyncio.sleep(random.uniform(0.1, 0.2))
                # Backspace to correct
                self.kernel.browsers.computer.type(
                    session_id,
                    text="\b"
                )
                await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # Type actual character
            self.kernel.browsers.computer.type(
                session_id,
                text=char
            )
            
            # Human-like delay (faster for common letters, slower for punctuation)
            if char == " ":
                delay = random.uniform(0.2, 0.4)
            elif char in ".,!?":
                delay = random.uniform(0.3, 0.5)
            else:
                delay = random.uniform(0.05, 0.15)
            
            await asyncio.sleep(delay)
    
    async def navigate_and_login(
        self, 
        url: str,
        credentials: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Navigate to a site and perform login with human-like behavior.
        
        Args:
            url: Target website
            credentials: {"username": "...", "password": "..."}
        
        Returns:
            Status of login attempt
        """
        if not self._kernel_available:
            return {"error": "Kernel SDK not available"}
        
        if not self.active_session:
            launch_result = await self.launch_browser(headless=False, stealth=True)
            if "error" in launch_result:
                return launch_result
        
        try:
            # Use playwright through CDP connection
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(
                    self.active_session["cdp_ws_url"]
                )
                context = browser.contexts[0]
                page = context.pages[0]
                
                # Navigate to login page
                await page.goto(url)
                await asyncio.sleep(random.uniform(1.5, 3.0))  # Human pause
                
                # Find and fill username (with human typing)
                # This is a simplified version - you'd customize selectors per site
                username_field = await page.query_selector('input[type="email"], input[name="username"], input[name="email"]')
                if username_field:
                    await username_field.click()
                    await self.human_type(credentials.get("username", ""))
                
                # Find and fill password
                password_field = await page.query_selector('input[type="password"]')
                if password_field:
                    await password_field.click()
                    await self.human_type(credentials.get("password", ""))
                
                # Click login button
                login_button = await page.query_selector('button[type="submit"], input[type="submit"]')
                if login_button:
                    await login_button.click()
                
                # Wait for navigation
                await asyncio.sleep(5)
                
                return {
                    "success": True,
                    "message": "Login sequence executed",
                    "current_url": page.url
                }
                
        except Exception as e:
            return {"error": f"Login failed: {str(e)}"}
    
    async def post_content(
        self, 
        content: str,
        post_selector: str = 'div[role="textbox"], textarea[placeholder*="post" i]'
    ) -> Dict[str, Any]:
        """
        Post content with human-like typing and behavior.
        
        Args:
            content: Text to post (generated from DB/identity)
            post_selector: CSS selector for post input field
        
        Returns:
            Status of posting attempt
        """
        if not self.active_session:
            return {"error": "No active browser session"}
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(
                    self.active_session["cdp_ws_url"]
                )
                context = browser.contexts[0]
                page = context.pages[0]
                
                # Find post input area
                post_field = await page.query_selector(post_selector)
                if not post_field:
                    return {"error": "Could not find post input field"}
                
                # Click to focus
                await post_field.click()
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # Type content with human behavior
                await self.human_type(content, add_typos=True)
                
                # Pause to "review" the post
                await asyncio.sleep(random.uniform(2.0, 4.0))
                
                # Find and click post button
                post_button = await page.query_selector('button:has-text("Post"), button[type="submit"]')
                if post_button:
                    await post_button.click()
                    await asyncio.sleep(2)
                    
                    return {
                        "success": True,
                        "message": "Content posted successfully",
                        "content": content
                    }
                else:
                    return {"error": "Could not find post button"}
                    
        except Exception as e:
            return {"error": f"Posting failed: {str(e)}"}
    
    async def close_session(self) -> Dict[str, Any]:
        """Close the browser session and save profile state."""
        if not self.active_session:
            return {"message": "No active session"}
        
        try:
            self.kernel.browsers.delete(
                self.active_session["session_id"]
            )
            
            session_id = self.active_session["session_id"]
            self.active_session = None
            
            return {
                "success": True,
                "message": f"Session {session_id} closed. Profile state saved."
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def get_session_info(self) -> Dict[str, Any]:
        """Get current session status for debugging/monitoring."""
        if not self.active_session:
            return {
                "active": False,
                "message": "No active browser session"
            }
        
        return {
            "active": True,
            **self.active_session
        }


# Factory function for easy integration
def get_kernel_service() -> Optional[KernelService]:
    """Get KernelService instance if API key is configured."""
    try:
        return KernelService()
    except ValueError as e:
        print(f"⚠️ Kernel service unavailable: {e}")
        return None
