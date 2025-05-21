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
        if isinstance(self.node, Element) and (
            self.node.tag == "pre" or (
                self.node.tag == "nav" and "links" in self.node.attributes.get("class", "")
            )):
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, "lightgray")
            cmds.append(rect)
        if isinstance(self.node, Element) and self.node.tag == "li" and \
            isinstance(self.node.parent, Element) and self.node.parent.tag == "ul":
            x2 = self.x + 4
            y1 = self.y + self.height/2 - 2
            y2 = y1 + 4
            cmds.append(DrawRect(self.x, y1, x2, y2, "black"))

        if self.layout_mode() == "inline":
            for x, y, word, font in self.display_list:
                if emoji.is_emoji(word):
                    cmds.append(DrawEmoji(x, y, word))
                else:
                    cmds.append(DrawText(x, y, word, font))
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

            self.weight: Literal["normal", "bold"] = "normal"
            self.style: Literal["roman", "italic", "roman mono", "italic mono"] = "roman"
            self.size: int = 14

            self.centering: bool = False
            self.superscript: bool = False
            self.pre: bool = False

            # [{ x: , word: , size: , weight: , style: , centering: , superscript: ,}]
            self.line = []
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

        fonts = [get_font(entry["size"], entry["weight"], entry["style"]) for entry in self.line]
        metrics = [font.metrics() for font in fonts]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        if any([entry["centering"] for entry in self.line]):
            last_entry = self.line[-1]
            last_width = get_measure(last_entry["word"], last_entry["size"], last_entry["weight"], last_entry["style"])
            line_width = self.line[0]["x"] + last_entry["x"] + last_width
            centering_delta = (self.width - line_width) / 2
        else:
            centering_delta = 0

        for i, entry in enumerate(self.line):
            font = fonts[i]

            if entry["superscript"]:
                y = self.y + baseline - metrics[i]["linespace"]
            else:
                y = self.y + baseline - metrics[i]["ascent"]

            x = self.x + entry["x"] + centering_delta
            if isinstance(self.node, Element) and self.node.tag == "li":
                x += HSTEP

            self.display_list.append((x, y, entry["word"], font))

        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent
        self.cursor_x = 0
        self.line = []

    def word(self, word):
        old_word = ""
        if "\u00AD" in word:
            old_word = word
            word = word.replace("\u00AD", "")

        width = get_measure(word, self.size, self.weight, self.style)
        space = get_measure(" ", self.size, self.weight, self.style)

        if self.pre:
            if word == "\n":
                self.flush()
            elif self.cursor_x + width <= self.width - SCROLLBAR_WIDTH:
                self.line.append(self.create_word(word))
                self.cursor_x += width
            else:
                self.flush()
                self.line.append(self.create_word(word))
                self.cursor_x += width
        elif self.cursor_x + width + space <= self.width - SCROLLBAR_WIDTH:
            self.line.append(self.create_word(word))
            self.cursor_x += width + space
        else:
            if old_word != "" and "\u00AD" in old_word:
                parts = old_word.split("\u00AD")
                hyphen_w = get_measure("-", self.size, self.weight, self.style)
                fitted_parts = []

                for part in parts:
                    part_w = get_measure(part, self.size, self.weight, self.style)
                    if self.cursor_x + part_w + hyphen_w < self.width - SCROLLBAR_WIDTH:
                        self.line.append(self.create_word(part))
                        self.cursor_x += part_w
                        fitted_parts.append(part)
                    else:
                        break

                leftover_parts = "".join(parts[len(fitted_parts):])
                if leftover_parts:
                    self.line.append(self.create_word("-"))
                    # Nextline:
                    self.flush()
                    self.line.append(self.create_word(leftover_parts))
                    self.cursor_x += get_measure(leftover_parts, self.size, self.weight, self.style) + space
            else:
                self.flush()
                self.line.append(self.create_word(word))
                self.cursor_x += width + space

    def create_word(self, word, x=None, size=None, weight=None, style=None, centering=None, superscript=None):
        return {
            "x": x if x else self.cursor_x,
            "word": word,
            "size": size if size else self.size,
            "weight": weight if weight else self.weight,
            "style": style if style else self.style,
            "centering": centering if centering else self.centering,
            "superscript": superscript if superscript else self.superscript
        }

    def open_tag(self, element: Element):
        if element.tag == "i":
            if "mono" in self.style:
                self.style = "italic mono"
            else:
                self.style = "italic"
        elif element.tag == "b":
            self.weight = "bold"
        elif element.tag == "small":
            self.size -= 2
        elif element.tag == "big":
            self.size += 4
        elif element.tag == "sup":
            self.superscript = True
            self.size = int(self.size / 2)
        elif element.tag == "br" or element == "br /":
            self.flush()
        elif element.tag == "h1":
            self.size = int(self.size * 1.5)
            if "title" in element.attributes.get("class", ""):
                self.centering = True
        elif element.tag == "pre":
            if "mono" not in self.style:
                self.style += " mono"
            self.pre = True

    def close_tag(self, element: Element):
        if element.tag == "i":
            if "mono" in self.style:
                self.style = "roman mono"
            else:
                self.style = "roman"
        elif element.tag == "b":
            self.weight = "normal"
        elif element.tag == "small":
            self.size += 2
        elif element.tag == "big":
            self.size -= 4
        elif element.tag == "sup":
            self.superscript = False
            self.size = int(self.size * 2)
        elif element.tag == "p":
            self.flush()
            self.cursor_y += VSTEP
        elif element.tag == 'h1':
            self.size = int(self.size / 1.5)
            self.centering = False
        elif element.tag == "pre":
            self.style = self.style.replace("mono", "").strip()
            self.pre = False

    def recurse(self, tree: Union[str, Text, Element]):
        if isinstance(tree, Text):
            words = []
            if self.pre:
                word = ""
                for c in tree.text:
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
                words = tree.text.split()
            for word in words:
                self.word(word)
        else:
            self.open_tag(tree)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree)
