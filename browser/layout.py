from typing import Literal, Union

import emoji
from browser.draw import DrawRect, DrawText, DrawEmoji
from browser.html_parser import Text, Element
import tkinter.font

HSTEP, VSTEP = 13, 18
SCROLLBAR_WIDTH = 12

font_cache = {}
measure_cache = {}

def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in font_cache:
        if "mono" in style:
            slant = style.replace("mono", "").strip()
            font = tkinter.font.Font(
                family="Courier",
                size=size,
                weight=weight,
                slant=slant)
        else:
            font = tkinter.font.Font(size=size, weight=weight, slant=style)
        label = tkinter.Label(font=font)
        font_cache[key] = (font, label)
    return font_cache[key][0]

def get_measure(word, size, weight, style):
    key = (word, size, weight, style)
    if key not in measure_cache:
        font = get_font(size, weight, style)
        measure = font.measure(word)
        measure_cache[key] = measure
    return measure_cache[key]

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)

class DocumentLayout:
    def __init__(self, node, screen_width):
        self.node = node
        self.parent = None
        self.children = []

        self.screen_width = screen_width
        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        self.width = self.screen_width - 2*HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []


class BlockLayout:
    BLOCK_ELEMENTS = [
        "html", "body", "article", "section", "nav", "aside",
        "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
        "footer", "address", "p", "hr", "pre", "blockquote",
        "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
        "figcaption", "main", "div", "table", "form", "fieldset",
        "legend", "details", "summary"
    ]

    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.display_list = []

        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            x2 = self.x + self.width
            y2 = self.y + self.height
            cmds.append(DrawRect(self.x, self.y, x2, y2, bgcolor))
        if isinstance(self.node, Element) and self.node.tag == "li" and \
            isinstance(self.node.parent, Element) and self.node.parent.tag == "ul":
            x2 = self.x + 4
            y1 = self.y + self.height/2 - 2
            y2 = y1 + 4
            cmds.append(DrawRect(self.x, y1, x2, y2, "black"))

        if self.layout_mode() == "inline":
            for x, y, word, font, color in self.display_list:
                if emoji.is_emoji(word):
                    cmds.append(DrawEmoji(x, y, word))
                else:
                    cmds.append(DrawText(x, y, word, font, color))
        return cmds

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and \
                  child.tag in self.BLOCK_ELEMENTS
                  for child in self.node.children]):
            return "block"
        elif self.node.children:
            return "inline"
        else:
            return "block"


    def layout(self):
        self.x = self.parent.x + (HSTEP if isinstance(self.parent.node, Element) and self.parent.node.tag == "li" else 0)
        self.width = self.parent.width

        if self.previous:
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
            self.cursor_y: float = 0
            self.cursor_x: float = 0

            # TODO: Remove
            self.style: Literal["roman", "italic", "roman mono", "italic mono"] = "roman"
            self.pre: bool = False

            self.line = [] # (x, word, font, color)
            self.recurse(self.node)
            self.flush()

        for child in self.children:
            child.layout()

        if mode == "block":
            self.height = sum([child.height for child in self.children])
        else:
            self.height = self.cursor_y

    def flush(self):
        if not self.line:
            return

        metrics = [font.metrics() for _, _, font, _ in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        for i, (rel_x, word, font, color) in enumerate(self.line):
            y = self.y + baseline - metrics[i]["ascent"]

            x = self.x + rel_x
            if isinstance(self.node, Element) and self.node.tag == "li":
                x += HSTEP

            self.display_list.append((x, y, word, font, color))

        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent
        self.cursor_x = 0
        self.line = []

    def word(self, node, word):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == "normal": style = "roman"
        if self.pre: style += " mono"
        size = int(float(node.style["font-size"][:-2]) * .75)
        color = node.style["color"]
        font = get_font(size, weight, style)

        old_word = ""
        if "\u00AD" in word:
            old_word = word
            word = word.replace("\u00AD", "")

        width = get_measure(word, size, weight, style)
        space = get_measure(" ", size, weight, style)

        if self.pre:
            if word == "\n":
                self.flush()
            elif self.cursor_x + width <= self.width - SCROLLBAR_WIDTH:
                self.line.append((self.cursor_x, word, font, color))
                self.cursor_x += width
            else:
                self.flush()
                self.line.append((word, size, weight, style, color))
                self.cursor_x += width
        elif self.cursor_x + width + space <= self.width - SCROLLBAR_WIDTH:
            self.line.append((self.cursor_x, word, font, color))
            self.cursor_x += width + space
        else:
            if old_word != "" and "\u00AD" in old_word:
                parts = old_word.split("\u00AD")
                hyphen_w = get_measure("-", size, weight, style)
                fitted_parts = []

                for part in parts:
                    part_w = get_measure(part, size, weight, style)
                    if self.cursor_x + part_w + hyphen_w < self.width - SCROLLBAR_WIDTH:
                        self.line.append((self.cursor_x, part, font, color))
                        self.cursor_x += part_w
                        fitted_parts.append(part)
                    else:
                        break

                leftover_parts = "".join(parts[len(fitted_parts):])
                if leftover_parts:
                    self.line.append((self.cursor_x, "-", font, color))
                    # Nextline:
                    self.flush()
                    self.line.append((self.cursor_x, leftover_parts, font, color))
                    self.cursor_x += get_measure(leftover_parts, size, weight, style) + space
            else:
                self.flush()
                self.line.append((self.cursor_x, word, font, color))
                self.cursor_x += width + space

    def recurse(self, node: Union[str, Text, Element]):
        if isinstance(node, Text):
            words = []
            if self.pre:
                word = ""
                for c in node.text:
                    if c == " " or c == "\n":
                        if word:
                            words.append(word)
                        word = ""
                        words.append(c)
                    else:
                        word += c
                if word:
                    words.append(word)
            else:
                words = node.text.split()
            for word in words:
                self.word(node, word)
        else:
            if node.tag == "br" or node == "br /":
                self.flush()
            for child in node.children:
                self.recurse(child)
