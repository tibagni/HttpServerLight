import socket
import re
import traceback
import gzip

from threading import current_thread
from typing import Callable, Tuple, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

def log(text: str) -> None:
    thread_name = current_thread().name
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for line in text.splitlines():
        if line:
            print(f"[{thread_name}]{timestamp}: {line}")


def logv(text: str) -> None:
    # TODO: Implement verbose logging
    log(f"\033[90m{text}\033[0m")


def logerr(text: str) -> None:
    log(f"\033[91m{text}\033[0m")


class HttpRequest:
    def __init__(self, method: str, path: str, headers: dict, body: bytes):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.query_params = self._build_query_map(path)

    def _build_query_map(self, path: str) -> dict:
        if "?" in path:
            qs = path.split("?")[1]
            qs_parts = qs.split("&")
            return {param[0]: param[1] for param in [p.split("=") for p in qs_parts if "=" in p]}

        return {}

    def __repr__(self):
        return (
            f"<HttpRequest"
            f"  method={self.method}"
            f"  path={self.path}"
            f"  headers={self.headers}"
            f"  query_params={self.query_params}"
            f"  body={self.body}"
            f">"
        )


class HttpResponse:
    STATUS_200_OK = 200
    STATUS_400_BAD_REQUEST = 400
    STATUS_404_NOT_FOUND = 404
    STATUS_500_INTERNAL_SERVER_ERROR = 500

    _STATUS_MESSAGES = {
        STATUS_200_OK: "OK",
        STATUS_400_BAD_REQUEST: "Bad Request",
        STATUS_404_NOT_FOUND: "Not Found",
        STATUS_500_INTERNAL_SERVER_ERROR: "Internal Server Error"
    }

    _PREFERRED_ENCODINGS = ["gzip"]

    _CONTENT_ENCODERS = {
        "gzip": gzip.compress
    }

    @staticmethod
    def _get_preferred_encoding(accepted_encoding_header: str) -> Optional[str]:
        accepted_encodings = [e.strip() for e in accepted_encoding_header.split(",")]

        for enc in HttpResponse._PREFERRED_ENCODINGS:
            if enc in accepted_encodings:
                return enc

    def __init__(self, status_code: int, headers: dict = {}, body: bytes = b""):
        self.status_code = status_code
        self.body = body
        self.headers = headers

    def serialize(self) -> bytes:
        status_message = self._STATUS_MESSAGES.get(self.status_code)
        response_line = f"HTTP/1.1 {self.status_code} {status_message}\r\n"
        headers = "".join(f"{k}: {v}\r\n" for k, v in self.headers.items())
        return (response_line + headers + "\r\n").encode("utf-8") + self.body

    def _compress(self, content_encoding: str):
        if "Content-Encoding" in self.headers:
            logerr(f"Response already compressed. Ignoring...")
            return

        if content_encoding not in self._CONTENT_ENCODERS.keys():
            logv(f"Content-Encoding {content_encoding} not supported. Do not encode the response")
            return

        # Replace the body with the compressed one
        compressed_body = self._CONTENT_ENCODERS[content_encoding](self.body)
        self.headers["Content-Encoding"] = content_encoding
        self.headers["Content-Length"] = len(compressed_body)
        self.body = compressed_body


    def __repr__(self):
        return (
            f"<HttpResponse"
            f" status_code={self.status_code}"
            f" headers={self.headers}"
            f" body={self.body}"
            f">"
        )


class HttpResponseBuilder:
    def __init__(self, status_code: int):
        self._status_code = status_code
        self._headers = {}
        self._body = b""

    def set_header(self, name: str, value) -> 'HttpResponseBuilder':
        self._headers[name] = value
        return self

    def set_body(self, body: bytes, content_type: str = "text/plain") -> 'HttpResponseBuilder':
        self.set_header("Content-Type", content_type)
        self.set_header("Content-Length", len(body))
        self._body = body
        return self

    def build(self) -> HttpResponse:
        return HttpResponse(
            status_code=self._status_code,
            headers=self._headers,
            body=self._body,
        )


