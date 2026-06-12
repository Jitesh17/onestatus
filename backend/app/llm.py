"""Provider-agnostic LLM access: one JSON-in, JSON-out call for the whole app.

llm_json() dispatches on config.settings.llm_provider:

  ollama     local Ollama /api/chat in JSON mode (the original week-2 path)
  openai     any OpenAI-compatible /v1/chat/completions endpoint: OpenAI itself,
             vLLM on the GPU box, LiteLLM proxies, even Ollama's own /v1
  anthropic  Anthropic /v1/messages

All three are a single stdlib-urllib POST; no SDK dependencies. Model, key,
base URL, temperature, and timeout come from config.settings at call time so
the /settings API switches providers live. Every failure raises ExtractorError,
which the routers map to a clean 503.

The extractor's `ollama_json` is a thin wrapper over this module and remains
the stable seam the test suite patches.
"""
import json
import urllib.error
import urllib.request

from .config import settings


class ExtractorError(RuntimeError):
    """Raised when the LLM call fails or its output is unusable."""


def _post_json(url, payload, headers, timeout):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise ExtractorError(f"LLM endpoint returned HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise ExtractorError(f"Cannot reach the LLM endpoint at {url} ({e}).") from e


def _parse_json_content(content):
    """Parse model output as JSON; tolerate prose-wrapped JSON (no JSON mode on
    the Anthropic API, and cloud models occasionally add a preamble)."""
    if not content:
        raise ExtractorError("The model returned an empty response.")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise ExtractorError(f"Model did not return valid JSON: {content[:200]}")


def _ollama(system_prompt, user_text, model, base_url):
    base = base_url or settings.ollama_url
    payload = {
        "model": model,
        "format": "json",
        "stream": False,
        "options": {"temperature": settings.llm_temperature},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    }
    try:
        body = _post_json(f"{base}/api/chat", payload, {}, settings.llm_timeout)
    except ExtractorError as e:
        raise ExtractorError(
            f"{e} Is `ollama serve` running and the model pulled?"
        ) from e
    return _parse_json_content(body.get("message", {}).get("content", ""))


def _openai(system_prompt, user_text, model, base_url):
    base = (base_url or settings.llm_base_url or "https://api.openai.com").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    payload = {
        "model": model,
        "temperature": settings.llm_temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    }
    headers = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    body = _post_json(f"{base}/v1/chat/completions", payload, headers, settings.llm_timeout)
    choices = body.get("choices") or []
    content = choices[0].get("message", {}).get("content", "") if choices else ""
    return _parse_json_content(content)


def _anthropic(system_prompt, user_text, model, base_url):
    base = (base_url or "https://api.anthropic.com").rstrip("/")
    payload = {
        "model": model,
        "max_tokens": 2048,
        "temperature": settings.llm_temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_text}],
    }
    headers = {
        "x-api-key": settings.llm_api_key,
        "anthropic-version": "2023-06-01",
    }
    body = _post_json(f"{base}/v1/messages", payload, headers, settings.llm_timeout)
    blocks = body.get("content") or []
    content = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return _parse_json_content(content)


_PROVIDERS = {"ollama": _ollama, "openai": _openai, "anthropic": _anthropic}


def llm_json(system_prompt, user_text, model=None, base_url=None):
    """Send a system+user prompt to the configured provider, return parsed JSON.

    `model`/`base_url` override the configured defaults for one call (the
    /extract and /dashboard/configure APIs expose the model override).
    """
    provider = _PROVIDERS.get(settings.llm_provider)
    if provider is None:
        raise ExtractorError(f"Unknown LLM provider: {settings.llm_provider!r}")
    return provider(system_prompt, user_text, model or settings.llm_model, base_url)
