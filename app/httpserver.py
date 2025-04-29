import socket

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

    def __repr__(self):
        return f"<HttpRequest method={self.method} path={self.path} headers={self.headers} body={self.body}>"

class HttpResponse:
    STATUS_404_NOT_FOUND = 404
    STATUS_200_OK = 200

    _STATUS_MESSAGES = {
        STATUS_200_OK: "OK",
        STATUS_404_NOT_FOUND: "Not Found",
    }

    def __init__(self, status_code: int, headers: dict = {}, body: bytes = b""):
        self.status_code = status_code
        self.body = body
        self.headers = headers

    def serialize(self) -> bytes:
        status_message = self._STATUS_MESSAGES.get(self.status_code)
        response_line = f"HTTP/1.1 {self.status_code} {status_message}\r\n"
        headers = "".join(f"{k}: {v}\r\n" for k, v in self.headers.items())
        return (response_line + headers + "\r\n").encode("utf-8") + self.body
    
    def __repr__(self):
        return f"<HttpResponse status_code={self.status_code} headers={self.headers} body={self.body}>"

class HttpResponseBuilder:
    def __init__(self, status_code: int):
        self._status_code = status_code
        self._headers = {}
        self._body = b""

    def set_header(self, name: str, value):
        self._headers[name] = value

    def set_body(self, body: bytes, content_type: str = "text/plain"):
        self.set_header("Content-Type", content_type)
        self.set_header("Content-Length", len(body))
        self._body = body

    def build(self) -> HttpResponse:
        return HttpResponse(
            status_code=self._status_code,
            headers=self._headers,
            body=self._body,
        )

class HttpRouter:
    def __init__(self):
        self._routes = {}

    def add_route(self, path: str, handler: Callable[[HttpRequest], HttpResponse]):
        if path in self._routes:
            raise ValueError(f"Route {path} already exists")

        self._routes[path] = handler

    def get_handler(self, path: str) -> Callable[[HttpRequest], HttpResponse]:
        if path not in self._routes:
            return lambda req: HttpResponseBuilder(404).build()

        return self._routes[path]

class HttpServer:
    def __init__(self, address: Tuple[str, int], router: HttpRouter, max_connections: int = 5, num_threads: int = 3):
        self.address = address
        self.server_socket = socket.create_server(address, reuse_port=True)
        self.max_connections = max_connections
        self.num_threads = num_threads
        self.router = router

    def start(self):
        log(f"Starting server on {self.address[0]}:{self.address[1]}...")
        self.server_socket.listen(self.max_connections)

        with ThreadPoolExecutor(max_workers=self.num_threads, thread_name_prefix="HttpThread") as executor:
            while True:
                client_socket, addr = self.server_socket.accept()
                executor.submit(self._handle_connection, client_socket, addr)

    def _handle_connection(self, client_socket: socket.socket, addr: Tuple[str, int]):
        logv(f"Accepted connection from {addr}")
        try:
            self._handle_request(client_socket, addr)
        except Exception as e:
            logerr(f"Error handling request: {e}")
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
            response = self.router.get_handler(request.path)(request)

            logv(f"Sending response {response} to {addr}")
            client_socket.sendall(response.serialize())
        else:
            log(f"Connection closed by client {addr}")

        client_socket.close()