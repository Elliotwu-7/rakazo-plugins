#!/usr/bin/env python3
"""Authenticated Streamable HTTP MCP adapter for NetEase 163 Mail."""

from __future__ import annotations

import email
import hmac
import html
import imaplib
import json
import os
import re
import smtplib
import ssl
import sys
from datetime import datetime
from email.header import decode_header
from email.message import EmailMessage, Message
from email.policy import default
from email.utils import parseaddr
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

SERVER_NAME = "netease-mail"
SERVER_VERSION = "1.0.0"
SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18"}
MCP_PATH = "/mcp"
HEALTH_PATH = "/health"
MAX_BODY_BYTES = 1024 * 1024
MAX_MESSAGE_BYTES = 5 * 1024 * 1024
MAX_PREVIEW_CHARS = 20_000
MAX_RECIPIENTS = 50


class MailError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"netease-mail-mcp: {message}", file=sys.stderr, flush=True)


def read_setting(env_name: str, file_env_name: str, default: str = "") -> str:
    file_name = os.environ.get(file_env_name, "").strip()
    if file_name:
        return Path(file_name).read_text(encoding="utf-8").strip()
    return os.environ.get(env_name, default).strip()


def required_token() -> str:
    token = read_setting("MCP_HTTP_TOKEN", "MCP_HTTP_TOKEN_FILE")
    if len(token) < 32:
        raise RuntimeError("MCP_HTTP_TOKEN or MCP_HTTP_TOKEN_FILE is not configured")
    return token


HTTP_TOKEN = required_token()
MAIL_USERNAME = read_setting("MAIL_USERNAME", "MAIL_USERNAME_FILE")
MAIL_AUTH_CODE = read_setting("MAIL_AUTH_CODE", "MAIL_AUTH_CODE_FILE")
MAIL_FROM = read_setting("MAIL_FROM", "MAIL_FROM_FILE") or MAIL_USERNAME
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.163.com").strip()
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.163.com").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))

TOOLS = [
    {
        "name": "get_mail_status",
        "description": "Check whether NetEase IMAP and SMTP credentials are configured and can authenticate. Secrets are never returned.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_folders",
        "description": "List IMAP folders available to the configured NetEase Mail account.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "search_messages",
        "description": "Search a bounded set of messages in one folder and return UID-based metadata without marking messages as read.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "default": "INBOX", "maxLength": 256},
                "text": {"type": "string", "maxLength": 256, "description": "Full-text search term"},
                "from": {"type": "string", "maxLength": 256, "description": "Sender substring"},
                "subject": {"type": "string", "maxLength": 256, "description": "Subject substring"},
                "since": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "before": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "unseen_only": {"type": "boolean", "default": False},
                "seen_only": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "read_message",
        "description": "Read one message by UID, returning bounded metadata and text preview. Marking as read requires mark_seen=true.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "default": "INBOX", "maxLength": 256},
                "uid": {"type": "string", "pattern": "^[1-9][0-9]{0,19}$"},
                "mark_seen": {"type": "boolean", "default": False},
            },
            "required": ["uid"],
            "additionalProperties": False,
        },
    },
    {
        "name": "send_email",
        "description": "Send a plain-text email after an explicit confirmation. Requires confirm=true and never includes Bcc in the message headers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 320},
                    "minItems": 1,
                    "maxItems": MAX_RECIPIENTS,
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 320},
                    "maxItems": MAX_RECIPIENTS,
                    "default": [],
                },
                "bcc": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 320},
                    "maxItems": MAX_RECIPIENTS,
                    "default": [],
                },
                "subject": {"type": "string", "maxLength": 998},
                "body": {"type": "string", "maxLength": 100_000},
                "confirm": {"type": "boolean"},
            },
            "required": ["to", "subject", "body", "confirm"],
            "additionalProperties": False,
        },
    },
]


def tool_result(payload: Any, is_error: bool = False) -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ],
        "isError": is_error,
    }


