"""Safety controls: read-only mode, deny-list and confirmation of risky calls.

Every SDK call - from a direct-mode tool, from ``call_tool`` or from inside
``execute_code`` - goes through :meth:`SafetyPolicy.enforce`, so no path can
skip these checks.

Confirmation works in two ways:

1. **Elicitation** - when the client supports MCP elicitation, the server asks
   the user directly ("Delete instance X?") and continues only on approval.
2. **Confirmation token** - otherwise the call is refused with a message that
   tells the model to ask the user, plus a token. The token is an HMAC of the
   exact tool name and arguments, so it approves only that one call; a second
   call with the token then runs. Clients show that second call (marked
   ``destructiveHint``) in their own approval UI.

Tokens and the ``request_state`` of an input request are single-use, expire,
and are bound to the caller (the MCP session, where the protocol has a stable
one), so an approval can't be replayed or redeemed by another connection.

Scripts (``execute_code``) can't stop to ask the model or the user, so a call
inside a script that needs approval is refused without a token
(:class:`ApprovalUnavailable`): otherwise the script could read the token from
the error and approve its own call.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from gcore_mcp_server.catalog import Access, ToolEntry, matches_any
from gcore_mcp_server.config.settings import env_flag, split_list

logger = logging.getLogger(__name__)


class ConfirmMode(str, Enum):
    DESTRUCTIVE = "destructive"
    """Confirm deletes and other destructive calls (default)."""

    WRITES = "writes"
    """Confirm every call that changes something."""

    NONE = "none"
    """Never ask (for trusted automation)."""


TOKEN_TTL_SECS = 600.0
MAX_OPEN_TOKENS = 1000


class ApprovalUnavailable(ToolError):
    """A call needs approval where nobody can be asked (inside a script)."""

    def __init__(self, tool: str, summary: str):
        self.tool = tool
        self.summary = summary
        super().__init__(
            f"APPROVAL NEEDED: {summary}\n"
            "This call was NOT executed: a script can't get the user's approval."
        )


class ConfirmationRequired(ToolError):
    """Raised when a call needs the user's approval before it runs."""

    def __init__(self, tool: str, token: str, summary: str):
        self.tool = tool
        self.token = token
        self.summary = summary
        super().__init__(
            f"CONFIRMATION REQUIRED: {summary}\n"
            "This call was NOT executed. Show the user exactly what will happen and "
            "ask for approval. Only if they approve, repeat the identical call with "
            f'confirm_token="{token}" (valid once, for 10 minutes).'
        )


