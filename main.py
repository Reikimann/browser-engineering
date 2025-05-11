import sys

from browser import load


if __name__ == "__main__":
    default_url = "file://homepage.html"
    url_str = sys.argv[1] if len(sys.argv) > 1 else default_url

    load(url_str)
