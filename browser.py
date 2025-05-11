import socket
import ssl

# Key: (scheme, host, port)
sockets = {}
MAX_REDIRECTS = 3

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


    def request(self, num_redirects = 0):
        if self.scheme == "data":
            content = self.data
        elif self.scheme == "file":
            content = self._handle_file_request()
        else:
            content = self._handle_network_request(num_redirects)

        return content


    def _handle_file_request(self):
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

        return content

    def _handle_network_request(self, num_redirects = 0):
        global sockets
        address = (self.scheme, self.host, self.port)
        s = sockets.get(address)

        if s is None:
            s = socket.socket(
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
            s.connect((self.host, self.port))

            if self.scheme == "https":
                ctx = ssl.create_default_context()
                s = ctx.wrap_socket(s, server_hostname=self.host)

            sockets[address] = s

        headers = {
            "Host": self.host,
            "Connection": "keep-alive",
            "User-Agent": "yeet-browser/1.0",
        }

        request = f"GET {self.path} HTTP/1.1\r\n"
        for key, val in headers.items():
            request += f"{key}: {val}\r\n"
        request += "\r\n"

        s.send(request.encode("utf-8"))

        response = s.makefile("rb")
        statusline = response.readline().decode("utf-8")
        version, status, explanation = statusline.split(" ", 2)

        response_headers = {}
        while True:
            line = response.readline()
            if line == b"\r\n": break
            header_line = line.decode("utf-8").strip()
            header, value = header_line.split(":", 1)
            response_headers[header.casefold()] = value.strip()

        if status.startswith("3") and "location" in response_headers:
            url = response_headers["location"]

            if "://" not in url:
                url = f"{self.scheme}://{self.host}{url}"

            if num_redirects < MAX_REDIRECTS:
                return URL(url).request(num_redirects + 1)
            else:
                return "Error: Too many redirects"

        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        content_length = int(response_headers.get("content-length", 0))
        content = response.read(content_length).decode("utf-8")

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
