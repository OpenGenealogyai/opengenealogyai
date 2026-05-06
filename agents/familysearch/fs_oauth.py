"""
FamilySearch OAuth 2.0 PKCE stub for OpenGenealogyAI.

All FamilySearch records are tier2-private — they are NEVER included in
public datasets or open Qdrant collections.

Real FamilySearch API: https://api.familysearch.org/platform/
OAuth endpoints:
  Authorization: https://ident.familysearch.org/cis-web/oauth2/v3/authorization
  Token:         https://ident.familysearch.org/cis-web/oauth2/v3/token

Flow: PKCE (code_verifier / code_challenge) — no client_secret required.
Users authorize in browser, callback delivers code, we exchange for bearer token.

Usage (agent context):
    from agents.familysearch.fs_oauth import FSAuthSession

    session = FSAuthSession(client_id=os.environ["FS_CLIENT_ID"],
                            redirect_uri="http://localhost:8765/callback")
    auth_url = session.get_authorization_url()
    # ... user visits auth_url, grants access, arrives at redirect_uri?code=... ...
    token = session.exchange_code(code)
    # token is stored in session; use session.get() for API calls
"""

import base64, hashlib, json, os, secrets, urllib.parse, urllib.request
from dataclasses import dataclass, field
from typing import Optional

FS_AUTH_URL = "https://ident.familysearch.org/cis-web/oauth2/v3/authorization"
FS_TOKEN_URL = "https://ident.familysearch.org/cis-web/oauth2/v3/token"
FS_API_BASE  = "https://api.familysearch.org"
FS_SCOPE     = "openid profile email"


def _pkce_pair() -> tuple[str, str]:
    """Generate (code_verifier, code_challenge) for PKCE."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@dataclass
class FSAuthSession:
    client_id: str
    redirect_uri: str
    _verifier: str = field(default="", init=False, repr=False)
    _challenge: str = field(default="", init=False, repr=False)
    _state: str = field(default="", init=False, repr=False)
    access_token: Optional[str] = field(default=None, init=False, repr=False)
    token_type: str = field(default="Bearer", init=False)

    def get_authorization_url(self) -> str:
        """Build the URL the user must visit in their browser to grant access."""
        self._verifier, self._challenge = _pkce_pair()
        self._state = secrets.token_hex(16)
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": FS_SCOPE,
            "code_challenge": self._challenge,
            "code_challenge_method": "S256",
            "state": self._state,
        }
        return f"{FS_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, state: Optional[str] = None) -> str:
        """Exchange authorization code for access token. Returns the token string."""
        if state and state != self._state:
            raise ValueError("OAuth state mismatch — possible CSRF")

        body = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "code_verifier": self._verifier,
        }).encode()

        req = urllib.request.Request(
            FS_TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Accept": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        self.access_token = data["access_token"]
        self.token_type = data.get("token_type", "Bearer")
        return self.access_token

    def get(self, path: str, accept: str = "application/json") -> dict:
        """Make an authenticated GET request to the FamilySearch platform API."""
        if not self.access_token:
            raise RuntimeError("Not authenticated — call exchange_code() first")
        url = f"{FS_API_BASE}{path}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"{self.token_type} {self.access_token}",
                "Accept": accept,
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