def _require_mail_config() -> Tuple[str, str, str]:
    if not MAIL_USERNAME or not MAIL_AUTH_CODE:
        raise MailError(
            "NetEase Mail credentials are not configured. Set MAIL_USERNAME and MAIL_AUTH_CODE in the adapter secret store."
        )
    return MAIL_USERNAME, MAIL_AUTH_CODE, MAIL_FROM


def _imap_connect() -> imaplib.IMAP4_SSL:
    username, auth_code, _ = _require_mail_config()
    connection = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=20)
    try:
        connection.login(username, auth_code)
        # 163 Mail may require the IMAP ID extension before accepting commands.
        try:
            connection._simple_command(
                "ID", '("name" "Rakazo Mail" "version" "1.0" "vendor" "Elliot Wu")'
            )
            connection._untagged_response("OK", [None], "ID")
        except (imaplib.IMAP4.error, OSError):
            pass
        return connection
    except Exception:
        try:
            connection.logout()
        except Exception:
            pass
        raise


def _smtp_connect() -> smtplib.SMTP_SSL:
    username, auth_code, _ = _require_mail_config()
    context = ssl.create_default_context()
    connection = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20, context=context)
    try:
        connection.login(username, auth_code)
        return connection
    except Exception:
        try:
            connection.quit()
        except Exception:
            pass
        raise


def _imap_utf7_encode(value: str) -> str:
    result: List[str] = []
    pending: List[str] = []

    def flush() -> None:
        if not pending:
            return
        import base64

        raw = "".join(pending).encode("utf-16-be")
        encoded = base64.b64encode(raw).decode("ascii").rstrip("=").replace("/", ",")
        result.append("&" + encoded + "-")
        pending.clear()

    for char in value:
        if 0x20 <= ord(char) <= 0x7E:
            flush()
            result.append("&-" if char == "&" else char)
        else:
            pending.append(char)
    flush()
    return "".join(result)


def _imap_utf7_decode(value: str) -> str:
    import base64

    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if not token:
            return "&"
        padded = token.replace(",", "/") + "=" * ((4 - len(token) % 4) % 4)
        try:
            return base64.b64decode(padded).decode("utf-16-be")
        except Exception:
            return "&" + token + "-"

    return re.sub(r"&([^-]*)-", replace, value)


