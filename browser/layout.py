from typing import Literal
import tkinter.font

HSTEP, VSTEP = 13, 18
SCROLLBAR_WIDTH = 12

class Text:
    def __init__(self, text):
        self.text = text

class Tag:
    def __init__(self, tag):
        self.tag = tag

class Layout:
    def __init__(self, tokens, width):
        self.display_list = []
        self.cursor_y = VSTEP
        self.cursor_x = HSTEP
        self.width = width
        self.weight: Literal["normal", "bold"] = "normal"
        self.style: Literal["roman", "italic"] = "roman"

        for tok in tokens:
            self.token(tok)

    def word(self, word):
        font = tkinter.font.Font(
            size=16,
            weight=self.weight,
            slant=self.style
        )
        width = font.measure(word)
        linebreak = font.metrics("linespace") * 1.25
        space = font.measure(" ")

        if self.cursor_x + width + space > self.width - SCROLLBAR_WIDTH:
            self.cursor_y += linebreak
            self.cursor_x = HSTEP

        self.display_list.append((self.cursor_x, self.cursor_y, word, font))
        self.cursor_x += width + space


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
