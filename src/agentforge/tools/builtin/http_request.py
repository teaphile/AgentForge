"""HTTP request tool with SSRF protection."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from agentforge.tools.base import Tool

# Block private/reserved IP ranges to prevent SSRF
_BLOCKED_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_url_safe(url: str) -> tuple[bool, str]:
    """Resolve the URL's host and reject private/internal IPs."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False, "Missing hostname"
        # Block common metadata endpoints by hostname
        if host in ("metadata.google.internal", "metadata.azure.internal"):
            return False, f"Blocked internal hostname: {host}"
        addrs = socket.getaddrinfo(host, None)
        for _family, _type, _proto, _canon, sockaddr in addrs:
            ip = ipaddress.ip_address(sockaddr[0])
            for net in _BLOCKED_RANGES:
                if ip in net:
                    return False, f"Blocked private/internal address: {ip}"
    except (socket.gaierror, ValueError) as e:
        return False, f"DNS resolution failed: {e}"
    return True, ""


async def _http_request(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: str | None = None,
) -> str:
    safe, reason = _is_url_safe(url)
    if not safe:
        return f"Error: Request blocked — {reason}"

    import httpx

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            kwargs: dict = {"headers": headers or {}}
            if body and method.upper() in ("POST", "PUT", "PATCH"):
                kwargs["content"] = body

            response = await client.request(method.upper(), url, **kwargs)

            # Build result
            result_parts = [
                f"Status: {response.status_code}",
                f"Content-Type: {response.headers.get('content-type', 'unknown')}",
            ]

            text = response.text
            if len(text) > 5000:
                text = text[:5000] + "\n\n... (truncated)"

            result_parts.append(f"\nBody:\n{text}")
            return "\n".join(result_parts)

    except httpx.TimeoutException:
        return f"Error: Request to {url} timed out after 30 seconds"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


http_request_tool = Tool(
    name="http_request",
    description="Make an HTTP request to a URL. Supports GET, POST, PUT, PATCH, DELETE methods.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to request",
            },
            "method": {
                "type": "string",
                "description": "HTTP method (GET, POST, PUT, PATCH, DELETE). Default: GET",
                "default": "GET",
            },
            "headers": {
                "type": "object",
                "description": "Optional request headers as key-value pairs",
            },
            "body": {
                "type": "string",
                "description": "Optional request body (for POST, PUT, PATCH)",
            },
        },
        "required": ["url"],
    },
    handler=_http_request,
)
