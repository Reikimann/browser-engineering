import socket
import ssl
import time
import gzip

from browser.constants import MAX_REDIRECTS

# Key: (scheme, host, port)
sockets = {}
# Key: "{scheme}://{host}{path}"
cache = {}

class URL:
    def __init__(self, url):
        self.view_source = False
        self.is_malformed = False

        if url.startswith("view-source:"):
            self.view_source = True
            _, url = url.split(":", 1)

        if url == "about:blank":
            self.is_malformed = True

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
            self.is_malformed = True

    def __str__(self):
        port_part = ":" + str(self.port)
        if self.scheme == "https" and self.port == 443:
            port_part = ""
        if self.scheme == "http" and self.port == 80:
            port_part = ""
        return self.scheme + "://" + self.host + port_part + self.path

    def request(self, num_redirects = 0):
        if self.is_malformed:
            return None

        if self.scheme == "data":
            content = self.data
        elif self.scheme == "file":
            content = self._handle_file_request()
        else:
            content = self._handle_network_request(num_redirects)

        return content

    def resolve(self, url):
        if "://" in url: return URL(url) # Absolute
        if not url.startswith("/"):      # Relative to current path
            dir, _ = self.path.rsplit("/", 1)
            while url.startswith("../"): # Relative with ../
                _, url = url.split("/", 1)
                if "/" in dir:
                    dir, _ = dir.rsplit("/", 1)
            url = dir + "/" + url
        if url.startswith("//"):         # Protocol-relative URL
            return URL(self.scheme + ":" + url)
        else:                            # Root-relative path
            return URL(self.scheme + "://" + self.host + \
                ":" + str(self.port) + url)

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
        # NOTE: Step 0: Check cache for request
        cached_entry = cache.get(f"{self.scheme}://{self.host}{self.path}")
        if cached_entry:
            age = time.time() - cached_entry["timestamp"]
            if age <= cached_entry["max-age"]:
                return cached_entry["content"]

        # NOTE: Step 1: Reuse or open a socket
        global sockets
        address = (self.scheme, self.host, self.port)
        s = sockets.get(address)

        if s is None or s.fileno() == -1:
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

        # NOTE: Step 2: Send GET request
        headers = {
            "Host": self.host,
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip",
            "User-Agent": "yeet-browser/1.0",
        }

        request = f"GET {self.path} HTTP/1.1\r\n"
        for key, val in headers.items():
            request += f"{key}: {val}\r\n"
        request += "\r\n"

        s.send(request.encode("utf-8"))

        # NOTE: Step 3: Parse statusline and response headers
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

        # NOTE: Step 4: Handle possible redirects
        if status.startswith("3") and "location" in response_headers:
            url = response_headers["location"]

            if "://" not in url:
                url = f"{self.scheme}://{self.host}{url}"

            if num_redirects < MAX_REDIRECTS:
                return URL(url).request(num_redirects + 1)
            else:
                return "Error: Too many redirects"

        # NOTE: Step 5: Read response body
        if "content-length" in response_headers:
            content_length = int(response_headers.get("content-length", 0))
        else:
            content_length = -1

        if "transfer-encoding" in response_headers and response_headers["transfer-encoding"] == "chunked":
            # NOTE: Transfer encoding work like below:
            # <chunk-size in hex>\r\n
            # <chunk-data>\r\n
            content = b""
            while True:
                size = response.readline().strip().decode("utf-8")
                if size == "0" or not size:
                    response.readline()
                    break

                chunck_size = int(size, 16)
                line = response.read(chunck_size)
                response.read(2) # Removes the last \r\n
                content += line
        else:
            content = response.read(content_length)

        # NOTE: Step 6: Decompress body if needed
        if "content-encoding" in response_headers:
            encoding = response_headers["content-encoding"]
            if encoding in ["gzip", "x-gzip"]:
                content = gzip.decompress(content)

        # NOTE: Step 7: Decode body to text (utf-8 encoding)
        content = content.decode("utf-8")

        # NOTE: Step 8: Cache request if allowed
        if "cache-control" in response_headers and status == "200":
            cache_directives = self._parse_cache_control(response_headers["cache-control"])

            if "max-age" in cache_directives and "no-store" not in cache_directives:
                url = f"{self.scheme}://{self.host}{self.path}"

                cache[url] = {
                    "content": content,
                    "max-age": int(cache_directives["max-age"]),
                    "timestamp": time.time()
                }

        return content

    def _parse_cache_control(self, header_value):
        cache_control = {}
        directives = header_value.split(",")

        for directive in directives:
            directive = directive.casefold().strip()

            if "=" in directive:
                key, value = directive.split("=")
                cache_control[key] = value
            else:
                cache_control[directive] = True

        return cache_control