class HttpRouter:
    class Route:
        def __init__(self, path: str, handler: Callable[[HttpRequest], HttpResponse]):
            self._validate_path(path)
            self.path = path
            self.handler = handler

        def matches_with(self, path: str) -> bool:
            # First make sure to not include any query string in our matching
            path = path.split("?")[0]

            # Do not consider the trailing '/' as a difference
            if path.rstrip("/") == self.path.rstrip("/"):
                return True

            if self._matches_with_dynamic_path(path):
                return True

            return False

        # TODO fix case when the URL has spaces
        def get_dynamic_segments(self, path: str) -> Optional[dict]:
            dynamic_segments_dict = None
            pattern = re.sub(r"\{([\w\.-]*)\}", r"([\\w\\.-]+)", self.path)
            url_match = re.match(pattern, path)
            if url_match:
                segment_names_pattern = re.sub(r"\{(\w*)\}", r"({\\w*})", self.path)
                segment_names_match = re.match(segment_names_pattern, self.path)
                if segment_names_match:
                    segment_names = segment_names_match.groups()
                    segment_values = url_match.groups()

                    # Fix the segment names. Use 'seg0, seg1, ...' if no name is provided
                    segment_names = (
                        pn[1:-1] if pn[1:-1] else f"seg{i}"
                        for i, pn in enumerate(segment_names)
                    )

                    params = zip(segment_names, segment_values)
                    dynamic_segments_dict = {name: value for name, value in params}

            return dynamic_segments_dict

        def _matches_with_dynamic_path(self, path: str) -> bool:
            # Check if the path matches the route
            path_parts = path.split("/")
            route_parts = self.path.split("/")

            if len(path_parts) != len(route_parts):
                return False

            for path_part, route_part in zip(path_parts, route_parts):
                if route_part.startswith("{") and route_part.endswith("}"):
                    continue
                if path_part != route_part:
                    return False

            return True

        def _validate_path(self, path: str) -> None:
            # Make sure all '{' and '}' are balanced
            stack = []
            for char in path:
                if char == "{":
                    stack.append("{")
                elif char == "}":
                    if not stack or stack[-1] != "{":
                        raise ValueError(f"Invalid Path: {path}")
                    stack.pop()

            if stack:
                raise ValueError(f"Invalid Path: {path}")

    def __init__(self):
        self._routes: list[HttpRouter.Route] = []

    def add_route(self, path: str, handler: Callable[[HttpRequest], HttpResponse]):
        for route in self._routes:
            if route.matches_with(path):
                raise ValueError(f"Route {path} already exists")

        self._routes.append(HttpRouter.Route(path, handler))

    def get_handler(self, path: str) -> Callable[[HttpRequest], HttpResponse]:
        for route in self._routes:
            if route.matches_with(path):
                dynamic_segments = route.get_dynamic_segments(path)
                if dynamic_segments:
                    # Pass the dynamic segments to the handler as kwargs
                    def handler_with_dynamic_segments(request: HttpRequest) -> HttpResponse:
                        return route.handler(request, **dynamic_segments)

                    return handler_with_dynamic_segments

                return route.handler

        return lambda req: HttpResponseBuilder(404).build()


class HttpServer:
    def __init__(
        self,
        address: Tuple[str, int],
        router: HttpRouter,
        max_connections: int = 5,
        num_threads: int = 3,
    ):
        self.address = address
        self.server_socket = socket.create_server(address, reuse_port=True)
        self.max_connections = max_connections
        self.num_threads = num_threads
        self.router = router

    def start(self):
        log(f"Starting server on {self.address[0]}:{self.address[1]}...")
        self.server_socket.listen(self.max_connections)

        with ThreadPoolExecutor(
            max_workers=self.num_threads, thread_name_prefix="HttpThread"
        ) as executor:
            while True:
                client_socket, addr = self.server_socket.accept()
                executor.submit(self._handle_connection, client_socket, addr)

    def _handle_connection(self, client_socket: socket.socket, addr: Tuple[str, int]):
        log(f"Accepted connection from {addr}")
        try:
            self._handle_request(client_socket, addr)
        except Exception as e:
            logerr(f"{e}")
            traceback.print_exc()
        finally:
            client_socket.close()
            log(f"Closed connection from {addr}")

    def _read_request(self, client_socket: socket.socket) -> Optional[HttpRequest]:
        # Handle the data from the request in chunks. First we read and parse the headers,
        # then we read the body if needed.
        header_buff: bytes = b""
        body_buff: bytes = b""

        # The headers end with a double CRLF, so we read until we find that.
        while b"\r\n\r\n" not in header_buff:
            chunk = client_socket.recv(1024)
            if not chunk:  # Connection closed
                break

            if b"\r\n\r\n" in chunk:
                # We have found the end of the headers, so we can split the buffer.
                buff_parts = chunk.split(b"\r\n\r\n")
                header_buff += buff_parts[0] + b"\r\n\r\n"
                body_buff = buff_parts[1]
            else:
                header_buff += chunk

        if not header_buff:
            return None

        # Parse the headers
        request_lines = header_buff.decode("utf-8").split("\r\n")
        request_line = request_lines[0]
        method, path, _ = request_line.split(" ")
        headers = {
            k: v
            for k, v in [line.split(": ") for line in request_lines[1:] if ": " in line]
        }

        # Check if we have a body to read. If the Content-Length header is present, we read that
        # many bytes.
        # For simplicity, we read the whole body here and put it in the request dictionary.
        content_length = headers.get("Content-Length")

        # Only read the payload for POST requests TODO: Handle other methods if needed
        if method == "POST" and content_length:
            logv(f"Content-Length: {content_length}. Read the body")
            content_length = int(content_length)
            while len(body_buff) < content_length:
                chunk = client_socket.recv(1024)
                if not chunk:
                    break
                body_buff += chunk

        return HttpRequest(method, path, headers, body_buff)

    def _handle_request(self, client_socket: socket.socket, addr: Tuple[str, int]):
        # Read the request from the client. The request is expected to be in HTTP/1.1 format.
        request = self._read_request(client_socket)

        if request:
            logv(f"Handle {request.method} request for {request.path} from {addr}")
            logv(f"Request: {request}")

            try:
                response = self.router.get_handler(request.path)(request)

                # See if we need to compress the response based on the request
                accept_encoding = request.headers.get("Accept-Encoding")
                if accept_encoding:
                    response_encoding = HttpResponse._get_preferred_encoding(accept_encoding)
                    if response_encoding:
                        logv(f"Encoding the response with {response_encoding} before sending...")
                        response._compress(response_encoding)

            except Exception as e:
                logerr(f"Error handling request: {e}")
                response = HttpResponseBuilder(500).build()

            logv(f"Sending response {response} to {addr}")
            client_socket.sendall(response.serialize())
        else:
            log(f"Connection closed by client {addr}")

        client_socket.close()
