from browser.html_parser import Element
import tkinter.font as tkfont

INHERITED_PROPERTIES = {
    "font-family": "sans-serif",
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}

SYSTEM_FONTS = set()
def init_fonts(root):
    global SYSTEM_FONTS
    SYSTEM_FONTS = set(tkfont.families(root))

def check_available_fonts(font):
    if font in {"sans-serif", "serif", "monospace"}:
        return True

    return font in SYSTEM_FONTS

def style(node, rules):
    node.style = {}
    # Inherited properties
    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value
    # Style sheets
    for selector, body in rules:
        if not selector.matches(node): continue
        for property, value in body.items():
            node.style[property] = value
    # Style attributes
    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items():
            node.style[property] = value
    # Inheriting font size percentages and em. Using "computed styles"
    if node.style["font-size"].endswith(("%", "em")):
        if node.parent:
            parent_font_size = node.parent.style["font-size"]
        else:
            # if the root `html` elements font-size uses percentages,
            # then its relative to the default font-size
            parent_font_size = INHERITED_PROPERTIES["font-size"]

        node_size = node.style["font-size"]
        parent_px = float(parent_font_size[:-2])
        if node_size.endswith("%"):
            node_pct = float(node_size[:-1]) / 100
            node.style["font-size"] = f"{node_pct * parent_px}px"
        elif node_size.endswith("em"):
            node_size = float(node_size[:-2])
            node.style["font-size"] = f"{node_size * parent_px}px"
    elif node.style["font-size"] == "0":
        node.style["font-size"] = "0px"

    for child in node.children:
        style(child, rules)

def cascade_priority(rule):
    selector, body = rule
    return selector.priority

class TagSelector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag

class ClassSelector:
    def __init__(self, className):
        self.className = className
        self.priority = 10

    def matches(self, node):
        return isinstance(node, Element) and \
            self.className in node.attributes.get("class", "").split()

class IdSelector:
    def __init__(self, id):
        self.id = id
        self.priority = 20

    def matches(self, node):
        if not isinstance(node, Element): return False
        node_id = node.attributes.get("id", "")
        return self.id == node_id

class DescendantSelector:
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    def matches(self, node):
        if not self.descendant.matches(node): return False
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

class CSSParser:
    SPECIAL_CHARACTERS = "#-.%,!\"'"

    def __init__(self, s):
        self.s = s
        self.i = 0

    def get_selector_type(self, selector):
        if selector.startswith("."):
            out = ClassSelector(selector[1:])
        elif selector.startswith("#"):
            out = IdSelector(selector[1:])
        else:
            out = TagSelector(selector.casefold())
        return out

    def selector(self):
        out = self.get_selector_type(self.word())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            descendant = self.get_selector_type(self.word())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out

    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except Exception:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in self.SPECIAL_CHARACTERS:
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception(
                f"Parsing error at position {self.i}: expected a word \
                but got '{self.s[self.i:]}'"
            )
        return self.s[start:self.i]

    def value(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i].isspace() or \
                self.s[self.i] in self.SPECIAL_CHARACTERS:
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception(
                f"Parsing error at position {self.i}: expected a value \
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
        value = self.value()
        return property.casefold(), value

    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                property, value = self.pair()
                pairs[property.casefold()] = value
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                why = self.ignore_until([";", "}"])
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
