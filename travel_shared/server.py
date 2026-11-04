"""HTTP adapter for AgentArts tool registration. Identity comes from server tokens."""

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .contracts import nonempty
from .tools import DEFAULT_DB, INTERNAL_ACTIONS, PUBLIC_ACTIONS, TravelTools


def make_server(address, tools, tokens):
    if not isinstance(tokens, dict) or not tokens:
        raise ValueError("TRAVEL_TOOL_TOKENS must be a nonempty token-to-principal JSON object")
    principals = {}
    for token, principal in tokens.items():
        nonempty(token, "token")
        if isinstance(principal, str):
            principal = {"user_id": principal, "allow_memory_write": False}
        if not isinstance(principal, dict) or set(principal) != {"user_id", "allow_memory_write"}:
            raise ValueError("token principal requires user_id and allow_memory_write")
        user_id = principal["user_id"]
        nonempty(user_id, "user identity")
        if type(principal["allow_memory_write"]) is not bool:
            raise ValueError("allow_memory_write must be boolean")
        principals[token] = principal

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Avoid persisting request/identity or authorization details in demo logs.
            pass

        def respond(self, code, body):
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):
            self.connection.settimeout(10)
            if self.path != "/v1/tools":
                self.respond(404, {"status": "not_found"})
                return
            authorization = self.headers.get("Authorization", "")
            principal = next((value for token, value in principals.items()
                              if hmac.compare_digest(authorization.encode("utf-8"),
                                                     ("Bearer " + token).encode("utf-8"))), None)
            if principal is None:
                self.respond(401, {"status": "unauthorized"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 262144 or self.headers.get("Transfer-Encoding"):
                    raise ValueError("request must contain at most 256 KiB of JSON")
                request = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeError, OSError):
                self.respond(400, {"status": "invalid", "errors": ["invalid JSON request or size"]})
                return
            action = request.get("action") if isinstance(request, dict) else None
            if isinstance(action, str) and action not in PUBLIC_ACTIONS:
                code = 403 if action in INTERNAL_ACTIONS else 400
                self.respond(code, {"status": "forbidden" if code == 403 else "invalid",
                                    "errors": ["action is not available through this HTTP adapter"]})
                return
            if (isinstance(action, str) and action in {"update", "delete", "clear"}
                    and not principal["allow_memory_write"]):
                self.respond(403, {"status": "forbidden",
                                   "errors": ["memory changes require a trusted write credential"]})
                return
            result = tools.handle(request, user_id=principal["user_id"])
            self.respond({"ok": 200, "invalid": 400, "unavailable": 503}[result["status"]], result)

    return ThreadingHTTPServer(address, Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    try:
        tokens = json.loads(os.environ.get("TRAVEL_TOOL_TOKENS", "{}"))
        server = make_server((args.host, args.port), TravelTools(args.db), tokens)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print("Travel tools listening on http://%s:%s/v1/tools" % server.server_address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
