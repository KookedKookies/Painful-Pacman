
import json
import math
import os
import random
import sys
import asyncio
from array import array
from collections import deque

import pygame



W, H = 31, 29
T = 24
TOP = 44
PANEL = 96
FPS = 60

UP, LEFT, DOWN, RIGHT = 0, 1, 2, 3
DIRS = [(0, -1), (-1, 0), (0, 1), (1, 0)]
REVERSE = {UP: DOWN, LEFT: RIGHT, DOWN: UP, RIGHT: LEFT}
DIR_NAMES = ["UP", "LEFT", "DOWN", "RIGHT"]

HOUSE_DOOR = (15, 12)
HOUSE_EXIT = (15, 11)
HOUSE_HOME = (15, 14)
PAC_START = (15, 25)

KEYS = {
    pygame.K_UP: UP, pygame.K_w: UP,
    pygame.K_LEFT: LEFT, pygame.K_a: LEFT,
    pygame.K_DOWN: DOWN, pygame.K_s: DOWN,
    pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT,
}


GHOST_NAMES = [
    "BLINKY", "PINKY", "INKY", "CLYDE",
    "VIOLET", "TOXIC", "PHANTOM", "BRUTE", "FROST",
    "FLASH", "SHADE", "TRACKER", "TRAPPER", "HUNTER",
    "MIRROR", "MIMIC", "WARP", "SPLITTER", "VOID",
]
GHOST_ROLES = [
    "CHASER", "AMBUSHER", "INTERCEPTOR", "CUTTER",
    "COPYCAT", "HAZARD", "PHASER", "CHARGER", "SLOWER",
    "SPEEDSTER", "INVISIBLE", "TRACKER", "TRAPPER", "HUNTER",
    "MIRROR", "MIMIC", "WARP", "SPLITTER", "VOID",
]
GHOST_COLORS = [
    (255, 48, 48),      # Blinky
    (255, 184, 255),    # Pinky
    (0, 224, 255),      # Inky
    (255, 184, 80),     # Clyde
    (170, 55, 255),     # Violet
    (55, 235, 80),      # Toxic
    (245, 245, 255),    # Phantom
    (145, 85, 45),      # Brute
    (120, 220, 255),    # Frost
    (255, 225, 40),     # Flash
    (105, 105, 115),    # Shade
    (20, 150, 75),      # Tracker
    (255, 125, 25),     # Trapper
    (185, 35, 45),      # Hunter
    (255, 120, 190),    # Mirror
    (255, 205, 55),     # Mimic
    (55, 100, 255),     # Warp
    (220, 40, 230),     # Splitter
    (20, 20, 25),       # Void
]

