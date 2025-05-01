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


def main():
    router = HttpRouter()
    router.add_route("/", handle_root)
    router.add_route("/test", handle_test)
    router.add_route("/echo/{echo_val}", handle_echo)
    router.add_route("/query", handle_query)
    
    server = HttpServer(("localhost", 8080), router)
    server.start()

if __name__ == "__main__":
    main()