@dataclass
class SafetyPolicy:
    """What the server allows, configured from the environment."""

    read_only: bool = False
    confirm: ConfirmMode = ConfirmMode.DESTRUCTIVE
    deny: list[str] = field(default_factory=list[str])
    use_elicitation: bool = True
    _secret: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    # token or request_state -> (digest of the call it approves, expiry); each
    # works once.
    _issued: dict[str, tuple[str, float]] = field(
        default_factory=dict[str, tuple[str, float]]
    )

    # ------------------------------------------------------------------ policy

    def is_denied(self, name: str) -> bool:
        """Denied by GCORE_DENY_TOOLS.

        Denying an operation also denies its ``*_and_poll`` variant (which runs
        the same request and then waits), so ``cloud.volumes.delete`` blocks
        ``cloud.volumes.delete_and_poll`` too.
        """
        return matches_any(name, self.deny) or matches_any(
            name.removesuffix("_and_poll"), self.deny
        )

    def blocked_reason(self, entry: ToolEntry) -> str | None:
        """Why ``entry`` may not run at all, or ``None`` if it may."""
        if self.is_denied(entry.name):
            return (
                f"{entry.name} is blocked by the server's deny-list (GCORE_DENY_TOOLS)."
            )
        if self.read_only and entry.access is not Access.READ:
            return (
                f"{entry.name} changes resources ({entry.access.value}), but the server "
                "runs in read-only mode (GCORE_READ_ONLY=true). Only read operations "
                "are allowed."
            )
        return None

    def needs_confirmation(self, entry: ToolEntry) -> bool:
        if self.confirm is ConfirmMode.NONE or entry.access is Access.READ:
            return False
        if self.confirm is ConfirmMode.WRITES:
            return True
        return entry.access is Access.DESTRUCTIVE

    # ------------------------------------------------------------------ tokens

    def _digest(
        self, name: str, arguments: dict[str, Any], purpose: str, caller: str
    ) -> str:
        payload = json.dumps(
            {"purpose": purpose, "caller": caller, "tool": name, "args": arguments},
            sort_keys=True,
            default=str,
        ).encode()
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _issue(
        self, purpose: str, name: str, arguments: dict[str, Any], caller: str, size: int
    ) -> str:
        now = time.monotonic()
        for old, (_, expires) in list(self._issued.items()):
            if expires < now:
                del self._issued[old]
        while len(self._issued) >= MAX_OPEN_TOKENS:  # oldest first
            del self._issued[next(iter(self._issued))]
        key = secrets.token_hex(size)
        self._issued[key] = (
            self._digest(name, arguments, purpose, caller),
            now + TOKEN_TTL_SECS,
        )
        return key

    def _consume(
        self,
        purpose: str,
        name: str,
        arguments: dict[str, Any],
        key: str | None,
        caller: str,
    ) -> bool:
        if not key:
            return False
        issued = self._issued.get(str(key))
        if issued is None:
            return False
        digest, expires = issued
        if expires < time.monotonic() or not hmac.compare_digest(
            digest, self._digest(name, arguments, purpose, caller)
        ):
            return False  # other call or caller: leave it for the one it was issued for
        del self._issued[str(key)]
        return True

    def issue_token(
        self, name: str, arguments: dict[str, Any], caller: str = ""
    ) -> str:
        """A confirmation token for this exact call: single use, short-lived."""
        return self._issue("token", name, arguments, caller, 8)

    def consume_token(
        self, name: str, arguments: dict[str, Any], token: str | None, caller: str = ""
    ) -> bool:
        """True (once) when ``token`` was issued for exactly this call and caller."""
        return self._consume("token", name, arguments, token, caller)

    def issue_request_state(
        self, name: str, arguments: dict[str, Any], caller: str = ""
    ) -> str:
        """``request_state`` for an input request: one answer, for this call only.

        Kept apart from confirmation tokens, so a client that logs or shows it
        does not leak something ``confirm_token`` would accept.
        """
        return self._issue("request_state", name, arguments, caller, 16)

    def _guard_answer(
        self, ctx: Any, name: str, arguments: dict[str, Any], caller: str
    ) -> Answer | None:
        """The answer carried by a retried request, or ``None`` if none applies."""
        try:
            responses = ctx.input_responses
            state = ctx.request_state
        except Exception:
            return None
        if not responses or CONFIRM_KEY not in responses or not state:
            return None
        if not self._consume("request_state", name, arguments, str(state), caller):
            return None  # unknown, used, expired or for another call: ask again
        result = responses[CONFIRM_KEY]
        content: dict[str, Any] = dict(getattr(result, "content", None) or {})
        return _answer(getattr(result, "action", None), content.get("value"))

    # ------------------------------------------------------------------ enforce

    async def enforce(
        self,
        entry: ToolEntry,
        arguments: dict[str, Any],
        ctx: Any | None,
        confirm_token: str | None = None,
        interactive: bool = True,
        summary: str | None = None,
    ) -> None:
        """Raise unless ``entry`` may run with ``arguments`` now.

        Raises ``ToolError`` when blocked or declined, ``ConfirmationRequired``
        when the model must ask the user, and ``InputNeeded`` (only when
        ``interactive``) to make a 2026-07-28 client ask the user and retry.
        Without ``interactive`` (inside a script) there is nobody to hand a
        token to: tokens are not accepted and ``ApprovalUnavailable`` is raised
        instead, unless the client can be asked directly (elicitation).
        """
        reason = self.blocked_reason(entry)
        if reason:
            raise ToolError(reason)
        if not self.needs_confirmation(entry):
            return
        caller = _caller(ctx)
        if interactive and self.consume_token(
            entry.name, arguments, confirm_token, caller
        ):
            logger.info("Confirmed by token: %s", entry.name)
            return

        summary = summary or describe_call(entry, arguments)
        if self.use_elicitation and ctx is not None:
            if _is_modern(ctx):
                if interactive:
                    answer = self._guard_answer(ctx, entry.name, arguments, caller)
                    if answer == "approved":
                        logger.info("Confirmed by user (input request): %s", entry.name)
                        return
                    if answer is not None:
                        raise ToolError(_refusal(answer, summary))
                    if _modern_client_can_elicit(ctx):
                        state = self.issue_request_state(entry.name, arguments, caller)
                        raise InputNeeded(_confirmation_request(summary, state))
            elif _legacy_client_can_elicit(ctx):
                answer = await _elicit(ctx, summary)
                if answer == "approved":
                    logger.info("Confirmed by user (elicitation): %s", entry.name)
                    return
                if answer is not None:
                    raise ToolError(_refusal(answer, summary))
                # None: elicitation failed - fall back to the token flow.
        if not interactive:
            raise ApprovalUnavailable(entry.name, summary)
        raise ConfirmationRequired(
            entry.name, self.issue_token(entry.name, arguments, caller), summary
        )

    async def enforce_batch(
        self,
        entry: ToolEntry,
        items: list[dict[str, Any]],
        ctx: Any | None,
        confirm_token: str | None = None,
        labels: list[str | None] | None = None,
    ) -> None:
        """Like :meth:`enforce`, for ``entry`` run once per item: one approval
        (or one token) for exactly this list, shown item by item."""
        await self.enforce(
            entry,
            {"batch": items},
            ctx,
            confirm_token,
            summary=describe_batch(entry, items, labels),
        )


