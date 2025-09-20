# common/anti_detection.py
"""
Improved anti-detection helpers (low-risk client-side measures).
Provides:
 - get_stealth_launch_args()
 - get_stealth_context_options(user_agent=None, is_mobile=False)
 - get_init_script() -> JS string to add via context.add_init_script(...)
 - get_extra_http_headers()
"""

from typing import Dict, Any, Optional

def get_stealth_launch_args() -> Dict[str, Any]:
    """
    Launch args to reduce some automation flags surface.
    Keep conservative — don't inject unknown flags that may break browser.
    """
    return {
        "args": [
            "--disable-blink-features=AutomationControlled",
            # keep GPU flags default; don't add aggressive flags unless tested
        ]
    }

def get_stealth_context_options(user_agent: Optional[str] = None, is_mobile: bool = False) -> Dict[str, Any]:
    """
    Options to pass to browser.new_context(...).
    Add timezone/locale/viewport defaults for regional consistency.
    """
    ua = user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.62 Safari/537.36"
    )
    viewport = {"width": 375, "height": 812} if is_mobile else {"width": 1280, "height": 800}

    return {
        "user_agent": ua,
        "viewport": viewport,
        "locale": "en-US",
        "timezone_id": "Asia/Kolkata",  # change if you want a different default
        # "color_scheme": "light"  # Playwright supports but test if you need
    }

def get_extra_http_headers() -> Dict[str, str]:
    """
    Extra HTTP headers to set on the context level.
    Keep headers realistic but not exhaustive.
    """
    return {
        "accept-language": "en-US,en;q=0.9",
        "referer": "https://twitter.com/",
        # basic Sec-CH hints (simple, not full ch-ua polyfill)
        "sec-ch-ua": '"Chromium";v="117", "Not;A Brand";v="24"',
    }

def get_init_script() -> str:
    """
    JS string to inject via context.add_init_script().
    This script runs before page JS and reduces detection hints.
    It's intentionally conservative (no heavy WebGL fingerprint spoofing).
    """
    return r"""
// navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// languages
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

// plugins - small fake list
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

// minimal chrome runtime stub
window.chrome = window.chrome || { runtime: {} };

// hardwareConcurrency - small conservative tweak
try {
  Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
} catch (e) {}

// platform hint
try {
  Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
} catch (e) {}

// permissions.query shim for notifications and similar
if (navigator.permissions && navigator.permissions.query) {
  const origQuery = navigator.permissions.query.bind(navigator.permissions);
  navigator.permissions.query = (params) => (
    params && params.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : origQuery(params)
  );
}

// minimal canvas / webgl tricks are intentionally omitted here; add if you know what you're doing.
"""

# Optional: helper to return everything together for convenience
def get_all_options(user_agent: Optional[str] = None, is_mobile: bool = False) -> Dict[str, Any]:
    return {
        "launch_args": get_stealth_launch_args(),
        "context_opts": get_stealth_context_options(user_agent, is_mobile),
        "init_script": get_init_script(),
        "extra_headers": get_extra_http_headers(),
    }
