import sys
import tkinter
from browser.gui import Browser
from browser.url import URL

if __name__ == "__main__":
    default_url = "file://data/homepage.html"
    url_str = sys.argv[1] if len(sys.argv) > 1 else default_url

    Browser().new_tab(URL(url_str))
    tkinter.mainloop()