SCATTER_TARGETS = [
    (W - 2, 1), (1, 1), (W - 2, H - 2), (1, H - 2),
    (W // 2, 2), (W // 2, H - 3), (3, H // 2), (W - 4, H // 2),
    (W // 3, 2), (2 * W // 3, 2), (W // 3, H - 3), (2 * W // 3, H - 3),
    (W // 2, H // 2), (W // 4, H // 2), (3 * W // 4, H // 2),
    (W // 2 - 5, H // 2), (W // 2 + 5, H // 2), (W // 2, H // 2 - 5),
    (W // 2, H // 2 + 5),
]
PATROL_TILES = [(7, 7), (23, 7), (7, 21), (23, 21)]     .
FRUIT_SPOTS = [(15, 5), (5, 15), (25, 15), (15, 21), (9, 9), (21, 9)]

FRUIT_TYPES = [
    ("CHERRY", 100), ("STRAWBERRY", 300), ("ORANGE", 500), ("APPLE", 700),
    ("MELON", 1000), ("GALAXIAN", 2000), ("BELL", 3000), ("KEY", 5000),
]


PELLET_TYPES = {
    "normal": dict(mult=1.0, color=(255, 216, 176), radius=7, label="POWER PELLET"),
    "mega":   dict(mult=1.7, color=(255, 210, 40),  radius=9, label="MEGA PELLET!"),
    "risk":   dict(mult=0.4, color=(255, 70, 70),   radius=6, label="RISK PELLET - HURRY!"),
    "chain":  dict(mult=1.0, color=(200, 90, 255),  radius=7, label="CHAIN PELLET - NEARBY GHOSTS ONLY"),
}

DIFFICULTIES = {
    1: dict(name="EASY", iq=(1, 1, 1, 1), prediction=0.0, speed=0.00, fright=1.30,
            gates=0, oneways=0, secrets=0, tele=1, fake=0.00, hunt=0),
    2: dict(name="HARD", iq=(2, 2, 3, 2), prediction=1.0, speed=0.08, fright=1.00,
            gates=3, oneways=3, secrets=1, tele=1, fake=0.08, hunt=8),
    3: dict(name="BRUTAL", iq=(5, 4, 4, 3), prediction=2.0, speed=0.16, fright=0.80,
            gates=6, oneways=5, secrets=2, tele=2, fake=0.15, hunt=14),
    4: dict(name="NIGHTMARE", iq=(6, 6, 6, 6), prediction=3.5, speed=0.24, fright=0.60,
            gates=9, oneways=7, secrets=4, tele=2, fake=0.22, hunt=20),
}

HABIT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pacman_habits.json")


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def dir_index(dx, dy):
    for i, (x, y) in enumerate(DIRS):
        if (x, y) == (dx, dy):
            return i
    return None


def turn_index(cur, new):
    """0 straight, 1 left, 2 right, 3 back (relative to travel direction)."""
    return (0, 1, 3, 2)[(new - cur) % 4]


def bfs(src, adj, limit=10 ** 9):
    dist = {src: 0}
    dq = deque([src])
    while dq:
        u = dq.popleft()
        du = dist[u]
        if du >= limit:
            continue
        for v in adj.get(u, ()):
            if v not in dist:
                dist[v] = du + 1
                dq.append(v)
    return dist


def build_schedule(level, diff):
    """Idea 16: SCATTER, CHASE, SCATTER, CHASE, SCATTER, CHASE, then HUNT/CHASE cycles."""
    def sc(t):
        return max(2.0, t * (1.0 - 0.06 * (level - 1)))
    chase = 20.0 + 2.0 * (level - 1)
    sched = [("scatter", sc(7)), ("chase", chase), ("scatter", sc(7)), ("chase", chase),
             ("scatter", sc(5)), ("chase", chase + 2)]
    hunt = DIFFICULTIES[diff]["hunt"]
    if hunt > 0:
        for _ in range(40):
            sched += [("hunt", hunt + 2.0 * (level - 1)), ("chase", 8.0)]
    else:
        sched.append(("chase", 99999.0))
    return sched



class SoundFX:
    """Generates simple arcade-style sounds in memory (no files needed)."""

    def __init__(self):
        self.enabled = False
        self.muted = False
        self.sounds = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            self.enabled = True
            self._build_sounds()
        except Exception:
            self.enabled = False

    def _tone(self, frequencies, duration=0.08, volume=0.18):
        if not self.enabled:
            return None
        sample_rate = 44100
        count = max(1, int(sample_rate * duration))
        buf = array("h")
        if not isinstance(frequencies, (list, tuple)):
            frequencies = [frequencies]
        for i in range(count):
            t = i / sample_rate
            fade = min(1.0, i / (sample_rate * 0.008))
            fade *= min(1.0, (count - i) / (sample_rate * 0.02))
            freq = frequencies[min(len(frequencies) - 1, int(i / count * len(frequencies)))]
            value = math.sin(2 * math.pi * freq * t)
            buf.append(int(32767 * volume * fade * value))
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build_sounds(self):
        s = self.sounds
        s["start"] = self._tone([440, 554, 659, 880], 0.24, 0.16)
        s["waka1"] = self._tone([430], 0.045, 0.13)
        s["waka2"] = self._tone([300], 0.045, 0.13)
        s["power"] = self._tone([260, 390, 520, 780], 0.20, 0.18)
        s["ghost"] = self._tone([740, 1040], 0.12, 0.18)
        s["fruit"] = self._tone([600, 900, 1200], 0.18, 0.20)
        s["death"] = self._tone([500, 430, 360, 290, 220], 0.45, 0.18)
        s["win"] = self._tone([523, 659, 784, 1047, 1319], 0.55, 0.18)
        s["level"] = self._tone([392, 523, 659, 784], 0.30, 0.16)
        s["tele"] = self._tone([700, 300, 900], 0.15, 0.14)
        s["hunt"] = self._tone([130, 98, 130, 98], 0.50, 0.20)
        s["bad"] = self._tone([220, 165, 130], 0.30, 0.18)
        s["gate"] = self._tone([180], 0.07, 0.12)

    def play(self, name):
        if self.enabled and not self.muted and self.sounds.get(name):
            try:
                self.sounds[name].play()
            except Exception:
                pass

    def toggle(self):
        self.muted = not self.muted
        return not self.muted




class Habits:
    """
    What the ghosts have OBSERVED about the player. Only past behaviour is
    stored. The global part is saved between sessions; the per-maze part
    (tile statistics, heat map, tunnel usage) resets with each new maze.
    """
    SAVE_KEYS = ("turns", "dir_choice", "escape", "corner_time", "dir_time")

    def __init__(self, persist=True):
        self.persist = persist
        self.turns = [1.0, 0.5, 0.5, 0.1]        # straight, left, right, back
        self.dir_choice = [0.5] * 4              # absolute direction picked at junctions
        self.escape = [0.5] * 4                  # direction picked while a ghost was close
        self.corner_time = [0.0] * 4             # seconds spent in TL, TR, BL, BR
        self.dir_time = [0.0] * 4
        self.records = 0
        self.new_maze()

    def new_maze(self):
        self.tile = {}       # junction tile -> [count per direction]
        self.tunnels = {}    # tunnel / teleporter entry tile -> uses
        self.heat = {}       # tile -> decaying visit heat (route memory)
        self.heat_t = 0.0

   
    def visit(self, t):
        self.heat[t] = self.heat.get(t, 0.0) + 1.0

    def tick(self, dt):
        self.heat_t += dt
        if self.heat_t >= 1.0:
            self.heat_t = 0.0
            for k in list(self.heat):
                v = self.heat[k] * 0.965
                if v < 0.05:
                    del self.heat[k]
                else:
                    self.heat[k] = v

    def record(self, tile, cur, new, escaping):
        tc = self.tile.setdefault(tile, [0.0] * 4)
        tc[new] += 1.0
        self.turns[turn_index(cur, new)] += 1.0
        self.dir_choice[new] += 1.0
        if escaping:
            self.escape[new] += 1.0
        self.records += 1
        if self.records % 25 == 0:      # gentle forgetting so the ghosts can re-adapt
            for arr in (self.turns, self.dir_choice, self.escape):
                for i in range(4):
                    arr[i] *= 0.96

    def record_tunnel(self, entry):
        self.tunnels[entry] = self.tunnels.get(entry, 0) + 1


    def probs(self, tile, cur, exits):
        """Probability of each exit at a junction: [(direction, p), ...]."""
        gl = []
        dsum = sum(self.dir_choice)
        for k in exits:
            dnorm = self.dir_choice[k] / dsum * 4.0
            gl.append(max(0.01, self.turns[turn_index(cur, k)] * dnorm))
        gs = sum(gl)
        p_global = [v / gs for v in gl]
        tc = self.tile.get(tile)
        tot = sum(tc[k] for k in exits) if tc else 0.0
        out = []
        for idx, k in enumerate(exits):
            if tot > 0:
                alpha = tot / (tot + 2.0)
                p = alpha * tc[k] / tot + (1.0 - alpha) * p_global[idx]
            else:
                p = p_global[idx]
            out.append((k, p))
        return out

    def predictability(self):
        if self.records < 8:
            return 0.3
        s = self.turns[:3]
        return clamp((max(s) / sum(s) - 0.34) / 0.5)

    def fav_dir(self):
        return max(range(4), key=lambda i: self.dir_time[i]) if sum(self.dir_time) > 10 else None

    def fav_escape(self):
        if sum(self.escape) - 2.0 < 3.0:
            return None
        return max(range(4), key=lambda i: self.escape[i])

    def fav_corner(self):
        if sum(self.corner_time) < 20.0:
            return None
        return max(range(4), key=lambda i: self.corner_time[i])

    def fav_tunnel_entry(self):
        if not self.tunnels:
            return None
        e = max(self.tunnels, key=lambda k: self.tunnels[k])
        return e if self.tunnels[e] >= 2 else None

    def turn_percent(self):
        s = self.turns[:3]
        tot = sum(s)
        return [int(round(100 * v / tot)) for v in s]

    # ---- persistence -----------------------------------------------
    @classmethod
    def load(cls, path=HABIT_FILE):
        h = cls()
        try:
            with open(path, "r") as f:
                d = json.load(f)
            for k in cls.SAVE_KEYS:
                cur = getattr(h, k)
                if k in d and len(d[k]) == len(cur):
                    setattr(h, k, [float(v) for v in d[k]])
            h.records = int(d.get("records", 0))
        except Exception:
            pass
        return h

    def save(self, path=HABIT_FILE):
        if not self.persist:
            return
        try:
            d = {k: getattr(self, k) for k in self.SAVE_KEYS}
            d["records"] = self.records
            with open(path, "w") as f:
                json.dump(d, f)
        except Exception:
            pass

    def forget(self, path=HABIT_FILE):
        self.__init__(self.persist)
        try:
            if self.persist and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


class Maze:


    def __init__(self, level, difficulty):
        self.level = level
        self.difficulty = difficulty
        self.cfg = DIFFICULTIES[difficulty]
        self.seed = 1337 + (level - 1) * 101
        self.rng = random.Random(self.seed)
        self.grid = self._base()
        self.links = {}          # tunnel + teleporter partners (for habit tracking)
        self.tele = {}           # teleporter tile -> partner tile (graph edges)
        self.tele_id = {}
        self.gates = []
        self.oneway = {}
        self.secret = set()
        self.power = {}
        self.snap_cache = {}
        self._tunnels()
        self._teleporters()
        self._power_pellets()
        self._build_graphs()
        self._place_features()
        self._build_graphs()
        self.pellets = sum(row.count(".") + row.count("o") for row in self.grid)

    # ---- base layout -------------------------------------------------
    def _base(self):
        rng = self.rng
        g = [['#'] * W for _ in range(H)]

        def in_house(x, y):
            return 11 <= x <= 19 and 12 <= y <= 16

        stack = [(1, 1)]
        g[1][1] = '.'
        while stack:
            x, y = stack[-1]
            choices = []
            for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                nx, ny = x + dx, y + dy
                if 1 <= nx < W - 1 and 1 <= ny < H - 1 and g[ny][nx] == '#' and not in_house(nx, ny):
                    choices.append((nx, ny, dx, dy))
            if choices:
                nx, ny, dx, dy = rng.choice(choices)
                g[y + dy // 2][x + dx // 2] = '.'
                g[ny][nx] = '.'
                stack.append((nx, ny))
            else:
                stack.pop()

        for y in range(2, H - 2):
            for x in range(2, W - 2):
                if g[y][x] == '#' and (x + y) % 2 == 1 and not (10 <= x <= 20 and 11 <= y <= 17):
                    horizontal = g[y][x - 1] == '.' and g[y][x + 1] == '.'
                    vertical = g[y - 1][x] == '.' and g[y + 1][x] == '.'
                    if (horizontal or vertical) and rng.random() < 0.18:
                        g[y][x] = '.'

 
        for y in range(12, 17):
            for x in range(11, 20):
                g[y][x] = '#'
        for y in range(13, 16):
            for x in range(12, 19):
                g[y][x] = ' '
        g[12][15] = '-'

        # Player spawn lane.
        for y in range(17, 26):
            g[y][15] = '.'
        for x in range(11, 20):
            g[25][x] = '.'

        # Solid border.
        for x in range(W):
            g[0][x] = g[H - 1][x] = '#'
        for y in range(H):
            g[y][0] = g[y][W - 1] = '#'
        g[PAC_START[1]][PAC_START[0]] = ' '
        return g

    def _tunnels(self):
        for row in (9, 21):
            self.grid[row][0] = ' '
            self.grid[row][W - 1] = ' '
            self.links[(0, row)] = (W - 1, row)
            self.links[(W - 1, row)] = (0, row)

    def _teleporters(self):
        # Pick teleporter endpoints from the actual maze instead of using
        # hard-coded coordinates.  They are regenerated for every level.
        # Keep them away from the spawn, ghost house, power pellets, and each
        # other so the portals are genuinely spread around the maze.
        candidates = []
        excluded = {PAC_START, HOUSE_EXIT, HOUSE_DOOR, HOUSE_HOME}
        excluded.update({(1, 1), (W - 2, 1), (1, H - 2), (W - 2, H - 2)})
        for y in range(1, H - 1):
            for x in range(1, W - 1):
                if self.grid[y][x] not in '. ':
                    continue
                if (x, y) in excluded:
                    continue
                # Avoid putting a portal immediately inside the ghost house
                # or directly beside the player's starting lane.
                if 10 <= x <= 20 and 11 <= y <= 17:
                    continue
                if abs(x - PAC_START[0]) + abs(y - PAC_START[1]) < 8:
                    continue
                candidates.append((x, y))

        self.rng.shuffle(candidates)
        chosen = []
        min_gap = 7
        for c in candidates:
            if all(abs(c[0] - q[0]) + abs(c[1] - q[1]) >= min_gap for q in chosen):
                chosen.append(c)
                if len(chosen) >= self.cfg["tele"] * 2:
                    break

        # If the maze is unusually cramped, relax the spacing rather than
        # failing to create the requested number of teleporters.
        if len(chosen) < self.cfg["tele"] * 2:
            for c in candidates:
                if c not in chosen:
                    chosen.append(c)
                    if len(chosen) >= self.cfg["tele"] * 2:
                        break

        for pid in range(self.cfg["tele"]):
            a, b = chosen[pid * 2], chosen[pid * 2 + 1]
            for t in (a, b):
                self.grid[t[1]][t[0]] = ' '
                self.tele_id[t] = pid
            self.tele[a] = b
            self.tele[b] = a
            self.links[a] = b
            self.links[b] = a

    def _power_pellets(self):
        corners = [(1, 1), (W - 2, 1), (1, H - 2), (W - 2, H - 2)]
        if self.difficulty == 1:
            kinds = ["normal", "normal", "mega", "normal"]
        else:
            kinds = ["normal", "mega", "risk", "chain"]
            self.rng.shuffle(kinds)
        for (x, y), k in zip(corners, kinds):
            self.grid[y][x] = 'o'
            self.power[(x, y)] = k

    # ---- graphs ------------------------------------------------------
    def _adj(self, passable):
        adj = {}
        for y in range(H):
            for x in range(W):
                if self.grid[y][x] in passable:
                    lst = []
                    for dx, dy in DIRS:
                        nx, ny = (x + dx) % W, y + dy
                        if 0 <= ny < H and self.grid[ny][nx] in passable:
                            lst.append((nx, ny))
                    if (x, y) in self.tele:
                        lst.append(self.tele[(x, y)])
                    adj[(x, y)] = lst
        return adj

    def _build_graphs(self):
        self.adj_pac = self._adj(". o")
        self.adj_gh = self._adj(". oS")
        self.adj_dead = self._adj(". oS-")
        self.base_reach = set(bfs(PAC_START, self.adj_pac))
        self.reach_gh = set(bfs(HOUSE_EXIT, self.adj_gh))
        self.dist_home = bfs(HOUSE_HOME, self.adj_dead)

    def snap(self, t):
        x = max(0, min(W - 1, int(round(t[0]))))
        y = max(0, min(H - 1, int(round(t[1]))))
        if (x, y) in self.reach_gh:
            return (x, y)
        r = self.snap_cache.get((x, y))
        if r is None:
            r = min(self.reach_gh, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2)
            self.snap_cache[(x, y)] = r
        return r

    def _is_open(self, x, y):
        return 0 <= y < H and self.grid[y][x % W] in ". o"

    def _pac_ok(self):
        """Every reachable tile must stay strongly connected under the one-way rules."""
        nodes = self.base_reach
        fwd = {}
        rev = {u: [] for u in nodes}
        for u in nodes:
            lst = []
            for v in self.adj_pac[u]:
                ow = self.oneway.get(v)
                if ow:
                    dx, dy = v[0] - u[0], v[1] - u[1]
                    if abs(dx) == W - 1:
                        dx = -1 if dx > 0 else 1
                    if (dx, dy) != ow:
                        continue
                lst.append(v)
                rev[v].append(u)
            fwd[u] = lst
        return (len(bfs(PAC_START, fwd)) == len(nodes) and
                len(bfs(PAC_START, rev)) == len(nodes))

    def _place_features(self):
        rng = self.rng
        cfg = self.cfg
        used = list(self.tele.keys()) + list(self.power.keys())

        def far_enough(c, d=4):
            return all(abs(c[0] - u[0]) + abs(c[1] - u[1]) >= d for u in used)

        corridors = []
        for (x, y) in sorted(self.base_reach):
            if x in (0, W - 1):
                continue
            if abs(x - PAC_START[0]) + abs(y - PAC_START[1]) < 7:
                continue
            if abs(x - HOUSE_EXIT[0]) + abs(y - HOUSE_EXIT[1]) < 5:
                continue
            o = self._is_open
            horiz = o(x - 1, y) and o(x + 1, y) and not o(x, y - 1) and not o(x, y + 1)
            vert = o(x, y - 1) and o(x, y + 1) and not o(x - 1, y) and not o(x + 1, y)
            if horiz or vert:
                corridors.append(((x, y), horiz))
        rng.shuffle(corridors)

        # Moving walls: gates that close and reopen on their own rhythm.
        n = 0
        for c, horiz in corridors:
            if n >= cfg["gates"]:
                break
            if far_enough(c, 5):
                self.gates.append(dict(pos=c, period=rng.uniform(9.0, 13.0),
                                       phase=rng.uniform(0.0, 12.0)))
                used.append(c)
                n += 1

        # One-way passages (never allowed to break connectivity).
        n = 0
        for c, horiz in corridors:
            if n >= cfg["oneways"]:
                break
            if c in used or not far_enough(c, 4):
                continue
            d = (rng.choice((-1, 1)), 0) if horiz else (0, rng.choice((-1, 1)))
            self.oneway[c] = d
            if self._pac_ok():
                used.append(c)
                n += 1
            else:
                del self.oneway[c]

        # Fake-safe areas: a dead end that secretly has a ghost-only door behind it.
        n = 0
        dead_ends = [t for t in sorted(self.base_reach)
                     if len(self.adj_pac[t]) == 1 and t not in self.tele and t not in self.power
                     and abs(t[0] - PAC_START[0]) + abs(t[1] - PAC_START[1]) > 8]
        rng.shuffle(dead_ends)
        for (x, y) in dead_ends:
            if n >= cfg["secrets"]:
                break
            nx, ny = self.adj_pac[(x, y)][0]
            dx, dy = x - nx, y - ny
            wx, wy = x + dx, y + dy
            bx, by = x + 2 * dx, y + 2 * dy
            if not (1 <= bx < W - 1 and 1 <= by < H - 1 and 1 <= wx < W - 1 and 1 <= wy < H - 1):
                continue
            if self.grid[wy][wx] != '#' or (bx, by) not in self.base_reach:
                continue
            if bfs((x, y), self.adj_pac).get((bx, by), 0) < 8:
                continue
            self.grid[wy][wx] = 'S'
            self.secret.add((wx, wy))
            n += 1


# =========================================================
# ENTITY
# =========================================================

class Ent:
    def __init__(self, tx, ty, **kwargs):
        self.tx = tx
        self.ty = ty
        self.dx = 0
        self.dy = 0
        self.p = 0.0
        self.__dict__.update(kwargs)

    def pos(self):
        return self.tx + self.dx * self.p, self.ty + self.dy * self.p

    @property
    def moving(self):
        return bool(self.dx or self.dy)




class Game:
    def __init__(self, sounds, habits):
        self.sounds = sounds
        self.habits = habits
        self.clock_t = 0.0
        self.difficulty = 4
        self.adaptive = True
        self.show_ai = False
        self.hi = 0
        self.new_game()

    @property
    def cfg(self):
        return DIFFICULTIES[self.difficulty]

    

    def new_game(self):
        self.level = 1
        self.score = 0
        self.lives = 3
        self.extra_life_given = False
        self.pressure = 0.35
        self.start_level()

    def next_level(self):
        self.level += 1
        self.sounds.play("level")
        self.start_level()

    def set_difficulty(self, level):
        if level in DIFFICULTIES:
            self.difficulty = level
            self.new_game()

    def start_level(self):
        self.maze = Maze(self.level, self.difficulty)
        m = self.maze
        self.grid = [list(r) for r in m.grid]
        self.total_pellets = m.pellets
        self.pellets = m.pellets
        self.gates = [dict(pos=g["pos"], period=g["period"], phase=g["phase"],
                           closed=False, warn=False) for g in m.gates]
        self.gate_at = {g["pos"]: g for g in self.gates}
        self.gate_time = 0.0
        self.habits.new_maze()
        self.wall_surface = None

        self.schedule = build_schedule(self.level, self.difficulty)
        self.mode_index = 0
        self.mode, self.mode_timer = self.schedule[0]

        self.over = False
        self.won = False
        self.dots_eaten = 0
        self.fright_chain = 0
        self.fruit_stage = 0
        self.fruit = None
        self.boost = 0.0
        self.aggro = 0.0
        self.banner = ""
        self.banner_t = 0.0

        self.level_time = 0.0
        self.since_death = 0.0
        self.captures = 0
        self.avg_dist = 8.0
        self.safe_time = 0.0
        self.perf_timer = 0.0
        self.hunt_hold = 0.0
        self.pressure_hunt = False
        self.last_mode_label = ""
        self.last_dir = UP

        # Expanded ghost mechanics.
        self.toxic_hazards = {}       # tile -> remaining seconds
        self.void_blocks = {}         # tile -> original tile
        self.void_timer = 8.0
        self.special_kind = None      # KING / SWARM / MIRROR / DEATH
        self.special_t = 0.0
        self.special_cooldown = 18.0
        self.death_route = []
        self.death_route_t = 0.0
        self.swarm_phase = 0.0
        self.mimic_t = 0.0
        self.mimic_target = 0
        self.split_t = 0.0
        self.warning_t = 0.0
        self.player_trail = deque(maxlen=90)
        self.spawn()

    def spawn(self):
        self.pac = Ent(PAC_START[0], PAC_START[1], kind="pac", want=(0, 0), face=-math.pi / 2, tp_cd=0.0)
        self.player_trail.clear()
        self.player_trail.append(PAC_START)
        starts = [
            (15, 11, True), (15, 14, False), (13, 14, False), (17, 14, False),
            (12, 14, False), (14, 14, False), (16, 14, False), (18, 14, False),
            (12, 15, False), (13, 15, False), (14, 15, False), (16, 15, False),
            (17, 15, False), (18, 15, False), (13, 13, False), (14, 13, False),
            (16, 13, False), (17, 13, False), (15, 15, False),
        ]
        self.ghosts = []
        for i, (x, y, out) in enumerate(starts):
            self.ghosts.append(Ent(
                x, y, kind="ghost", i=i, out=out, leaving=False, dead=False, fright=0.0,
                wait=0.0, tp_cd=0.0, plan="-", plan_t=0.0, last_target=(x, y),
                clyde_state="chase", clyde_t=0.0, phase_t=0.0, phase_cd=3.0,
                charge_t=0.0, charge_dir=None, invisible_t=0.0, visible_flash=0.0,
                warp_cd=2.0, mimic_target=random.randrange(4), mimic_t=random.uniform(8, 15),
                split_t=0.0, route_copy=[], trail_target=None,
            ))
        self.life_dots = 0
        self.idle = 0.0
        self.release_cd = 0.0
        self.boost = 0.0
        self.aggro = 0.0
        self.fright_chain = 0
        self.state = "ready"
        self.ready_t = 2.0
        self.death_t = 0.0
        self._fcache = {}
        self.pac_tile = (self.pac.tx, self.pac.ty)
        self.pac_field = {}
        self.path_h, self.path_l, self.junctions, self.spots = [], [], [], []
        self.ai_dirty = True
        self.ai_age = 9.0
        self.refresh_ai()
        self.sounds.play("start")

    # -----------------------------------------------------
    # Map queries
    # -----------------------------------------------------

    def tile_char(self, x, y):
        if not (0 <= y < H):
            return None
        return self.grid[y][x % W]

    def gate_closed(self, x, y):
        g = self.gate_at.get((x % W, y))
        return g is not None and g["closed"]

    def static_pac(self, x, y, dx, dy):
        """Passable for Pac-Man ignoring the (temporary) closed gates."""
        c = self.tile_char(x, y)
        if c is None or c not in " .o":
            return False
        ow = self.maze.oneway.get((x % W, y))
        return not ow or ow == (dx, dy)

    def can_enter_pac(self, x, y, dx, dy):
        return self.static_pac(x, y, dx, dy) and not self.gate_closed(x, y)

    def can_enter_ghost(self, g, x, y, dx, dy):
        c = self.tile_char(x, y)
        if c is None:
            return False
        if c == "#" and not (g.i == 6 and g.phase_t > 0):
            return False
        if c == "-":
            return g.dead or g.leaving
        if g.dead:
            return True                      # eyes ignore gates and one-ways
        if self.gate_closed(x, y):
            return False
        ow = self.maze.oneway.get((x % W, y))
        return not ow or ow == (dx, dy)

    def can_enter(self, e, x, y, dx, dy):
        if e.kind == "pac":
            return self.can_enter_pac(x, y, dx, dy)
        return self.can_enter_ghost(e, x, y, dx, dy)

    
    def step(self, e, speed, dt, decide):
        if not e.moving:
            decide(e)
            if not e.moving:
                e.p = 0.0
                return
        e.p += speed * dt
        guard = 0
        while e.p >= 1.0 and guard < 4:
            guard += 1
            nx = (e.tx + e.dx) % W
            ny = e.ty + e.dy
            if not self.can_enter(e, nx, ny, e.dx, e.dy):
                e.p = 0.0
                e.dx = e.dy = 0
                decide(e)
                break
            e.p -= 1.0
            prev = (e.tx, e.ty)
            wrapped = abs(nx - e.tx) > 1
            e.tx, e.ty = nx, ny
            if wrapped and e.kind == "pac":
                self.habits.record_tunnel(prev)
            self.on_arrive(e)
            decide(e)
            if not e.moving:
                e.p = 0.0
                break

    def on_arrive(self, e):
        t = (e.tx, e.ty)
        if e.kind == "pac":
            self.ai_dirty = True
            self.habits.visit(t)
        else:
            if e.leaving and t == HOUSE_EXIT:
                e.leaving = False
                e.out = True
            if e.dead and t == HOUSE_HOME:
                e.dead = False
                e.out = False
                e.leaving = True
                e.fright = 0.0
                e.dx = e.dy = 0
                e.p = 0.0
                e.wait = 0.6
        if t in self.maze.tele and e.tp_cd <= 0:
            if e.kind == "pac":
                self.habits.record_tunnel(t)
            e.tx, e.ty = self.maze.tele[t]
            e.tp_cd = 0.9
            if e.kind == "pac":
                self.sounds.play("tele")

    def reverse(self, e):
        """Turn around in place (keeps the on-screen position continuous)."""
        if not e.moving:
            return
        if not self.can_enter(e, e.tx, e.ty, -e.dx, -e.dy):
            return
        e.tx = (e.tx + e.dx) % W
        e.ty = e.ty + e.dy
        e.dx, e.dy = -e.dx, -e.dy
        e.p = max(0.0, min(1.0, 1.0 - e.p))

    def pac_decide(self, p):
        prev = (p.dx, p.dy)
        wx, wy = p.want
        if (wx or wy) and self.can_enter_pac(p.tx + wx, p.ty + wy, wx, wy):
            p.dx, p.dy = wx, wy
        elif p.moving and not self.can_enter_pac(p.tx + p.dx, p.ty + p.dy, p.dx, p.dy):
            p.dx = p.dy = 0
        if p.moving:
            p.face = math.atan2(p.dy, p.dx)
            self.last_dir = dir_index(p.dx, p.dy)
            if prev != (0, 0):
                self.record_choice(p, prev)

    def record_choice(self, p, prev):
        t = (p.tx, p.ty)
        if len(self.maze.adj_pac.get(t, ())) < 3:
            return
        cur = dir_index(*prev)
        new = dir_index(p.dx, p.dy)
        if cur is None or new is None:
            return
        near = any(g.out and not g.dead and g.fright <= 0 and
                   math.hypot(g.tx - p.tx, g.ty - p.ty) < 6.5 for g in self.ghosts)
        self.habits.record(t, cur, new, near)

    def set_want(self, direction):
        p = self.pac
        p.want = direction
        if p.moving and direction == (-p.dx, -p.dy):
            self.reverse(p)
            if p.moving:
                p.face = math.atan2(p.dy, p.dx)
                self.last_dir = dir_index(p.dx, p.dy)

    def pac_speed(self):
        s = min(7.2, 6.5 + (self.level - 1) * 0.08)
        if self.boost > 0:
            s *= 1.18

        # Toxic is an area hazard, not a single exact-tile trap.
        px, py = self.pac.pos()
        toxic_dist = min(99.0, *(math.hypot(px - x, py - y) for x, y in self.toxic_hazards)) if self.toxic_hazards else 99.0
        if toxic_dist < 2.2:
            s *= 0.58 if toxic_dist < 0.8 else 0.68 if toxic_dist < 1.4 else 0.80

        # Frost has a smooth proximity aura.
        frost_dist = 999.0
        for g in self.ghosts:
            if g.i == 8 and g.out and not g.dead and g.fright <= 0:
                gx, gy = g.pos()
                frost_dist = min(frost_dist, math.hypot(gx - px, gy - py))
        if frost_dist < 8:
            s *= 0.66 if frost_dist < 2.2 else (0.76 if frost_dist < 4.2 else (0.87 if frost_dist < 6.0 else 0.94))
        return max(3.0, s)


    def pac_dir_index(self):
        p = self.pac
        if p.moving:
            return dir_index(p.dx, p.dy)
        return self.last_dir

    def refresh_ai(self):
        self.ai_dirty = False
        self.ai_age = 0.0
        p = self.pac
        self.pac_tile = (p.tx, p.ty)
        self.pac_field = bfs(self.pac_tile, self.maze.adj_pac)
        cur = self.pac_dir_index()
        self.path_h, self.junctions = self.likely_path(28, True, cur)
        self.path_l, _ = self.likely_path(28, False, cur)
        self.spots = self.compute_spots(cur)

    def likely_path(self, steps, use_habits, cur):
        """Predicted future tiles from current heading + observed junction habits (ideas 1, 7)."""
        p = self.pac
        x, y = p.tx, p.ty
        d = cur
        path, junc = [], []
        if p.moving:
            dx, dy = DIRS[d]
            if self.static_pac(x + dx, y + dy, dx, dy):
                x, y = (x + dx) % W, y + dy
                path.append((x, y))
        while len(path) < steps:
            exits = []
            for k, (dx, dy) in enumerate(DIRS):
                if k != REVERSE[d] and self.static_pac(x + dx, y + dy, dx, dy):
                    exits.append(k)
            if not exits:
                k = REVERSE[d]
                dx, dy = DIRS[k]
                if self.static_pac(x + dx, y + dy, dx, dy):
                    exits = [k]
                else:
                    break
            if len(exits) == 1:
                nd = exits[0]
            elif use_habits:
                pr = self.habits.probs((x, y), d, exits)
                junc.append((len(path), (x, y), d, exits))
                nd = max(pr, key=lambda t: t[1])[0]
            else:
                nd = d if d in exits else exits[0]
            dx, dy = DIRS[nd]
            x, y = (x + dx) % W, y + dy
            d = nd
            path.append((x, y))
        return path, junc

    def walk(self, tile, k, n):
        x, y = tile
        d = k
        for _ in range(n):
            dx, dy = DIRS[d]
            if not self.static_pac(x + dx, y + dy, dx, dy):
                alts = [j for j in range(4) if j != REVERSE[d] and
                        self.static_pac(x + DIRS[j][0], y + DIRS[j][1], DIRS[j][0], DIRS[j][1])]
                if len(alts) != 1:
                    break
                d = alts[0]
                dx, dy = DIRS[d]
            x, y = (x + dx) % W, y + dy
        return (x, y)

    def compute_spots(self, cur):
        """Ambush points that cover the exits of the next junction (ideas 3, 6)."""
        spots = []
        if self.junctions:
            _, tile, d, exits = self.junctions[0]
            ordered = sorted(self.habits.probs(tile, d, exits), key=lambda t: -t[1])
            for k, _ in ordered:
                spots.append(self.walk(tile, k, 5))
        behind = self.walk(self.pac_tile, REVERSE[cur], 4)
        tail = self.path_h[-1] if self.path_h else self.pac_tile
        for extra in (tail, behind, self.pac_tile):
            if len(spots) >= 3:
                break
            if extra not in spots:
                spots.append(extra)
        while len(spots) < 3:
            spots.append(self.pac_tile)
        return spots

    def field_for(self, tile):
        f = self._fcache.get(tile)
        if f is None:
            f = bfs(tile, self.maze.adj_gh)
            self._fcache[tile] = f
        return f

    # -----------------------------------------------------
    # AI: modes, intelligence and parameters
    # -----------------------------------------------------

    def effective_mode(self):
        m = self.mode
        if m == "scatter" and self.aggro > 0:
            m = "chase"
        if m == "chase" and self.pressure_hunt:
            m = "hunt"
        return m

    def ai_factor(self):
        if not self.adaptive or self.difficulty < 2:
            return 1.0
        return 0.6 + 0.6 * self.pressure

    def ghost_iq(self, g):
        iq = self.cfg["iq"][min(g.i, len(self.cfg["iq"]) - 1)]
        if self.difficulty >= 2:
            iq = min(6, iq + (self.level - 1) // 2)
        if iq >= 3 and self.effective_mode() == "hunt":
            iq = min(6, iq + 1)
        return iq

    def pred_secs(self):
        base = self.cfg["prediction"]
        if base <= 0:
            return 0.0
        secs = base * self.ai_factor() + 0.12 * (self.level - 1)
        if self.effective_mode() == "hunt":
            secs += 1.0
        if self.aggro > 0:
            secs += 0.5
        return min(5.0, secs)

    def coordination(self, iq):
        if iq < 4:
            return 0.0
        c = 0.6 + 0.2 * (iq - 4)
        if self.effective_mode() == "hunt":
            c += 0.3
        return c

    def elroy(self):
        r = self.pellets / max(1, self.total_pellets)
        return 3 if r <= 0.03 else 2 if r <= 0.07 else 1 if r <= 0.13 else 0

    def ghost_speed(self, g):
        if g.dead:
            return 9.5
        if g.leaving:
            return 4.2
        lvl = self.level
        if g.fright > 0:
            return max(2.4, 3.0 - (lvl - 1) * 0.03)

        iq = self.ghost_iq(g)
        base = 5.15 + min(1.15, (lvl - 1) * 0.12)
        bonus = self.cfg["speed"]
        if self.adaptive and self.difficulty >= 2 and iq >= 5:
            bonus += 0.22 * self.pressure
        if self.effective_mode() == "hunt" and iq >= 4:
            bonus += 0.20
        if self.aggro > 0:
            bonus += 0.30
        if g.i == 0:
            bonus += (0.0, 0.35, 0.7, 1.0)[self.elroy()] * (0.5 if self.difficulty == 1 else 1.0)

        spd = base + bonus
        gx, gy = g.pos()
        px, py = self.pac.pos()
        if iq >= 3:
            d = math.hypot(gx - px, gy - py)
            if d < 5:
                spd *= 1.06
            elif d < 10:
                spd *= 1.03
        if g.ty in (9, 21) and (g.tx < 5 or g.tx > W - 6):
            spd *= 0.65

        # Distinct movement personalities.
        modifiers = {
            4: 1.04,   # Violet: slightly quicker while copying routes
            5: 0.98,   # Toxic: spends power on hazard placement
            6: 0.92,   # Phantom
            7: 0.84,   # Brute
            8: 0.91,   # Frost
            9: 1.48,   # Flash
            10: 1.04,  # Shade
            11: 1.06,  # Tracker
            12: 0.88,  # Trapper
            13: 1.10,  # Hunter
            14: 1.03,  # Mirror
            15: 1.00,  # Mimic
            16: 0.94,  # Warp
            17: 0.98,  # Splitter
            18: 0.96,  # Void
        }
        spd *= modifiers.get(g.i, 1.0)
        if g.i == 7 and g.charge_t > 0:
            spd *= 1.55
        if g.i == 6 and g.phase_t > 0:
            spd *= 1.08
        if self.special_kind == "KING" and g.i != 0:
            spd += 0.55
        cap = self.pac_speed() * (1.42 if g.i == 9 else 1.18)
        return min(spd, max(4.0, cap))

  

    def classic_target(self, g):
        p = self.pac
        pt = (p.tx, p.ty)
        d = DIRS[self.pac_dir_index()]
        if g.i == 0:
            return pt
        if g.i == 1:
            return (p.tx + 4 * d[0], p.ty + 4 * d[1])
        if g.i == 2:
            bl = self.ghosts[0]
            px, py = p.tx + 2 * d[0], p.ty + 2 * d[1]
            return (px + (px - bl.tx), py + (py - bl.ty))
        dist = math.hypot(g.tx - p.tx, g.ty - p.ty)
        return pt if dist >= 8 else SCATTER_TARGETS[3]

    def route_memory(self, gf):
        """Idea 2: the hottest tile of Pac-Man's remembered route near him."""
        best, bs = None, 0.0
        for t, h in self.habits.heat.items():
            if h < 2.0:
                continue
            pd = self.pac_field.get(t)
            if pd is None or pd < 3 or pd > 10:
                continue
            s = h - 0.2 * pd - 0.12 * gf.get(t, 999)
            if s > bs:
                bs, best = s, t
        return best

    def intercept_point(self, g, horizon, gf):
        gs, ps = 5.5, self.pac_speed()
        for i, t in enumerate(horizon):
            if gf.get(t, 999) / gs <= (i + 1) / ps:
                return t, i
        return horizon[-1], len(horizon) - 1

    def ghost_target(self, g):
        mode = self.effective_mode()
        iq = self.ghost_iq(g)
        p = self.pac
        pt = (p.tx, p.ty)
        g.plan = "-"

        if mode == "scatter" and not (g.i == 0 and self.elroy() >= 1 and self.difficulty >= 2):
            if iq >= 5 and g.i == 3:
                c = self.habits.fav_corner()
                if c is not None:
                    g.plan = "CORNER"
                    return PATROL_TILES[c]
            g.plan = "SCATTER"
            return SCATTER_TARGETS[g.i]

        if iq <= 1:
            g.plan = "CLASSIC"
            return self.classic_target(g)

        secs = self.pred_secs()
        steps = max(1, min(28, int(secs * 6.0)))
        path = self.path_h if iq >= 3 else self.path_l
        if not path:
            path = [pt]
        horizon = path[:steps]
        gf = self.field_for((g.tx, g.ty)) if iq >= 3 else None

        if g.i == 0:
            return self.target_blinky(g, iq, horizon, gf, pt)
        if g.i == 1:
            return self.target_pinky(g, iq, horizon, gf, pt)
        if g.i == 2:
            return self.target_inky(g, iq, horizon, gf, pt)
        if g.i == 3:
            return self.target_clyde(g, iq, horizon, gf, pt)
        if g.i == 4:
            return self.target_violet(g, iq, horizon, gf, pt)
        if g.i == 5:
            return self.target_toxic(g, iq, horizon, gf, pt)
        if g.i == 6:
            return self.target_phantom(g, iq, horizon, gf, pt)
        if g.i == 7:
            return self.target_brute(g, iq, horizon, gf, pt)
        if g.i == 8:
            return self.target_frost(g, iq, horizon, gf, pt)
        if g.i == 9:
            return self.target_flash(g, iq, horizon, gf, pt)
        if g.i == 10:
            return self.target_shade(g, iq, horizon, gf, pt)
        if g.i == 11:
            return self.target_tracker(g, iq, horizon, gf, pt)
        if g.i == 12:
            return self.target_trapper(g, iq, horizon, gf, pt)
        if g.i == 13:
            return self.target_hunter(g, iq, horizon, gf, pt)
        if g.i == 14:
            return self.target_mirror(g, iq, horizon, gf, pt)
        if g.i == 15:
            return self.target_mimic(g, iq, horizon, gf, pt)
        if g.i == 16:
            return self.target_warp(g, iq, horizon, gf, pt)
        if g.i == 17:
            return self.target_splitter(g, iq, horizon, gf, pt)
        return self.target_void(g, iq, horizon, gf, pt)

    def target_blinky(self, g, iq, horizon, gf, pt):
        """CHASER: prediction, route memory and short/long routing."""
        g.plan = "PREDICT"
        if iq == 2:
            return horizon[-1]
        cut, idx = self.intercept_point(g, horizon, gf)
        target = cut
        hot = self.route_memory(gf)
        if hot is not None and gf.get(hot, 999) <= gf.get(pt, 999) + 4:
            target = hot
            g.plan = "ROUTE"
        if iq >= 4:                                   # idea 15
            if g.plan_t <= 0:
                d_short = gf.get(pt, 999)
                tg = gf.get(cut, 999) / 5.5
                tp = (idx + 1) / self.pac_speed()
                g.plan = "LONG" if (d_short > 4 and tg < tp) else "SHORT"
                g.plan_t = 0.8
            if g.plan == "SHORT":
                return pt
            return target
        return target

    def target_pinky(self, g, iq, horizon, gf, pt):
        """AMBUSHER: blocks the most likely exit of the next junction."""
        g.plan = "BLOCK"
        if iq == 2:
            return horizon[-1]
        if gf.get(pt, 999) <= 4:
            g.plan = "CLOSE"
            return horizon[min(2, len(horizon) - 1)]
        return self.spots[0]

    def target_inky(self, g, iq, horizon, gf, pt):
        """INTERCEPTOR: mirrors Blinky through Pac-Man so he pushes Pac into the other ghost."""
        bl = self.ghosts[0]
        b = (bl.tx, bl.ty) if (bl.out and not bl.dead) else pt
        pivot = horizon[min(len(horizon) - 1, 1)]
        vec = (pivot[0] + (pivot[0] - b[0]), pivot[1] + (pivot[1] - b[1]))
        if iq >= 4 and self.pac_field.get(b, 99) > 10:
            g.plan = "SPOT"
            return self.spots[1]
        g.plan = "PUSH"
        return vec

    def target_clyde(self, g, iq, horizon, gf, pt):
        """CUTTER: classic near/far below IQ 4, tactical state machine at IQ 4+."""
        dist = math.hypot(g.tx - pt[0], g.ty - pt[1])
        if iq < 4:
            g.plan = "CLASSIC"
            if dist >= 8:
                return horizon[-1] if iq >= 2 else pt
            return SCATTER_TARGETS[3]

        hunt = self.effective_mode() == "hunt"
        if g.clyde_t <= 0:
            r = random.random()
            if dist < 8:
                st = "chase" if r < 0.35 else ("fake" if (r < 0.75 and not hunt) else "ambush")
            else:
                st = "chase" if r < 0.35 else ("ambush" if r < 0.65 else "patrol")
            g.clyde_state = st
            g.clyde_t = random.uniform(2.5, 5.5)
        # Sudden turn-around at a strategic junction while pretending to retreat.
        if (g.clyde_state == "fake" and len(self.maze.adj_gh.get((g.tx, g.ty), ())) >= 3
                and self.pac_field.get((g.tx, g.ty), 99) <= 9 and random.random() < 0.3):
            g.clyde_state = "ambush"
            g.clyde_t = 3.0

        st = g.clyde_state
        g.plan = st.upper()
        if st == "chase":
            return horizon[min(len(horizon) - 1, 3)]
        if st == "fake":
            return SCATTER_TARGETS[3]
        if st == "ambush":
            return self.spots[2]
        # patrol: favourite tunnel exit, favourite corner, favourite escape direction
        entry = self.habits.fav_tunnel_entry()
        if iq >= 5 and entry is not None and entry in self.maze.links:
            g.plan = "TUNNEL"
            return self.maze.links[entry]
        c = self.habits.fav_corner()
        if c is not None:
            g.plan = "CORNER"
            return PATROL_TILES[c]
        fe = self.habits.fav_escape()
        if fe is not None:
            return self.walk(pt, fe, 7)
        return horizon[-1]


    # ---- expanded ghost targets --------------------------------------
    def _route_target(self, g, horizon, gf, fallback):
        """Choose a reachable future tile, preferring an interception point."""
        if not horizon:
            return fallback
        if gf:
            for t in reversed(horizon):
                if gf.get(t, 999) <= max(4, len(horizon) * 0.75):
                    return t
        return horizon[-1]

    def target_violet(self, g, iq, horizon, gf, pt):
        """Violet copies the player's recent path, including repeated escape habits."""
        g.plan = "COPY"
        trail = list(self.player_trail)
        if len(trail) >= 8:
            # Pick a point behind the player so Violet follows the route instead of
            # simply becoming another direct chaser. Higher IQ copies farther ahead.
            idx = max(0, len(trail) - (8 + min(20, iq * 2)))
            for t in reversed(trail[idx:]):
                if self.pac_field.get(t, 999) >= 2:
                    g.route_copy = trail[idx:]
                    return t
        if self.habits.heat:
            candidates = [(heat - 0.12 * (gf.get(t, 999) if gf else 999), t)
                          for t, heat in self.habits.heat.items() if self.pac_field.get(t, 999) < 20]
            if candidates:
                return max(candidates)[1]
        return self._route_target(g, horizon, gf, pt)

    def target_toxic(self, g, iq, horizon, gf, pt):
        """Toxic aims for the corridor Pac-Man is most likely to use next."""
        g.plan = "HAZARD"
        if self.junctions:
            _, tile, d, exits = self.junctions[0]
            probs = self.habits.probs(tile, d, exits)
            k = max(probs, key=lambda z: z[1])[0]
            return self.walk(tile, k, 3 + min(5, iq))
        return horizon[min(5, len(horizon) - 1)]

    def target_phantom(self, g, iq, horizon, gf, pt):
        """Phantom approaches from a route that may be separated by walls."""
        g.plan = "PHASE"
        if self.special_kind == "MIRROR":
            return ((W - pt[0]) % W, H - 1 - pt[1])
        if horizon:
            idx = min(len(horizon) - 1, 7)
            return horizon[idx]
        return pt

    def target_brute(self, g, iq, horizon, gf, pt):
        """Brute chooses a charge direction and commits until the next junction."""
        g.plan = "CHARGE"
        if g.charge_t <= 0:
            if g.moving:
                g.charge_dir = (g.dx, g.dy)
            else:
                d = self.pac_dir_index()
                g.charge_dir = DIRS[d]
            g.charge_t = random.uniform(1.0, 2.2)
        if g.charge_dir:
            dx, dy = g.charge_dir
            return ((g.tx + dx * 6) % W, g.ty + dy * 6)
        return pt

    def target_frost(self, g, iq, horizon, gf, pt):
        """Frost takes the nearest useful tile so its slowing aura overlaps Pac-Man."""
        g.plan = "SLOW"
        return horizon[min(2, len(horizon) - 1)] if horizon else pt

    def target_flash(self, g, iq, horizon, gf, pt):
        """Flash aims directly but turns poorly."""
        g.plan = "FAST"
        return horizon[min(3, len(horizon) - 1)] if horizon else pt

    def target_shade(self, g, iq, horizon, gf, pt):
        """Shade attacks from a favorite corner or escape route while hidden."""
        g.plan = "HIDE"
        c = self.habits.fav_corner()
        if c is not None:
            return PATROL_TILES[c]
        e = self.habits.fav_escape()
        if e is not None:
            return self.walk(pt, e, 6)
        return self.spots[min(1, len(self.spots) - 1)] if self.spots else pt

    def target_tracker(self, g, iq, horizon, gf, pt):
        """Tracker follows where Pac-Man has actually been, not where he is now."""
        g.plan = "TRAIL"
        if self.special_kind == "DEATH" and self.death_route:
            route = [t for t in self.death_route if self.pac_field.get(t, 999) < 999]
            if route:
                g.plan = "DEATH"
                return route[min(len(route) - 1, 4 + iq)]
        trail = list(self.player_trail)
        if trail:
            for t in reversed(trail):
                if self.pac_field.get(t, 999) >= 3 and (not gf or gf.get(t, 999) < 999):
                    g.trail_target = t
                    return t
        return self.path_l[min(8, len(self.path_l) - 1)] if self.path_l else pt

    def target_trapper(self, g, iq, horizon, gf, pt):
        """Trapper camps the most valuable junction/escape intersection."""
        g.plan = "TRAP"
        best = None
        best_score = -999
        for tile, counts in self.habits.tile.items():
            if sum(counts) < 2:
                continue
            dist = self.pac_field.get(tile, 999)
            if dist > 18:
                continue
            score = sum(counts) + 5.0 / max(1, dist)
            if score > best_score:
                best_score, best = score, tile
        if best is not None:
            return best
        if self.junctions:
            return self.junctions[0][1]
        return pt

    def target_hunter(self, g, iq, horizon, gf, pt):
        """Hunter is the strongest escape predictor."""
        g.plan = "HUNT"
        if not horizon:
            return pt
        # Bias farther into the predicted path so Hunter cuts ahead instead of tailing.
        idx = min(len(horizon) - 1, max(5, int(self.pred_secs() * 7)))
        return horizon[idx]

    def target_mirror(self, g, iq, horizon, gf, pt):
        """Mirror deliberately travels opposite Pac-Man's observed direction."""
        g.plan = "MIRROR"
        d = self.pac_dir_index()
        od = REVERSE[d]
        if self.special_kind == "MIRROR":
            od = d
        return self.walk(pt, od, 7 + min(7, iq))

    def target_mimic(self, g, iq, horizon, gf, pt):
        """Mimic switches between another ghost's targeting styles."""
        g.plan = "MIMIC"
        if g.mimic_t <= 0:
            g.mimic_target = random.randrange(min(14, len(self.ghosts)))
            if g.mimic_target == g.i:
                g.mimic_target = 0
            g.mimic_t = random.uniform(15, 30)
        other = self.ghosts[g.mimic_target]
        if other.i < 4:
            return self.classic_target(other)
        return other.last_target if hasattr(other, "last_target") else pt

    def target_warp(self, g, iq, horizon, gf, pt):
        """Warp targets Pac-Man's next likely zone, then teleports between fixed links."""
        g.plan = "WARP"
        if self.maze.tele:
            pairs = list(self.maze.tele.items())
            best = min((t for t in self.maze.tele), key=lambda t: self.pac_field.get(t, 999))
            return best
        return horizon[min(6, len(horizon) - 1)] if horizon else pt

    def target_splitter(self, g, iq, horizon, gf, pt):
        """Splitter uses the predicted route while its decoys create uncertainty."""
        g.plan = "SPLIT"
        return horizon[min(5, len(horizon) - 1)] if horizon else pt

    def target_void(self, g, iq, horizon, gf, pt):
        """Void positions near Pac-Man's future route and closes nearby alternatives."""
        g.plan = "VOID"
        if self.special_kind == "KING":
            return pt
        return horizon[min(8, len(horizon) - 1)] if horizon else pt

    # -----------------------------------------------------
    # Ghost movement
    # -----------------------------------------------------

    def ghost_options(self, g):
        cur = dir_index(g.dx, g.dy) if g.moving else None
        opts, rev = [], None
        for k, (dx, dy) in enumerate(DIRS):
            nx, ny = (g.tx + dx) % W, g.ty + dy
            allowed = self.can_enter_ghost(g, nx, ny, dx, dy)
            # Phantom can phase through a wall while its phase timer is active.
            if g.i == 6 and g.phase_t > 0 and 0 <= ny < H and self.tile_char(nx, ny) == "#":
                allowed = True
            if g.i == 18 and (nx, ny) in self.void_blocks:
                allowed = False
            if not allowed:
                continue
            if cur is not None and k == REVERSE[cur]:
                rev = (k, nx, ny)
                continue
            opts.append((k, nx, ny))
        if not opts and rev is not None:
            opts.append(rev)
        return opts

    def ghost_decide(self, g):
        if g.leaving:
            if g.tx != HOUSE_EXIT[0]:
                g.dx, g.dy = (1 if g.tx < HOUSE_EXIT[0] else -1), 0
            else:
                g.dx, g.dy = 0, -1
            return

        opts = self.ghost_options(g)
        if not opts:
            g.dx = g.dy = 0
            return

        # Flash has terrible turning: it keeps going straight whenever possible.
        if g.i == 9 and g.moving:
            straight = dir_index(g.dx, g.dy)
            for k, nx, ny in opts:
                if k == straight:
                    g.dx, g.dy = DIRS[k]
                    g.plan = "STRAIGHT"
                    return

        # Brute commits to its current charge direction whenever the route allows it.
        if g.i == 7 and g.charge_t > 0 and g.charge_dir:
            cd = dir_index(*g.charge_dir)
            for k, nx, ny in opts:
                if k == cd:
                    g.dx, g.dy = DIRS[k]
                    return

        if g.dead:
            best = min(opts, key=lambda o: self.maze.dist_home.get((o[1], o[2]), 9999))
            g.dx, g.dy = DIRS[best[0]]
            return

        if g.fright > 0:
            k, _, _ = random.choice(opts)
            g.dx, g.dy = DIRS[k]
            return

        if g.i == 16 and g.tp_cd <= 0 and self.maze.tele:
            # Warp deliberately uses its teleport network when a portal is useful.
            portal = min(self.maze.tele, key=lambda t: self.pac_field.get(t, 999))
            if math.hypot(g.tx - portal[0], g.ty - portal[1]) <= 1.5:
                g.tx, g.ty = self.maze.tele[portal]
                g.tp_cd = 2.5
                self.sounds.play("tele")
                g.dx = g.dy = 0
                return

        target = self.ghost_target(g)
        tile = self.maze.snap(target)
        g.last_target = tile
        field = self.field_for(tile)
        iq = self.ghost_iq(g)
        coord = self.coordination(iq)

        best, best_d = None, float("inf")
        for k, nx, ny in opts:
            d = float(field.get((nx, ny), 999))
            if coord > 0:                               # team spacing: avoid stacking on one branch
                for o in self.ghosts:
                    if o is g or o.dead or not o.out:
                        continue
                    if math.hypot(nx - o.tx, ny - o.ty) < 2.2:
                        d += 2.5 * coord
            if d < best_d:
                best_d, best = d, k
        g.dx, g.dy = DIRS[best]

    # -----------------------------------------------------
    # Game flow
    # -----------------------------------------------------


    # ---- expanded ghost mechanics ------------------------------------
    def special_active(self, name):
        return self.special_kind == name and self.special_t > 0

    def update_special_ghosts(self, dt):
        """Rare team events: King, Swarm, Mirror and Death."""
        self.special_t = max(0.0, self.special_t - dt)
        self.special_cooldown = max(0.0, self.special_cooldown - dt)
        self.swarm_phase += dt * 5.0

        if self.special_kind and self.special_t <= 0:
            old = self.special_kind
            self.special_kind = None
            self.special_cooldown = random.uniform(22, 38)
            self.set_banner(f"{old} EVENT ENDED", 1.5)

        # Rare means rare in real time, not per-frame probability.
        if (self.level >= 3 and self.special_kind is None and
                self.special_cooldown <= 0 and random.random() < 0.0015 * dt):
            self.special_kind = random.choice(("KING", "SWARM", "MIRROR", "DEATH"))
            self.special_t = random.uniform(9, 15)
            self.special_cooldown = 25.0
            self.set_banner({
                "KING": "KING GHOST: ALL GHOSTS AGGRESSIVE!",
                "SWARM": "SWARM: HUNDREDS OF SHADOWS INCOMING!",
                "MIRROR": "MIRROR EVENT: THE MAZE IS REFLECTED!",
                "DEATH": "DEATH GHOST: YOUR FAVORITE ROUTES ARE MARKED!",
            }[self.special_kind], 2.5)
            self.sounds.play("hunt")

        # Death Ghost continuously learns the player's most-used route.
        if self.special_kind == "DEATH":
            route = sorted(self.habits.heat.items(), key=lambda kv: -kv[1])
            self.death_route = [t for t, _ in route[:10]]
        else:
            self.death_route = []

    def update_toxic(self, dt):
        """Toxic paints a fading area trail wherever it travels."""
        for t in list(self.toxic_hazards):
            self.toxic_hazards[t] -= dt
            if self.toxic_hazards[t] <= 0:
                del self.toxic_hazards[t]

        toxic = next((g for g in self.ghosts if g.i == 5 and g.out and not g.dead), None)
        if not toxic:
            return

        x, y = toxic.pos()
        cx, cy = int(round(x)) % W, int(round(y))
        # Paint the current tile plus a small wake. This makes the hazard obvious
        # even when Toxic is moving quickly through an intersection.
        paint = {(cx, cy), ((cx - toxic.dx) % W, cy - toxic.dy)}
        if toxic.moving:
            paint.add(((cx - 2 * toxic.dx) % W, cy - 2 * toxic.dy))
        for t in paint:
            if self.tile_char(*t) in (".", "o", " "):
                self.toxic_hazards[t] = max(self.toxic_hazards.get(t, 0.0), 2.8)

    def update_void(self, dt):
        """Void temporarily removes safe route tiles, then restores them."""
        self.void_timer -= dt
        restored = False
        for t in list(self.void_blocks):
            # Restore only tiles that were actually closed by Void.
            if self.void_blocks[t][1] <= 0:
                old, _ = self.void_blocks.pop(t)
                restored = True
                x, y = t
                self.grid[y][x] = old
        for t in list(self.void_blocks):
            old, remain = self.void_blocks[t]
            self.void_blocks[t] = (old, remain - dt)
        if restored:
            self.maze.adj_pac = self.maze._adj(". o")
            self.maze.adj_gh = self.maze._adj(". oS")
            self.maze.adj_dead = self.maze._adj(". oS-")
            self._fcache.clear()
            self.ai_dirty = True

        if self.level < 2 or self.void_timer > 0:
            return
        self.void_timer = random.uniform(12, 20)
        candidates = []
        for t in self.path_h[5:20]:
            x, y = t
            if (x, y) in self.void_blocks or (x, y) in self.maze.tele:
                continue
            if t == (self.pac.tx, self.pac.ty):
                continue
            if self.tile_char(x, y) in ". o" and len(self.maze.adj_pac.get(t, ())) >= 2:
                candidates.append(t)
        random.shuffle(candidates)
        for t in candidates[:min(2, 1 + self.level // 3)]:
            x, y = t
            old = self.grid[y][x]
            self.void_blocks[t] = (old, random.uniform(3.0, 5.0))
            self.grid[y][x] = "#"
        if candidates:
            self.wall_surface = None
            self._fcache.clear()
            # Rebuild dynamic movement graphs so AI cannot target a path Void just closed.
            self.maze.adj_pac = self.maze._adj(". o")
            self.maze.adj_gh = self.maze._adj(". oS")
            self.maze.adj_dead = self.maze._adj(". oS-")
            self.ai_dirty = True
            self.set_banner("VOID CLOSED A ROUTE!", 1.5)
            self.sounds.play("gate")

    def update_new_ghosts(self, dt):
        for g in self.ghosts:
            if g.i == 6:
                g.phase_t = max(0.0, g.phase_t - dt)
                g.phase_cd = max(0.0, g.phase_cd - dt)
                if g.phase_t <= 0 and g.phase_cd <= 0 and random.random() < 0.18 * dt:
                    g.phase_t = 2.5
                    g.phase_cd = 7.0
            elif g.i == 7:
                g.charge_t = max(0.0, g.charge_t - dt)
            elif g.i == 10:
                # Shade cycles invisibility; a brief flash makes it fair.
                g.invisible_t = max(0.0, g.invisible_t - dt)
                g.visible_flash = max(0.0, g.visible_flash - dt)
                if g.invisible_t <= 0 and random.random() < 0.10 * dt:
                    g.invisible_t = random.uniform(2.5, 4.5)
                    g.visible_flash = 0.8
            elif g.i == 15:
                g.mimic_t -= dt
            elif g.i == 17:
                g.split_t = max(0.0, g.split_t - dt)
                if g.split_t <= 0 and random.random() < 0.045 * dt:
                    g.split_t = 4.0

    def update_gates(self, dt):
        self.gate_time += dt
        ents = [self.pac] + self.ghosts
        for g in self.gates:
            ph = (self.gate_time + g["phase"]) % g["period"]
            cut = g["period"] * 0.6
            want_closed = ph >= cut
            g["warn"] = (cut - 1.0) <= ph < cut
            if want_closed and not g["closed"]:
                pos = g["pos"]
                busy = any((e.tx, e.ty) == pos or
                           (e.moving and ((e.tx + e.dx) % W, e.ty + e.dy) == pos) for e in ents)
                if busy:
                    want_closed = False
                else:
                    self.sounds.play("gate")
            g["closed"] = want_closed

    def update_mode(self, dt):
        if any(g.fright > 0 for g in self.ghosts):
            return
        self.mode_timer -= dt
        if self.mode_timer > 0:
            return
        if self.mode_index < len(self.schedule) - 1:
            old = self.mode
            self.mode_index += 1
            self.mode, self.mode_timer = self.schedule[self.mode_index]
            if self.mode == "hunt":
                self.sounds.play("hunt")
                self.set_banner("HUNT MODE - THE GHOSTS ARE COORDINATING", 3.0)
            if "scatter" in (old, self.mode):
                for g in self.ghosts:
                    if g.out and not g.dead:
                        self.reverse(g)

    def update_perf(self, dt):
        """Idea 9: dynamic pressure from how well the player is doing."""
        self.level_time += dt
        self.since_death += dt
        px, py = self.pac.pos()
        dmin = 99.0
        for g in self.ghosts:
            if g.out and not g.dead and g.fright <= 0:
                gx, gy = g.pos()
                dmin = min(dmin, math.hypot(px - gx, py - gy))
        if dmin < 99:
            self.avg_dist += (dmin - self.avg_dist) * min(1.0, dt * 0.25)
        if dmin < 5.5:
            self.safe_time = max(0.0, self.safe_time - dt * 0.5)
        else:
            self.safe_time += dt

        self.perf_timer += dt
        if self.perf_timer >= 0.5:
            self.perf_timer = 0.0
            dpm = (self.dots_eaten / (self.level_time / 60.0)) if self.level_time > 10 else 20.0
            skill = (0.24 * clamp(dpm / 45.0)
                     + 0.18 * clamp((self.avg_dist - 3.0) / 8.0)
                     + 0.20 * clamp(self.since_death / 60.0)
                     + 0.14 * clamp((self.lives - 1) / 2.0)
                     + 0.10 * clamp(self.captures / 4.0)
                     + 0.14 * self.habits.predictability())
            self.pressure += (skill - self.pressure) * 0.15

        # Late-level / long-survival trigger for HUNT (idea 16).
        cond = self.difficulty >= 3 and (
            (self.level >= 2 and self.pellets <= self.total_pellets * 0.22) or self.safe_time >= 45.0)
        if cond:
            self.hunt_hold += dt
        else:
            self.hunt_hold = max(0.0, self.hunt_hold - dt * 0.5)
        was = self.pressure_hunt
        self.pressure_hunt = self.hunt_hold >= 4.0
        if self.pressure_hunt and not was:
            self.sounds.play("hunt")
            self.set_banner("HUNT MODE - THE GHOSTS ARE COORDINATING", 3.0)

    def release_ghosts(self, dt):
        """Idea 17: smarter ghost-house release (dots, idle time, distance, hunt)."""
        self.release_cd = max(0.0, self.release_cd - dt)
        waiting = [g for g in self.ghosts[1:] if not g.out and not g.leaving and not g.dead]
        if not waiting:
            return
        self.idle += dt
        if self.release_cd > 0:
            return
        nxt = waiting[0]
        d = self.difficulty
        scale = max(0.3, 1.0 - 0.12 * (d - 1) - 0.05 * (self.level - 1))
        release_requirements = (0, 4, 14, 28)
        base_need = release_requirements[nxt.i] if nxt.i < 4 else 28 + (nxt.i - 3) * 4
        need = base_need * scale
        idle_limit = max(1.2, 4.2 - 0.25 * (self.level - 1) - 0.6 * (d - 1))
        release = False
        if self.life_dots >= need:
            release = True
        elif self.idle >= idle_limit:
            release = True
        elif d >= 3 and self.mode in ("chase", "hunt") and self.pac_field.get(HOUSE_EXIT, 0) > 16:
            release = True
        elif self.effective_mode() == "hunt":
            release = True
        if release:
            nxt.leaving = True
            self.idle = 0.0
            self.release_cd = 0.8

    def set_banner(self, text, secs=2.0):
        self.banner = text
        self.banner_t = secs

    # ---- fruit (idea 12) ------------------------------------------------
    def maybe_spawn_fruit(self):
        # Fruits now appear throughout the level instead of only twice.
        # Six spawn stages make them a regular part of the run without
        # covering the maze in collectibles.
        fruit_thresholds = (0.12, 0.27, 0.42, 0.57, 0.72, 0.87)
        if self.fruit_stage >= len(fruit_thresholds):
            return
        if self.fruit is not None:
            return
        thr = fruit_thresholds[self.fruit_stage] * self.total_pellets
        if self.dots_eaten < thr:
            return

        self.fruit_stage += 1
        px, py = self.pac.tx, self.pac.ty

        # Pick a random reachable/open tile anywhere in the maze. This also
        # makes the fruit locations change from level to level.
        cands = []
        for y in range(1, H - 1):
            for x in range(1, W - 1):
                if self.tile_char(x, y) not in (" ", ".", "o"):
                    continue
                if (x, y) in self.maze.tele:
                    continue
                if (x, y) in self.void_blocks:
                    continue
                if 10 <= x <= 20 and 11 <= y <= 17:
                    continue
                if math.hypot(x - px, y - py) < 7:
                    continue
                cands.append((x, y))

        if not cands:
            cands = [
                s for s in FRUIT_SPOTS
                if self.tile_char(*s) in (" ", ".", "o")
            ]
        if not cands:
            return

        # Use the maze's seeded RNG so the placement is random but reproducible
        # for a given level, rather than always appearing in the same spots.
        pos = self.maze.rng.choice(cands)
        if random.random() < self.cfg["fake"]:
            effect = "fake"
        elif self.difficulty == 1:
            effect = "boost"
        else:
            effect = random.choice(("boost", "aggro"))
        shown = effect if effect != "fake" else random.choice(("boost", "aggro"))
        self.fruit = dict(pos=pos, kind=min(self.level - 1, len(FRUIT_TYPES) - 1),
                          effect=effect, shown=shown, timer=12.0)

    def collect_fruit(self):
        f = self.fruit
        if not f:
            return
        px, py = self.pac.pos()
        if math.hypot(px - f["pos"][0], py - f["pos"][1]) >= 0.7:
            return
        name, value = FRUIT_TYPES[f["kind"]]
        value *= max(1, self.level)
        if f["effect"] == "boost":
            self.score += value
            self.boost = 6.0
            self.set_banner(f"{name}: SPEED BOOST!", 2.0)
            self.sounds.play("fruit")
        elif f["effect"] == "aggro":
            self.score += value * 2
            self.aggro = 8.0
            self.set_banner(f"{name}: x2 POINTS - GHOSTS ENRAGED!", 2.5)
            self.sounds.play("bad")
        else:
            self.aggro = 4.0
            self.set_banner("FAKE FRUIT! THE GHOSTS NOTICED YOU", 2.5)
            self.sounds.play("bad")
        self.fruit = None

    # ---- pellets (idea 13) -------------------------------------------------
    def collect_tile(self):
        p = self.pac
        c = self.grid[p.ty][p.tx]
        if c not in ".o":
            return
        self.grid[p.ty][p.tx] = " "
        self.pellets -= 1
        self.dots_eaten += 1
        self.life_dots += 1
        self.idle = 0.0

        if c == ".":
            self.score += 10
            self.sounds.play("waka1" if self.dots_eaten % 2 else "waka2")
        else:
            self.score += 50
            kind = self.maze.power.get((p.tx, p.ty), "normal")
            info = PELLET_TYPES[kind]
            secs = max(1.5, 6.0 - (self.level - 1) * 0.35) * self.cfg["fright"] * info["mult"]
            if self.adaptive and self.difficulty >= 2:
                secs *= 1.15 - 0.3 * self.pressure
            secs = max(1.2, secs)
            for g in self.ghosts:
                if g.dead:
                    continue
                if kind == "chain" and math.hypot(g.tx - p.tx, g.ty - p.ty) >= 8.0:
                    continue
                g.fright = secs
                if g.out and not g.leaving:
                    self.reverse(g)
            self.fright_chain = 0
            self.set_banner(info["label"], 1.8)
            self.sounds.play("power")

        self.maybe_spawn_fruit()
        if self.score >= 10000 and not self.extra_life_given:
            self.extra_life_given = True
            self.lives += 1
            self.set_banner("EXTRA LIFE!", 2.0)
        if self.pellets <= 0:
            self.won = True
            self.state = "won"
            self.sounds.play("win")
            self.habits.save()

    def check_collisions(self):
        p = self.pac
        px, py = p.pos()
        for g in self.ghosts:
            if g.dead or not (g.out or g.leaving):
                continue
            gx, gy = g.pos()
            if math.hypot(gx - px, gy - py) >= 0.68:
                continue
            if g.fright > 0:
                g.dead = True
                g.out = True
                g.fright = 0.0
                g.leaving = False
                self.fright_chain += 1
                self.captures += 1
                self.score += 200 * (2 ** min(self.fright_chain - 1, 3))
                self.sounds.play("ghost")
            else:
                self.lives -= 1
                self.pressure *= 0.7              # rubber-band: ease off after a death
                self.since_death = 0.0
                self.state = "dying"
                self.death_t = 1.3
                self.sounds.play("death")
                return

    def update(self, dt):
        self.clock_t += dt
        self.hi = max(self.hi, self.score)
        if self.banner_t > 0:
            self.banner_t -= dt

        if self.state == "ready":
            self.ready_t -= dt
            if self.ready_t <= 0:
                self.state = "play"
            return
        if self.state == "dying":
            self.death_t -= dt
            if self.death_t <= 0:
                if self.lives <= 0:
                    self.over = True
                    self.state = "over"
                    self.habits.save()
                else:
                    self.spawn()
            return
        if self.state in ("over", "won"):
            return

        self._fcache = {}
        self.boost = max(0.0, self.boost - dt)
        self.aggro = max(0.0, self.aggro - dt)
        self.update_gates(dt)
        self.update_perf(dt)
        self.update_mode(dt)
        self.update_special_ghosts(dt)
        self.update_toxic(dt)
        self.update_void(dt)
        self.update_new_ghosts(dt)
        self.habits.tick(dt)

        p = self.pac
        p.tp_cd -= dt
        if p.moving:
            self.habits.dir_time[self.last_dir] += dt
        px, py = p.pos()
        self.habits.corner_time[(1 if py >= H / 2 else 0) * 2 + (1 if px >= W / 2 else 0)] += dt

        self.ai_age += dt
        if self.ai_dirty or self.ai_age >= 0.12:
            self.refresh_ai()

        for g in self.ghosts:
            g.fright = max(0.0, g.fright - dt)
            g.tp_cd -= dt
            g.plan_t -= dt
            g.clyde_t -= dt

        self.step(p, self.pac_speed(), dt, self.pac_decide)
        current_pac_tile = (p.tx, p.ty)
        if not self.player_trail or self.player_trail[-1] != current_pac_tile:
            self.player_trail.append(current_pac_tile)
        self.collect_tile()
        if self.state != "play":
            return
        if self.fruit:
            self.fruit["timer"] -= dt
            if self.fruit["timer"] <= 0:
                self.fruit = None
        self.collect_fruit()

        self.release_ghosts(dt)
        for g in self.ghosts:
            if g.wait > 0:
                g.wait -= dt
                continue
            if not (g.out or g.leaving or g.dead):
                continue
            self.step(g, self.ghost_speed(g), dt, self.ghost_decide)

        self.check_collisions()

    # Toxic trail slows Pac-Man; Shade warns without revealing itself.
        if (self.pac.tx, self.pac.ty) in self.toxic_hazards:
            self.boost = min(self.boost, 0.0)
        shade = next((g for g in self.ghosts if g.i == 10 and g.out and not g.dead), None)
        if shade and shade.invisible_t > 0:
            sx, sy = shade.pos()
            px, py = self.pac.pos()
            d = math.hypot(sx - px, sy - py)
            if d < 4.0 and self.warning_t <= 0:
                self.warning_t = 1.2
                self.set_banner("WARNING: SOMETHING IS NEARBY...", 1.0)
        self.warning_t = max(0.0, self.warning_t - dt)


    def build_wall_surface(self):
        surf = pygame.Surface((W * T, H * T))
        surf.fill((0, 0, 0))
        for y in range(H):
            for x in range(W):
                if self.grid[y][x] not in "#S":
                    continue
                px, py = x * T, y * T
                segs = [((px, py), (px + T, py)), ((px, py), (px, py + T)),
                        ((px, py + T), (px + T, py + T)), ((px + T, py), (px + T, py + T))]
                for k, (dx, dy) in enumerate(DIRS):
                    nx, ny = x + dx, y + dy
                    nc = self.grid[ny][nx] if (0 <= nx < W and 0 <= ny < H) else None
                    if nc is None or nc not in "#S":
                        pygame.draw.line(surf, (42, 60, 255), segs[k][0], segs[k][1], 2)
        self.wall_surface = surf

    def mode_label(self):
        if any(g.fright > 0 for g in self.ghosts):
            return "FRIGHTENED", (60, 130, 255)
        if self.special_kind:
            return self.special_kind, (255, 80, 220)
        m = self.effective_mode()
        if m == "hunt":
            return "HUNT", (255, 80, 80)
        if self.aggro > 0:
            return m.upper() + "+", (255, 140, 60)
        return m.upper(), (255, 255, 255)

    def draw(self, screen, font, small, big):
        if self.wall_surface is None:
            self.build_wall_surface()
        screen.fill((0, 0, 0))

        # Header.
        yel = (255, 216, 0)
        screen.blit(font.render(f"SCORE {self.score}", True, yel), (8, 10))
        hi = font.render(f"HI {self.hi}", True, (200, 200, 200))
        screen.blit(hi, (W * T // 4 + 10, 10))
        lv = font.render(f"LEVEL {self.level}", True, yel)
        screen.blit(lv, (W * T // 2 + 20, 10))
        lives = font.render(f"LIVES {max(0, self.lives)}", True, yel)
        screen.blit(lives, (W * T - lives.get_width() - 8, 10))

        screen.blit(self.wall_surface, (0, TOP))
        self.draw_maze_items(screen)

        if self.fruit:
            self.draw_fruit(screen)
        if self.show_ai:
            self.draw_ai_vision(screen)

        self.draw_pac(screen)
        for g in self.ghosts:
            self.draw_ghost(screen, g)

        # Banner / ready text.
        if self.state == "ready":
            t = big.render("READY!", True, (255, 255, 0))
            screen.blit(t, (W * T // 2 - t.get_width() // 2, TOP + 19 * T + 2))
        if self.banner_t > 0 and self.banner:
            t = font.render(self.banner, True, (255, 255, 255))
            bx = W * T // 2 - t.get_width() // 2
            pygame.draw.rect(screen, (0, 0, 0), (bx - 6, TOP + 10 * T - 2, t.get_width() + 12, 24))
            screen.blit(t, (bx, TOP + 10 * T))

        self.draw_panel(screen, font, small)
        if self.over or self.won:
            self.draw_end_screen(screen, font, big)

    def draw_maze_items(self, screen):
        # Dots / power pellets.
        for y in range(H):
            for x in range(W):
                c = self.grid[y][x]
                px, py = x * T, y * T + TOP
                if c == "-":
                    pygame.draw.line(screen, (255, 184, 255), (px, py + T // 2), (px + T, py + T // 2), 2)
                elif c == ".":
                    pygame.draw.circle(screen, (255, 216, 176), (px + T // 2, py + T // 2), 3)
                elif c == "o":
                    kind = self.maze.power.get((x, y), "normal")
                    info = PELLET_TYPES[kind]
                    pulse = 0 if int(self.clock_t * 5) % 2 == 0 else 2
                    r = info["radius"] - (pulse if kind != "risk" else 0)
                    pygame.draw.circle(screen, info["color"], (px + T // 2, py + T // 2), r)
                    if kind == "mega":
                        pygame.draw.circle(screen, (255, 255, 200), (px + T // 2, py + T // 2), r + 3, 1)
                    elif kind == "chain":
                        pygame.draw.circle(screen, (120, 40, 200), (px + T // 2, py + T // 2), r + 3, 1)

        # Toxic temporary danger trails.
        for (x, y), remain in self.toxic_hazards.items():
            cx, cy = x * T + T // 2, y * T + TOP + T // 2
            pulse = 2 + int(2 * math.sin(self.clock_t * 8))
            pygame.draw.circle(screen, (55, 255, 80), (cx, cy), max(2, pulse + 2), 1)
            pygame.draw.circle(screen, (25, 150, 50), (cx, cy), 2)

        # Void-blocked tiles.
        for x, y in self.void_blocks:
            px, py = x * T, y * T + TOP
            pygame.draw.rect(screen, (15, 15, 20), (px, py, T, T))
            pygame.draw.line(screen, (100, 20, 120), (px, py), (px+T, py+T), 2)
            pygame.draw.line(screen, (100, 20, 120), (px+T, py), (px, py+T), 2)

        # Teleporters.
        cols = [(200, 60, 255), (60, 255, 160)]
        for t, pid in self.maze.tele_id.items():
            cx, cy = t[0] * T + T // 2, t[1] * T + TOP + T // 2
            for k in range(3):
                r = int(4 + k * 3 + 1.5 * math.sin(self.clock_t * 4 + k))
                pygame.draw.circle(screen, cols[pid], (cx, cy), r, 1)

        # One-way arrows.
        for (x, y), (dx, dy) in self.maze.oneway.items():
            cx, cy = x * T + T // 2, y * T + TOP + T // 2
            tip = (cx + dx * 8, cy + dy * 8)
            bx, by = cx - dx * 3, cy - dy * 3
            l = (bx - dy * 6, by + dx * 6)
            r = (bx + dy * 6, by - dx * 6)
            pygame.draw.polygon(screen, (0, 200, 255), [tip, l, r], 2)

        # Gates.
        for g in self.gates:
            x, y = g["pos"]
            px, py = x * T, y * T + TOP
            if g["closed"]:
                pygame.draw.rect(screen, (255, 140, 0), (px + 1, py + 1, T - 2, T - 2))
                pygame.draw.line(screen, (120, 60, 0), (px + 2, py + 2), (px + T - 3, py + T - 3), 2)
                pygame.draw.line(screen, (120, 60, 0), (px + T - 3, py + 2), (px + 2, py + T - 3), 2)
            elif g["warn"] and int(self.clock_t * 8) % 2 == 0:
                pygame.draw.rect(screen, (255, 200, 60), (px + 1, py + 1, T - 2, T - 2), 2)
            else:
                for cx, cy in ((px + 2, py + 2), (px + T - 3, py + 2), (px + 2, py + T - 3), (px + T - 3, py + T - 3)):
                    pygame.draw.circle(screen, (110, 70, 10), (cx, cy), 2)

    def draw_pac(self, screen):
        if self.state == "dying":
            prog = 1.0 - max(0.0, self.death_t) / 1.3
            if prog >= 1.0:
                return
            mouth = 0.05 + prog * (math.pi - 0.05)
            f = -math.pi / 2
        else:
            mouth = 0.05 + abs(math.sin(self.clock_t * 12)) * 0.60
            f = self.pac.face
            if not self.pac.moving:
                mouth = 0.35
        x, y = self.pac.pos()
        cx = (x + 0.5) * T
        cy = (y + 0.5) * T + TOP
        r = T * 0.45
        pts = [(cx, cy)]
        for i in range(25):
            a = f + mouth + i * (2 * math.pi - 2 * mouth) / 24
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        pygame.draw.polygon(screen, (255, 224, 0), pts)
        if self.boost > 0 and self.state != "dying":
            pygame.draw.circle(screen, (0, 255, 220), (int(cx), int(cy)), int(r) + 3, 2)

    def draw_ghost(self, screen, g):
        x, y = g.pos()
        if not (g.out or g.leaving or g.dead):
            y += 0.12 * math.sin(self.clock_t * 5 + g.i)
        cx = int((x + 0.5) * T)
        cy = int((y + 0.5) * T + TOP)
        r = int(T * 0.42)
        if g.dead:
            self.draw_eyes(screen, g, cx, cy)
            return

        # Shade is invisible except for a warning flicker; the eyes are hidden too.
        if g.i == 10 and g.invisible_t > 0 and g.visible_flash <= 0 and g.fright <= 0:
            return

        if g.fright > 0:
            flash = g.fright < 2 and int(self.clock_t * 8) % 2
            color = (255, 255, 255) if flash else (35, 65, 255)
        else:
            color = GHOST_COLORS[g.i]
        pygame.draw.circle(screen, color, (cx, cy - 2), r)
        pygame.draw.rect(screen, color, (cx - r, cy - 2, 2 * r, r + 4))
        for k in range(3):
            fx = cx - r + int((k * 2 + 1) * r / 3)
            pygame.draw.circle(screen, (0, 0, 0), (fx, cy + r), 3)
        self.draw_eyes(screen, g, cx, cy)
        if self.effective_mode() == "hunt" and g.fright <= 0:
            pygame.draw.circle(screen, (255, 60, 60), (cx, cy), r + 3, 1)

        if g.i == 5:  # Toxic
            pygame.draw.circle(screen, (60, 255, 80), (cx, cy), r + 4, 1)
        elif g.i == 6 and g.phase_t > 0:
            pygame.draw.circle(screen, (240, 240, 255), (cx, cy), r + 4, 2)
        elif g.i == 7 and g.charge_t > 0:
            pygame.draw.line(screen, (255, 100, 40), (cx, cy), (cx + g.dx * 12, cy + g.dy * 12), 3)
        elif g.i == 9:
            pygame.draw.circle(screen, (255, 240, 60), (cx, cy), r + 3, 1)
        elif g.i == 12:
            pygame.draw.rect(screen, (255, 145, 30), (cx - r - 3, cy - r - 3, 2*r + 6, 2*r + 6), 1)
        elif g.i == 14:
            pygame.draw.line(screen, (255, 180, 210), (cx-r-3, cy), (cx+r+3, cy), 1)
        elif g.i == 17 and g.split_t > 0:
            for a in (0, math.pi/2, math.pi, 3*math.pi/2):
                sx = int(cx + math.cos(a) * (r + 7))
                sy = int(cy + math.sin(a) * (r + 7))
                pygame.draw.circle(screen, (220, 40, 230), (sx, sy), max(2, r//3))

        if self.special_kind == "SWARM" and g.i == 5:
            for k in range(22):
                a = self.swarm_phase + k * (2 * math.pi / 22)
                rr = r + 8 + (k % 4) * 3
                sx = int(cx + math.cos(a) * rr)
                sy = int(cy + math.sin(a) * rr)
                pygame.draw.circle(screen, (190, 190, 190), (sx, sy), 2)

        if self.special_kind == "KING" and g.i == 0:
            pygame.draw.polygon(screen, (255, 215, 40),
                                [(cx-8, cy-r-4), (cx-5, cy-r-10), (cx, cy-r-5),
                                 (cx+5, cy-r-10), (cx+8, cy-r-4)])

    def draw_eyes(self, screen, g, cx, cy):
        for side in (-1, 1):
            ex, ey = cx + side * 4, cy - 5
            pygame.draw.circle(screen, (255, 255, 255), (ex, ey), 4)
            pygame.draw.circle(screen, (20, 40, 255),
                               (ex + int(g.dx * 1.5), ey + int(g.dy * 1.5)), 2)

    def draw_ai_vision(self, screen):
        for i, (x, y) in enumerate(self.path_h[:14]):
            pygame.draw.circle(screen, (255, 255, 0), (x * T + T // 2, y * T + TOP + T // 2), 2)
        for i, (x, y) in enumerate(self.spots):
            cx, cy = x * T + T // 2, y * T + TOP + T // 2
            pygame.draw.line(screen, GHOST_COLORS[min(i + 1, 3)], (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
            pygame.draw.line(screen, GHOST_COLORS[min(i + 1, 3)], (cx - 5, cy + 5), (cx + 5, cy - 5), 2)
        for g in self.ghosts:
            if g.dead or not g.out:
                continue
            gx, gy = g.pos()
            tx, ty = g.last_target
            pygame.draw.line(screen, GHOST_COLORS[g.i],
                             (int((gx + 0.5) * T), int((gy + 0.5) * T + TOP)),
                             (tx * T + T // 2, ty * T + TOP + T // 2), 1)

    def draw_fruit(self, screen):
        f = self.fruit
        x, y = f["pos"]
        cx = x * T + T // 2
        cy = y * T + TOP + T // 2
        ring = (0, 255, 220) if f["shown"] == "boost" else (255, 70, 70)
        if f["timer"] > 3 or int(self.clock_t * 6) % 2 == 0:
            pygame.draw.circle(screen, ring, (cx, cy), 13, 1)
        kind = f["kind"]
        if kind == 0:
            pygame.draw.circle(screen, (230, 30, 50), (cx - 4, cy + 3), 5)
            pygame.draw.circle(screen, (230, 30, 50), (cx + 4, cy + 3), 5)
            pygame.draw.line(screen, (40, 190, 70), (cx - 4, cy - 2), (cx, cy - 8), 2)
            pygame.draw.line(screen, (40, 190, 70), (cx + 4, cy - 2), (cx, cy - 8), 2)
        elif kind == 1:
            pts = [(cx, cy + 8), (cx - 9, cy - 4), (cx - 5, cy - 8), (cx, cy - 5), (cx + 5, cy - 8), (cx + 9, cy - 4)]
            pygame.draw.polygon(screen, (235, 45, 65), pts)
        elif kind == 2:
            pygame.draw.circle(screen, (255, 145, 25), (cx, cy), 9)
            pygame.draw.circle(screen, (80, 190, 60), (cx + 4, cy - 8), 3)
        elif kind == 3:
            pygame.draw.circle(screen, (235, 40, 45), (cx - 4, cy), 7)
            pygame.draw.circle(screen, (235, 40, 45), (cx + 4, cy), 7)
            pygame.draw.rect(screen, (90, 55, 25), (cx - 1, cy - 10, 2, 5))
            pygame.draw.ellipse(screen, (70, 190, 75), (cx, cy - 12, 7, 4))
        elif kind == 4:
            pygame.draw.ellipse(screen, (75, 205, 80), (cx - 10, cy - 7, 20, 14))
            for off in (-5, 0, 5):
                pygame.draw.line(screen, (30, 130, 55), (cx + off, cy - 6), (cx + off, cy + 6), 1)
        elif kind == 5:
            pygame.draw.polygon(screen, (40, 120, 255), [(cx, cy - 10), (cx - 8, cy + 7), (cx, cy + 3), (cx + 8, cy + 7)])
            pygame.draw.circle(screen, (255, 80, 80), (cx, cy), 3)
        elif kind == 6:
            pygame.draw.circle(screen, (255, 210, 40), (cx, cy), 9)
            pygame.draw.rect(screen, (255, 210, 40), (cx - 9, cy, 18, 6))
            pygame.draw.circle(screen, (255, 210, 40), (cx, cy + 8), 3)
        else:
            pygame.draw.circle(screen, (255, 215, 40), (cx - 5, cy - 2), 5, 3)
            pygame.draw.line(screen, (255, 215, 40), (cx, cy - 2), (cx + 10, cy - 2), 3)
            pygame.draw.line(screen, (255, 215, 40), (cx + 6, cy - 2), (cx + 6, cy + 4), 3)

    def draw_panel(self, screen, font, small):
        y0 = TOP + H * T + 4
        label, color = self.mode_label()
        adapt = "ADAPT" if (self.adaptive and self.difficulty >= 2) else "FIXED"
        screen.blit(small.render(f"{label:<11}{self.cfg['name']:<10}AI:{adapt}   PRESSURE", True, color), (8, y0))
        bx = 8 + 8 * 34 + 130
        pygame.draw.rect(screen, (60, 60, 60), (bx, y0 + 2, 120, 12), 1)
        pygame.draw.rect(screen, (255, int(220 - 180 * self.pressure), 40),
                         (bx + 1, y0 + 3, int(118 * clamp(self.pressure)), 10))

        iqs = " ".join(f"{GHOST_NAMES[g.i][0]}{self.ghost_iq(g)}" for g in self.ghosts)
        plans = "/".join(g.plan[:5] for g in self.ghosts)
        screen.blit(small.render(f"IQ {iqs}   PLAN {plans}", True, (190, 190, 190)), (8, y0 + 18))
        active = self.special_kind if self.special_kind else "NONE"
        screen.blit(small.render(f"GHOSTS 19  SPECIAL:{active}", True, (220, 150, 255)), (8, y0 + 34))

        h = self.habits
        fd = h.fav_dir()
        fe = h.fav_escape()
        fc = h.fav_corner()
        ft = h.fav_tunnel_entry()
        s, l, r = h.turn_percent()
        corner = ("TL", "TR", "BL", "BR")[fc] if fc is not None else "-"
        line = (f"HABITS fav:{DIR_NAMES[fd] if fd is not None else '-'} "
                f"esc:{DIR_NAMES[fe] if fe is not None else '-'} "
                f"turns S{s} L{l} R{r} corner:{corner} tunnel:{'Y' if ft else '-'}")
        screen.blit(small.render(line, True, (170, 200, 255)), (8, y0 + 52))

        fx = []
        if self.boost > 0:
            fx.append(f"BOOST {self.boost:.0f}")
        if self.aggro > 0:
            fx.append(f"ENRAGED {self.aggro:.0f}")
        fx_text = "  ".join(fx) if fx else "1-4 DIFF  5 ADAPT  V AI-VIEW  K FORGET  M MUTE"
        screen.blit(small.render(fx_text, True, (255, 200, 90) if fx else (130, 130, 130)), (8, y0 + 70))
        screen.blit(small.render("PELLETS: cream=normal gold=mega red=risk purple=chain", True, (130, 130, 130)),
                    (8, y0 + 88))

    def draw_end_screen(self, screen, font, big):
        oy = TOP + H * T // 2 - 55
        pygame.draw.rect(screen, (0, 0, 0), (0, oy, W * T, 110))
        if self.won:
            title, color, sub = "LEVEL CLEAR!", (124, 255, 124), "Press Enter for the next level"
        else:
            title, color, sub = "GAME OVER", (255, 80, 80), "Press Enter to restart"
        msg = big.render(title, True, color)
        s = font.render(sub, True, (255, 255, 255))
        screen.blit(msg, (W * T // 2 - msg.get_width() // 2, oy + 12))
        screen.blit(s, (W * T // 2 - s.get_width() // 2, oy + 58))


# =========================================================
# MAIN
# =========================================================

async def main():
    fresh = "--fresh" in sys.argv
    try:
        pygame.mixer.pre_init(44100, -16, 1, 512)
    except Exception:
        pass
    pygame.init()

    screen = pygame.display.set_mode((W * T, H * T + TOP + PANEL))
    pygame.display.set_caption("PAINFUL PAC-MAN")

    font = pygame.font.SysFont("couriernew", 17, bold=True)
    small = pygame.font.SysFont("couriernew", 14, bold=True)
    big = pygame.font.SysFont("couriernew", 31, bold=True)

    clock = pygame.time.Clock()
    sounds = SoundFX()
    habits = Habits(persist=False) if fresh else Habits.load()
    game = Game(sounds, habits)

    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                k = event.key
                if k == pygame.K_ESCAPE:
                    running = False
                elif k in KEYS:
                    game.set_want(DIRS[KEYS[k]])
                elif k == pygame.K_m:
                    sounds.toggle()
                elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    game.set_difficulty(k - pygame.K_0)
                elif k in (pygame.K_5, pygame.K_t):
                    game.adaptive = not game.adaptive
                elif k == pygame.K_v:
                    game.show_ai = not game.show_ai
                elif k == pygame.K_k:
                    habits.forget()
                    game.habits.new_maze()
                    game.set_banner("THE GHOSTS FORGOT EVERYTHING", 2.0)
                elif k == pygame.K_RETURN:
                    if game.won:
                        game.next_level()
                    elif game.over:
                        game.new_game()

        game.update(dt)
        game.draw(screen, font, small, big)
        pygame.display.flip()
        # Give the browser/WASM event loop time to process input and render.
        await asyncio.sleep(0)

    habits.save()
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
