from browser.html_parser import Element

def style(node):
    node.style = {}
    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items():
            node.style[property] = value
    for child in node.children:
        style(child)

class CSSParser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception(
                f"Parsing error at position {self.i}: expected a word \
                but got '{self.s[self.i:]}'"
            )
        return self.s[start:self.i]

    def literal(self, literal):
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception(
                f"Parsing error at position {self.i}: expected '{literal}' \
                but got '{self.s[self.i] if self.i < len(self.s) else 'EOF'}'"
            )
        self.i += 1

    def pair(self):
        property = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        value = self.word()
        return property.casefold(), value

    def body(self):
        pairs = {}
        while self.i < len(self.s):
            try:
                property, value = self.pair()
                pairs[property.casefold()] = value
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                why = self.ignore_until([";"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None
