from PIL import ImageTk, Image
emoji_cache = {}


class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.color = color
        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            fill=self.color,
            anchor="nw")


class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=0,
            fill=self.color)


class DrawEmoji:
    def __init__(self, x1, y1, emoji):
        self.size = 24
        self.top = y1
        self.left = x1
        self.bottom = y1 + self.size
        self.emoji = emoji

    def execute(self, scroll, canvas):
        codepoints = []
        for char in self.emoji:
            # Format specifier: hexadecimal, 4 digits, zero-padding
            codepoints.append("{:04x}".format(ord(char)).upper())
        emoji_png = "-".join(codepoints)

        if emoji_png not in emoji_cache:
            image = Image.open(f"data/openmoji-72x72-color/{emoji_png}.png")
            emoji_cache[emoji_png] = ImageTk.PhotoImage(image.resize((self.size, self.size)))

        canvas.create_image(
            self.left, self.top - scroll,
            anchor="nw",
            image=emoji_cache[emoji_png])