def _caller(ctx: Any | None) -> str:
    """Who an approval belongs to: the MCP session, where it is stable.

    On 2026-07-28 connections every request gets a new session ID, so those
    approvals are bound to the call only (HTTP has no client authentication
    to bind them to; see server.py).
    """
    if ctx is None or _is_modern(ctx):
        return ""
    try:
        return str(ctx.session_id)
    except Exception:
        return ""


Answer = Literal["approved", "declined", "unanswered"]


def _answer(action: Any, value: Any) -> Answer:
    """Map an elicitation result to what it means for the call.

    ``cancel`` means nobody answered: the user closed the prompt, or the
    client could not show it (headless runs such as ``claude -p`` cancel every
    prompt). Reporting that as the user's "no" would put words in their mouth.
    """
    if action == "accept":
        # Accept means yes; only an explicitly unticked box means no.
        return "declined" if value is False else "approved"
    if action == "decline":
        return "declined"
    return "unanswered"


def _refusal(answer: Answer, summary: str) -> str:
    if answer == "declined":
        return f"The user declined: {summary} Nothing was changed."
    return (
        f"Not approved: {summary} Nothing was changed. The approval prompt was "
        "closed without an answer, or the client could not show it (headless "
        "runs such as `claude -p` or CI agents cannot). Tell the user this. To "
        "approve through the conversation instead, the server can be started "
        "with GCORE_CONFIRM_VIA=model; for trusted automation, GCORE_CONFIRM=none."
    )


class InputNeeded(Exception):
    """Carries an ``InputRequiredResult`` the tool must return to the client."""

    def __init__(self, result: Any):
        super().__init__("input required")
        self.result = result


CONFIRM_KEY = "gcore_confirm"


def _confirmation_request(summary: str, state: str) -> Any:
    import mcp_types as mt

    return mt.InputRequiredResult(
        input_requests={
            CONFIRM_KEY: mt.ElicitRequest(
                params=mt.ElicitRequestFormParams(
                    message=summary,
                    # Optional and pre-ticked: Accept submits at once (a
                    # required box sent Enter on Accept back to the box).
                    requested_schema={  # pyright: ignore[reportArgumentType]
                        "type": "object",
                        "properties": {
                            "value": {
                                "type": "boolean",
                                "title": APPROVE_TITLE,
                                "default": True,
                            }
                        },
                    },
                )
            )
        },
        # Echoed back on retry; binds the answer to these exact arguments.
        request_state=state,
    )


def _is_modern(ctx: Any) -> bool:
    try:
        return bool(ctx._is_modern_protocol())  # pyright: ignore[reportPrivateUsage]
    except Exception:
        return False


def _modern_client_can_elicit(ctx: Any) -> bool:
    try:
        meta: dict[str, Any] = dict(ctx.request_context.meta or {})
    except Exception:
        return False
    caps: Any = meta.get("io.modelcontextprotocol/clientCapabilities") or {}
    return isinstance(caps, dict) and "elicitation" in caps


MAX_VALUE_CHARS = 500


def _is_identifier(name: str) -> bool:
    return name in ("name", "id") or name.endswith(("_id", "_name", "_ids"))


# Fields that name a resource for people (in the order tried), read from the
# target's own get operation so a prompt can say "45.82.30.198", not a UUID.
LABEL_FIELDS = (
    "name",
    "floating_ip_address",
    "cname",
    "hostname",
    "domain",
    "email",
    "title",
    "ip_address",
    "address",
)
# Shown once for the whole prompt when every item has the same value.
SCOPE_ARGS = ("project_id", "region_id")


def describe_call(
    entry: ToolEntry, arguments: dict[str, Any], label: str | None = None
) -> str:
    """Prompt text for one call (see :func:`describe_items`)."""
    return describe_items(entry, [arguments], [label])


def describe_batch(
    entry: ToolEntry,
    items: list[dict[str, Any]],
    labels: list[str | None] | None = None,
) -> str:
    """Prompt text for one operation run once per item."""
    return describe_items(entry, items, labels or [None] * len(items))


