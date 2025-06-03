import tkinter as tk
import platform

from browser.css_parser import CSSParser, cascade_priority, style, init_fonts
from browser.layout import DocumentLayout, paint_tree, Text
from browser.html_parser import Element, HTMLParser
from browser.constants import SCROLL_STEP, WIDTH, HEIGHT, VSTEP, SCROLLBAR_WIDTH
from browser.url import URL

DEFAULT_STYLE_SHEET = CSSParser(open("data/browser.css").read()).parse()

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list


class Browser:
    def __init__(self):
        self.tabs = []
        self.active_tab: Tab

        self.height = HEIGHT
        self.width = WIDTH
        self.window = tk.Tk()
        init_fonts(self.window)
        self.canvas = tk.Canvas(self.window,
                                width=self.width,
                                height=self.height,
                                bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=1)

        self.system_platform = platform.system()

        self.window.bind("<Down>", self.handle_down)
        self.window.bind("<Up>", self.handle_up)
        self.window.bind("<Button-1>", self.handle_click)
        # TEST: Is this necesarry on windows or mac?
        if self.system_platform == "Linux":
            self.window.bind("<Button-5>", self.handle_scroll_linux)
            self.window.bind("<Button-4>", self.handle_scroll_linux)
        else:
            self.window.bind("<MouseWheel>", self.handle_scroll_mouse)
        self.window.bind("<Configure>", self.handle_resize)

    def new_tab(self, url):
        new_tab = Tab()
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        self.active_tab.draw(self.canvas, self.width, self.height)

    def handle_resize(self, e):
        self.width, self.height = e.width, e.height
        self.active_tab.resize(self.width)
        self.draw()

    def handle_scroll_mouse(self, e):
        self.active_tab.scrollmouse(e.delta, self.system_platform)
        self.draw()

    def handle_scroll_linux(self, e):
        if e.num == 5:
            self.active_tab.scrolldown(self.height)
        elif e.num == 4:
            self.active_tab.scrollup()
        self.draw()

    def handle_click(self, e):
        self.active_tab.click(e.x, e.y)
        self.draw()

    def handle_down(self, _):
        self.active_tab.scrolldown(self.height)
        self.draw()

    def handle_up(self, _):
        self.active_tab.scrollup()
        self.draw()


class Tab:
    def __init__(self):
        self.blank = False
        self.nodes = []
        self.document: DocumentLayout
        self.url: URL
        self.scroll = 0

    # FIX: Not debounced -> Performance: poor
    def resize(self, width):
        self.document.layout(width)
        self.display_list = []
        paint_tree(self.document, self.display_list)

    def draw(self, canvas, width, height):
        for cmd in self.display_list:
            if cmd.top > self.scroll + height: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll, canvas)

        if self.document.height > height:
            self.draw_scrollbar(canvas,  width, height)

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
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)

    def draw_scrollbar(self, canvas, width, height):
        percent_shown = height / self.document.height # visible content
        percent_offset = self.scroll / self.document.height # fraction of content scrolled
        # if 20% is visible then scrollbar thumb should be 20% of screenheight
        scrollbar_height = percent_shown * height

        x0 = width - SCROLLBAR_WIDTH
        x1 = width
        y0 = percent_offset * height
        y1 = y0 + scrollbar_height

        canvas.create_rectangle(x0, y0, x1, y1, fill="blue")

    def click(self, x, y):
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

    def scrollup(self):
        self.scroll = max(0, self.scroll - SCROLL_STEP)

    def scrolldown(self, height):
        max_y = max(self.document.height + 2*VSTEP - height, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)

    # NOTE: Darwin and Windows scrolling not tested
    # It's currently possible to scroll past bottom
    def scrollmouse(self, delta, platform):
        if platform == "Windows":
            delta = -1 * (delta // 120)
        elif platform == "Darwin":
            delta = delta
        else:
            delta = 0

        self.scroll += delta * SCROLL_STEP
        self.scroll = max(0, self.scroll)
