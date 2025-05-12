import sys
import tkinter
from browser.gui import Browser

if __name__ == "__main__":
    default_url = "file://homepage.html"
    url_str = sys.argv[1] if len(sys.argv) > 1 else default_url

    Browser().load(url_str)
    tkinter.mainloop()
