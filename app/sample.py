import os
import mimetypes

from app.httpserver import HttpRequest, HttpResponse, HttpResponseBuilder, HttpRouter, HttpServer

def handle_root(request: HttpRequest) -> HttpResponse:
    return (HttpResponseBuilder(HttpResponse.STATUS_200_OK)
            .set_body(b"Hello, World!")
            .build())

def handle_test(request: HttpRequest) -> HttpResponse:
    return (HttpResponseBuilder(HttpResponse.STATUS_200_OK)
            .set_body(b"Test!")
            .build())

def handle_echo(request: HttpRequest, **kwargs) -> HttpResponse:
    return (HttpResponseBuilder(HttpResponse.STATUS_200_OK)
            .set_body(f"{kwargs['echo_val']}!".encode("utf-8"))
            .build())

def handle_query(request: HttpRequest) -> HttpResponse:
    return (HttpResponseBuilder(HttpResponse.STATUS_200_OK)
            .set_body(f"{request.query_params}".encode("utf-8"))
            .build())

def handle_files(request: HttpRequest, **kwargs) -> HttpResponse:
    if "file_name" in kwargs:
        file_name = kwargs["file_name"]
        file_path = os.path.join("files", file_name)

        if not os.path.exists(file_path):
            return (HttpResponseBuilder(HttpResponse.STATUS_404_NOT_FOUND)
                    .set_body(f"File {file_name} not found".encode("utf-8"))
                    .build())
        
        if not os.path.isfile(file_path):
            return (HttpResponseBuilder(HttpResponse.STATUS_400_BAD_REQUEST)
                    .set_body(f"{file_name} is not a file".encode("utf-8"))
                    .build())
        
        with open(file_path, "rb") as file:
            file_content = file.read()
            mimetype, _ = mimetypes.guess_type(file_path)
            mimetype = mimetype if mimetype else "application/octet-stream"
            return (HttpResponseBuilder(HttpResponse.STATUS_200_OK)
                    .set_body(file_content, mimetype)
                    .build())
    
    return (HttpResponseBuilder(HttpResponse.STATUS_400_BAD_REQUEST)
            .set_body(f"Specify a file".encode("utf-8"))
            .build())

def main():
    router = HttpRouter()
    router.add_route("/", handle_root)
    router.add_route("/test", handle_test)
    router.add_route("/echo/{echo_val}", handle_echo)
    router.add_route("/query", handle_query)
    router.add_route("/files/{file_name}", handle_files)
    
    server = HttpServer(("localhost", 8080), router)
    server.start()

if __name__ == "__main__":
    main()