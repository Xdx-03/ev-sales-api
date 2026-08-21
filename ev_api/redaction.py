from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

# Keys are normalised before comparison, so these also cover common spellings such
# as ``access_token``, ``client-secret`` and ``x-api-key``.
_SENSITIVE_KEY_SUFFIXES = (
    "password",
    "passwd",
    "pwd",
    "authorization",
    "token",
    "jwt",
    "cookie",
    "secret",
    "apikey",
    "credential",
    "credentials",
    "sessionid",
    "sessionkey",
    "privatekey",
    "csrf",
    "xsrf",
    "auth",
    "username",
    "phone",
    "mobile",
    "email",
    "address",
    "idcard",
    "identity",
    "realname",
    "customername",
    "openid",
    "unionid",
    "vin",
    "orderno",
    "ticketno",
    "paymentno",
    "contractno",
)

_PLAINTEXT_KEY = r"(?:password|passwd|pwd|authorization|proxy[-_ ]?authorization|access[-_ ]?token|refresh[-_ ]?token|id[-_ ]?token|auth[-_ ]?token|token|jwt|cookie|set[-_ ]?cookie|secret|client[-_ ]?secret|api[-_ ]?key|x[-_ ]?api[-_ ]?key|credential|session[-_ ]?id|session[-_ ]?key|private[-_ ]?key|csrf|xsrf|auth|username|phone|mobile|email|address|id[-_ ]?card|identity|real[-_ ]?name|customer[-_ ]?name|open[-_ ]?id|union[-_ ]?id|vin|order[-_ ]?no|ticket[-_ ]?no|payment[-_ ]?no|contract[-_ ]?no|id|order[-_ ]?id|car[-_ ]?id|customer[-_ ]?id|cust[-_ ]?id|model[-_ ]?id|sku[-_ ]?id|appointment[-_ ]?id|test[-_ ]?drive[-_ ]?id|delivery[-_ ]?id|ticket[-_ ]?id|payment[-_ ]?id|warehouse[-_ ]?id|user[-_ ]?id|executor[-_ ]?id|lock[-_ ]?order[-_ ]?id)s?"

# Header values may contain spaces and cookie separators, so mask the whole line.
_SENSITIVE_HEADER_RE = re.compile(
    r"^(?P<prefix>[ \t]*(?:authorization|proxy-authorization|cookie|set-cookie|x-api-key|api-key)[ \t]*:[ \t]*).*$",
    re.IGNORECASE | re.MULTILINE,
)

# The same fields can occur in query strings or log messages rather than at the
# start of a header line. Quoted values stop at their matching quote; unquoted
# values stop at a query-string separator, comma, or newline.
_BULK_PAIR_RE = re.compile(
    r"(?P<prefix>(?P<key_quote>[\"']?)(?P<key>authorization|proxy[-_ ]?authorization|cookie|set[-_ ]?cookie)(?P=key_quote)[ \t]*[:=][ \t]*)"
    r"(?P<value>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^&,\r\n]+)",
    re.IGNORECASE,
)

_SENSITIVE_PAIR_RE = re.compile(
    rf"(?P<prefix>(?P<key_quote>[\"']?)(?P<key>{_PLAINTEXT_KEY})(?P=key_quote)[ \t]*[:=][ \t]*)"
    r"(?P<value>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^&,;}\]\r\n]+?)"
    r"(?=[ \t]+[A-Za-z_][A-Za-z0-9_.-]*[ \t]*[:=]|[&,;}\]\r\n]|$)",
    re.IGNORECASE,
)

_BEARER_RE = re.compile(r"\b(Bearer)[ \t]+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
)
_NUMERIC_PATH_ID_RE = re.compile(r"(?<=/)\d+(?=(?:/|[ ?#\"']|$))")

# Camel/snake/kebab identifiers are detected through the separated ``id`` word.
# These compact spellings cover APIs that return lower-case keys without separators.
_COMPACT_BUSINESS_ID_KEYS = {
    "appointmentid",
    "brandid",
    "carid",
    "customerid",
    "custid",
    "deliveryid",
    "executorid",
    "lockorderid",
    "modelid",
    "orderid",
    "paymentid",
    "skuid",
    "testdriveid",
    "ticketid",
    "userid",
    "warehouseid",
}


def is_sensitive_key(key: object) -> bool:
    """Return whether a mapping key conventionally contains a credential."""

    key_text = str(key)
    word_separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key_text)
    word_separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", word_separated)
    words = {word.lower() for word in re.findall(r"[A-Za-z0-9]+", word_separated)}
    words.update(word[:-1] for word in tuple(words) if word.endswith("s"))
    normalised = re.sub(r"[^a-z0-9]", "", key_text.lower())
    normalised_candidates = {normalised}
    if normalised.endswith("s"):
        normalised_candidates.add(normalised[:-1])
    if "id" in words or normalised == "id" or normalised in _COMPACT_BUSINESS_ID_KEYS:
        return True
    return any(
        suffix in words or any(candidate.endswith(suffix) for candidate in normalised_candidates)
        for suffix in _SENSITIVE_KEY_SUFFIXES
    )


def _mask_pair(match: re.Match[str]) -> str:
    value = match.group("value")
    if len(value) >= 2 and value[0] in {'"', "'"} and value[-1] == value[0]:
        masked_value = f"{value[0]}{REDACTED}{value[-1]}"
    else:
        masked_value = REDACTED
    return f"{match.group('prefix')}{masked_value}"


def redact_text(text: str) -> str:
    """Redact credentials from JSON text, headers, query strings, and logs."""

    if not text:
        return text

    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
        except (TypeError, ValueError):
            pass
        else:
            if isinstance(parsed, (dict, list)):
                return json.dumps(redact_sensitive(parsed), ensure_ascii=False, indent=2)

    redacted = _SENSITIVE_HEADER_RE.sub(lambda match: f"{match.group('prefix')}{REDACTED}", text)
    redacted = _BULK_PAIR_RE.sub(_mask_pair, redacted)
    redacted = _SENSITIVE_PAIR_RE.sub(_mask_pair, redacted)
    redacted = _BEARER_RE.sub(lambda match: f"{match.group(1)} {REDACTED}", redacted)
    redacted = _JWT_RE.sub(REDACTED, redacted)
    return _NUMERIC_PATH_ID_RE.sub(REDACTED, redacted)


def redact_sensitive(value: Any) -> Any:
    """Recursively return a report-safe copy of a JSON-like value."""

    if isinstance(value, Mapping):
        return {
            key: REDACTED if is_sensitive_key(key) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, set):
        return {redact_sensitive(item) for item in value}
    if isinstance(value, (bytes, bytearray)):
        return redact_text(bytes(value).decode("utf-8", errors="replace"))
    if isinstance(value, str):
        return redact_text(value)
    return value


# A short alias is convenient at attachment boundaries and for callers that do
# not need to distinguish structured values from text.
redact = redact_sensitive
