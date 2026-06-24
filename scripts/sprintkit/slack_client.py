"""Slack Web API client (stdlib urllib) for epic estimation posts."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from http.client import IncompleteRead
from typing import Any

from sprintkit.env_loader import load_env_files, slack_token_setup_hint

SLACK_API = "https://slack.com/api/"
_MAX_API_RETRIES = 3
_env_bootstrapped = False


class SlackError(Exception):
    """Slack API or configuration error."""


def bootstrap_slack_env(config: dict[str, Any], *, repo_root=None) -> list[str]:
    """Load .env files once before resolving Slack credentials."""
    global _env_bootstrapped
    if _env_bootstrapped:
        return []
    _env_bootstrapped = True
    return load_env_files(config, repo_root=repo_root)


def _slack_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("slack") or {}


def resolve_bot_token(config: dict[str, Any]) -> str:
    bootstrap_slack_env(config)
    slack_cfg = _slack_config(config)
    env_name = slack_cfg.get("botTokenEnv") or "SLACK_BOT_TOKEN"
    token = os.environ.get(env_name)
    if not token:
        raise SlackError(
            "Slack bot token not found.\n" + slack_token_setup_hint(config)
        )
    return token


def _read_api_response(resp) -> dict[str, Any]:
    raw = resp.read()
    if not raw:
        raise SlackError("Slack API returned an empty response")
    return json.loads(raw.decode("utf-8"))


def _request_slack(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{SLACK_API}{method}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _read_api_response(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SlackError(f"Slack HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, IncompleteRead, TimeoutError) as exc:
        raise SlackError(f"Slack request failed: {exc}") from exc

    if not data.get("ok"):
        error = data.get("error") or "unknown_error"
        if error == "missing_scope":
            needed = data.get("needed")
            provided = data.get("provided")
            detail = f" (needed: {needed}; provided: {provided})" if needed else ""
            raise SlackError(f"Slack API error: {error}{detail}")
        raise SlackError(f"Slack API error: {error}")
    return data


def _api_call(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(_MAX_API_RETRIES):
        try:
            return _request_slack(token, method, payload)
        except SlackError as exc:
            message = str(exc)
            retriable = any(
                token in message
                for token in ("HTTP 429", "ratelimited", "request failed", "empty response")
            )
            if not retriable or attempt + 1 >= _MAX_API_RETRIES:
                raise
            time.sleep(2**attempt + 1)
            last_error = exc

    raise SlackError(f"Slack request failed after retries: {last_error}")


def _normalize_channel_name(name: str) -> str:
    return name.lstrip("#").strip()


def _channel_name_target(name: str) -> str:
    return f"#{_normalize_channel_name(name)}"


# Example ID from .env.example — not a real workspace channel.
_PLACEHOLDER_CHANNEL_IDS = frozenset({"C0123456789"})


def _configured_channel_name(config: dict[str, Any]) -> str:
    slack_cfg = _slack_config(config)
    return _normalize_channel_name(slack_cfg.get("channel") or "")


def _is_placeholder_channel_id(channel_id: str) -> bool:
    return channel_id.strip() in _PLACEHOLDER_CHANNEL_IDS


def _lookup_channel_id_by_list(token: str, target: str) -> str | None:
    """Try one conversations.list page; None if not found or lookup fails."""
    payload: dict[str, Any] = {
        "types": "public_channel,private_channel",
        "limit": 200,
        "exclude_archived": True,
    }
    data = _request_slack(token, "conversations.list", payload)
    for channel in data.get("channels") or []:
        if channel.get("name") == target:
            return channel["id"]
    return None


def resolve_channel_id(
    token: str,
    config: dict[str, Any],
    *,
    allow_name_fallback: bool = True,
) -> str:
    slack_cfg = _slack_config(config)
    if slack_cfg.get("channelId"):
        return str(slack_cfg["channelId"])

    channel_id_env = slack_cfg.get("channelIdEnv") or "SLACK_CHANNEL_ID"
    env_channel = os.environ.get(channel_id_env)
    if env_channel:
        channel_id = env_channel.strip()
        if _is_placeholder_channel_id(channel_id):
            target = _configured_channel_name(config)
            if target and allow_name_fallback:
                return _channel_name_target(target)
            raise SlackError(
                f"SLACK_CHANNEL_ID is set to the example placeholder ({channel_id}). "
                "Copy the real channel ID from Slack → channel About panel, or remove "
                "SLACK_CHANNEL_ID to use the channel name from em-config.yaml."
            )
        return channel_id

    target = _configured_channel_name(config)
    if not target:
        raise SlackError("slack.channel is not configured in em-config.yaml")

    try:
        channel_id = _lookup_channel_id_by_list(token, target)
    except SlackError as exc:
        if not allow_name_fallback:
            raise SlackError(
                f"Could not resolve Slack channel #{target}: {exc}\n"
                "Set SLACK_CHANNEL_ID in .env.local (recommended) or slack.channelId "
                "in em-config.yaml to skip conversations.list."
            ) from exc
        channel_id = None

    if channel_id:
        return channel_id

    if allow_name_fallback:
        # chat.postMessage accepts #channel-name for public channels the bot is in.
        return _channel_name_target(target)

    raise SlackError(
        f"Slack channel #{target} not found. Invite the bot to the channel, set "
        "SLACK_CHANNEL_ID, and ensure channels:read (and groups:read for private "
        "channels) scopes."
    )


def _chat_permalink(token: str, channel_id: str, message_ts: str) -> str | None:
    try:
        data = _api_call(
            token,
            "chat.getPermalink",
            {"channel": channel_id, "message_ts": message_ts},
        )
        return data.get("permalink")
    except SlackError:
        return None


def post_message(
    token: str,
    channel_id: str,
    *,
    text: str,
    blocks: list[dict[str, Any]],
    thread_ts: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "channel": channel_id,
        "text": text,
        "blocks": blocks,
        "unfurl_links": False,
        "unfurl_media": False,
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts
    return _api_call(token, "chat.postMessage", payload)


def post_epic_estimation(
    canvas: dict[str, Any],
    config: dict[str, Any],
    *,
    use_fallback: bool = False,
) -> dict[str, Any]:
    """Post epic estimation blocks to configured Slack channel."""
    from sprintkit.render.slack_blocks import (
        build_slack_blocks,
        build_slack_blocks_fallback,
    )

    token = resolve_bot_token(config)
    channel_id = resolve_channel_id(token, config)
    builder = build_slack_blocks_fallback if use_fallback else build_slack_blocks
    message = builder(canvas)
    fallback_used = use_fallback

    try:
        result = post_message(
            token,
            channel_id,
            text=message["text"],
            blocks=message["blocks"],
        )
    except SlackError as exc:
        err = str(exc)
        if "channel_not_found" in err:
            target = _configured_channel_name(config)
            name_target = _channel_name_target(target) if target else ""
            if name_target and channel_id != name_target:
                result = post_message(
                    token,
                    name_target,
                    text=message["text"],
                    blocks=message["blocks"],
                )
                channel_id = result.get("channel") or name_target
            else:
                raise SlackError(
                    f"{err}\n"
                    f"Invite the bot to #{target} and set a valid SLACK_CHANNEL_ID "
                    "(Slack → channel About → Channel ID)."
                ) from exc
        elif use_fallback or "invalid_blocks" not in err:
            raise
        else:
            message = build_slack_blocks_fallback(canvas)
            fallback_used = True
            result = post_message(
                token,
                channel_id,
                text=message["text"],
                blocks=message["blocks"],
            )

    thread_ts = result.get("ts")
    for chunk in message.get("thread_blocks") or []:
        post_message(
            token,
            channel_id,
            text=message["text"],
            blocks=chunk,
            thread_ts=thread_ts,
        )

    permalink = _chat_permalink(token, channel_id, thread_ts) if thread_ts else None
    slack_cfg = _slack_config(config)
    channel_name = _normalize_channel_name(slack_cfg.get("channel") or channel_id)

    return {
        "posted": True,
        "ts": thread_ts,
        "channel": channel_name,
        "channelId": channel_id,
        "permalink": permalink,
        "fallbackUsed": fallback_used,
    }


def check_slack_setup(
    config: dict[str, Any],
    *,
    repo_root=None,
) -> dict[str, Any]:
    """Validate token + channel without posting (local and cloud smoke test)."""
    env_files = bootstrap_slack_env(config, repo_root=repo_root)
    token = resolve_bot_token(config)
    auth = _api_call(token, "auth.test", {})
    channel_target = resolve_channel_id(token, config)
    slack_cfg = _slack_config(config)
    env_name = slack_cfg.get("botTokenEnv") or "SLACK_BOT_TOKEN"
    channel_id_env = slack_cfg.get("channelIdEnv") or "SLACK_CHANNEL_ID"
    env_channel = (os.environ.get(channel_id_env) or "").strip()
    resolved_by_id = (
        (channel_target.startswith("C") or channel_target.startswith("G"))
        and not channel_target.startswith("#")
    )
    channel_verified = False
    if resolved_by_id:
        try:
            info = _request_slack(
                token,
                "conversations.info",
                {"channel": channel_target},
            )
            channel_verified = bool((info.get("channel") or {}).get("id"))
        except SlackError:
            channel_verified = False
    status: dict[str, Any] = {
        "ok": True,
        "tokenEnv": env_name,
        "tokenPresent": True,
        "team": auth.get("team"),
        "botUser": auth.get("user"),
        "channel": _normalize_channel_name(slack_cfg.get("channel") or channel_target),
        "channelId": channel_target,
        "channelResolvedById": resolved_by_id,
        "envFilesLoaded": env_files,
        "channelIdFromConfig": bool(slack_cfg.get("channelId")),
        "channelIdFromEnv": bool(env_channel),
        "channelVerified": channel_verified,
    }
    if env_channel and _is_placeholder_channel_id(env_channel):
        status["ok"] = False
        status["error"] = (
            f"SLACK_CHANNEL_ID is the example placeholder ({env_channel}). "
            "Set the real ID from Slack → #gautam-personal-agent → About."
        )
    elif resolved_by_id and not channel_verified:
        status["warning"] = (
            f"Channel ID {channel_target} was not found via conversations.info. "
            "It may be wrong — confirm in Slack → channel About panel."
        )
    elif not resolved_by_id:
        status["warning"] = (
            f"Using channel name {channel_target} (conversations.list unavailable or "
            "channel not found). Set SLACK_CHANNEL_ID for private channels and to "
            "avoid workspace-wide channel scans."
        )
    return status
