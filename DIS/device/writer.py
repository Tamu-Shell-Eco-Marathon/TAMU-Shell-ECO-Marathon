import framebuf

class Writer:
    def __init__(self, device, font, verbose = True):
        self.device = device
        self.font = font

        # For this font: hmap() == True, reverse() == False
        # So we render as MONO_HMSB directly.
        self.map = framebuf.MONO_HLSB

        self.height = font.height()
        self.reverse = font.reverse()  # will be False here

        if verbose:
            print("Font height {} Hmap: {} Reverse: {}".format(
                self.height, font.hmap(), self.reverse))

        self.clip = True
        self.row_clip = False
        self.col_clip = False
        self.wrap = False
        self.col = 0
        self.row = 0
        self.cpos = 0
        self.tab = 0
        self.text_style = 0     #0 = normal, 1 = invert, 2 = underline

    # -------------- Position/style helpers ---------------------------

    def set_clip(self, clip, row_clip=False, col_clip=False):
        self.clip = clip
        self.row_clip = row_clip
        self.col_clip = col_clip

    def set_textpos(self, col, row):
        self.col = col
        self.row = row
     
    def set_style(self, style):
        self.text_style = style
    
    def home(self):
        self.set_textpos(0, 0)

    # ----------------- Printing ---------------------

    def _newline(self):
        self.col = 0
        self.row += self.height
        if self.row >= self.device.height:
            if self.row_clip:
                self.row = 0

    def printstring(self, s, invert=False):
        for c in s:
            self._printchar(c, invert)

    def _printchar(self, c, invert=False):
        if c == "\n":
            self._newline()
            return
        if c == "\t":
            self.col = (self.col + self.tab) // self.tab * self.tab
            return

        glyph, ht, wd = self.font.get_ch(c)
        if glyph is None:
            return  # unsupported character

        # Wrap / clip checks
        if self.col + wd > self.device.width:
            if self.wrap:
                # Only do newline if wrapping is enabled
                self._newline()
                if self.row + ht > self.device.height:
                    if self.row_clip:
                        return
                    else:
                        self.row = 0
            else:
                # No wrap: just draw and let the framebuffer clip.
                pass

        if self.row + ht > self.device.height:
            if self.row_clip:
                return
            else:
                self.row = 0

        # Color / style
        color = 1
        if invert:
            color = 0

        style = self.text_style
        if style & 1:
            color = 0 if color else 1

        buf = bytearray(glyph)   # memoryview → bytes
        fbc = framebuf.FrameBuffer(buf, wd, ht, self.map)

        self.device.blit(fbc, self.col, self.row, -1)

        if style & 2:
            self.device.line(self.col, self.row + ht - 1,
                             self.col + wd, self.row + ht - 1, color)

        self.col += wd

    # ------------ Metrics ------------

    def stringlen(self, s):
        l = 0
        for c in s:
            glyph, ht, wd = self.font.get_ch(c)
            if glyph:
                l += wd
        return l
