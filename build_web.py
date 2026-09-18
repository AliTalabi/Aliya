from pathlib import Path
import re

SRC = Path("Aliya.py").read_text(encoding="utf-8")

for old in [
    "import pgzrun\n",
    "import webbrowser\n",
    "import pyperclip\n",
    "import tkinter as tk\n",
    "from tkinter import messagebox\n",
    "from ctypes import windll\n",
]:
    SRC = SRC.replace(old, "", 1)

SRC = SRC.replace("from pgzero import clock, music\n", "")
SRC = SRC.replace("from pgzero.keyboard import keyboard\n", "")
SRC = SRC.replace("from pgzero.actor import Actor\n", "")
SRC = SRC.replace("from pgzero.loaders import sounds\n", "")

# Remove the Windows-only window manipulation by matching complete lines.
SRC = re.sub(r"(?m)^hwnd = pygame\.display\.get_wm_info\(\)\['window'\]\n", "", SRC)
SRC = re.sub(r"(?m)^windll\.user32\.MoveWindow\([^\n]*\)\n?", "", SRC)

# Replace the Tkinter cheat dialog with a harmless browser state transition.
SRC = re.sub(
    r"(?ms)^def hack_game\(\):\n.*?(?=^def shop_come\(\):)",
    'def hack_game():\n    global game_status\n    game_status = "starting_menu"\n\n\n',
    SRC,
    count=1,
)

SRC = re.sub(r"webbrowser\.open\([^\n]+\)", "pass", SRC)
SRC = re.sub(r"pyperclip\.copy\([^\n]+\)", "pass", SRC)
SRC = SRC.replace("pgzrun.go()\n", "")

