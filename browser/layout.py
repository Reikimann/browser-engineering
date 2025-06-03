import emoji
from browser.css_parser import check_available_fonts
from browser.draw import DrawRect, DrawText, DrawEmoji
from browser.constants import WIDTH, HSTEP, VSTEP, SCROLLBAR_WIDTH
from browser.html_parser import Text, Element
import tkinter.font

font_cache = {}
measure_cache = {}

def get_font(family, size, weight, style):
    if style == "oblique": style = "italic"
    key = (family, size, weight, style)
    if key not in font_cache:
        font = tkinter.font.Font(
            family=family,
            size=size,
            weight=weight,
            slant=style)
        label = tkinter.Label(font=font)
        font_cache[key] = (font, label)
    return font_cache[key][0]

def get_measure(word, family, size, weight, style, font=None):
    key = (word, family, size, weight, style)
    if key not in measure_cache:
        font = font if font else get_font(family, size, weight, style)
        measure = font.measure(word)
        measure_cache[key] = measure
    return measure_cache[key]

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)

class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []

    def layout(self, screen_width = WIDTH):
        self.children = []
        self.width = screen_width - 2*HSTEP
        self.x = HSTEP
        self.y = VSTEP

        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        child.layout()

        self.height = child.height

    def paint(self):
        return []

class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for word in self.children:
            word.layout()

        if not self.children:
            self.height = 0
            return

        metrics = [word.font.metrics() for word in self.children]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.y + 1.25 * max_ascent
        for i, word in enumerate(self.children):
            word.y = baseline - metrics[i]["ascent"]
        max_descent = max([metric["descent"] for metric in metrics])
        self.height = 1.25 * (max_ascent + max_descent)

    def paint(self):
        return []

class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.font = None

    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal": style = "roman"
        size = int(float(self.node.style["font-size"][:-2]) * .75)
        family = self.node.style["font-family"]
        if family != "sans-serif":
            for font_family in family.split(","):
                font_family = font_family.replace("\"", "")
                if check_available_fonts(font_family):
                    family = font_family
        self.font = get_font(family, size, weight, style)
        self.width = get_measure(self.word, family, size, weight, style, self.font)

        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = self.font.metrics("linespace")

    def paint(self):
        color = self.node.style["color"]
        if emoji.is_emoji(self.word):
            return [DrawEmoji(self.x, self.y, self.word)]
        else:
            return [DrawText(self.x, self.y, self.word, self.font, color)]


class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def __repr__(self) -> str:
        return f"BlockLayout(x={self.x} y={self.y} width={self.width} height={self.height} node={self.node})"

    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")

        if bgcolor != "transparent":
            x2 = self.x + self.width
            y2 = self.y + self.height
            cmds.append(DrawRect(self.x, self.y, x2, y2, bgcolor))
        return cmds

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif self.node.children:
            if any(isinstance(child, Element) and \
                  child.style.get("display", "inline") == "block"
                  for child in self.node.children):
                return "block"
            return "inline"
        else:
            return "block"

    def layout(self):
        self.x = self.parent.x
        self.compute_width()

        if self.previous:
            # NOTE: This doesn't work when a block-layout Elements height uses em/rem-units
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        mode = self.layout_mode()
        if mode == "block":
            previous = None
            for child in self.node.children:
                if isinstance(child, Element) and child.tag == "head":
                    continue
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next
        else:
            self.new_line()
            self.recurse(self.node)

        for child in self.children:
            child.layout()

        self.compute_height()

    def word(self, node, word):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == "normal": style = "roman"
        size = int(float(node.style["font-size"][:-2]) * .75)
        family = node.style["font-family"]
        if family != "sans-serif":
            for font_family in family.split(","):
                font_family = font_family.replace("\"", "")
                if check_available_fonts(font_family):
                    family = font_family
        font = get_font(family, size, weight, style)

        width = get_measure(word, family, size, weight, style, font)
        if self.cursor_x + width > self.width - SCROLLBAR_WIDTH:
            self.new_line()

        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, line, previous_word)
        line.children.append(text)
        self.cursor_x += width + get_measure(" ", family, size, weight, style, font)

    def recurse(self, node):
        if isinstance(node, Text):
            for word in node.text.split():
                self.word(node, word)
        else:
            if node.tag == "br" or node == "br /":
                self.new_line()
            for child in node.children:
                self.recurse(child)

    def new_line(self):
        self.cursor_x = 0
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)

    def compute_width(self):
        css_width = self.node.style.get("width", "auto")
        if css_width == "auto":
            self.width = self.parent.width
        elif css_width.endswith("%"):
            self.width = int(self.parent.width * float(css_width[:-1]) / 100)
        elif css_width.endswith("px"):
            self.width = int(float(css_width[:-2]))

    def compute_height(self):
        css_height = self.node.style.get("height", "auto")
        if css_height == "auto":
            self.height = sum([child.height for child in self.children])
        elif css_height.endswith("px"):
            self.height = int(float(css_height[:-2]))
