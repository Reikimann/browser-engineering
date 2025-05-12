import tkinter as tk
from PIL import ImageTk, Image
from url import URL
import platform
import emoji

emoji_cache = {}

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
SCROLLBAR_WIDTH = 12

def layout(body, width):
    display_list = []
    cursor_y, cursor_x = VSTEP, HSTEP

    for c in body:
        if c == "\n":
            cursor_y += VSTEP
            cursor_x = HSTEP
        else:
            display_list.append((cursor_x, cursor_y, c))
            cursor_x += HSTEP

            if cursor_x >= width - HSTEP:
                cursor_y += VSTEP
                cursor_x = HSTEP

    return display_list

class Browser:
    def __init__(self):
        self.screen_width = WIDTH
        self.screen_height = HEIGHT
        self.raw_text = ""
        self.blank = False

        self.window = tk.Tk()
        self.canvas = tk.Canvas(
            self.window,
            width=self.screen_width,
            height=self.screen_height
        )
        self.canvas.pack(fill=tk.BOTH, expand=1)

        self.scroll = 0
        self.system = platform.system()

        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        if self.system == "Linux":
            self.window.bind("<Button-5>", self.scroll_linux)
            self.window.bind("<Button-4>", self.scroll_linux)
        else:
            self.window.bind("<MouseWheel>", self.scrollmouse)

        if not self.blank:
            self.window.bind("<Configure>", self.resize)

    def resize(self, e):
        self.screen_height, self.screen_width = e.height, e.width
        self.redraw()

    def redraw(self):
        # This is not debounced. Performance: poor
        if self.raw_text:
            self.display_list = layout(self.raw_text, self.screen_width)

        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            if y > self.scroll + self.screen_height: continue
            if y + VSTEP < self.scroll: continue
            # FIX: This doesnt work on multi-codepoint emojis
            # Use emoji.is_emoji(word) check this with full words
            if (c in emoji.EMOJI_DATA):
                codepoints = []
                for char in c:
                    # Format specifier: hexadecimal, 4 digits, zero-padding
                    codepoints.append("{:04x}".format(ord(char)).upper())
                emoji_png = "-".join(codepoints)
                if emoji_png not in emoji_cache:
                    image = Image.open(f"openmoji-72x72-color/{emoji_png}.png")
                    emoji_cache[emoji_png] = ImageTk.PhotoImage(image.resize((16, 16)))

                self.canvas.create_image(x, y - self.scroll, anchor="nw", image=emoji_cache[emoji_png])
            else:
                self.canvas.create_text(x, y - self.scroll, text=c)

        if self.display_list and max(y for _, y, _ in self.display_list) + VSTEP > self.screen_height:
            self.draw_scrollbar()

    def load(self, url_str):
        url = URL(url_str)
        body = url.request()

        if body:
            if url.view_source:
                self.raw_text = body
            else:
                self.raw_text = lex(body)

            self.display_list = layout(self.raw_text, self.screen_width)

            self.draw()
        else:
            self.blank = True
            self.display_list = []

    def draw_scrollbar(self):
        max_y = max(y for _, y, _ in self.display_list) + VSTEP
        percent_shown = self.screen_height / max_y # visible content
        percent_offset = self.scroll / max_y # fraction of content scrolled
        # if 20% is visible then scrollbar thumb should be 20% of screenheight
        scrollbar_height = percent_shown * self.screen_height

        x0 = self.screen_width - SCROLLBAR_WIDTH
        x1 = self.screen_width
        y0 = percent_offset * self.screen_height
        y1 = y0 + scrollbar_height

        self.canvas.create_rectangle(x0, y0, x1, y1, fill="blue")

    def scroll_linux(self, e):
        if e.num == 5:
            self.scrolldown(e)
        elif e.num == 4:
            self.scrollup(e)

    # NOTE: Darwin and Windows scrolling not tested
    # It's currently possible to scroll past bottom
    def scrollmouse(self, e):
        print(e)
        if self.system == "Windows":
            delta = -1 * (e.delta // 120)
        elif self.system == "Darwin":
            delta = e.delta
        else:
            delta = 0

        self.scroll += delta * SCROLL_STEP
        self.scroll = max(0, self.scroll)
        self.draw()

    def scrollup(self, e):
        self.scroll = max(0, self.scroll - SCROLL_STEP)
        self.draw()

    def scrolldown(self, e):
        if not self.display_list:
            return

        max_y = max(y for _, y, _ in self.display_list)
        # Max_y gives the top of the last characters y-position
        content_height = max_y + VSTEP
        max_scroll = max(0, content_height - self.screen_height)
        self.scroll = min(self.scroll + SCROLL_STEP, max_scroll)
        self.draw()