ADAPTER = r'''
import asyncio
import os
import sys
import time
import pygame

pygame.init()
try:
    pygame.mixer.init()
except Exception:
    pass

_screen_surface = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(TITLE)
_image_cache = {}
_sound_cache = {}
_events = []
_running = True

def _find_asset(folder, name, extensions=()):
    name = str(name)
    candidates = [os.path.join(folder, name)]
    candidates.extend(os.path.join(folder, name + ext) for ext in extensions)
    for path in candidates:
        if os.path.isfile(path):
            return path
    if os.path.isdir(folder):
        wanted = name.lower()
        for entry in os.listdir(folder):
            stem, _ = os.path.splitext(entry)
            if entry.lower() == wanted or stem.lower() == wanted:
                return os.path.join(folder, entry)
    raise FileNotFoundError(f"Missing asset: {folder}/{name}")

def _load_image(name):
    key = str(name)
    if key not in _image_cache:
        image = pygame.image.load(
            _find_asset("images", key, (".png", ".jpg", ".jpeg", ".webp"))
        ).convert_alpha()
        _image_cache[key] = image
    return _image_cache[key]

class _Draw:
    def text(self, text, **kwargs):
        font = pygame.font.Font(None, int(kwargs.get("fontsize", 30)))
        color = pygame.Color(kwargs.get("color", "white"))
        surface = font.render(str(text), True, color)
        if "center" in kwargs:
            rect = surface.get_rect(center=tuple(map(int, kwargs["center"])))
        else:
            rect = surface.get_rect(
                topleft=tuple(map(int, kwargs.get("topleft", (0, 0))))
            )
        _screen_surface.blit(surface, rect)

class _Screen:
    def __init__(self):
        self.draw = _Draw()

    def blit(self, image, pos):
        _screen_surface.blit(_load_image(image), tuple(map(int, pos)))

    def fill(self, color):
        _screen_surface.fill(color)

screen = _Screen()
sys.modules["__main__"].screen = screen

class Actor:
    def __init__(self, image):
        self._image_name = str(image)
        self._surface = _load_image(self._image_name)
        self._x = 0.0
        self._y = 0.0
        self.angle = 0

    @property
    def image(self):
        return self._image_name

    @image.setter
    def image(self, value):
        self._image_name = str(value)
        self._surface = _load_image(self._image_name)

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self._x = float(value)

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        self._y = float(value)

    @property
    def pos(self):
        return self._x, self._y

    @pos.setter
    def pos(self, value):
        self._x = float(value[0])
        self._y = float(value[1])

    @property
    def width(self):
        return self._surface.get_width()

    @property
    def height(self):
        return self._surface.get_height()

    @property
    def rect(self):
        return self._surface.get_rect(center=(round(self._x), round(self._y)))

    def draw(self):
        surface = self._surface
        if self.angle:
            surface = pygame.transform.rotate(surface, self.angle)
        _screen_surface.blit(
            surface,
            surface.get_rect(center=(round(self._x), round(self._y))),
        )

    def collidepoint(self, pos):
        return self.rect.collidepoint(pos)

    def colliderect(self, other):
        return self.rect.colliderect(other.rect)

    def collidelist(self, actors):
        return self.rect.collidelist([actor.rect for actor in actors])

class _Clock:
    def schedule(self, fn, delay):
        _events.append([time.monotonic() + float(delay), 0.0, fn])

    def schedule_unique(self, fn, delay):
        _events[:] = [e for e in _events if e[2] is not fn]
        self.schedule(fn, delay)

    def schedule_interval(self, fn, interval):
        interval = float(interval)
        _events.append([time.monotonic() + interval, interval, fn])

    def tick(self):
        now = time.monotonic()
        due = []
        keep = []
        for event in _events:
            if now >= event[0]:
                due.append(event)
            else:
                keep.append(event)
        _events[:] = keep
        for _, interval, fn in due:
            fn()
            if interval > 0 and _running:
                _events.append([now + interval, interval, fn])

clock = _Clock()

class _Keyboard:
    def __getattr__(self, key):
        mapping = {
            "left": pygame.K_LEFT,
            "right": pygame.K_RIGHT,
            "up": pygame.K_UP,
            "down": pygame.K_DOWN,
        }
        if key not in mapping:
            return False
        return bool(pygame.key.get_pressed()[mapping[key]])

keyboard = _Keyboard()

class _Sound:
    def __init__(self, name):
        self.name = name

    def play(self):
        try:
            path = _find_asset("sounds", self.name, (".ogg", ".wav"))
            if self.name not in _sound_cache:
                _sound_cache[self.name] = pygame.mixer.Sound(path)
            _sound_cache[self.name].play()
        except Exception:
            pass

class _Sounds:
    def __getattr__(self, name):
        return _Sound(name)

sounds = _Sounds()

class _Music:
    def __init__(self):
        self.current = None

    def play(self, name):
        try:
            path = _find_asset("music", name, (".ogg", ".wav", ".mp3"))
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1)
            self.current = path
        except Exception:
            pass

    def stop(self):
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def pause(self):
        try:
            pygame.mixer.music.pause()
        except Exception:
            pass

    def unpause(self):
        try:
            pygame.mixer.music.unpause()
        except Exception:
            pass

music = _Music()

def quit():
    global _running
    _running = False

async def _main():
    global _running
    fps = pygame.time.Clock()
    while _running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                _running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                callback = globals().get("on_mouse_down")
                if callback:
                    callback(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                callback = globals().get("on_mouse_up")
                if callback:
                    callback(event.pos)

        clock.tick()
        update()
        _screen_surface.fill((0, 0, 0))
        draw()
        pygame.display.flip()
        fps.tick(60)
        await asyncio.sleep(0)
'''

marker = 'TITLE = "Aliya"\n'
if marker not in SRC:
    raise SystemExit("TITLE marker not found")

SRC = SRC.replace(marker, marker + ADAPTER + "\n", 1)

# The adapter is inserted before actors are constructed and the game loop is
# appended only after all original functions/callbacks have been defined.
SRC += "\nasyncio.run(_main())\n"

Path("main.py").write_text(SRC, encoding="utf-8")
Path("Aliya_web.py").write_text(SRC, encoding="utf-8")

compile(Path("main.py").read_text(encoding="utf-8"), "main.py", "exec")
print("Generated native pygame browser entrypoint:", len(SRC), "bytes")