def describe_items(
    entry: ToolEntry, items: list[dict[str, Any]], labels: list[str | None]
) -> str:
    """What an approval prompt says, readable at a glance.

    Clients fold long prompts after a few lines, so the first lines carry the
    decision: what kind of change, and which targets by name. Then one line
    per item with its identifiers, never shortened, so the user can check
    exactly what is affected. Project and region are said once when every
    item shares them. Only very long other values (e.g. record contents) are
    shortened, each with the number of characters left out.
    """
    kind = "DESTRUCTIVE" if entry.access is Access.DESTRUCTIVE else "Change"
    lines = [f"{kind}: {entry.summary.rstrip('.')} ({entry.name})"]
    common = {
        k: items[0][k]
        for k in SCOPE_ARGS
        if k in items[0] and all(item.get(k) == items[0][k] for item in items)
    }
    where = ", ".join(f"{k.removesuffix('_id')} {v}" for k, v in common.items())
    count = f"{len(items)} items" if len(items) > 1 else "1 item"
    names = [label for label in labels if label]
    head = f"{count}" + (f" in {where}" if where else "")
    if names:
        shown = ", ".join(names[:12]) + (
            f", +{len(names) - 12} more" if len(names) > 12 else ""
        )
        head += f": {shown}"
    lines.append(head)
    for i, (item, label) in enumerate(zip(items, labels), 1):
        rest = {k: v for k, v in item.items() if k not in common}
        lines.append(f"  {i}. {(label + ' - ') if label else ''}{_shown(rest)}")
    return "\n".join(lines)


def _shown(arguments: dict[str, Any]) -> str:
    """Arguments as ``key value`` pairs, target identifiers first and never
    shortened; other values as JSON."""
    parts: list[str] = []
    for key in sorted(arguments, key=lambda k: (not _is_identifier(k), k)):
        value = arguments[key]
        text = (
            value if isinstance(value, (str, int)) else json.dumps(value, default=str)
        )
        text = str(text)
        if not _is_identifier(key) and len(text) > MAX_VALUE_CHARS:
            text = (
                f"{text[:MAX_VALUE_CHARS]}… ({len(text) - MAX_VALUE_CHARS} more chars)"
            )
        parts.append(f"{key} {text}")
    return ", ".join(parts) or "(no arguments)"


APPROVE_TITLE = "Yes, run it"


class _Approval(BaseModel):
    # The docstring is shown in the form: it speaks to the person approving.
    """Accept runs it; Decline (or unticking the box) refuses."""

    value: bool = Field(default=True, title=APPROVE_TITLE)


def _legacy_client_can_elicit(ctx: Any) -> bool:
    try:
        caps = ctx.session.client_params.capabilities
        return getattr(caps, "elicitation", None) is not None
    except Exception:
        return False


async def _elicit(ctx: Any, summary: str) -> Answer | None:
    """Ask the user; the answer, or ``None`` if the client can't be asked."""
    try:
        result = await ctx.elicit(summary, response_type=_Approval)
    except Exception as exc:
        logger.info("Elicitation unavailable (%s); using confirmation token", exc)
        return None
    data = getattr(result, "data", None)
    return _answer(getattr(result, "action", None), getattr(data, "value", data))


def policy_from_env(read_only_default: bool = False) -> SafetyPolicy:
    """Build the policy from GCORE_READ_ONLY, GCORE_CONFIRM, GCORE_DENY_TOOLS.

    ``read_only_default`` applies when GCORE_READ_ONLY is unset (the HTTP
    transport passes True).
    """
    raw_confirm = (os.getenv("GCORE_CONFIRM") or "destructive").strip().lower()
    try:
        confirm = ConfirmMode(raw_confirm)
    except ValueError:
        logger.warning(
            "Unknown GCORE_CONFIRM %r; using 'destructive' (valid: destructive, writes, none)",
            raw_confirm,
        )
        confirm = ConfirmMode.DESTRUCTIVE
    return SafetyPolicy(
        read_only=env_flag("GCORE_READ_ONLY", default=read_only_default),
        confirm=confirm,
        deny=split_list(os.getenv("GCORE_DENY_TOOLS")),
        use_elicitation=_confirm_via_client(),
    )


def _confirm_via_client() -> bool:
    """GCORE_CONFIRM_VIA: ``client`` (default) or ``model``.

    ``client`` asks the user in the client's own dialog when the client supports
    that (MCP "elicitation"), and falls back to the model otherwise. ``model``
    always uses the confirmation-token round trip through the model.
    GCORE_ELICITATION=true/false is the older spelling.
    """
    raw = (os.getenv("GCORE_CONFIRM_VIA") or "").strip().lower()
    if raw in ("client", "model"):
        return raw == "client"
    if raw:
        logger.warning(
            "Unknown GCORE_CONFIRM_VIA %r; using 'client' (valid: client, model)", raw
        )
    return env_flag("GCORE_ELICITATION", default=True)
