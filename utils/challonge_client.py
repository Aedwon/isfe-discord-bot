"""
Challonge API Client

Provides async HTTP client for Challonge API v1.
API Docs: https://api.challonge.com/v1
"""

import aiohttp
import os
import re
from typing import Optional, Tuple, List, Dict, Any


class ChallongeAPIError(Exception):
    """Custom exception for Challonge API errors."""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ChallongeClient:
    """Async client for Challonge API v1."""
    
    BASE_URL = "https://api.challonge.com/v1"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("CHALLONGE_API_KEY")
        if not self.api_key:
            raise ValueError("CHALLONGE_API_KEY not found in environment")
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make authenticated request to Challonge API."""
        url = f"{self.BASE_URL}/{endpoint}.json"
        
        # Add API key to params
        params = kwargs.pop("params", {})
        params["api_key"] = self.api_key
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, **kwargs) as resp:
                if resp.status == 401:
                    raise ChallongeAPIError("Invalid API key", 401)
                elif resp.status == 404:
                    raise ChallongeAPIError("Tournament not found", 404)
                elif resp.status >= 400:
                    text = await resp.text()
                    raise ChallongeAPIError(f"API error: {text}", resp.status)
                
                return await resp.json()
    
    async def get_tournament(self, slug: str) -> dict:
        """Get tournament details."""
        data = await self._request("GET", f"tournaments/{slug}")
        return data.get("tournament", {})
    
    async def validate_tournament(self, slug: str) -> Tuple[bool, dict, str]:
        """Validate that a tournament exists and is accessible."""
        try:
            tournament = await self.get_tournament(slug)
            return True, tournament, None
        except ChallongeAPIError as e:
            return False, None, e.message
    
    async def get_participants(self, slug: str) -> List[dict]:
        """Get all participants in a tournament."""
        data = await self._request("GET", f"tournaments/{slug}/participants")
        return [p.get("participant", {}) for p in data]
    
    async def get_matches(self, slug: str, state: str = "all") -> List[dict]:
        """Get matches from tournament.
        
        Args:
            slug: Tournament slug/ID
            state: 'all', 'open', 'pending', or 'complete'
        """
        params = {}
        if state != "all":
            params["state"] = state
        
        data = await self._request("GET", f"tournaments/{slug}/matches", params=params)
        return [m.get("match", {}) for m in data]
    
    async def update_match(self, slug: str, match_id: int, winner_id: int, scores_csv: str) -> dict:
        """Update match result.
        
        Args:
            slug: Tournament slug
            match_id: Match ID
            winner_id: Participant ID of winner
            scores_csv: Score in "X-Y" format
        """
        data = {
            "match": {
                "winner_id": winner_id,
                "scores_csv": scores_csv
            }
        }
        result = await self._request("PUT", f"tournaments/{slug}/matches/{match_id}", json=data)
        return result.get("match", {})


def parse_challonge_url(url: str) -> Optional[str]:
    """Extract tournament slug from Challonge URL.
    
    Supports:
    - https://challonge.com/tournament_slug
    - https://subdomain.challonge.com/tournament_slug
    """
    patterns = [
        r"https?://(?:[\w-]+\.)?challonge\.com/([a-zA-Z0-9_-]+)",
    ]
    
    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            return match.group(1)
    
    return None


def build_participant_cache(participants: List[dict]) -> Dict[int, str]:
    """Build ID -> Name mapping from participant list."""
    cache = {}
    for p in participants:
        pid = p.get("id")
        name = p.get("name") or p.get("display_name") or f"Player {pid}"
        if pid:
            cache[pid] = name
    return cache


def find_participant_by_name(cache: Dict[int, str], search: str) -> Optional[Tuple[int, str]]:
    """Find participant by partial name match (case-insensitive)."""
    search_lower = search.lower().strip()
    
    # Exact match first
    for pid, name in cache.items():
        if name.lower() == search_lower:
            return pid, name
    
    # Partial match
    for pid, name in cache.items():
        if search_lower in name.lower():
            return pid, name
    
    return None


def format_match_display(match: dict, participants: Dict[int, str], include_state: bool = False) -> str:
    """Format match for display in Discord."""
    match_num = match.get("suggested_play_order") or match.get("id") or "?"
    p1_id = match.get("player1_id")
    p2_id = match.get("player2_id")
    
    p1_name = participants.get(p1_id, "TBD") if p1_id else "TBD"
    p2_name = participants.get(p2_id, "TBD") if p2_id else "TBD"
    
    state = match.get("state", "unknown")
    scores = match.get("scores_csv", "")
    
    line = f"`#{match_num}` {p1_name} vs {p2_name}"
    
    if include_state and state == "complete":
        winner_id = match.get("winner_id")
        winner_name = participants.get(winner_id, "?")
        line += f" → 🏆 {winner_name} ({scores})"
    
    return line