def _quote_mailbox(folder: str) -> str:
    if not isinstance(folder, str) or not folder.strip() or len(folder) > 256:
        raise MailError("folder must be a non-empty string of at most 256 characters")
    if any(ord(char) < 32 for char in folder):
        raise MailError("folder contains control characters")
    encoded = _imap_utf7_encode(folder.strip())
    return '"' + encoded.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _quote_search(value: str, label: str) -> str:
    if len(value) > 256 or any(ord(char) < 32 for char in value):
        raise MailError(f"{label} must be at most 256 characters without control characters")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _imap_date(value: str, label: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise MailError(f"{label} must be a YYYY-MM-DD date") from exc
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{parsed.day:02d}-{months[parsed.month - 1]}-{parsed.year:04d}"


def _select(connection: imaplib.IMAP4_SSL, folder: str, readonly: bool = True) -> Dict[str, Any]:
    typ, data = connection.select(_quote_mailbox(folder), readonly=readonly)
    if typ != "OK":
        raise MailError(f"Unable to select folder {folder!r}")
    exists = 0
    try:
        exists = int(data[0]) if data and data[0] is not None else 0
    except (TypeError, ValueError):
        pass
    return {"folder": folder, "messages": exists, "readonly": readonly}


def _decode_header_value(value: Optional[str]) -> str:
    if not value:
        return ""
    chunks: List[str] = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            try:
                chunks.append(chunk.decode(charset or "utf-8", errors="replace"))
            except LookupError:
                chunks.append(chunk.decode("utf-8", errors="replace"))
        else:
            chunks.append(chunk)
    return "".join(chunks)


def _parse_fetch_metadata(data: List[Any]) -> Dict[str, Any]:
    flags: List[str] = []
    internal_date = ""
    size = 0
    headers: Optional[Message] = None
    for item in data:
        if isinstance(item, tuple):
            raw = item[1]
            if isinstance(raw, bytes):
                headers = email.message_from_bytes(raw, policy=default)
        elif isinstance(item, bytes):
            text = item.decode("utf-8", errors="replace")
            flag_match = re.search(r"FLAGS \(([^)]*)\)", text, re.IGNORECASE)
            if flag_match:
                flags = flag_match.group(1).split()
            date_match = re.search(r'INTERNALDATE "([^"]+)"', text, re.IGNORECASE)
            if date_match:
                internal_date = date_match.group(1)
            size_match = re.search(r"RFC822\.SIZE (\d+)", text, re.IGNORECASE)
            if size_match:
                size = int(size_match.group(1))
    if headers is None:
        headers = email.message_from_bytes(b"", policy=default)
    return {
        "from": _decode_header_value(headers.get("From")),
        "to": _decode_header_value(headers.get("To")),
        "cc": _decode_header_value(headers.get("Cc")),
        "date": _decode_header_value(headers.get("Date")),
        "subject": _decode_header_value(headers.get("Subject")),
        "message_id": headers.get("Message-ID", ""),
        "internal_date": internal_date,
        "size": size,
        "flags": flags,
    }


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.skip_depth = 0
        self._block_tags = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag in {"script", "style"}:
            self.skip_depth += 1
        if tag in self._block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in self._block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def _html_to_text(value: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(value)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _extract_message(message: Message) -> Tuple[str, List[Dict[str, Any]]]:
    text_parts: List[str] = []
    attachments: List[Dict[str, Any]] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if filename or disposition == "attachment":
            payload = part.get_payload(decode=True) or b""
            attachments.append(
                {
                    "filename": _decode_header_value(filename),
                    "content_type": content_type,
                    "size": len(payload),
                }
            )
            continue
        if content_type == "text/plain":
            try:
                text_parts.append(part.get_content())
            except Exception:
                payload = part.get_payload(decode=True) or b""
                text_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
        elif content_type == "text/html" and not text_parts:
            try:
                text_parts.append(_html_to_text(part.get_content()))
            except Exception:
                payload = part.get_payload(decode=True) or b""
                text_parts.append(_html_to_text(payload.decode(part.get_content_charset() or "utf-8", errors="replace")))
    preview = "\n\n".join(part.strip() for part in text_parts if part.strip())
    if len(preview) > MAX_PREVIEW_CHARS:
        preview = preview[:MAX_PREVIEW_CHARS] + "\n[truncated]"
    return preview, attachments


def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "get_mail_status":
        result: Dict[str, Any] = {
            "configured": bool(MAIL_USERNAME and MAIL_AUTH_CODE),
            "username_configured": bool(MAIL_USERNAME),
            "authorization_configured": bool(MAIL_AUTH_CODE),
            "imap": {"host": IMAP_HOST, "port": IMAP_PORT, "authenticated": False},
            "smtp": {"host": SMTP_HOST, "port": SMTP_PORT, "authenticated": False},
        }
        if not result["configured"]:
            result["message"] = "Credentials are missing. NetEase requires an official client authorization code."
            return tool_result(result)
        try:
            connection = _imap_connect()
            try:
                result["imap"]["authenticated"] = True
            finally:
                try:
                    connection.logout()
                except Exception:
                    pass
            result["imap_ok"] = True
        except Exception as exc:
            result["imap_error"] = str(exc)[:500]
        try:
            connection = _smtp_connect()
            try:
                result["smtp"]["authenticated"] = True
            finally:
                try:
                    connection.quit()
                except Exception:
                    pass
            result["smtp_ok"] = True
        except Exception as exc:
            result["smtp_error"] = str(exc)[:500]
        result["ok"] = bool(result.get("imap_ok") and result.get("smtp_ok"))
        if not result["ok"]:
            result["message"] = "Authentication failed. Verify that MAIL_AUTH_CODE is the NetEase client authorization code, not the web login password."
        return tool_result(result)

    if name == "list_folders":
        connection = _imap_connect()
        try:
            typ, data = connection.list()
            if typ != "OK":
                raise MailError("Unable to list mail folders")
            folders: List[Dict[str, Any]] = []
            for raw in data or []:
                if not isinstance(raw, bytes):
                    continue
                line = raw.decode("utf-8", errors="replace")
                match = re.search(r'^\((.*?)\)\s+"?(.)"?\s+(.+)$', line)
                if not match:
                    continue
                flags = match.group(1).split()
                delimiter = match.group(2)
                encoded_name = match.group(3).strip()
                if encoded_name.startswith('"') and encoded_name.endswith('"'):
                    encoded_name = encoded_name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                folders.append(
                    {
                        "name": _imap_utf7_decode(encoded_name),
                        "flags": flags,
                        "delimiter": delimiter,
                    }
                )
            return tool_result({"folders": folders, "count": len(folders)})
        finally:
            try:
                connection.logout()
            except Exception:
                pass

    if name == "search_messages":
        folder = str(arguments.get("folder") or "INBOX")
        limit = arguments.get("limit", 20)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise MailError("limit must be an integer from 1 to 50")
        criteria: List[str] = []
        if arguments.get("unseen_only") is True:
            criteria.append("UNSEEN")
        if arguments.get("seen_only") is True:
            criteria.append("SEEN")
        for key, command, label in (
            ("text", "TEXT", "text"),
            ("from", "FROM", "from"),
            ("subject", "SUBJECT", "subject"),
        ):
            value = arguments.get(key)
            if value:
                criteria.extend([command, _quote_search(str(value), label)])
        for key, command in (("since", "SINCE"), ("before", "BEFORE")):
            value = arguments.get(key)
            if value:
                criteria.extend([command, _imap_date(str(value), key)])
        if not criteria:
            criteria.append("ALL")
        connection = _imap_connect()
        try:
            selected = _select(connection, folder, readonly=True)
            typ, data = connection.uid("search", None, *criteria)
            if typ != "OK":
                raise MailError("IMAP search failed")
            uids: List[str] = []
            for raw in data or []:
                if isinstance(raw, bytes):
                    uids.extend(part.decode("ascii", errors="ignore") for part in raw.split())
            uids = [uid for uid in uids if uid.isdigit()]
            selected_uids = list(reversed(uids))[:limit]
            messages: List[Dict[str, Any]] = []
            for uid in selected_uids:
                typ, fetched = connection.uid(
                    "fetch",
                    uid,
                    "(FLAGS INTERNALDATE RFC822.SIZE BODY.PEEK[HEADER.FIELDS (FROM TO CC DATE SUBJECT MESSAGE-ID)])",
                )
                if typ != "OK":
                    continue
                metadata = _parse_fetch_metadata(fetched or [])
                metadata["uid"] = uid
                messages.append(metadata)
            return tool_result({"folder": selected["folder"], "matched": len(uids), "returned": len(messages), "messages": messages})
        finally:
            try:
                connection.logout()
            except Exception:
                pass

    if name == "read_message":
        folder = str(arguments.get("folder") or "INBOX")
        uid = str(arguments.get("uid") or "")
        if not re.fullmatch(r"[1-9][0-9]{0,19}", uid):
            raise MailError("uid must be a positive decimal UID")
        mark_seen = arguments.get("mark_seen") is True
        connection = _imap_connect()
        try:
            selected = _select(connection, folder, readonly=not mark_seen)
            typ, size_data = connection.uid("fetch", uid, "(RFC822.SIZE)")
            if typ != "OK":
                raise MailError("Unable to fetch message size")
            size = 0
            for item in size_data or []:
                if isinstance(item, bytes):
                    match = re.search(rb"RFC822\.SIZE (\d+)", item)
                    if match:
                        size = int(match.group(1))
                        break
            if size > MAX_MESSAGE_BYTES:
                raise MailError(f"Message is {size} bytes, above the {MAX_MESSAGE_BYTES}-byte safety limit")
            spec = "BODY[]" if mark_seen else "BODY.PEEK[]"
            typ, data = connection.uid("fetch", uid, f"({spec})")
            if typ != "OK":
                raise MailError("Unable to read message")
            raw_message: Optional[bytes] = None
            for item in data or []:
                if isinstance(item, tuple) and isinstance(item[1], bytes):
                    raw_message = item[1]
                    break
            if raw_message is None:
                raise MailError("Message UID was not found in this folder")
            message = email.message_from_bytes(raw_message, policy=default)
            preview, attachments = _extract_message(message)
            if mark_seen:
                connection.uid("store", uid, "+FLAGS", "(\\Seen)")
            return tool_result(
                {
                    "folder": selected["folder"],
                    "uid": uid,
                    "from": _decode_header_value(message.get("From")),
                    "to": _decode_header_value(message.get("To")),
                    "cc": _decode_header_value(message.get("Cc")),
                    "date": _decode_header_value(message.get("Date")),
                    "subject": _decode_header_value(message.get("Subject")),
                    "message_id": message.get("Message-ID", ""),
                    "mark_seen": mark_seen,
                    "text": preview,
                    "attachments": attachments,
                }
            )
        finally:
            try:
                connection.logout()
            except Exception:
                pass

    if name == "send_email":
        if arguments.get("confirm") is not True:
            raise MailError("send_email requires confirm=true after explicit user confirmation")
        _, _, from_address = _require_mail_config()

        def recipients(key: str) -> List[str]:
            value = arguments.get(key, [])
            if value is None:
                return []
            if not isinstance(value, list) or len(value) > MAX_RECIPIENTS:
                raise MailError(f"{key} must be an array of at most {MAX_RECIPIENTS} addresses")
            output: List[str] = []
            for item in value:
                if not isinstance(item, str):
                    raise MailError(f"{key} contains a non-string address")
                address = parseaddr(item)[1].strip()
                if not address or "@" not in address or any(ord(char) < 32 for char in address):
                    raise MailError(f"Invalid email address in {key}")
                output.append(address)
            return output

        to_addresses = recipients("to")
        cc_addresses = recipients("cc")
        bcc_addresses = recipients("bcc")
        if not to_addresses:
            raise MailError("to must contain at least one recipient")
        subject = arguments.get("subject")
        body = arguments.get("body")
        if not isinstance(subject, str) or len(subject) > 998:
            raise MailError("subject must be a string of at most 998 characters")
        if not isinstance(body, str) or len(body) > 100_000:
            raise MailError("body must be a string of at most 100000 characters")
        message = EmailMessage()
        message["From"] = from_address
        message["To"] = ", ".join(to_addresses)
        if cc_addresses:
            message["Cc"] = ", ".join(cc_addresses)
        if bcc_addresses:
            message["Bcc"] = ", ".join(bcc_addresses)
        message["Subject"] = subject
        message.set_content(body)
        connection = _smtp_connect()
        try:
            refused = connection.send_message(
                message,
                from_addr=from_address,
                to_addrs=to_addresses + cc_addresses + bcc_addresses,
            )
        finally:
            try:
                connection.quit()
            except Exception:
                pass
        return tool_result(
            {
                "sent": True,
                "from": from_address,
                "to": to_addresses,
                "cc": cc_addresses,
                "bcc_count": len(bcc_addresses),
                "subject": subject,
                "refused": refused,
                "message_id": message.get("Message-ID", ""),
            }
        )

    raise MailError(f"Unknown tool: {name}")


def handle_request(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") if isinstance(request.get("params"), dict) else {}
    if request_id is None and isinstance(method, str) and method.startswith("notifications/"):
        return None
    if method == "initialize":
        requested = params.get("protocolVersion")
        protocol = requested if requested in SUPPORTED_PROTOCOLS else "2025-06-18"
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": protocol,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Use get_mail_status before troubleshooting. Search and read by UID without marking messages read by default. "
                    "send_email requires confirm=true and explicit user confirmation of recipients, subject and body."
                ),
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if not isinstance(name, str):
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "Tool name is required"}}
        try:
            return {"jsonrpc": "2.0", "id": request_id, "result": call_tool(name, arguments)}
        except Exception as exc:
            log(f"tool {name} failed: {exc}")
            return {"jsonrpc": "2.0", "id": request_id, "result": tool_result(str(exc), is_error=True)}
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def encode_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "NetEaseMailMCPHTTP/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        log(f"http {self.client_address[0]} {format % args}")

    def _authorized(self) -> bool:
        value = self.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            return False
        return hmac.compare_digest(value[7:].strip(), HTTP_TOKEN)

    def _send(
        self,
        status: int,
        body: bytes = b"",
        content_type: str = "application/json; charset=utf-8",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.send_response(status)
        if body:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if length <= 0:
            raise ValueError("Request body is required")
        if length > MAX_BODY_BYTES:
            raise ValueError("Request body is too large")
        return self.rfile.read(length)

    @staticmethod
    def _parse_json_body(raw: bytes) -> Any:
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON body") from exc

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == HEALTH_PATH:
            self._send(
                200,
                encode_json(
                    {
                        "ok": True,
                        "service": "netease-mail-mcp-http",
                        "credentials_configured": bool(MAIL_USERNAME and MAIL_AUTH_CODE),
                    }
                ),
            )
            return
        if path != MCP_PATH:
            self._send(404, encode_json({"ok": False, "error": "Not found"}))
            return
        if not self._authorized():
            self._send(401, encode_json({"ok": False, "error": "Invalid MCP HTTP credentials"}), extra_headers={"WWW-Authenticate": "Bearer"})
            return
        self._send(200, b": netease-mail-mcp ready\n\n", "text/event-stream; charset=utf-8", {"Connection": "close"})

    def do_DELETE(self) -> None:
        if urlparse(self.path).path != MCP_PATH:
            self._send(404, encode_json({"ok": False, "error": "Not found"}))
            return
        if not self._authorized():
            self._send(401, encode_json({"ok": False, "error": "Invalid MCP HTTP credentials"}))
            return
        self._send(200, encode_json({"ok": True}))

    def do_OPTIONS(self) -> None:
        self._send(
            204,
            extra_headers={
                "Allow": "GET, POST, DELETE, OPTIONS",
                "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Mcp-Session-Id, MCP-Protocol-Version, Last-Event-ID",
            },
        )

    def do_POST(self) -> None:
        if urlparse(self.path).path != MCP_PATH:
            self._send(404, encode_json({"ok": False, "error": "Not found"}))
            return
        # Consume the bounded request body before an auth rejection. Otherwise
        # the unread bytes corrupt the next request on an HTTP/1.1 keep-alive
        # connection, which makes clients see an HTTP 501 from BaseHTTPRequestHandler.
        try:
            raw = self._read_body()
        except ValueError as exc:
            self._send(400, encode_json({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}))
            return
        if not self._authorized():
            self._send(401, encode_json({"ok": False, "error": "Invalid MCP HTTP credentials"}), extra_headers={"WWW-Authenticate": "Bearer"})
            return
        try:
            payload = self._parse_json_body(raw)
        except ValueError as exc:
            self._send(400, encode_json({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}))
            return
        if isinstance(payload, dict):
            requests = [payload]
        elif isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
            requests = payload
        else:
            self._send(400, encode_json({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid JSON-RPC request"}}))
            return
        responses: List[Dict[str, Any]] = []
        for request in requests:
            try:
                response = handle_request(request)
            except Exception as exc:
                log(f"request failed: {exc}")
                response = {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32603, "message": str(exc)}}
            if response is not None:
                responses.append(response)
        if not responses:
            self._send(202)
            return
        body: Any = responses[0] if isinstance(payload, dict) else responses
        self._send(200, encode_json(body))


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    host = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_HTTP_PORT", "3197"))
    server = Server((host, port), Handler)
    log(f"HTTP bridge listening on http://{host}:{port}{MCP_PATH}")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
