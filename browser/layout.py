from typing import Literal
import tkinter.font

HSTEP, VSTEP = 13, 18
SCROLLBAR_WIDTH = 12

font_cache = {}
measure_cache = {}

def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in font_cache:
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


class Text:
    def __init__(self, text):
        self.text = text

class Tag:
    def __init__(self, tag):
        self.tag = tag

class Layout:
    def __init__(self, tokens, screen_width):
        self.display_list = []
        # [{ x: , word: , size: , weight: , style: , centering: , superscript: ,}]
        self.line = []

        self.cursor_y: float = VSTEP
        self.cursor_x: float = HSTEP
        self.screen_width: int = screen_width

        self.weight: Literal["normal", "bold"] = "normal"
        self.style: Literal["roman", "italic"] = "roman"
        self.size: int = 12

        self.centering: bool = False
        self.superscript: bool = False

        for tok in tokens:
            self.token(tok)

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
        width = get_measure(word, self.size, self.weight, self.style)
        space = get_measure(" ", self.size, self.weight, self.style)

        if self.cursor_x + width < self.screen_width - HSTEP - SCROLLBAR_WIDTH:
            if "\u00AD" in word:
                word = word.replace("\u00AD", "")

            self.line.append({"x": self.cursor_x,
                              "word": word,
                              "size": self.size,
                              "weight": self.weight,
                              "style": self.style,
                              "centering": self.centering,
                              "superscript": self.superscript})
            self.cursor_x += width + space
        else:
            if "\u00AD" in word:
                parts = word.split("\u00AD")
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

                leftover_parts = "".join([p for p in parts if p not in fitted_parts])
                self.line.append({"x": self.cursor_x,
                                  "word": "-",
                                  "size": self.size,
                                  "weight": self.weight,
                                  "style": self.style,
                                  "centering": self.centering,
                                  "superscript": self.superscript})
                # Nextline:
                self.flush()
                self.cursor_x = HSTEP
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

    def token(self, tok):
        if isinstance(tok, str):
            self.word(tok)
        elif isinstance(tok, Text):
            for word in tok.text.split():
                self.word(word)
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "sup":
            self.superscript = True
            self.size = int(self.size / 2)
        elif tok.tag == "/sup":
            self.superscript = False
            self.size = int(self.size * 2)
        elif tok.tag == "br" or tok.tag == "br /":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP
        elif tok.tag.startswith("h1"):
            self.size = int(self.size * 1.5)
            if 'class="title"' in tok.tag:
                self.centering = True
        elif tok.tag == '/h1':
            self.size = int(self.size / 1.5)
            self.centering = False
