#!/usr/bin/env python3
import os
import unittest

os.environ.setdefault("MCP_HTTP_TOKEN", "x" * 64)

import server  # noqa: E402


class AdapterTests(unittest.TestCase):
    def test_round_trip_modified_utf7(self):
        for value in ["INBOX", "已发送", "A&B", "项目/归档"]:
            self.assertEqual(server._imap_utf7_decode(server._imap_utf7_encode(value)), value)

    def test_initialize_and_tools(self):
        response = server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
        )
        self.assertEqual(response["result"]["serverInfo"]["name"], "netease-mail")
        tools = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(
            {tool["name"] for tool in tools["result"]["tools"]},
            {"get_mail_status", "list_folders", "search_messages", "read_message", "send_email"},
        )

    def test_send_requires_confirmation(self):
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "send_email",
                    "arguments": {"to": ["a@example.com"], "subject": "x", "body": "y", "confirm": False},
                },
            }
        )
        self.assertTrue(response["result"]["isError"])
        self.assertIn("confirm=true", response["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
