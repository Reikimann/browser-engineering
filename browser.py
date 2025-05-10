import socket
import ssl

class URL:
    def __init__(self, url):
        if url.startswith(("http://", "https://")):
            self.scheme, url = url.split("://", 1)
            assert self.scheme in ["http", "https", "file"]

            if "/" not in url:
                url = url + "/"
            self.host, url = url.split("/", 1)
            self.path = "/" + url

            if self.scheme == "http":
                self.port = 80
            elif self.scheme == "https":
                self.port = 443

            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)
        elif url.startswith("file://"):
            self.scheme = "file"
            self.host = ""
            self.path = url[len("file://"):]
            self.port = None
        elif url.startswith("data:"):
            import re

            self.scheme = "data"
            self.data = url[url.find(",")+1:]
            match = re.search(r"([^,]+),", url)
            self.mediatype = match.group(1) if match else "text/plain"
            self.host = ""
            self.path = ""
            self.port = None
        else:
            raise ValueError(f"Unsupported URL scheme in {url}")

    def request(self):
        if self.scheme == "data":
            content = self.data
        elif self.scheme == "file":
            if self.path == "":
                return f"Error: No path provided"

            try:
                with open(self.path, "r") as f:
                    content = f.read()
            except FileNotFoundError:
                content = f"Error: File not found: {self.path}"
            except PermissionError:
                content = f"Error: Permission denied: {self.path}"
            except IsADirectoryError:
                content = f"Error: Provided path is a directory: {self.path}"
            except Exception as e:
                raise e
        else:
            s = socket.socket(
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
            s.connect((self.host, self.port))

            if self.scheme == "https":
                ctx = ssl.create_default_context()
                s = ctx.wrap_socket(s, server_hostname=self.host)

            headers = {
                "Host": self.host,
                "Connection": "close",
                "User-Agent": "yeet-browser/1.0",
            }

            request = f"GET {self.path} HTTP/1.1\r\n"
            for key, val in headers.items():
                request += f"{key}: {val}\r\n"
            request += "\r\n"

            s.send(request.encode("utf-8"))

            response = s.makefile("r", encoding="utf-8", newline="\r\n")
            statusline = response.readline()
            version, status, explanation = statusline.split(" ", 2)

            response_headers = {}
            while True:
                line = response.readline()
                if line == "\r\n": break
                header, value = line.split(":", 1)
                response_headers[header.casefold()] = value.strip()

            assert "transfer-encoding" not in response_headers
            assert "content-encoding" not in response_headers

            content = response.read()
            s.close()

        return content

def show(content):
    in_tag = False
    in_entity = False
    entity = ""

    for c in content:
        if in_entity:
            if c == ";":
                if entity == "lt":
                    print("<", end="")
                elif entity == "gt":
                    print(">", end="")
                else:
                    print(f"&{entity};", end="")

                in_entity = False
                entity = ""
            else:
                entity += c
        elif c == "&":
            in_entity = True
            entity = ""
        elif c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            print(c, end="")

def load(url_str):
    view_source = url_str.startswith("view-source:")
    if view_source:
        url_str = url_str[len("view-source:"):]

    url = URL(url_str)

    content = url.request()
    if view_source:
        print(content, end="")
    else:
        show(content)

if __name__ == "__main__":
    import sys

    default_url = "file://homepage.html"
    url_str = sys.argv[1] if len(sys.argv) > 1 else default_url

    load(url_str)
