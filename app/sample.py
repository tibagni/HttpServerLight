from app.httpserver import HttpRequest, HttpResponse, HttpResponseBuilder, HttpRouter, HttpServer

def handle_root(request: HttpRequest) -> HttpResponse:
    response = HttpResponseBuilder(HttpResponse.STATUS_200_OK)
    response.set_body(b"Hello, World!")
    return response.build()

def main():
    router = HttpRouter()
    router.add_route("/", handle_root)
    
    server = HttpServer(("localhost", 8080), router)
    server.start()

if __name__ == "__main__":
    main()