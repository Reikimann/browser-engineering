import tkinter
from url import URL
import platform

def lex(body):
    in_tag = False
    in_entity = False
    entity = ""
    text = ""

    for c in body:
        if in_entity:
            if c == ";":
                if entity == "lt":
                    text += "<"
                elif entity == "gt":
                    text += ">"
                else:
                    text += f"&{entity};"

                in_entity = False
                entity = ""
            else:
                entity += c
        elif c == "&":
            in_entity = True
            entity = ""
        elif c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            text += c

    return text

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18

SCROLL_STEP = 100

def layout(body):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    for c in body:
        if c == "\n":
            cursor_y += VSTEP
            cursor_x = HSTEP
        else:
            display_list.append((cursor_x, cursor_y, c))
            cursor_x += HSTEP

            if cursor_x >= WIDTH - HSTEP:
                cursor_y += VSTEP
                cursor_x = HSTEP

    return display_list

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()

        self.scroll = 0
        self.system = platform.system()

        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        if self.system == "Linux":
            self.window.bind("<Button-5>", self.scroll_linux)
            self.window.bind("<Button-4>", self.scroll_linux)
        else:
            self.window.bind("<MouseWheel>", self.scrollmouse)

    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=c)

    def load(self, url_str):
        url = URL(url_str)
        body = url.request()

        if url.view_source:
            self.display_list = layout(body)
        else:
            rendered_content = lex(body)
            self.display_list = layout(rendered_content)

        self.draw()

    def scroll_linux(self, e):
        if e.num == 5:
            self.scrolldown(e)
        elif e.num == 4:
            self.scrollup(e)

    # TODO: Handle mouse scrolling (Darwin and Windows)
    def scrollmouse(self, e):
        print(e.delta)
        pass

    # TODO: Handle overscroll (this is for keyboard)
    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()

    def scrollup(self, e):
        self.scroll = max(0, self.scroll - SCROLL_STEP)
        self.draw()
