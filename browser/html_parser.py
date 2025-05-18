import re
import json

class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self) -> str:
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    # TODO: Add attributes back to the element with repr
    def __repr__(self) -> str:
        return f"<{self.tag}>"


with open("data/entities.json", "r", encoding="utf-8") as f:
    ENTITY_MAP = json.load(f)

def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)

class HTMLParser:
    SELF_CLOSING_TAGS = [
        "area", "base", "br", "meta", "col", "hr", "img", "wbr",
        "input", "link", "param", "source", "track", "embed",
    ]

    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]

    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def parse(self):
        in_tag = False
        buffer: str = ""
        i: int = 0

        while i < len(self.body):
            c = self.body[i]
            if c == "<":
                in_tag = True
                if buffer: self.add_text(buffer)
                buffer = ""
            elif c == ">":
                in_tag = False
                if buffer: self.add_tag(buffer)
                buffer = ""
            elif not in_tag and c == "&":
                m = re.search(r"&.*?;", self.body[i:])
                if m:
                    entity = m.group(0)
                    if entity in ENTITY_MAP:
                        buffer += ENTITY_MAP[entity]["characters"]
                    i += len(entity) - 1
            else:
                buffer += c
            i += 1

        if not in_tag and buffer:
            self.add_text(buffer)

        return self.finish()

    def add_text(self, text):
        if text.isspace(): return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"): return
        self.implicit_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def finish(self):
        if not self.unfinished:
            self.implicit_tags(None)
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            else:
                break

    ATTRIBUTE_REGEX = re.compile(r'''
        (?P<name>[^\s="'>/=]+)                  # Attribute name
        (?:\s*=\s*
            (?P<value>                          # Attribute Value
                "[^"]*"                         # Double-quoted
                | '[^']*'                       # Single-quoted
                | [^\s"'=<>`]+                  # Unquoted
            )
        )?                                      # Empty attribute (=value is optional)
    ''', re.VERBOSE)

    def get_attributes(self, text):
        parts = text.split(None, 1)
        tag = parts[0].casefold()
        attributes = {}

        if len(parts) > 1:
            attribute_text = parts[1]
            for match in self.ATTRIBUTE_REGEX.finditer(attribute_text):
                name = match.group("name").casefold()
                value = match.group("value")
                attributes[name] = value.strip("\"'") if value else ""
        return tag, attributes
