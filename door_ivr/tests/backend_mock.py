#!/usr/bin/env python3

"""
Mock http server of {fauna|portier}.initlab.org's door API.

Written without any dependencies as the intention is to be standalone.
"""

import http
import json
import http.server
import re
import socketserver

PORT = 3002


class FaunaHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/api/doors':
            self.send_response(http.HTTPStatus.OK)
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    [
                        {'id': 'example_door', 'name': 'Врата', 'supported_actions': ['open'], 'number': 1},
                        {'id': 'example_door_2', 'name': 'Врата 2', 'supported_actions': ['open', 'unlock', 'lock'], 'number': 2},
                        {'id': 'example_door_3', 'name': 'Врата 3', 'supported_actions': ['lock', 'unlock', 'open'], 'number': 3},
                    ],
                    indent=4
                ).encode('utf-8')
            )
        else:
            raise NotImplementedError(f"GET {self.path!r} is not implemented")

    def do_POST(self):
        post_data = self.rfile.read(int(self.headers['content-length']))
        print('POST data:', post_data, flush=True)
        door_action_re = re.compile(r"/api/doors/[^/]+/(open|lock|unlock)")
        if self.path == '/api/phone_access/phone_number_token':
            if post_data.endswith(b'880000000'):  # hack to have a not-found result
                self.send_response(http.HTTPStatus.NOT_FOUND)
                self.end_headers()
                self.wfile.write(b'{}')  # the response body is not inline with the backend
            else:
                self.send_response(http.HTTPStatus.OK)
                self.end_headers()
                self.wfile.write(
                    b'{"user":{"name":"admin"},"auth_token":{"token":"abc","expires_at":"2044-04-01T00:00:00.000Z"}}'
                )
        elif self.path == '/api/phone_access/verify_pin':
            self.send_response(http.HTTPStatus.OK)
            self.end_headers()
            self.wfile.write(b'{"pin": "%s"}' % (b'valid' if post_data == b'pin=123456' else b'invalid'))
        elif door_action_re.fullmatch(self.path):
            self.send_response(http.HTTPStatus.NO_CONTENT)
            self.end_headers()
        else:
            raise NotImplementedError(f"POST {self.path!r} is not implemented")


if __name__ == '__main__':
    server_address = ("127.0.0.1", PORT)
    with socketserver.TCPServer(server_address, FaunaHandler) as httpd:
        print(f"serving at http://{server_address[0]}:{server_address[1]}")
        httpd.serve_forever()
