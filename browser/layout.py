from typing import Literal, Union
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


class Layout:
    def __init__(self, tree, screen_width):
        self.display_list = []

        self.cursor_y: float = VSTEP
        self.cursor_x: float = HSTEP
        self.screen_width: int = screen_width

        self.weight: Literal["normal", "bold"] = "normal"
        self.style: Literal["roman", "italic", "roman mono", "italic mono"] = "roman"
        self.size: int = 12

        self.centering: bool = False
        self.superscript: bool = False
        # NOTE: view-source: doesnt work rn
        self.pre: bool = False

        # [{ x: , word: , size: , weight: , style: , centering: , superscript: ,}]
        self.line = []
        self.recurse(tree)
        self.flush()

    def flush(self):
        if not self.line: return

        fonts = [get_font(entry["size"], entry["weight"], entry["style"]) for entry in self.line]
        metrics = [font.metrics() for font in fonts]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        if any([entry["centering"] for entry in self.line]):
            last_entry = self.line[-1]
            last_width = get_measure(last_entry["word"], last_entry["size"], last_entry["weight"], last_entry["style"])
            line_width = self.line[0]["x"] + last_entry["x"] + last_width
            centering_delta = (self.screen_width - line_width) / 2
        else:
            centering_delta = 0

        for i, entry in enumerate(self.line):
            font = fonts[i]

            if entry["superscript"]:
                y = baseline - metrics[i]["linespace"]
            else:
                y = baseline - metrics[i]["ascent"]

            self.display_list.append((entry["x"] + centering_delta, y, entry["word"], font))

        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent
        self.cursor_x = HSTEP
        self.line = []

    def word(self, word):
        old_word = ""
        if "\u00AD" in word:
            old_word = word
            word = word.replace("\u00AD", "")

        width = get_measure(word, self.size, self.weight, self.style)
        space = get_measure(" ", self.size, self.weight, self.style)

        if self.cursor_x + width + space <= self.screen_width - HSTEP - SCROLLBAR_WIDTH:
            self.line.append({"x": self.cursor_x,
                              "word": word,
                              "size": self.size,
                              "weight": self.weight,
                              "style": self.style,
                              "centering": self.centering,
                              "superscript": self.superscript})
            self.cursor_x += width + space
        else:
            if old_word != "" and "\u00AD" in old_word:
                parts = old_word.split("\u00AD")
                hyphen_w = get_measure("-", self.size, self.weight, self.style)
                fitted_parts = []

                for part in parts:
                    part_w = get_measure(part, self.size, self.weight, self.style)
                    if self.cursor_x + part_w + hyphen_w < self.screen_width - HSTEP - SCROLLBAR_WIDTH:
                        self.line.append({"x": self.cursor_x,
                                          "word": part,
                                          "size": self.size,
                                          "weight": self.weight,
                                          "style": self.style,
                                          "centering": self.centering,
                                          "superscript": self.superscript})
                        self.cursor_x += part_w
                        fitted_parts.append(part)
                    else:
                        break

                leftover_parts = "".join(parts[len(fitted_parts):])
                if leftover_parts:
                    self.line.append({"x": self.cursor_x,
                                      "word": "-",
                                      "size": self.size,
                                      "weight": self.weight,
                                      "style": self.style,
                                      "centering": self.centering,
                                      "superscript": self.superscript})
                    # Nextline:
                    self.flush()
                    self.line.append({"x": self.cursor_x,
                                      "word": leftover_parts,
                                      "size": self.size,
                                      "weight": self.weight,
                                      "style": self.style,
                                      "centering": self.centering,
                                      "superscript": self.superscript})
                    self.cursor_x += get_measure(leftover_parts, self.size, self.weight, self.style) + space
            else:
                self.flush()
                self.line.append({"x": self.cursor_x,
                                  "word": word,
                                  "size": self.size,
                                  "weight": self.weight,
                                  "style": self.style,
                                  "centering": self.centering,
                                  "superscript": self.superscript})
                self.cursor_x += width + space

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
        # FIX: This doesn't preserve whitespace `isspace() return`
        elif element.tag == "pre":
            self.style = self.style.replace("mono", "").strip()
            self.pre = False

    def recurse(self, tree: Union[str, Text, Element]):
        if isinstance(tree, str):
            self.word(tree)
        elif isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree)
