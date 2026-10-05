"""Verify auth extensions survive the actual MCP HTTP response serializer."""
import asyncio
import json
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from tests.test_procurement_http_app import app
from server_http import handle_list_tools


class OpenAIWireTest(unittest.TestCase):
    def assert_declarations(self, tools):
        self.assertTrue(tools)
        for tool in tools:
            self.assertTrue(tool['securitySchemes'], tool['name'])
            self.assertEqual(tool['securitySchemes'], tool['_meta']['securitySchemes'])
        protected = {tool['name']: tool for tool in tools}
        self.assertEqual(protected['get_my_profile']['securitySchemes'],
                         [{'type': 'oauth2', 'scopes': ['pro']}])
        self.assertFalse(protected['process_bid_room']['annotations']['readOnlyHint'])

    def test_handler_nested_json_serialization_keeps_extensions(self):
        result = asyncio.run(handle_list_tools(None, None))
        self.assert_declarations(json.loads(result.model_dump_json(by_alias=True))['tools'])

    def test_http_tools_list_keeps_extensions_without_authentication(self):
        with patch.dict(os.environ, {'WA_HOSTED': '1'}), TestClient(app) as client:
            response = client.post('/mcp', headers={'Accept': 'application/json'},
                                   json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()['result']
        self.assertFalse(result.get('nextCursor'))
        self.assert_declarations(result['tools'])


if __name__ == '__main__':
    unittest.main()
