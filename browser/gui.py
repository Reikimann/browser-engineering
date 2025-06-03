import tkinter as tk
import platform

from browser.css_parser import CSSParser, cascade_priority, style, init_fonts
from browser.layout import DocumentLayout, paint_tree, Text
from browser.html_parser import Element, HTMLParser
from browser.constants import SCROLL_STEP, WIDTH, HEIGHT, VSTEP, SCROLLBAR_WIDTH

DEFAULT_STYLE_SHEET = CSSParser(open("data/browser.css").read()).parse()

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list


class Browser:
    def __init__(self):
        self.screen_width = WIDTH
        self.screen_height = HEIGHT
        self.blank = False
        self.nodes = []
        self.document = None
        self.url = None

        self.window = tk.Tk()
        init_fonts(self.window)
        self.canvas = tk.Canvas(
            self.window,
            width=self.screen_width,
            height=self.screen_height,
            bg="white"
        )
        self.canvas.pack(fill=tk.BOTH, expand=1)

        self.scroll = 0
        self.system = platform.system()

        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Button-1>", self.click)
        # TEST: Is this necesarry on windows or mac?
        if self.system == "Linux":
            self.window.bind("<Button-5>", self.scroll_linux)
            self.window.bind("<Button-4>", self.scroll_linux)
        else:
            self.window.bind("<MouseWheel>", self.scrollmouse)

        if not self.blank:
            self.window.bind("<Configure>", self.resize)

    # FIX: Not debounced -> Performance: poor
    def resize(self, e):
        self.screen_height, self.screen_width = e.height, e.width
        self.redraw()

    def redraw(self):
        self.document.layout(self.screen_width)
        self.display_list = []
        paint_tree(self.document, self.display_list)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for cmd in self.display_list:
            if cmd.top > self.scroll + self.screen_height: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll, self.canvas)

        if self.document.height > self.screen_height:
            self.draw_scrollbar()

    def load(self, url):
        self.url = url
        body = url.request()

        if not body:
            self.blank = True
            self.display_list = []
            return

        if url.view_source:
            parser = HTMLParser("")
            parser.add_tag("pre")
            for word in body.split(" "):
                parser.add_text(word + " ")
            self.nodes = parser.finish()
        else:
            self.nodes = HTMLParser(body).parse()

        rules = DEFAULT_STYLE_SHEET.copy()

        for node in tree_to_list(self.nodes, []):
            if not isinstance(node, Element): continue
            if node.tag == "link" and node.attributes.get("rel") == "stylesheet" and \
                    "href" in node.attributes:
                link = node.attributes["href"]
                style_url = url.resolve(link)
                try: # Ingores style sheets that fail to download
                    body = style_url.request()
                except Exception as e:
                    print(f"Error downloading {style_url}: {e}")
                    continue
                rules.extend(CSSParser(body).parse())
            elif node.tag == "style" and node.children:
                rules.extend(CSSParser(node.children[0].text).parse())

        style(self.nodes, sorted(rules, key=cascade_priority))
        self.scroll = 0
        self.document = DocumentLayout(self.nodes)
        self.redraw()

    def draw_scrollbar(self):
        percent_shown = self.screen_height / self.document.height # visible content
        percent_offset = self.scroll / self.document.height # fraction of content scrolled
        # if 20% is visible then scrollbar thumb should be 20% of screenheight
        scrollbar_height = percent_shown * self.screen_height

        x0 = self.screen_width - SCROLLBAR_WIDTH
        x1 = self.screen_width
        y0 = percent_offset * self.screen_height
        y1 = y0 + scrollbar_height

        self.canvas.create_rectangle(x0, y0, x1, y1, fill="blue")

    def click(self, e):
        x, y = e.x, e.y
        y += self.scroll

        objs = [obj for obj in tree_to_list(self.document, [])
                if obj.x <= x < obj.x + obj.width
                and obj.y <= y < obj.y + obj.height]
        if not objs: return

        elt = objs[-1].node
        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == "a" and "href" in elt.attributes:
                url = self.url.resolve(elt.attributes["href"])
                return self.load(url)
            elt = elt.parent

    def scrollup(self, _):
        self.scroll = max(0, self.scroll - SCROLL_STEP)
        self.draw()

    def scrolldown(self, _):
        max_y = max(self.document.height + 2*VSTEP - self.screen_height, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.draw()

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
