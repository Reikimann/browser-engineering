import tkinter as tk
from PIL import ImageTk, Image
import platform
import emoji

from browser.url import URL
from browser.layout import Layout, VSTEP, SCROLLBAR_WIDTH
from browser.html_parser import HTMLParser, Text, Element, print_tree

emoji_cache = {}

SCROLL_STEP = 100
WIDTH, HEIGHT = 800, 600


class Browser:
    def __init__(self):
        self.screen_width = WIDTH
        self.screen_height = HEIGHT
        self.blank = False
        self.nodes = []

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
        # TEST: Is this necesarry on windows or mac?
        if self.system == "Linux":
            self.window.bind("<Button-5>", self.scroll_linux)
            self.window.bind("<Button-4>", self.scroll_linux)
        else:
            self.window.bind("<MouseWheel>", self.scrollmouse)

        if not self.blank:
            self.window.bind("<Configure>", self.resize)

    def resize(self, e):
        self.screen_height, self.screen_width = e.height, e.width
        # FIX: Not debounced -> Performance: poor
        self.display_list = Layout(self.nodes, self.screen_width).display_list
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, c, f in self.display_list:
            if y > self.scroll + self.screen_height: continue
            if y + VSTEP < self.scroll: continue
            if emoji.is_emoji(c):
                codepoints = []
                for char in c:
                    # Format specifier: hexadecimal, 4 digits, zero-padding
                    codepoints.append("{:04x}".format(ord(char)).upper())
                emoji_png = "-".join(codepoints)
                if emoji_png not in emoji_cache:
                    image = Image.open(f"data/openmoji-72x72-color/{emoji_png}.png")
                    emoji_cache[emoji_png] = ImageTk.PhotoImage(image.resize((20, 20)))

                self.canvas.create_image(x, y - self.scroll, anchor="nw", image=emoji_cache[emoji_png])
            else:
                self.canvas.create_text(x, y - self.scroll, anchor="nw", text=c, font=f)

        if self.display_list and self.display_list[-1][1] + VSTEP > self.screen_height:
            self.draw_scrollbar()

    def load(self, url_str):
        url = URL(url_str)
        body = url.request()

        if body:
            # FIX: View-source
            if url.view_source:
                self.nodes = body.split()
            else:
                self.nodes = HTMLParser(body).parse()

            self.display_list = Layout(self.nodes, self.screen_width).display_list
            self.draw()
        else:
            self.blank = True
            self.display_list = []

    def draw_scrollbar(self):
        max_y = self.display_list[-1][1] + VSTEP
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

        max_y = self.display_list[-1][1]
        # Max_y gives the top of the last characters y-position
        content_height = max_y + VSTEP
        max_scroll = max(0, content_height - self.screen_height)
        self.scroll = min(self.scroll + SCROLL_STEP, max_scroll)
        self.draw()
