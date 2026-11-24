#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUARDIÃO - Missão Segurança
Jogo educativo de segurança feito com Pygame.

Como jogar
  1. Digite seu nome e escolha a área de atuação: Casa, Hospital, Indústria, Mercado ou Museu.
  2. No mapa isométrico, arraste cada medida de segurança (lista à direita) até um ponto de alerta (!).
       - Arraste e solte, ou clique na medida e depois clique no ponto.
       - Arraste uma medida já colocada para mover/trocar; clique direito no ponto para remover.
       - Passe o mouse sobre medidas e pontos para ver dicas.
       - Botão "Dica" (3 por partida): aponta um ponto mal protegido e destaca a medida certa.
  3. Clique em "Iniciar simulação": a noite cai e as ameaças tentam invadir.
  4. Pontuação por ponto: medida ideal = 100%, medida parcial = 50%, sem proteção adequada = 0%.

Resolução
  - A janela se ajusta sozinha ao tamanho do seu monitor e tudo é desenhado em resolução nativa.
  - Botão "Tela cheia" (ou F11 / Alt+Enter) alterna tela cheia a qualquer momento.
  - Para abrir já em tela cheia:  python guardiao_seguranca.py --tela-cheia
  - Para forçar um tamanho:  python guardiao_seguranca.py --escala 1.5   (1.0 = 1280x720)

Requisitos: Python 3.8+ e pygame 2.1+      (pip install pygame)
Executar:   python guardiao_seguranca.py
"""

import math
import os
import random
import sys

# Evita que o Windows estique (e borre) a janela quando a escala de tela é 125%/150%.
if sys.platform == "win32":
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame
import pygame.gfxdraw as gfx

# ---------------------------------------------------------------------------
# Configuração geral e escala
# ---------------------------------------------------------------------------
BASE_W, BASE_H = 1280, 720      # espaço de projeto; tudo é multiplicado por K na tela
FPS = 60
GW, GH = 16, 12                 # tamanho do terreno (em tiles)
FLOOR_Z = 4                     # altura do piso interno
SQ2 = 1.41421

K = 1.0
W, H = BASE_W, BASE_H
TOP_H, SIDE_W = 64, 340
MAP_AREA = pygame.Rect(0, 64, 940, 656)
HW, HH, ZS = 33.0, 16.5, 1.1
MAP_W, MAP_H = 940, 620
ORIGIN_X, ORIGIN_Y = 0.0, 0.0

_FONT_PATH = {}
_FONT_CACHE = {}
_TEXT_CACHE = {}
_ICON_CACHE = {}
_SHADOW_CACHE = {}
_GLOW_CACHE = {}
_ADD_GLOW_CACHE = {}
_GRAD_CACHE = {}
_STATIC_WORLDS = {}
_PREVIEWS = {}


def S(v):
    """Converte uma medida do espaço de projeto (1280x720) para pixels de tela."""
    return int(round(v * K))


def apply_scale(k):
    global K, W, H, TOP_H, SIDE_W, MAP_AREA, HW, HH, ZS, MAP_W, MAP_H, ORIGIN_X, ORIGIN_Y
    K = float(k)
    W, H = S(BASE_W), S(BASE_H)
    TOP_H, SIDE_W = S(64), S(340)
    MAP_AREA = pygame.Rect(0, TOP_H, W - SIDE_W, H - TOP_H)
    HW, HH, ZS = 33.0 * K, 16.5 * K, 1.1 * K
    MAP_W = MAP_AREA.w
    pad_top = 80 * K
    MAP_H = int((GW + GH) * HH + pad_top + 86 * K)
    ORIGIN_X = GH * HW + (MAP_W - (GW + GH) * HW) / 2.0
    ORIGIN_Y = pad_top
    for c in (_FONT_CACHE, _TEXT_CACHE, _ICON_CACHE, _SHADOW_CACHE, _GLOW_CACHE, _ADD_GLOW_CACHE,
              _GRAD_CACHE, _STATIC_WORLDS, _PREVIEWS):
        c.clear()


apply_scale(1.0)

# Tema (contraste reforçado para leitura)
BG_DARK = (12, 16, 32)
PANEL = (22, 28, 50)
PANEL_2 = (33, 41, 70)
PANEL_3 = (48, 60, 100)
TEXT = (242, 245, 252)
MUTED = (176, 186, 216)
SUBTLE = (136, 148, 186)
ACCENT = (86, 168, 255)
GREEN = (58, 206, 126)
AMBER = (255, 184, 64)
RED = (242, 78, 92)
GOLD = (255, 205, 80)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def clamp(v, a=0.0, b=255.0):
    return a if v < a else b if v > b else v


def shade(c, f):
    return (int(clamp(c[0] * f)), int(clamp(c[1] * f)), int(clamp(c[2] * f)))


def mix(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def lighten(c, t):
    return mix(c, (255, 255, 255), t)


def rgba(c, a):
    return (c[0], c[1], c[2], int(clamp(a)))


def ease_out_cubic(t):
    t = clamp(t, 0.0, 1.0)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease_out_back(t, s=1.70158):
    t = clamp(t, 0.0, 1.0) - 1
    return t * t * ((s + 1) * t + s) + 1


def approach(cur, target, dt, speed=12.0):
    return cur + (target - cur) * min(1.0, dt * speed)


def iso(gx, gy, gz=0.0):
    """Coordenadas do grid -> coordenadas locais da superfície do mapa."""
    return (ORIGIN_X + (gx - gy) * HW, ORIGIN_Y + (gx + gy) * HH - gz * ZS)


def ipt(p):
    return (int(round(p[0])), int(round(p[1])))


def point_in_poly(x, y, pts):
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Fontes e texto (tamanhos em unidades de projeto; convertidos com K)
# ---------------------------------------------------------------------------
FONT_NAMES = ["segoeui", "segoe ui", "inter", "opensans", "helveticaneue", "helvetica",
              "arial", "dejavusans", "liberationsans", "freesans"]


def _find_font(bold):
    for name in FONT_NAMES:
        try:
            p = pygame.font.match_font(name, bold=bold)
        except Exception:
            p = None
        if p:
            return p
    return None


def font(size, bold=False):
    px = max(8, int(round(size * K)))
    key = (px, bold)
    f = _FONT_CACHE.get(key)
    if f is None:
        if bold not in _FONT_PATH:
            _FONT_PATH[bold] = _find_font(bold)
        path = _FONT_PATH[bold]
        try:
            f = pygame.font.Font(path, px) if path else pygame.font.Font(None, int(px * 1.32))
        except Exception:
            f = pygame.font.Font(None, int(px * 1.32))
        if bold:
            if False not in _FONT_PATH:
                _FONT_PATH[False] = _find_font(False)
            if path is None or path == _FONT_PATH[False]:
                try:
                    f.set_bold(True)   # sem arquivo negrito: negrito sintético
                except Exception:
                    pass
        _FONT_CACHE[key] = f
    return f


def text_surf(txt, size, color, bold=False):
    key = (txt, size, tuple(color[:3]), bold)
    s = _TEXT_CACHE.get(key)
    if s is None:
        if len(_TEXT_CACHE) > 2500:
            _TEXT_CACHE.clear()
        s = font(size, bold).render(txt, True, tuple(color[:3]))
        _TEXT_CACHE[key] = s
    return s


def draw_text(surf, txt, size, color, pos, bold=False, anchor="topleft", alpha=255, shadow=None):
    s = text_surf(txt, size, color, bold)
    r = s.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if shadow:
        sh = text_surf(txt, size, shadow, bold)
        if alpha < 255:
            sh = sh.copy()
            sh.set_alpha(int(clamp(alpha * 0.7)))
        surf.blit(sh, r.move(0, max(1, S(1.5))))
    if alpha < 255:
        s = s.copy()
        s.set_alpha(int(clamp(alpha)))
    surf.blit(s, r)
    return r


def outlined_text(txt, size, color, outline=(18, 20, 32), bold=True):
    base = font(size, bold).render(txt, True, color)
    edge = font(size, bold).render(txt, True, outline)
    o = max(1, S(2))
    w, h = base.get_width() + 2 * o, base.get_height() + 2 * o
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for dx in (0, o, 2 * o):
        for dy in (0, o, 2 * o):
            if (dx, dy) != (o, o):
                s.blit(edge, (dx, dy))
    s.blit(base, (o, o))
    return s


def wrap(txt, size, maxw, bold=False):
    """maxw em pixels de tela."""
    f = font(size, bold)
    lines, cur = [], ""
    for word in txt.split():
        test = (cur + " " + word).strip()
        if f.size(test)[0] <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def ellipsize(txt, size, maxw, bold=False):
    f = font(size, bold)
    if f.size(txt)[0] <= maxw:
        return txt
    while txt and f.size(txt + "...")[0] > maxw:
        txt = txt[:-1]
    return txt.rstrip() + "..."


def fit_text(txt, size, maxw, bold=False, min_size=12):
    s = size
    while s > min_size and font(s, bold).size(txt)[0] > maxw:
        s -= 1
    return ellipsize(txt, s, maxw, bold), s


# ---------------------------------------------------------------------------
# Superfícies auxiliares (sombras, gradientes, brilhos) - medidas em pixels de tela
# ---------------------------------------------------------------------------
def soft_shadow(w, h, radius, blur, alpha):
    alpha = int(alpha) // 10 * 10
    key = (w, h, radius, blur, alpha)
    s = _SHADOW_CACHE.get(key)
    if s is None:
        if len(_SHADOW_CACHE) > 250:
            _SHADOW_CACHE.clear()
        pad = blur * 2
        big = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
        pygame.draw.rect(big, (0, 0, 0, alpha), (pad, pad, w, h), border_radius=radius)
        sw, sh = big.get_size()
        small = pygame.transform.smoothscale(big, (max(1, sw // 8), max(1, sh // 8)))
        s = pygame.transform.smoothscale(small, (sw, sh))
        _SHADOW_CACHE[key] = s
    return s


def grad_rect(w, h, top, bottom, radius):
    """Retângulo arredondado com degradê vertical (cacheado)."""
    key = (w, h, top, bottom, radius)
    s = _GRAD_CACHE.get(key)
    if s is None:
        if len(_GRAD_CACHE) > 300:
            _GRAD_CACHE.clear()
        s = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
        for yy in range(h):
            pygame.draw.line(s, rgba(mix(top, bottom, yy / max(1, h - 1)), 255), (0, yy), (w, yy))
        if radius > 0:
            mask = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
            s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        _GRAD_CACHE[key] = s
    return s


def draw_panel(surf, rect, color, radius=None, shadow=True, border=None, border_w=1, shadow_alpha=90,
               alpha=255, top=None):
    """Painel arredondado. rect/radius em pixels de tela. top = cor do topo para degradê."""
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    radius = S(14) if radius is None else radius
    if shadow:
        blur = S(14)
        sh = soft_shadow(rect.w, rect.h, radius, blur, shadow_alpha)
        if alpha < 255:
            sh = sh.copy()
            sh.set_alpha(alpha)
        surf.blit(sh, (rect.x - blur * 2, rect.y - blur * 2 + S(6)))
    if top is not None:
        g = grad_rect(rect.w, rect.h, top, color, radius)
        if alpha < 255:
            g = g.copy()
            g.set_alpha(alpha)
        surf.blit(g, rect.topleft)
    elif alpha < 255:
        tmp = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(tmp, rgba(color, alpha), tmp.get_rect(), border_radius=radius)
        surf.blit(tmp, rect.topleft)
    else:
        pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border:
        if alpha < 255:
            tmp = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(tmp, rgba(border, alpha), tmp.get_rect(), max(1, border_w), border_radius=radius)
            surf.blit(tmp, rect.topleft)
        else:
            pygame.draw.rect(surf, border, rect, max(1, border_w), border_radius=radius)


def vgradient(w, h, top, bottom, mid=None):
    s = pygame.Surface((max(1, w), max(1, h)))
    for y in range(h):
        t = y / max(1, h - 1)
        if mid is not None:
            c = mix(top, mid, t * 2) if t < 0.5 else mix(mid, bottom, (t - 0.5) * 2)
        else:
            c = mix(top, bottom, t)
        pygame.draw.line(s, c, (0, y), (w, y))
    return s


def glow_surf(radius, color, strength=1.0):
    """Brilho radial com alpha (mistura normal). radius em pixels."""
    radius = max(2, int(radius))
    key = (radius, color, round(strength, 2))
    s = _GLOW_CACHE.get(key)
    if s is None:
        if len(_GLOW_CACHE) > 200:
            _GLOW_CACHE.clear()
        s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        step = max(1, radius // 60)
        for r in range(radius, 0, -step):
            a = int(255 * strength * (1 - r / radius) ** 1.8)
            pygame.draw.circle(s, rgba(color, a), (radius, radius), r)
        _GLOW_CACHE[key] = s
    return s


def add_glow_surf(radius, color, flat=1.0):
    key = (radius, color, flat)
    s = _ADD_GLOW_CACHE.get(key)
    if s is None:
        tmp = pygame.Surface((radius * 2, radius * 2))
        tmp.fill((0, 0, 0))
        step = max(1, radius // 50)
        for r in range(radius, 0, -step):
            f = (1 - r / radius) ** 1.6
            pygame.draw.circle(tmp, shade(color, f), (radius, radius), r)
        if flat != 1.0:
            s = pygame.transform.smoothscale(tmp, (radius * 2, max(1, int(radius * 2 * flat))))
        else:
            s = tmp
        _ADD_GLOW_CACHE[key] = s
    return s


def blit_add_glow(surf, x, y, radius, color, flat=1.0, k=1.0):
    """Brilho aditivo. Intensidade e raio quantizados para manter o cache pequeno."""
    k = round(clamp(k, 0.0, 1.0) * 8) / 8.0
    if k <= 0:
        return
    step = max(2, S(6))
    radius = max(step, int(radius) // step * step)
    if len(_ADD_GLOW_CACHE) > 300:
        _ADD_GLOW_CACHE.clear()
    g = add_glow_surf(radius, shade(color, k), flat)
    surf.blit(g, (int(x - g.get_width() / 2), int(y - g.get_height() / 2)), special_flags=pygame.BLEND_RGB_ADD)


def blur_surface(s, factor):
    w, h = s.get_size()
    small = pygame.transform.smoothscale(s, (max(1, int(w / factor)), max(1, int(h / factor))))
    return pygame.transform.smoothscale(small, (w, h))


def add_outline(surf, color=(22, 24, 40), alpha=150, d=None):
    """Contorno escuro fino ao redor da silhueta (estilo ilustração)."""
    d = d or max(1, int(round(K)))
    w, h = surf.get_size()
    sil = surf.copy()
    sil.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGB_MULT)
    sil.fill(tuple(color) + (0,), special_flags=pygame.BLEND_RGB_ADD)
    ring = pygame.Surface((w, h), pygame.SRCALPHA)
    for dx, dy in ((-d, 0), (d, 0), (0, -d), (0, d)):
        ring.blit(sil, (dx, dy))
    ring.set_alpha(alpha)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(ring, (0, 0))
    out.blit(surf, (0, 0))
    return out


# ---------------------------------------------------------------------------
# Ícones vetoriais (desenhados em 4x e suavizados)
# ---------------------------------------------------------------------------
def icon(kind, size, color=(255, 255, 255)):
    size = max(4, int(round(size * K)))
    key = (kind, size, color)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    S = size * 4
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    k = S / 100.0
    C = rgba(color, 255)
    T = (0, 0, 0, 0)

    def p(x, y):
        return (int(x * k), int(y * k))

    def R(x, y, w, h):
        return pygame.Rect(int(x * k), int(y * k), max(1, int(w * k)), max(1, int(h * k)))

    def circ(x, y, r, c=C, w=0):
        pygame.draw.circle(s, c, p(x, y), max(1, int(r * k)), max(1, int(w * k)) if w else 0)

    def rect(x, y, w, h, c=C, rad=0, wd=0):
        pygame.draw.rect(s, c, R(x, y, w, h), max(1, int(wd * k)) if wd else 0, border_radius=int(rad * k))

    def pg(pts, c=C):
        pygame.draw.polygon(s, c, [p(*q) for q in pts])

    def line(a, b, w, c=C):
        pygame.draw.line(s, c, p(*a), p(*b), max(1, int(w * k)))
        circ(a[0], a[1], w / 2, c)
        circ(b[0], b[1], w / 2, c)

    def arc(cx, cy, r, w, a0, a1, c=C):
        n = 28
        pts = []
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
        for i in range(n, -1, -1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.append((cx + (r - w) * math.cos(a), cy - (r - w) * math.sin(a)))
        pg(pts, c)

    def half_disc(cx, cy, r, c=C):
        pts = [(cx + r * math.cos(math.radians(a)), cy - r * math.sin(math.radians(a))) for a in range(0, 181, 6)]
        pg(pts, c)

    def drop(x, y, r):
        circ(x, y, r)
        pg([(x - r * 0.86, y - r * 0.5), (x + r * 0.86, y - r * 0.5), (x, y - r * 2.1)])

    def shield_pts(cx, cy, sc):
        base = [(0, -38), (32, -26), (30, 2), (0, 38), (-30, 2), (-32, -26)]
        return [(cx + a * sc, cy + b * sc) for a, b in base]

    if kind == "lock":
        arc(50, 42, 22, 8, 0, 180)
        rect(28, 40, 8, 12)
        rect(64, 40, 8, 12)
        rect(22, 46, 56, 40, rad=9)
        circ(50, 62, 6, T)
        rect(47.5, 63, 5, 12, T)
    elif kind == "bars":
        rect(16, 16, 68, 68, rad=8, wd=7)
        for x in (34, 50, 66):
            rect(x - 3, 18, 6, 64)
        rect(18, 47, 64, 6)
    elif kind == "smoke":
        circ(50, 38, 26)
        circ(50, 38, 17, T, w=4)
        circ(50, 38, 5, T)
        circ(36, 80, 8)
        circ(50, 76, 10)
        circ(64, 80, 8)
        rect(36, 78, 28, 10)
    elif kind == "camera":
        pg([(16, 34), (64, 26), (70, 50), (22, 58)])
        pg([(66, 28), (86, 30), (88, 47), (72, 48)])
        circ(28, 44, 4, T)
        rect(34, 56, 9, 20)
        rect(22, 74, 34, 9, rad=3)
    elif kind == "wifi":
        arc(42, 74, 46, 9, 45, 135)
        arc(42, 74, 31, 9, 45, 135)
        arc(42, 74, 16, 9, 45, 135)
        circ(42, 74, 6)
        arc(77, 64, 9, 4, 0, 180)
        rect(64, 62, 26, 22, rad=4)
        circ(77, 72, 3, T)
    elif kind == "bulb":
        circ(50, 44, 22)
        rect(38, 60, 24, 8, rad=2)
        rect(40, 70, 20, 6, rad=2)
        rect(44, 78, 12, 5, rad=2)
        line((43, 42), (50, 50), 3, T)
        line((50, 50), (57, 42), 3, T)
        for ang in (160, 125, 90, 55, 20):
            a = math.radians(ang)
            line((50 + 29 * math.cos(a), 44 - 29 * math.sin(a)), (50 + 37 * math.cos(a), 44 - 37 * math.sin(a)), 5)
    elif kind == "siren":
        half_disc(50, 64, 24)
        rect(20, 62, 60, 13, rad=4)
        arc(50, 64, 16, 4, 100, 160, T)
        for ang in (20, 55, 90, 125, 160):
            a = math.radians(ang)
            line((50 + 31 * math.cos(a), 62 - 31 * math.sin(a)), (50 + 41 * math.cos(a), 62 - 41 * math.sin(a)), 5)
        rect(26, 80, 48, 6, rad=2)
    elif kind == "extinguisher":
        rect(34, 36, 32, 52, rad=11)
        rect(43, 24, 14, 14)
        line((50, 26), (70, 20), 5)
        line((57, 32), (73, 40), 4)
        line((73, 40), (75, 58), 4)
        rect(34, 54, 32, 7, T)
    elif kind == "badge":
        rect(22, 16, 56, 70, rad=9)
        rect(40, 22, 20, 6, T, rad=3)
        circ(50, 45, 10, T)
        pygame.draw.ellipse(s, T, R(34, 57, 32, 18))
        rect(26, 67, 48, 10)
        rect(33, 74, 34, 4, T, rad=2)
    elif kind == "fingerprint":
        for r, a0, a1 in ((36, 25, 155), (29, 5, 175), (22, -10, 190), (15, -30, 210), (8, -60, 240)):
            arc(50, 58, r, 4.6, a0, a1)
        line((50, 56), (50, 76), 4.6)
    elif kind == "shield":
        pg(shield_pts(50, 50, 1.0))
        line((35, 50), (46, 61), 8, T)
        line((46, 61), (66, 38), 8, T)
    elif kind == "sprinkler":
        rect(42, 10, 16, 10, rad=2)
        line((50, 20), (50, 32), 6)
        rect(26, 32, 48, 6, rad=3)
        for dx, dy in ((30, 58), (50, 64), (70, 58), (40, 84), (60, 84)):
            drop(dx, dy, 7)
    elif kind == "bracelet":
        pygame.draw.ellipse(s, C, R(12, 26, 76, 48), max(1, int(9 * k)))
        rect(35, 56, 30, 22, rad=5)
        rect(41, 61, 18, 12, T, rad=2)
        arc(72, 26, 10, 4, 10, 80)
        arc(72, 26, 19, 4, 10, 80)
    elif kind == "guard":
        rect(24, 58, 52, 32, rad=16)
        circ(50, 41, 14)
        rect(34, 19, 32, 12, rad=5)
        rect(29, 29, 42, 5, rad=2)
        circ(61, 70, 4, T)
    elif kind == "helmet":
        half_disc(50, 62, 30)
        rect(12, 60, 76, 10, rad=5)
        rect(46.5, 33, 7, 27, T)
        rect(16, 76, 68, 5, rad=2)
    elif kind == "gauge":
        arc(50, 56, 36, 8, -35, 215)
        line((50, 56), (68, 36), 6)
        circ(50, 56, 7)
        for ang in (180, 135, 90, 45, 0):
            a = math.radians(ang)
            line((50 + 20 * math.cos(a), 56 - 20 * math.sin(a)), (50 + 24 * math.cos(a), 56 - 24 * math.sin(a)), 3)
        rect(34, 82, 32, 8, rad=3)
    elif kind == "antenna":
        rect(16, 14, 16, 70, rad=5)
        rect(68, 14, 16, 70, rad=5)
        arc(32, 48, 12, 4, -60, 60)
        arc(32, 48, 22, 4, -50, 50)
        arc(68, 48, 12, 4, 120, 240)
        arc(68, 48, 22, 4, 130, 230)
        rect(12, 84, 24, 6, rad=2)
        rect(64, 84, 24, 6, rad=2)
    elif kind == "panic":
        rect(14, 62, 72, 20, rad=6)
        half_disc(50, 64, 28)
        rect(46.5, 42, 7, 12, T, rad=2)
        circ(50, 59, 3.5, T)
    elif kind == "keypad":
        rect(24, 8, 52, 84, rad=9)
        rect(32, 16, 36, 13, T, rad=3)
        for i in range(3):
            for j in range(4):
                rect(32 + i * 13, 36 + j * 12, 10, 9, T, rad=2)
    elif kind == "metal":
        rect(14, 12, 14, 78, rad=4)
        rect(72, 12, 14, 78, rad=4)
        rect(14, 12, 72, 14, rad=4)
        circ(50, 44, 7)
        rect(43, 54, 14, 26, rad=5)
        arc(50, 62, 22, 3, 120, 240)
        arc(50, 62, 22, 3, -60, 60)
    elif kind == "radar":
        rect(34, 8, 32, 14, rad=4)
        arc(50, 22, 18, 5, 215, 325)
        arc(50, 22, 32, 5, 220, 320)
        arc(50, 22, 46, 5, 225, 315)
        rect(30, 78, 40, 14, rad=3, wd=4)
    elif kind == "glass":
        rect(12, 14, 58, 68, rad=4, wd=7)
        line((24, 40), (40, 24), 4)
        line((24, 58), (56, 26), 4)
        pg(shield_pts(70, 70, 0.68), T)
        pg(shield_pts(70, 70, 0.52))
        line((63, 70), (68, 75), 4, T)
        line((68, 75), (78, 63), 4, T)
    elif kind == "cylinder":
        rect(32, 26, 36, 64, rad=14)
        rect(43, 14, 14, 14, rad=2)
        line((34, 12), (66, 12), 5)
        rect(32, 50, 36, 6, T)
        circ(50, 70, 6, T)
    elif kind == "laser":
        rect(10, 12, 12, 78, rad=4)
        rect(78, 12, 12, 78, rad=4)
        line((22, 26), (78, 46), 4)
        line((22, 46), (78, 26), 4)
        line((22, 60), (78, 80), 4)
        line((22, 80), (78, 60), 4)
    # --- icones de locais ---
    elif kind == "house":
        pg([(10, 52), (50, 16), (90, 52)])
        rect(66, 22, 9, 20)
        rect(22, 48, 56, 40)
        rect(44, 62, 12, 26, T, rad=2)
        rect(29, 56, 10, 10, T)
        rect(61, 56, 10, 10, T)
    elif kind == "hospital":
        rect(18, 24, 64, 64, rad=6)
        rect(44, 34, 12, 32, T, rad=2)
        rect(34, 44, 32, 12, T, rad=2)
        rect(42, 74, 16, 14, T)
        rect(30, 14, 40, 12, rad=3)
    elif kind == "factory":
        pg([(10, 88), (10, 48), (30, 60), (30, 48), (50, 60), (50, 48), (70, 60), (70, 18), (86, 18), (86, 88)])
        for x in (16, 34, 52):
            rect(x, 70, 8, 8, T)
        rect(74, 70, 7, 18, T)
    elif kind == "cart":
        line((8, 20), (22, 20), 6)
        line((22, 20), (32, 62), 6)
        pg([(26, 30), (88, 30), (80, 60), (32, 60)])
        line((32, 62), (80, 62), 6)
        circ(40, 78, 8)
        circ(72, 78, 8)
        rect(40, 38, 4, 16, T)
        rect(54, 38, 4, 16, T)
        rect(68, 38, 4, 16, T)
    elif kind == "museum":
        pg([(10, 34), (50, 10), (90, 34)])
        rect(14, 34, 72, 7)
        for x in (20, 36, 56, 72):
            rect(x, 44, 8, 34)
        rect(10, 80, 80, 8)
        circ(50, 25, 4, T)
    # --- icones de interface ---
    elif kind == "check":
        line((22, 52), (42, 72), 13)
        line((42, 72), (80, 30), 13)
    elif kind == "cross":
        line((26, 26), (74, 74), 13)
        line((74, 26), (26, 74), 13)
    elif kind == "bang":
        rect(43, 14, 14, 50, rad=6)
        circ(50, 80, 8)
    elif kind == "warning":
        pg([(50, 8), (94, 88), (6, 88)])
        rect(45, 34, 10, 30, T, rad=3)
        circ(50, 75, 6, T)
    elif kind == "play":
        pg([(28, 16), (84, 50), (28, 84)])
    elif kind == "back":
        line((60, 22), (32, 50), 11)
        line((32, 50), (60, 78), 11)
    elif kind == "ff":
        pg([(12, 20), (50, 50), (12, 80)])
        pg([(50, 20), (88, 50), (50, 80)])
    elif kind == "person":
        circ(50, 32, 17)
        rect(20, 56, 60, 36, rad=18)
    elif kind == "star":
        pts = []
        for i in range(10):
            r = 46 if i % 2 == 0 else 19
            a = math.radians(90 + i * 36)
            pts.append((50 + r * math.cos(a), 52 - r * math.sin(a)))
        pg(pts)
    elif kind == "replay":
        arc(50, 52, 34, 10, 40, 330)
        pg([(70, 8), (90, 34), (60, 38)])
    elif kind == "grid":
        for i in range(2):
            for j in range(2):
                rect(16 + i * 38, 16 + j * 38, 30, 30, rad=6)
    elif kind == "exit":
        rect(16, 14, 40, 72, rad=6, wd=8)
        line((44, 50), (86, 50), 9)
        pg([(70, 32), (92, 50), (70, 68)])
    elif kind == "expand":
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            cx, cy = 50 - 32 * sx, 50 - 32 * sy
            line((cx, cy), (cx + 22 * sx, cy), 10)
            line((cx, cy), (cx, cy + 22 * sy), 10)
    elif kind == "compress":
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            cx, cy = 50 - 12 * sx, 50 - 12 * sy
            line((cx, cy), (cx - 22 * sx, cy), 10)
            line((cx, cy), (cx, cy - 22 * sy), 10)
    elif kind == "chat":
        rect(12, 16, 76, 56, rad=16)
        pg([(28, 66), (24, 88), (48, 70)])
        circ(32, 44, 6, T)
        circ(50, 44, 6, T)
        circ(68, 44, 6, T)
    else:
        circ(50, 50, 30)

    out = pygame.transform.smoothscale(s, (size, size))
    _ICON_CACHE[key] = out
    return out



# ---------------------------------------------------------------------------
# Primitivas isométricas (luz vindo de trás-esquerda: face esquerda clara, direita escura)
# ---------------------------------------------------------------------------
def _pt(gx, gy, gz, off):
    x, y = iso(gx, gy, gz)
    return (int(round(x - off[0])), int(round(y - off[1])))


def poly(surf, pts, color):
    if len(pts) < 3:
        return
    gfx.filled_polygon(surf, pts, color)
    gfx.aapolygon(surf, pts, color)


def draw_box(surf, x, y, z, w, d, h, color, off, top=None, bands=None, edge=True, ao=True):
    def P(a, b, c):
        return _pt(a, b, c, off)

    ct = top or lighten(color, 0.12)
    if h > 0.01:
        L = [P(x, y + d, z), P(x + w, y + d, z), P(x + w, y + d, z + h), P(x, y + d, z + h)]
        Rr = [P(x + w, y, z), P(x + w, y + d, z), P(x + w, y + d, z + h), P(x + w, y, z + h)]
        poly(surf, L, shade(color, 0.92))
        poly(surf, Rr, shade(color, 0.72))
        if bands:
            for b0, b1, bc in bands:
                poly(surf, [P(x, y + d, z + b0), P(x + w, y + d, z + b0), P(x + w, y + d, z + b1), P(x, y + d, z + b1)], shade(bc, 0.92))
                poly(surf, [P(x + w, y, z + b0), P(x + w, y + d, z + b0), P(x + w, y + d, z + b1), P(x + w, y, z + b1)], shade(bc, 0.72))
        if ao and h >= 7:
            # sombra de contato na base + brilho suave no topo das faces
            for a0, a1, al in ((0, 2.5, 62), (2.5, 6, 34), (6, 11, 14)):
                if a0 >= h * 0.7:
                    break
                a1 = min(a1, h * 0.7)
                gfx.filled_polygon(surf, [P(x, y + d, z + a0), P(x + w, y + d, z + a0), P(x + w, y + d, z + a1), P(x, y + d, z + a1)], (0, 0, 0, al))
                gfx.filled_polygon(surf, [P(x + w, y, z + a0), P(x + w, y + d, z + a0), P(x + w, y + d, z + a1), P(x + w, y, z + a1)], (0, 0, 0, al))
            t0 = h - max(2.0, h * 0.22)
            gfx.filled_polygon(surf, [P(x, y + d, z + t0), P(x + w, y + d, z + t0), P(x + w, y + d, z + h), P(x, y + d, z + h)], (255, 255, 255, 30))
            gfx.filled_polygon(surf, [P(x + w, y, z + t0), P(x + w, y + d, z + t0), P(x + w, y + d, z + h), P(x + w, y, z + h)], (255, 255, 255, 14))
    Tt = [P(x, y, z + h), P(x + w, y, z + h), P(x + w, y + d, z + h), P(x, y + d, z + h)]
    poly(surf, Tt, ct)
    if edge and h > 0.01:
        hl = lighten(ct, 0.45)
        pygame.draw.aaline(surf, hl, Tt[3], Tt[2])
        pygame.draw.aaline(surf, lighten(ct, 0.2), Tt[2], Tt[1])
        pygame.draw.aaline(surf, shade(color, 0.6), P(x + w, y + d, z), P(x + w, y + d, z + h))


def draw_cyl(surf, cx, cy, z, r, h, color, off, top=None, notop=False):
    bx, by = iso(cx, cy, z)
    tx, ty = iso(cx, cy, z + h)
    bx -= off[0]
    by -= off[1]
    tx -= off[0]
    ty -= off[1]
    rx, ry = r * HW * SQ2, r * HH * SQ2
    n = 18

    def arc(a0, a1, cxx, cyy, steps=8):
        return [(cxx + rx * math.cos(a0 + (a1 - a0) * i / steps), cyy + ry * math.sin(a0 + (a1 - a0) * i / steps)) for i in range(steps + 1)]

    front = arc(0, math.pi, bx, by, n)
    topf = arc(math.pi, 0, tx, ty, n)
    poly(surf, [ipt(q) for q in front + topf], shade(color, 0.84))
    # faixa iluminada à esquerda e sombra à direita
    lit = arc(0.58 * math.pi, 0.94 * math.pi, bx, by) + arc(0.94 * math.pi, 0.58 * math.pi, tx, ty)
    poly(surf, [ipt(q) for q in lit], shade(color, 1.0))
    dk = arc(0.0, 0.28 * math.pi, bx, by) + arc(0.28 * math.pi, 0.0, tx, ty)
    poly(surf, [ipt(q) for q in dk], shade(color, 0.68))
    if not notop:
        c = top or lighten(color, 0.12)
        gfx.filled_ellipse(surf, int(tx), int(ty), max(1, int(rx)), max(1, int(ry)), c)
        gfx.aaellipse(surf, int(tx), int(ty), max(1, int(rx)), max(1, int(ry)), shade(c, 0.85))


def draw_cone(surf, cx, cy, z, r, h, color, off):
    bx, by = iso(cx, cy, z)
    ax, ay = iso(cx, cy, z + h)
    bx -= off[0]
    by -= off[1]
    ax -= off[0]
    ay -= off[1]
    rx, ry = r * HW * SQ2, r * HH * SQ2
    front = [(bx + rx * math.cos(math.pi * i / 14), by + ry * math.sin(math.pi * i / 14)) for i in range(15)]
    poly(surf, [ipt(q) for q in front] + [ipt((ax, ay))], shade(color, 0.7))
    left = [(bx + rx * math.cos(math.pi * (0.45 + 0.55 * i / 8)), by + ry * math.sin(math.pi * (0.45 + 0.55 * i / 8))) for i in range(9)]
    poly(surf, [ipt(q) for q in left] + [ipt((ax, ay))], color)
    pygame.draw.aaline(surf, lighten(color, 0.25), ipt((ax, ay)), ipt((bx - rx * 0.55, by + ry * 0.6)))


def draw_sphere(surf, cx, cy, z, rp, color, off):
    x, y = iso(cx, cy, z)
    x, y = int(x - off[0]), int(y - off[1])
    rp = max(2, int(rp * ZS))
    gfx.filled_circle(surf, x, y, rp, shade(color, 0.72))
    gfx.aacircle(surf, x, y, rp, shade(color, 0.66))
    gfx.filled_circle(surf, int(x - rp * 0.1), int(y - rp * 0.14), int(rp * 0.82), color)
    gfx.filled_circle(surf, int(x - rp * 0.3), int(y - rp * 0.36), max(1, int(rp * 0.36)), lighten(color, 0.18))


def part_points(p):
    k = p[0]
    if k == "box":
        _, x, y, z, w, d, h = p[:7]
        return [iso(a, b, c) for a in (x, x + w) for b in (y, y + d) for c in (z, z + h)]
    if k in ("cyl", "cone"):
        _, cx, cy, z, r, h = p[:6]
        rx, ry = r * HW * SQ2, r * HH * SQ2
        bx, by = iso(cx, cy, z)
        tx, ty = iso(cx, cy, z + h)
        return [(bx - rx, by + ry), (bx + rx, by + ry), (tx - rx, ty - ry), (tx + rx, ty - ry)]
    if k == "sph":
        _, cx, cy, z, rp = p[:5]
        x, y = iso(cx, cy, z)
        r = rp * ZS + 1
        return [(x - r, y - r), (x + r, y + r)]
    if k == "flat":
        return [iso(*q) for q in p[1]]
    if k == "ell":
        _, cx, cy, z, r = p[:5]
        x, y = iso(cx, cy, z)
        return [(x - r * HW * SQ2, y - r * HH * SQ2), (x + r * HW * SQ2, y + r * HH * SQ2)]
    return []


def part_height(p):
    """(z da base, z do topo) de uma parte, em unidades de projeto."""
    k = p[0]
    if k == "box":
        return p[3], p[3] + p[6]
    if k in ("cyl", "cone"):
        return p[3], p[3] + p[5]
    if k == "sph":
        return p[3], p[3] + p[4]
    if k == "flat":
        zs = [q[2] for q in p[1]]
        return min(zs), max(zs)
    if k == "ell":
        return p[3], p[3]
    return 0, 0


def draw_part(s, p, off):
    k = p[0]
    if k == "box":
        _, x, y, z, w, d, h, c, kw = p
        kw = dict(kw)
        alpha = kw.pop("alpha", None)
        if alpha is not None:
            tmp = pygame.Surface(s.get_size(), pygame.SRCALPHA)
            draw_box(tmp, x, y, z, w, d, h, c, off, ao=False, **kw)
            tmp.set_alpha(alpha)
            s.blit(tmp, (0, 0))
        else:
            draw_box(s, x, y, z, w, d, h, c, off, **kw)
    elif k == "cyl":
        _, cx, cy, z, r, h, c, kw = p
        draw_cyl(s, cx, cy, z, r, h, c, off, **kw)
    elif k == "cone":
        _, cx, cy, z, r, h, c = p[:7]
        draw_cone(s, cx, cy, z, r, h, c, off)
    elif k == "sph":
        _, cx, cy, z, rp, c = p
        draw_sphere(s, cx, cy, z, rp, c, off)
    elif k == "flat":
        _, pts, c = p
        poly(s, [_pt(a, b, cz, off) for a, b, cz in pts], c)
    elif k == "ell":
        _, cx, cy, z, r, c = p
        x, y = iso(cx, cy, z)
        gfx.filled_ellipse(s, int(x - off[0]), int(y - off[1]), max(1, int(r * HW * SQ2)), max(1, int(r * HH * SQ2)), c)


class Prop:
    """Objeto estático do cenário, pré-renderizado (com contorno) numa superfície própria."""

    def __init__(self, parts, fp, outline=True, tag=None, round_r=None):
        self.parts = parts
        self.fp = fp
        self.tag = tag
        self.round_r = round_r
        self.depth = (fp[0] + fp[1]) / 2 + (fp[2] + fp[3]) / 2
        zs = [part_height(p) for p in parts]
        self.z0 = min(z[0] for z in zs)
        self.h = max(z[1] for z in zs) - self.z0
        pts = []
        for p in parts:
            pts.extend(part_points(p))
        pad = 3 + max(1, int(round(K)))
        minx = math.floor(min(q[0] for q in pts)) - pad
        miny = math.floor(min(q[1] for q in pts)) - pad
        maxx = math.ceil(max(q[0] for q in pts)) + pad
        maxy = math.ceil(max(q[1] for q in pts)) + pad
        self.pos = (int(minx), int(miny))
        w, h = max(1, int(maxx - minx)), max(1, int(maxy - miny))
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for p in parts:
            draw_part(surf, p, self.pos)
        self.surf = add_outline(surf, alpha=135) if outline else surf
        self.rect = pygame.Rect(self.pos, (w, h))


def behind(a, b, eps=0.02):
    """True se o footprint a está atrás do footprint b (visto da câmera)."""
    return a[1] <= b[0] + eps or a[3] <= b[2] + eps


def topo_sort(props):
    import heapq
    n = len(props)
    edges = [[] for _ in range(n)]
    indeg = [0] * n
    for i in range(n):
        a = props[i]
        for j in range(i + 1, n):
            b = props[j]
            if not a.rect.colliderect(b.rect):
                continue
            if behind(a.fp, b.fp):
                edges[i].append(j)
                indeg[j] += 1
            elif behind(b.fp, a.fp):
                edges[j].append(i)
                indeg[i] += 1
            elif a.depth <= b.depth:
                edges[i].append(j)
                indeg[j] += 1
            else:
                edges[j].append(i)
                indeg[i] += 1
    heap = [(props[i].depth, i) for i in range(n) if indeg[i] == 0]
    heapq.heapify(heap)
    out, seen = [], set()
    while heap:
        _, i = heapq.heappop(heap)
        out.append(props[i])
        seen.add(i)
        for j in edges[i]:
            indeg[j] -= 1
            if indeg[j] == 0:
                heapq.heappush(heap, (props[j].depth, j))
    if len(out) < n:
        out.extend(sorted((props[i] for i in range(n) if i not in seen), key=lambda p: p.depth))
    return out


# ---------------------------------------------------------------------------
# Móveis e objetos (composição de caixas, cilindros, cones e esferas)
# ---------------------------------------------------------------------------
WOOD = (176, 124, 78)
WOOD_D = (128, 88, 56)
METAL = (176, 182, 192)
WHITE = (242, 244, 248)
DARK = (54, 58, 70)


def furniture(kind, x, y, w, d, o, z):
    c = o.get("c")
    h = o.get("h")
    parts = []
    fp = (x, x + w, y, y + d)

    def B(bx, by, bz, bw, bd, bh, col, **kw):
        parts.append(("box", bx, by, bz, bw, bd, bh, col, kw))

    def CY(cx, cy, cz, r, ch, col, **kw):
        parts.append(("cyl", cx, cy, cz, r, ch, col, kw))

    def SP(cx, cy, cz, rp, col):
        parts.append(("sph", cx, cy, cz, rp, col))

    def FL(pts, col):
        parts.append(("flat", pts, col))

    def EL(cx, cy, cz, r, col):
        parts.append(("ell", cx, cy, cz, r, col))

    if kind == "box":
        kw = {"bands": o["bands"]} if "bands" in o else {}
        if "top" in o:
            kw["top"] = o["top"]
        B(x, y, z + o.get("z", 0), w, d, h or 20, c or (180, 180, 190), **kw)
    elif kind == "muro":
        B(x, y, z, w, d, h or 18, c or (214, 204, 188), top=(184, 174, 158))
    elif kind == "hedge":
        B(x, y, z, w, d, h or 14, (74, 150, 84), top=(96, 178, 100))
    elif kind == "bed":
        wood = o.get("wood", WOOD)
        B(x, y, z, w, 0.14, 24, wood)
        B(x, y + 0.14, z, w, d - 0.14, 8, wood)
        B(x + 0.05, y + 0.16, z + 8, w - 0.1, d - 0.22, 5, (244, 244, 248))
        B(x + 0.15, y + 0.22, z + 13, w - 0.3, 0.38, 4, (255, 255, 255))
        B(x + 0.04, y + 0.72, z + 13, w - 0.08, d - 0.8, 2.5, c or (100, 140, 225))
    elif kind == "hbed":
        B(x, y, z, w, 0.1, 26, METAL)
        B(x, y + 0.1, z + 4, w, d - 0.1, 8, (200, 205, 215))
        B(x + 0.04, y + 0.12, z + 12, w - 0.08, d - 0.18, 4, (248, 248, 252))
        B(x + 0.12, y + 0.18, z + 16, w - 0.24, 0.3, 3, (255, 255, 255))
        B(x + 0.04, y + 0.6, z + 16, w - 0.08, d - 0.7, 2, c or (150, 196, 236))
        B(x + w - 0.02, y + 0.5, z + 12, 0.05, d * 0.45, 7, METAL)
        CY(x + w + 0.16, y + 0.3, z, 0.03, 46, METAL)
        B(x + w + 0.09, y + 0.25, z + 38, 0.14, 0.1, 10, (190, 230, 250))
        fp = (x, x + w + 0.22, y, y + d)
    elif kind == "sofa":
        col = c or (90, 120, 170)
        if o.get("back", "y") == "y":
            B(x, y, z, 0.28, d, 22, shade(col, 0.95))
            B(x, y, z, w, 0.2, 15, col)
            B(x + 0.28, y + 0.2, z, w - 0.28, d - 0.4, 9, col)
            B(x + 0.3, y + 0.22, z + 9, w - 0.32, d - 0.44, 3, lighten(col, 0.12))
            B(x, y + d - 0.2, z, w, 0.2, 15, col)
        else:
            B(x, y, z, w, 0.28, 22, shade(col, 0.95))
            B(x, y, z, 0.2, d, 15, col)
            B(x + 0.2, y + 0.28, z, w - 0.4, d - 0.28, 9, col)
            B(x + 0.22, y + 0.3, z + 9, w - 0.44, d - 0.32, 3, lighten(col, 0.12))
            B(x + w - 0.2, y, z, 0.2, d, 15, col)
    elif kind == "table":
        col = c or WOOD
        th = h or 15
        for lx, ly in ((x + 0.06, y + 0.06), (x + w - 0.14, y + 0.06), (x + 0.06, y + d - 0.14), (x + w - 0.14, y + d - 0.14)):
            B(lx, ly, z, 0.08, 0.08, th, shade(col, 0.8))
        B(x, y, z + th, w, d, 3, col)
        if o.get("vase"):
            CY(x + w / 2, y + d / 2, z + th + 3, 0.07, 9, (236, 236, 246))
            SP(x + w / 2, y + d / 2, z + th + 16, 6, (240, 110, 130))
    elif kind == "chair":
        col = c or WOOD
        B(x, y, z, w, 0.08, 20, shade(col, 0.9))
        B(x, y + 0.08, z, w, d - 0.08, 9, col)
    elif kind == "desk":
        col = c or (210, 190, 160)
        B(x, y, z, 0.08, d, 14, shade(col, 0.8))
        B(x + w - 0.08, y, z, 0.08, d, 14, shade(col, 0.8))
        B(x, y, z + 14, w, d, 3, col)
        B(x + w * 0.3, y + 0.08, z + 17, w * 0.38, 0.06, 13, (34, 38, 50), bands=[(2, 12, (70, 140, 230))])
        B(x + w * 0.3, y + 0.25, z + 17, w * 0.38, 0.18, 1, (60, 64, 76))
        if o.get("router"):
            B(x + w - 0.36, y + 0.14, z + 17, 0.26, 0.18, 4, (36, 38, 46))
            B(x + w - 0.32, y + 0.16, z + 21, 0.03, 0.03, 9, (36, 38, 46))
            B(x + w - 0.16, y + 0.16, z + 21, 0.03, 0.03, 9, (36, 38, 46))
    elif kind == "monitors":
        col = c or (90, 96, 112)
        B(x, y, z, w, d, 16, col, top=(70, 76, 90))
        n = max(1, int(w / 0.7))
        for i in range(n):
            sx = x + 0.08 + i * (w - 0.16) / n
            B(sx, y + 0.06, z + 16, (w - 0.16) / n - 0.06, 0.06, 14, (30, 34, 46), bands=[(2, 12, (70, 160, 250))])
    elif kind == "counter":
        col = c or (236, 236, 240)
        B(x, y, z, w, d, 17, col)
        B(x - 0.02, y - 0.02, z + 17, w + 0.04, d + 0.04, 3, o.get("top", (88, 90, 100)))
    elif kind == "stove":
        B(x, y, z, w, d, 17, (230, 230, 236))
        FL([(x + 0.1, y + d + 0.01, z + 3), (x + w - 0.1, y + d + 0.01, z + 3), (x + w - 0.1, y + d + 0.01, z + 12), (x + 0.1, y + d + 0.01, z + 12)], (50, 52, 60))
        B(x, y, z + 17, w, d, 2, (40, 42, 48))
        for fx, fy in ((0.28, 0.3), (0.72, 0.3), (0.28, 0.72), (0.72, 0.72)):
            EL(x + w * fx, y + d * fy, z + 19.3, 0.1, (96, 96, 108))
    elif kind == "fridge":
        B(x, y, z, w, d, h or 44, (232, 236, 242), bands=[(28, 29, (196, 200, 208))])
    elif kind == "wardrobe":
        B(x, y, z, w, d, h or 46, c or WOOD_D, bands=[(2, 4, shade(WOOD_D, 0.8)), (42, 44, shade(WOOD_D, 0.8))])
    elif kind == "bookshelf":
        B(x, y, z, w, d, h or 42, WOOD, bands=[(5, 11, (200, 80, 80)), (15, 21, (80, 140, 200)), (25, 31, (230, 180, 60)), (35, 39, (100, 180, 120))])
    elif kind == "tv":
        B(x, y, z, w, d, 10, DARK)
        if w > d:
            B(x + 0.1, y + d / 2 - 0.03, z + 10, w - 0.2, 0.06, 18, (25, 28, 38), bands=[(2, 16, (40, 60, 110))])
        else:
            B(x + w / 2 - 0.03, y + 0.1, z + 10, 0.06, d - 0.2, 18, (25, 28, 38), bands=[(2, 16, (40, 60, 110))])
    elif kind == "plant":
        cx, cy = x + w / 2, y + d / 2
        CY(cx, cy, z, 0.16, 10, (196, 104, 72))
        SP(cx, cy, z + 20, o.get("r", 12), c or (76, 168, 92))
        fp = (cx - 0.18, cx + 0.18, cy - 0.18, cy + 0.18)
    elif kind == "tree":
        r = o.get("r", 21)
        if o.get("pine"):
            col = c or (52, 132, 86)
            CY(x, y, z, 0.07, 14, (110, 78, 50))
            parts.append(("cone", x, y, z + 8, 0.46, 30, shade(col, 0.95)))
            parts.append(("cone", x, y, z + 26, 0.37, 28, col))
            parts.append(("cone", x, y, z + 44, 0.27, 26, lighten(col, 0.08)))
        else:
            col = c or (74, 166, 90)
            CY(x, y, z, 0.08, 26, (122, 86, 56))
            SP(x + 0.13, y - 0.11, z + 31, r * 0.76, shade(col, 0.9))
            SP(x - 0.12, y + 0.1, z + 34, r * 0.8, col)
            SP(x + 0.02, y - 0.02, z + 49, r * 0.7, lighten(col, 0.07))
        fp = (x - 0.25, x + 0.25, y - 0.25, y + 0.25)
    elif kind == "floorlamp":
        CY(x, y, z, 0.1, 2, (60, 60, 70))
        CY(x, y, z + 2, 0.025, 30, (74, 74, 84))
        CY(x, y, z + 30, 0.15, 9, (255, 234, 186), top=(255, 248, 222))
        fp = (x - 0.12, x + 0.12, y - 0.12, y + 0.12)
    elif kind == "bush":
        col = c or (84, 172, 96)
        SP(x, y, z + 9, o.get("r", 12), col)
        SP(x + 0.2, y + 0.05, z + 6, int(o.get("r", 12) * 0.7), lighten(col, 0.05))
        fp = (x - 0.2, x + 0.3, y - 0.2, y + 0.25)
    elif kind in ("car", "ambulance"):
        col = c or ((246, 246, 250) if kind == "ambulance" else (220, 70, 70))
        dr = o.get("dir", "x")
        bands = [(6, 9, (226, 50, 60))] if kind == "ambulance" else None
        bh = 16 if kind == "ambulance" else 11
        if dr == "x":
            B(x + 0.18, y - 0.03, z, 0.32, d + 0.06, 6, (30, 30, 34))
            B(x + w - 0.5, y - 0.03, z, 0.32, d + 0.06, 6, (30, 30, 34))
            B(x, y, z + 3, w, d, bh, col, bands=bands)
            if kind == "ambulance":
                B(x + 0.05, y + 0.05, z + 3 + bh, w * 0.75, d - 0.1, 9, col)
                B(x + w * 0.5, y + 0.3, z + 12 + bh, 0.25, d - 0.6, 3, (230, 50, 60))
            else:
                B(x + w * 0.28, y + 0.06, z + 3 + bh, w * 0.45, d - 0.12, 9, (70, 92, 124), top=col)
        else:
            B(x - 0.03, y + 0.18, z, w + 0.06, 0.32, 6, (30, 30, 34))
            B(x - 0.03, y + d - 0.5, z, w + 0.06, 0.32, 6, (30, 30, 34))
            B(x, y, z + 3, w, d, bh, col, bands=bands)
            if kind == "ambulance":
                B(x + 0.05, y + 0.05, z + 3 + bh, w - 0.1, d * 0.72, 9, col)
                B(x + 0.3, y + d * 0.55, z + 12 + bh, w - 0.6, 0.25, 3, (230, 50, 60))
            else:
                B(x + 0.06, y + d * 0.28, z + 3 + bh, w - 0.12, d * 0.45, 9, (70, 92, 124), top=col)
    elif kind == "truck":
        B(x - 0.03, y + 0.3, z, w + 0.06, 0.3, 6, (30, 30, 34))
        B(x - 0.03, y + d - 0.55, z, w + 0.06, 0.3, 6, (30, 30, 34))
        B(x, y, z + 5, w, d * 0.72, 34, (236, 236, 242), bands=[(18, 23, (60, 120, 200))])
        B(x + 0.05, y + d * 0.74, z + 3, w - 0.1, d * 0.26, 26, c or (210, 64, 60), bands=[(14, 23, (60, 80, 110))])
    elif kind == "server":
        led = [(10, 11, (90, 230, 150)), (17, 18, (90, 230, 150)), (24, 25, (255, 190, 80)), (31, 32, (90, 230, 150)), (38, 39, (90, 200, 255)), (45, 46, (90, 230, 150))]
        B(x, y, z, w, d, h or 52, (44, 49, 62), bands=led)
    elif kind == "rack":
        post = (90, 100, 122)
        B(x, y, z, 0.05, 0.05, 46, post)
        B(x + w - 0.05, y, z, 0.05, 0.05, 46, post)
        B(x, y + d - 0.05, z, 0.05, 0.05, 46, post)
        for lv in (0, 15, 30):
            B(x, y, z + lv, w, d, 2, post)
            if w >= d:
                B(x + 0.05, y + 0.05, z + lv + 2, w * 0.44, d - 0.1, 11, (204, 154, 94))
                B(x + w * 0.52, y + 0.06, z + lv + 2, w * 0.42, d - 0.12, 9, (110, 150, 205))
            else:
                B(x + 0.05, y + 0.05, z + lv + 2, w - 0.1, d * 0.44, 11, (204, 154, 94))
                B(x + 0.06, y + d * 0.52, z + lv + 2, w - 0.12, d * 0.42, 9, (110, 150, 205))
        B(x, y, z + 44, w, d, 2, post)
        B(x + w - 0.05, y + d - 0.05, z, 0.05, 0.05, 46, post)
    elif kind == "crate":
        col = c or (198, 152, 94)
        hh = h or 16
        B(x, y, z, w, d, hh, col, bands=[(2, 4, shade(col, 0.8)), (hh - 4, hh - 2, shade(col, 0.8))])
    elif kind == "pallet":
        col = c or (206, 172, 112)
        hh = h or 18
        B(x, y, z, w, d, 3, (164, 126, 80))
        B(x + 0.05, y + 0.05, z + 3, w - 0.1, d - 0.1, hh, col, bands=[(hh - 6, hh - 4, (230, 210, 150))])
    elif kind == "barrel":
        CY(x, y, z, 0.2, 22, c or (212, 62, 52))
        CY(x, y, z + 8, 0.205, 3, shade(c or (212, 62, 52), 0.7), notop=True)
        fp = (x - 0.2, x + 0.2, y - 0.2, y + 0.2)
    elif kind == "tank":
        r = o.get("r", 0.5)
        col = c or (150, 168, 186)
        CY(x, y, z, r, h or 54, col)
        CY(x, y, z + 18, r + 0.01, 6, (240, 200, 40), notop=True)
        CY(x, y, z + (h or 54), 0.08, 8, (110, 114, 124))
        fp = (x - r, x + r, y - r, y + r)
    elif kind == "machine":
        col = c or (244, 190, 50)
        hh = h or 34
        B(x, y, z, w, d, hh, col, bands=[(4, 8, (60, 60, 70)), (hh - 10, hh - 7, (40, 40, 48))])
        B(x + 0.15, y + 0.15, z + hh, w - 0.3, d - 0.3, 10, shade(col, 0.86))
        B(x + w * 0.62, y + d - 0.02, z + 12, w * 0.25, 0.05, 10, (60, 200, 120))
    elif kind == "conveyor":
        B(x, y, z, w, d, 10, (74, 80, 92))
        B(x, y + 0.05, z + 10, w, d - 0.1, 2, (36, 37, 44))
        i = 0
        while 0.2 + i * 0.85 + 0.3 < w:
            B(x + 0.2 + i * 0.85, y + d / 2 - 0.15, z + 12, 0.3, 0.3, 7, (206, 166, 106))
            i += 1
    elif kind == "forklift":
        B(x - 0.03, y + 0.1, z, w + 0.06, 0.25, 6, (30, 30, 34))
        B(x - 0.03, y + d * 0.55, z, w + 0.06, 0.25, 6, (30, 30, 34))
        B(x, y, z + 3, w, d * 0.7, 12, (250, 200, 40))
        B(x + 0.08, y + 0.08, z + 15, w - 0.16, d * 0.42, 14, (60, 62, 72), top=(80, 84, 96))
        B(x, y + d * 0.7, z, w, 0.08, 34, (60, 62, 72))
        B(x + 0.08, y + d * 0.78, z + 2, 0.08, d * 0.22, 2, (84, 86, 96))
        B(x + w - 0.16, y + d * 0.78, z + 2, 0.08, d * 0.22, 2, (84, 86, 96))
    elif kind == "display":
        B(x, y, z, w, d, 18, (68, 58, 84))
        SP(x + w / 2, y + d / 2, z + 24, 5, (255, 214, 90))
        B(x + 0.04, y + 0.04, z + 18, w - 0.08, d - 0.08, 18, (190, 228, 248), top=(220, 242, 252), alpha=120)
    elif kind == "statue":
        B(x, y, z, w, d, 22, (226, 222, 214))
        cx, cy = x + w / 2, y + d / 2
        CY(cx, cy, z + 22, 0.13, 22, c or (186, 186, 198))
        SP(cx, cy, z + 50, 6, lighten(c or (186, 186, 198), 0.1))
    elif kind == "column":
        CY(x, y, z, 0.22, 64, (242, 238, 230))
        B(x - 0.27, y - 0.27, z + 64, 0.54, 0.54, 5, (232, 228, 220))
        fp = (x - 0.27, x + 0.27, y - 0.27, y + 0.27)
    elif kind == "bench":
        col = c or WOOD
        if w >= d:
            B(x + 0.05, y + 0.05, z, 0.08, d - 0.1, 6, DARK)
            B(x + w - 0.13, y + 0.05, z, 0.08, d - 0.1, 6, DARK)
        else:
            B(x + 0.05, y + 0.05, z, w - 0.1, 0.08, 6, DARK)
            B(x + 0.05, y + d - 0.13, z, w - 0.1, 0.08, 6, DARK)
        B(x, y, z + 6, w, d, 3, col)
    elif kind == "reception":
        col = c or (242, 242, 246)
        B(x, y, z, w, d, 20, col, top=o.get("top", (120, 180, 200)))
        if o.get("L"):
            B(x, y + d, z, 0.5, o["L"], 20, col, top=o.get("top", (120, 180, 200)))
            fp = (x, x + w, y, y + d + o["L"])
    elif kind == "crib":
        B(x, y, z, w, d, 4, (236, 236, 242))
        B(x + 0.05, y + 0.05, z + 4, w - 0.1, d - 0.1, 4, c or (250, 190, 210))
        B(x, y, z + 4, w, d, 10, (220, 236, 250), alpha=110)
    elif kind == "oxygen":
        nx = max(1, int(w / 0.38))
        ny = max(1, int(d / 0.38))
        for s_ in range(nx + ny):
            for i in range(nx):
                j = s_ - i
                if 0 <= j < ny:
                    cx, cy = x + 0.2 + i * 0.38, y + 0.2 + j * 0.38
                    CY(cx, cy, z, 0.14, 36, (60, 170, 110))
                    CY(cx, cy, z + 36, 0.1, 5, (240, 240, 240))
    elif kind == "cabinet":
        B(x, y, z, w, d, h or 40, (242, 244, 248), bands=[(10, 11, (150, 190, 220)), (20, 21, (150, 190, 220)), (30, 31, (150, 190, 220))])
    elif kind == "checkout":
        B(x, y, z, w, d, 16, (226, 226, 232))
        B(x + 0.05, y + 0.05, z + 16, w - 0.1, d * 0.58, 2, (40, 40, 46))
        B(x + 0.1, y + d * 0.68, z + 16, w * 0.55, d * 0.24, 9, (60, 64, 76), bands=[(4, 8, (90, 200, 140))])
    elif kind == "oven":
        B(x, y, z, w, d, 34, (150, 155, 166), bands=[(10, 22, (255, 140, 50))])
        B(x - 0.03, y - 0.03, z + 34, w + 0.06, d + 0.06, 4, (120, 124, 136))
    elif kind == "freezer":
        B(x, y, z, w, d, 26, (240, 244, 248), top=(170, 216, 242), bands=[(18, 20, (120, 170, 220))])
    elif kind == "safe":
        B(x, y, z, w, d, 24, (72, 76, 88), bands=[(3, 4, (110, 114, 126)), (20, 21, (110, 114, 126))])
    elif kind == "booth":
        col = c or (230, 232, 238)
        B(x, y, z, w, d, 34, col, bands=[(16, 28, (140, 200, 236))])
        B(x - 0.08, y - 0.08, z + 34, w + 0.16, d + 0.16, 4, (70, 80, 100))
    elif kind == "barrier":
        B(x, y, z, 0.22, 0.22, 16, (240, 200, 40))
        n = 6
        seg = w / n
        for i in range(n):
            B(x + 0.22 + i * seg, y + 0.07, z + 12, seg, 0.08, 3, (230, 60, 60) if i % 2 == 0 else (245, 245, 245))
        fp = (x, x + 0.22 + w, y, y + 0.22)
    elif kind == "fence":
        col = c or (220, 222, 228)
        if o.get("dir", "x") == "x":
            B(x, y, z, 0.08, 0.08, 18, col)
            B(x, y + 0.01, z + 7, w, 0.06, 2, col)
            B(x, y + 0.01, z + 14, w, 0.06, 2, col)
            fp = (x, x + w, y, y + 0.1)
        else:
            B(x, y, z, 0.08, 0.08, 18, col)
            B(x + 0.01, y, z + 7, 0.06, d, 2, col)
            B(x + 0.01, y, z + 14, 0.06, d, 2, col)
            fp = (x, x + 0.1, y, y + d)
    elif kind == "lamp":
        B(x - 0.04, y - 0.04, z, 0.08, 0.08, 62, (60, 64, 76))
        B(x - 0.13, y - 0.13, z + 62, 0.26, 0.26, 5, (80, 84, 96), top=(255, 238, 180))
        fp = (x - 0.13, x + 0.13, y - 0.13, y + 0.13)
    elif kind == "mailbox":
        B(x, y, z, 0.06, 0.06, 14, WOOD_D)
        B(x - 0.1, y - 0.06, z + 14, 0.26, 0.18, 8, (60, 100, 180))
        fp = (x - 0.1, x + 0.16, y - 0.06, y + 0.12)
    elif kind == "fountain":
        CY(x, y, z, 0.85, 8, (206, 200, 190))
        CY(x, y, z + 2, 0.74, 7, (116, 192, 236), top=(146, 212, 246))
        CY(x, y, z + 8, 0.12, 16, (206, 200, 190))
        SP(x, y, z + 28, 7, (178, 228, 250))
        fp = (x - 0.85, x + 0.85, y - 0.85, y + 0.85)
    elif kind == "rope":
        CY(x, y, z, 0.04, 15, (206, 172, 64))
        B(x, y - 0.015, z + 11, w, 0.03, 2, (180, 32, 44))
        CY(x + w, y, z, 0.04, 15, (206, 172, 64))
        fp = (x - 0.05, x + w + 0.05, y - 0.05, y + 0.05)
    elif kind == "toilet":
        B(x, y, z, w, d * 0.35, 17, WHITE)
        B(x + 0.05, y + d * 0.35, z, w - 0.1, d * 0.6, 9, WHITE, top=(210, 222, 236))
    elif kind == "sink":
        B(x, y, z, w, d, 16, WHITE, top=(214, 228, 240))
    elif kind == "bathtub":
        B(x, y, z, w, d, 11, WHITE)
        FL([(x + 0.08, y + 0.08, z + 11.2), (x + w - 0.08, y + 0.08, z + 11.2), (x + w - 0.08, y + d - 0.08, z + 11.2), (x + 0.08, y + d - 0.08, z + 11.2)], (164, 212, 242))
    elif kind == "archive":
        B(x, y, z, w, d, h or 46, (204, 194, 172), bands=[(8, 9, (150, 130, 100)), (18, 19, (150, 130, 100)), (28, 29, (150, 130, 100)), (38, 39, (150, 130, 100))])
    elif kind == "flatfile":
        B(x, y, z, w, d, 16, (132, 138, 148), bands=[(5, 6, DARK), (10, 11, DARK)])
    elif kind == "shelf":
        B(x, y, z, w, d, h or 32, c or (212, 216, 224), bands=o.get("bands"))
    elif kind == "gondola":
        B(x, y, z, w, d, h or 30, (226, 229, 236), bands=[(4, 10, (232, 92, 82)), (13, 19, (92, 170, 232)), (22, 28, (250, 200, 72))])
        n = int(max(w, d) / 0.5)
        for i in range(n):
            col = ((240, 120, 90), (110, 200, 120), (250, 210, 90), (120, 160, 240))[i % 4]
            if w >= d:
                B(x + 0.08 + i * 0.5, y + 0.1, z + (h or 30), 0.3, d - 0.2, 6, col)
            else:
                B(x + 0.1, y + 0.08 + i * 0.5, z + (h or 30), w - 0.2, 0.3, 6, col)
    else:
        B(x, y, z, w or 0.5, d or 0.5, h or 16, c or (190, 190, 200))
    return parts, fp


# ---------------------------------------------------------------------------
# Personagens
# ---------------------------------------------------------------------------
PERSON = {
    "mom": dict(body=(232, 110, 140), legs=(60, 70, 110), skin=(240, 198, 160), hair=(110, 60, 30), acc="hair_long"),
    "dad": dict(body=(80, 140, 210), legs=(50, 55, 75), skin=(225, 180, 140), hair=(40, 30, 25), acc="hair"),
    "kid": dict(body=(250, 200, 60), legs=(60, 90, 160), skin=(240, 200, 165), hair=(60, 40, 20), acc="hair", scale=0.78),
    "doctor": dict(body=(245, 246, 250), legs=(80, 130, 190), skin=(220, 175, 135), hair=(30, 25, 20), acc="hair", item="clip"),
    "nurse": dict(body=(110, 200, 190), legs=(110, 200, 190), skin=(200, 150, 110), hair=(50, 30, 20), acc="hair_long"),
    "worker": dict(body=(255, 160, 40), legs=(60, 70, 100), skin=(215, 170, 130), acc="helmet", hat=(255, 215, 0)),
    "worker2": dict(body=(70, 120, 200), legs=(50, 60, 80), skin=(190, 140, 100), acc="helmet", hat=(250, 250, 250)),
    "cashier": dict(body=(220, 60, 60), legs=(50, 50, 60), skin=(235, 190, 150), hair=(150, 90, 40), acc="hair_long"),
    "shopper": dict(body=(120, 180, 110), legs=(80, 80, 110), skin=(200, 155, 115), hair=(30, 20, 15), acc="hair", item="sack2"),
    "baker": dict(body=(250, 250, 250), legs=(70, 70, 80), skin=(230, 185, 145), acc="cap", hat=(250, 250, 250)),
    "guide": dict(body=(60, 62, 90), legs=(40, 40, 55), skin=(230, 185, 145), hair=(200, 200, 200), acc="hair"),
    "visitor": dict(body=(240, 170, 80), legs=(70, 90, 140), skin=(180, 130, 95), hair=(20, 20, 20), acc="hair_long"),
    "operator": dict(body=(90, 100, 130), legs=(40, 44, 60), skin=(220, 175, 135), hair=(70, 40, 20), acc="hair"),
}

THREATS = {
    "thief": dict(body=(46, 46, 62), legs=(30, 30, 40), skin=(220, 175, 140), acc="beanie", mask=True, item="sack", hat=(26, 26, 32)),
    "intruder": dict(body=(96, 96, 112), legs=(40, 40, 55), skin=(210, 165, 130), acc="hood", mask=True),
    "vandal": dict(body=(222, 112, 40), legs=(50, 50, 70), skin=(200, 150, 110), acc="hood", item="spray"),
    "robber": dict(body=(132, 30, 42), legs=(30, 30, 40), skin=(220, 175, 140), acc="skimask", item="bag"),
    "shoplifter": dict(body=(70, 110, 166), legs=(45, 50, 70), skin=(225, 180, 140), acc="cap", hat=(200, 60, 60), item="sack2"),
    "smuggler": dict(body=(142, 106, 70), legs=(60, 45, 35), skin=(220, 175, 140), acc="fedora", hat=(60, 45, 35), item="case"),
    "roof": dict(body=(30, 30, 40), legs=(24, 24, 32), skin=(215, 170, 130), acc="beanie", mask=True, hat=(20, 20, 26)),
}


def draw_person(s, fx, fy, st, t, moving, arms_up=False):
    """Desenha um personagem com os pés em (fx, fy). Tamanhos acompanham a escala K."""
    sc = st.get("scale", 1.0) * 1.12 * K
    ph = t * 9.0
    sw = math.sin(ph) * 3.2 * sc if moving else 0.0
    bob = abs(math.cos(ph)) * 1.6 * sc if moving else math.sin(t * 2.2) * 0.4 * sc
    body = st["body"]
    legs = st.get("legs", (50, 55, 75))
    skin = st.get("skin", (235, 190, 150))
    hair = st.get("hair", (60, 40, 25))
    acc = st.get("acc")
    item = st.get("item")
    hip = fy - 13 * sc - bob
    lw = max(2, int(round(4 * sc)))
    shoe = shade(legs, 0.55)
    # perna de trás
    pygame.draw.line(s, shade(legs, 0.78), (int(fx - 2 * sc), int(hip)), (int(fx - 2 * sc - sw), int(fy - 2 * sc)), lw)
    gfx.filled_circle(s, int(fx - 2 * sc - sw), int(fy - 1.5 * sc), max(1, int(2.2 * sc)), shoe)
    tw, th = int(15 * sc), int(17 * sc)
    torso = pygame.Rect(0, 0, tw, th)
    torso.midbottom = (int(fx), int(hip + 3 * sc))
    hr = max(3, int(7.2 * sc))
    hx, hy = int(fx + 1 * sc), int(torso.y - hr + 2 * sc)
    if item == "sack":
        gfx.filled_circle(s, int(fx - 8 * sc), int(torso.y + 5 * sc), int(7 * sc), (150, 132, 100))
        gfx.aacircle(s, int(fx - 8 * sc), int(torso.y + 5 * sc), int(7 * sc), (110, 96, 72))
    if acc == "hair_long":
        pygame.draw.rect(s, shade(hair, 0.9), (hx - hr, hy - int(2 * sc), hr + int(2 * sc), hr + int(8 * sc)), border_radius=max(1, int(3 * sc)))
    # perna da frente
    pygame.draw.line(s, legs, (int(fx + 2 * sc), int(hip)), (int(fx + 2 * sc + sw), int(fy - 2 * sc)), lw)
    gfx.filled_circle(s, int(fx + 2 * sc + sw), int(fy - 1.5 * sc), max(1, int(2.2 * sc)), shoe)
    sh_y = torso.y + int(4 * sc)
    aw = max(2, int(round(4 * sc)))
    if arms_up:
        pygame.draw.line(s, shade(body, 0.7), (torso.left + int(2 * sc), sh_y), (int(torso.left - 3 * sc), int(sh_y - 11 * sc)), aw)
    else:
        pygame.draw.line(s, shade(body, 0.7), (torso.left + int(2 * sc), sh_y), (int(torso.left + 1 * sc + sw * 0.8), int(sh_y + 10 * sc)), aw)
    pygame.draw.rect(s, shade(body, 0.82), torso, border_radius=max(2, int(6 * sc)))
    hl = pygame.Rect(torso.x + int(2 * sc), torso.y + int(2 * sc), max(1, tw // 2), max(1, th - int(5 * sc)))
    pygame.draw.rect(s, body, hl, border_radius=max(1, int(4 * sc)))
    pygame.draw.line(s, shade(body, 0.62), (torso.x + int(3 * sc), torso.bottom - 1), (torso.right - int(3 * sc), torso.bottom - 1), max(1, int(sc)))
    if arms_up:
        hand = (int(torso.right + 3 * sc), int(sh_y - 11 * sc))
    else:
        hand = (int(torso.right - 1 * sc - sw * 0.8), int(sh_y + 10 * sc))
    pygame.draw.line(s, shade(body, 0.95), (torso.right - int(2 * sc), sh_y), hand, aw)
    gfx.filled_circle(s, hand[0], hand[1], max(1, int(2.2 * sc)), skin)
    # cabeça
    eyes = (30, 30, 40)
    if acc == "hood":
        gfx.filled_circle(s, hx - int(sc), hy, hr + int(2 * sc), shade(body, 0.9))
        gfx.aacircle(s, hx - int(sc), hy, hr + int(2 * sc), shade(body, 0.7))
        gfx.filled_circle(s, hx + int(2 * sc), hy + int(sc), hr - int(2 * sc), skin)
    elif acc == "skimask":
        gfx.filled_circle(s, hx, hy, hr, (38, 38, 44))
        gfx.aacircle(s, hx, hy, hr, (26, 26, 30))
        pygame.draw.rect(s, skin, (hx - int(sc), hy - int(3 * sc), hr + int(sc), int(4 * sc)))
    elif acc in ("beanie", "cap", "helmet"):
        hat = st.get("hat", (40, 40, 50))
        gfx.filled_circle(s, hx, hy - int(sc), hr, hat)
        gfx.filled_circle(s, hx + int(sc), hy + int(2 * sc), hr - int(sc), skin)
        gfx.aacircle(s, hx + int(sc), hy + int(2 * sc), hr - int(sc), shade(skin, 0.85))
        if acc == "beanie":
            pygame.draw.rect(s, shade(hat, 0.75), (hx - hr, hy - int(3 * sc), 2 * hr, max(2, int(3 * sc))))
        elif acc == "cap":
            pygame.draw.rect(s, shade(hat, 0.85), (hx, hy - hr + int(3 * sc), hr + int(5 * sc), max(2, int(3 * sc))))
        else:
            pygame.draw.rect(s, shade(hat, 0.8), (hx - hr - int(sc), hy - int(2 * sc), 2 * hr + int(4 * sc), max(2, int(2 * sc))))
            gfx.filled_circle(s, hx - int(hr * 0.35), hy - int(hr * 0.6), max(1, int(1.6 * sc)), lighten(hat, 0.5))
    elif acc == "fedora":
        gfx.filled_circle(s, hx, hy, hr, skin)
        hat = st.get("hat", (60, 45, 35))
        pygame.draw.rect(s, hat, (hx - hr + int(sc), hy - hr - int(4 * sc), 2 * hr - int(2 * sc), int(7 * sc)), border_radius=max(1, int(2 * sc)))
        pygame.draw.ellipse(s, shade(hat, 0.85), (hx - hr - int(3 * sc), hy - hr + int(sc), 2 * hr + int(6 * sc), max(2, int(4 * sc))))
    else:
        if acc in ("hair", "hair_long"):
            gfx.filled_circle(s, hx - int(sc), hy - int(sc), hr, hair)
            gfx.filled_circle(s, hx + int(sc), hy + int(sc), hr - int(sc), skin)
            gfx.filled_circle(s, hx - int(hr * 0.45), hy - int(hr * 0.65), max(1, int(1.6 * sc)), lighten(hair, 0.35))
        else:
            gfx.filled_circle(s, hx, hy, hr, skin)
    if st.get("mask"):
        pygame.draw.rect(s, (24, 24, 30), (hx - hr + int(2 * sc), hy - int(sc), 2 * hr - int(sc), max(2, int(4 * sc))))
        eyes = (245, 245, 245)
    if acc == "skimask":
        eyes = (20, 20, 24)
    ey = hy if acc != "beanie" else hy + int(sc)
    e = max(1, int(round(2 * sc)))
    pygame.draw.rect(s, eyes, (hx + int(2 * sc), ey, e, e))
    pygame.draw.rect(s, eyes, (hx + int(5 * sc), ey, e, e))
    if acc not in ("skimask",) and not st.get("mask"):
        gfx.filled_circle(s, hx + int(1 * sc), hy + int(3.5 * sc), max(1, int(1.2 * sc)), shade(skin, 0.86))
    # itens na mão
    hx2, hy2 = hand
    if item == "spray":
        pygame.draw.rect(s, (220, 220, 230), (hx2 - int(2 * sc), hy2 - int(7 * sc), int(5 * sc), int(8 * sc)), border_radius=max(1, int(2 * sc)))
        pygame.draw.rect(s, (230, 60, 60), (hx2 - int(2 * sc), hy2 - int(9 * sc), int(5 * sc), int(3 * sc)))
    elif item == "case":
        pygame.draw.rect(s, (70, 50, 36), (hx2 - int(6 * sc), hy2 - int(sc), int(12 * sc), int(9 * sc)), border_radius=max(1, int(2 * sc)))
    elif item == "clip":
        pygame.draw.rect(s, (240, 230, 200), (hx2 - int(3 * sc), hy2 - int(8 * sc), int(7 * sc), int(9 * sc)))
    elif item == "bag":
        pygame.draw.rect(s, (30, 30, 36), (hx2 - int(5 * sc), hy2 - int(sc), int(11 * sc), int(8 * sc)), border_radius=max(1, int(3 * sc)))
    elif item == "sack2":
        pygame.draw.rect(s, (236, 232, 214), (hx2 - int(4 * sc), hy2 - int(2 * sc), int(9 * sc), int(10 * sc)), border_radius=max(1, int(2 * sc)))


def char_surface():
    return pygame.Surface((S(64), S(96)), pygame.SRCALPHA)


CHAR_FEET = (32, 90)   # posição dos pés dentro da superfície do personagem (unidades de projeto)


def draw_char_shadow(surf, x, y, alpha=80, scale=1.0):
    gfx.filled_ellipse(surf, int(x), int(y), max(2, int(S(10) * scale)), max(1, int(S(4.5) * scale)), (0, 0, 0, int(alpha)))


class Walker:
    """Personagem amigável que circula pelo local (clima The Sims)."""

    def __init__(self, world, style, route, speed=0.85):
        self.world = world
        self.st = PERSON.get(style, PERSON["dad"])
        self.route = [tuple(p) for p in route]
        self.i = 0
        self.x, self.y = self.route[0]
        self.speed = speed
        self.wait = random.uniform(0.2, 1.6)
        self.t = random.random() * 10
        self.facing = 1
        self.moving = False
        self.surf = char_surface()
        self.fz = world.floor_z(self.x, self.y)

    @property
    def fp(self):
        return (self.x - 0.15, self.x + 0.15, self.y - 0.15, self.y + 0.15)

    @property
    def depth(self):
        return self.x + self.y

    @property
    def srect(self):
        sx, sy = iso(self.x, self.y, self.fz)
        return pygame.Rect(int(sx - S(24)), int(sy - S(80)), S(48), S(84))

    def update(self, dt):
        self.t += dt
        self.fz = approach(self.fz, self.world.floor_z(self.x, self.y), dt, 10)
        if len(self.route) < 2:
            self.moving = False
            return
        if self.wait > 0:
            self.wait -= dt
            self.moving = False
            return
        tx, ty = self.route[(self.i + 1) % len(self.route)]
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        step = self.speed * dt
        if dist <= step:
            self.x, self.y = tx, ty
            self.i = (self.i + 1) % len(self.route)
            self.wait = random.uniform(0.6, 2.2)
        else:
            self.x += dx / dist * step
            self.y += dy / dist * step
            if abs(dx - dy) > 0.01:
                self.facing = 1 if dx - dy > 0 else -1
        self.moving = True

    def render(self):
        self.surf.fill((0, 0, 0, 0))
        draw_person(self.surf, S(CHAR_FEET[0]), S(CHAR_FEET[1]), self.st, self.t, self.moving)
        img = add_outline(self.surf, alpha=170)
        return img if self.facing > 0 else pygame.transform.flip(img, True, False)

    def draw(self, surf, off):
        sx, sy = iso(self.x, self.y, self.fz)
        draw_char_shadow(surf, sx + off[0], sy + off[1])
        img = self.render()
        surf.blit(img, (int(sx - S(CHAR_FEET[0]) + off[0]), int(sy - S(CHAR_FEET[1]) + off[1])))


class AmbientCar:
    COLORS = [(230, 70, 70), (70, 130, 220), (250, 200, 60), (240, 240, 245), (60, 180, 120), (150, 90, 200)]

    def __init__(self, world, lane_y, direction):
        self.world = world
        self.y = lane_y
        self.dir = direction
        self.surf = pygame.Surface((S(124), S(96)), pygame.SRCALPHA)
        self.reset(first=True)

    def reset(self, first=False):
        self.c = random.choice(self.COLORS)
        self.speed = random.uniform(1.8, 2.8)
        self.x = (-1.6 if self.dir > 0 else GW + 0.1) if not first else random.uniform(0, GW - 2)
        self.wait = 0 if first else random.uniform(1.0, 5.0)

    @property
    def fp(self):
        return (self.x, self.x + 1.5, self.y - 0.35, self.y + 0.35)

    @property
    def depth(self):
        return self.x + 0.75 + self.y

    @property
    def srect(self):
        ax, ay = iso(self.x, self.y + 0.35, 0)
        return pygame.Rect(int(ax - S(10)), int(ay - S(54)), S(124), S(96))

    def update(self, dt):
        if self.wait > 0:
            self.wait -= dt
            return
        self.x += self.dir * self.speed * dt
        if (self.dir > 0 and self.x > GW + 0.2) or (self.dir < 0 and self.x < -1.7):
            self.reset()

    def alpha(self):
        if self.wait > 0:
            return 0
        lo = clamp((self.x + 0.15) / 0.9, 0, 1)
        hi = clamp((GW - 1.5 - self.x + 0.15) / 0.9, 0, 1)
        return lo * hi

    def draw(self, surf, off):
        a = self.alpha()
        if a <= 0.02:
            return
        self.surf.fill((0, 0, 0, 0))
        ax, ay = iso(self.x, self.y + 0.35, 0)
        lo = (ax - S(10), ay - S(54))
        x, y, w, d = self.x, self.y - 0.32, 1.5, 0.64
        draw_box(self.surf, x + 0.18, y - 0.03, 0, 0.32, d + 0.06, 6, (30, 30, 34), lo, ao=False)
        draw_box(self.surf, x + w - 0.5, y - 0.03, 0, 0.32, d + 0.06, 6, (30, 30, 34), lo, ao=False)
        draw_box(self.surf, x, y, 3, w, d, 11, self.c, lo, bands=[(6, 7, lighten(self.c, 0.3))])
        draw_box(self.surf, x + w * 0.28, y + 0.06, 14, w * 0.45, d - 0.12, 9, (70, 92, 124), lo, top=self.c, ao=False)
        img = add_outline(self.surf, alpha=140)
        img.set_alpha(int(255 * a))
        gx, gy = iso(self.x + 0.75, self.y, 0)
        gfx.filled_ellipse(surf, int(gx + off[0]), int(gy + off[1] + S(2)), S(40), S(14), (0, 0, 0, int(55 * a)))
        surf.blit(img, (int(lo[0] + off[0]), int(lo[1] + off[1])))

    def head(self):
        fx = self.x + (1.55 if self.dir > 0 else -0.05)
        return iso(fx, self.y, 8)


# ---------------------------------------------------------------------------
# Efeitos visuais
# ---------------------------------------------------------------------------
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max", "c", "r", "g", "drag")

    def __init__(self, x, y, vx, vy, life, c, r, g=0.0, drag=0.0):
        self.x, self.y = x, y
        self.vx, self.vy = vx * K, vy * K
        self.life = self.max = life
        self.c, self.r, self.g, self.drag = c, r * K, g * K, drag

    def update(self, dt):
        self.life -= dt
        self.vy += self.g * dt
        if self.drag:
            k = max(0.0, 1 - self.drag * dt)
            self.vx *= k
            self.vy *= k
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.life > 0

    def draw(self, surf, off):
        f = max(0.0, self.life / self.max)
        r = max(1, int(self.r * (0.35 + 0.65 * f)))
        gfx.filled_circle(surf, int(self.x + off[0]), int(self.y + off[1]), r, rgba(self.c, 255 * min(1.0, f * 1.4)))


class FloatText:
    def __init__(self, text, color, x, y, size=21):
        self.t = 0.0
        self.x, self.y = x, y
        self.surf = outlined_text(text, size, color)

    def update(self, dt):
        self.t += dt
        return self.t < 1.7

    def draw(self, surf, off):
        p = self.t
        rise = S(40) * ease_out_cubic(p / 1.3)
        sc = ease_out_back(p / 0.25) if p < 0.25 else 1.0
        alpha = 255 if p < 1.15 else int(255 * clamp(1 - (p - 1.15) / 0.55, 0, 1))
        s = self.surf
        if abs(sc - 1) > 0.01:
            s = pygame.transform.smoothscale(s, (max(1, int(s.get_width() * sc)), max(1, int(s.get_height() * sc))))
        if alpha < 255:
            s = s.copy()
            s.set_alpha(alpha)
        surf.blit(s, s.get_rect(center=(int(self.x + off[0]), int(self.y + off[1] - rise))))


class Shield:
    def __init__(self, x, y, color, cracked=False, height=48):
        self.x, self.y = x, y
        self.c = color
        self.t = 0.0
        self.cracked = cracked
        self.hgt = height

    def update(self, dt):
        self.t += dt
        return self.t < 1.5

    def draw(self, surf, off):
        p = self.t
        k = ease_out_back(p / 0.35) * K
        a = 1.0 if p < 0.95 else clamp(1 - (p - 0.95) / 0.55, 0, 1)
        cx, cy = self.x + off[0], self.y + off[1]
        rx, ry, hg = 38 * k, 19 * k, self.hgt * k
        if rx < 2:
            return
        pts = [(cx + rx * math.cos(math.pi * i / 24), cy - hg * math.sin(math.pi * i / 24)) for i in range(25)]
        pts += [(cx + rx * math.cos(math.pi - math.pi * i / 12), cy + ry * math.sin(math.pi - math.pi * i / 12)) for i in range(13)]
        ip = [ipt(q) for q in pts]
        gfx.filled_polygon(surf, ip, rgba(self.c, 70 * a))
        gfx.aapolygon(surf, ip, rgba(self.c, 235 * a))
        gfx.aapolygon(surf, [(x + 1, y) for x, y in ip], rgba(self.c, 120 * a))
        hl = [ipt((cx + rx * 0.78 * math.cos(math.pi * (0.55 + 0.3 * i / 8)), cy - hg * 0.78 * math.sin(math.pi * (0.55 + 0.3 * i / 8)))) for i in range(9)]
        pygame.draw.aalines(surf, lighten(self.c, 0.6), False, hl)
        gfx.aaellipse(surf, int(cx), int(cy), int(rx), max(1, int(ry)), rgba(self.c, 200 * a))
        if self.cracked:
            cc = rgba(shade(self.c, 0.55), 255 * a)
            for ang, ln in ((0.3, 0.8), (0.62, 0.7), (0.85, 0.6)):
                x0, y0 = cx + rx * 0.1 * math.cos(math.pi * ang), cy - hg * 0.35
                x1, y1 = cx + rx * ln * math.cos(math.pi * ang), cy - hg * ln * math.sin(math.pi * ang)
                gfx.line(surf, int(x0), int(y0), int(x1), int(y1), cc)
                gfx.line(surf, int(x0) + 1, int(y0), int(x1) + 1, int(y1), cc)


def draw_fire(surf, sx, sy, size, t):
    if size <= 0.03:
        return
    size *= K
    layers = (((255, 84, 30), 1.0), ((255, 158, 40), 0.72), ((255, 232, 120), 0.42))
    for li, (col, scl) in enumerate(layers):
        for k in range(3):
            ox = (k - 1) * 9 * size * scl
            hgt = (38 + 11 * math.sin(t * 12 + k * 2.1 + li)) * size * scl
            wd = 10 * size * scl
            cx = sx + ox
            cy = sy
            pts = [(cx - wd * math.cos(math.pi * i / 8), cy - wd + wd * math.sin(math.pi * i / 8)) for i in range(9)]
            pts.append((cx + math.sin(t * 9 + k) * 3 * size, cy - hgt))
            ip = [ipt(q) for q in pts]
            gfx.filled_polygon(surf, ip, rgba(col, 235))
            gfx.aapolygon(surf, ip, rgba(col, 235))


def draw_gas(surf, sx, sy, size, t, color=(110, 210, 90)):
    if size <= 0.03:
        return
    size *= K
    for i in range(7):
        a = t * 0.9 + i * 0.9
        rx = (14 + 10 * math.sin(i * 1.7)) * size * 1.15
        px = sx + math.cos(a) * 18 * size + (i - 3) * 6 * size
        py = sy - 10 * size - math.sin(a * 1.3) * 7 * size - i * 2 * size
        gfx.filled_circle(surf, int(px), int(py), max(2, int(rx)), rgba(color, 105))
        gfx.aacircle(surf, int(px), int(py), max(2, int(rx)), rgba(shade(color, 0.75), 150))


def draw_virus(surf, sx, sy, t, scale=1.0, alpha=255):
    scale *= K
    r = 10 * scale
    rot = t * 3
    for i in range(8):
        a = rot + i * math.pi / 4
        x1, y1 = sx + math.cos(a) * r, sy + math.sin(a) * r
        x2, y2 = sx + math.cos(a) * (r + 7 * scale), sy + math.sin(a) * (r + 7 * scale)
        pygame.draw.line(surf, (200, 60, 230), (int(x1), int(y1)), (int(x2), int(y2)), max(2, int(3 * scale)))
        gfx.filled_circle(surf, int(x2), int(y2), max(1, int(2.5 * scale)), rgba((255, 90, 160), alpha))
    gfx.filled_circle(surf, int(sx), int(sy), int(r), rgba((150, 40, 200), alpha))
    gfx.filled_circle(surf, int(sx - r * 0.25), int(sy - r * 0.3), max(1, int(r * 0.45)), rgba((230, 120, 255), alpha))
    gfx.aacircle(surf, int(sx), int(sy), int(r), rgba((255, 140, 255), alpha))


def draw_alert_bubble(surf, cx, cy, t, color=(255, 132, 50), symbol="!"):
    """Marcador em forma de alfinete, com pulso suave."""
    r = S(14)
    pr = r + S(5) + S(3) * math.sin(t * 5)
    gfx.aacircle(surf, cx, cy, int(pr), rgba(color, 120))
    gfx.aacircle(surf, cx, cy, int(pr) + 1, rgba(color, 60))
    gfx.filled_circle(surf, cx, cy + S(3), r + 1, (0, 0, 0, 60))
    gfx.filled_trigon(surf, cx - S(6), cy + r - S(5), cx + S(6), cy + r - S(5), cx, cy + r + S(7), color)
    gfx.aatrigon(surf, cx - S(6), cy + r - S(5), cx + S(6), cy + r - S(5), cx, cy + r + S(7), color)
    gfx.filled_circle(surf, cx, cy, r, color)
    gfx.aacircle(surf, cx, cy, r, shade(color, 0.85))
    gfx.filled_circle(surf, cx - S(4), cy - S(5), max(1, S(4)), rgba(lighten(color, 0.6), 160))
    draw_text(surf, symbol, 19, (255, 255, 255), (cx, cy + S(1)), bold=True, anchor="center")


def draw_badge(surf, cx, cy, m, scale=1.0, alpha=255, ring=None, dim=False):
    r = max(4, int(S(19) * scale))
    cx, cy = int(cx), int(cy)
    gfx.filled_circle(surf, cx, cy + S(4), r + S(2), (0, 0, 0, int(70 * alpha / 255)))
    gfx.filled_circle(surf, cx, cy, r + S(3), rgba((255, 255, 255), alpha))
    gfx.aacircle(surf, cx, cy, r + S(3), rgba((255, 255, 255), alpha))
    col = m["color"] if not dim else mix(m["color"], (90, 90, 100), 0.55)
    gfx.filled_circle(surf, cx, cy, r, rgba(shade(col, 0.82), alpha))
    gfx.filled_circle(surf, cx, cy - max(1, r // 8), r - max(1, r // 8), rgba(col, alpha))
    gfx.aacircle(surf, cx, cy, r, rgba(shade(col, 0.8), alpha))
    # brilho
    gfx.filled_ellipse(surf, cx - r // 3, cy - r // 2, max(1, r // 2), max(1, r // 4), rgba((255, 255, 255), 55 * alpha / 255))
    ic = icon(m["icon"], 26)
    if abs(scale - 1) > 0.02:
        sz = max(2, int(ic.get_width() * scale))
        ic = pygame.transform.smoothscale(ic, (sz, sz))
    if alpha < 255:
        ic = ic.copy()
        ic.set_alpha(alpha)
    surf.blit(ic, ic.get_rect(center=(cx, cy)))
    if ring:
        gfx.aacircle(surf, cx, cy, r + S(6), ring)
        gfx.aacircle(surf, cx, cy, r + S(7), ring)


def draw_iso_ring(surf, cx, cy, r, color, alpha, fill=0.35, thick=2):
    rx, ry = max(2, int(r * HW * SQ2)), max(1, int(r * HH * SQ2))
    if fill > 0:
        gfx.filled_ellipse(surf, int(cx), int(cy), rx, ry, rgba(color, alpha * fill))
    for i in range(max(1, int(thick * K))):
        gfx.aaellipse(surf, int(cx), int(cy), rx - i, max(1, ry - i), rgba(color, alpha))


# ---------------------------------------------------------------------------
# Dados dos locais
# ---------------------------------------------------------------------------
def M(mid, name, desc, ic, color):
    return dict(id=mid, name=name, desc=desc, icon=ic, color=color)


C_BLUE, C_TEAL, C_ORANGE, C_PURPLE = (86, 140, 255), (52, 186, 164), (255, 160, 56), (146, 104, 250)
C_RED, C_YELLOW, C_GRAY, C_PINK = (236, 72, 86), (240, 186, 40), (104, 120, 160), (246, 120, 172)
C_GREEN, C_SKY = (72, 190, 120), (56, 156, 236)

LOCATIONS = {}

# ---------------------------------- CASA ----------------------------------
LOCATIONS["casa"] = dict(
    name="Casa", art="a", gender="a", color=(255, 138, 88), icon="house",
    tagline="Proteja sua família e o seu lar",
    wall=(240, 226, 206),
    ground=[("road", 0, 10, 16, 2), ("sidewalk", 0, 9, 16, 1), ("concrete", 12, 8, 3, 1), ("path", 5, 8, 1, 1)],
    rooms=[
        ("Quarto", 3, 2, 4, 3, ("carpet", (178, 160, 210), (170, 152, 202))),
        ("Banheiro", 7, 2, 2, 3, ("tile", (232, 242, 248), (205, 225, 238))),
        ("Cozinha", 9, 2, 3, 3, ("tile", (244, 240, 232), (214, 200, 180))),
        ("Sala", 3, 5, 5, 3, ("wood", (198, 148, 100), (184, 136, 92))),
        ("Escritório", 8, 5, 4, 3, ("wood", (170, 122, 84), (158, 112, 76))),
        ("Garagem", 12, 4, 3, 4, ("concrete", (178, 180, 186), (170, 172, 178))),
    ],
    doors=[("x", 5, 8), ("x", 4, 5), ("x", 7, 5), ("y", 8, 6), ("x", 9, 5), ("y", 12, 6),
           ("x", 12, 8), ("x", 13, 8), ("x", 14, 8)],
    decor=[("window", "y", 3, 3), ("window", "x", 4, 2), ("window", "x", 8, 2), ("window", "x", 10, 2),
           ("window", "y", 3, 6), ("window", "x", 13, 4)],
    decals=[("rug", 4.3, 5.75, 1.5, 1.5, (214, 92, 96)), ("rug", 4.0, 4.25, 1.3, 0.6, (240, 200, 120))],
    props=[
        ("bed", 3.35, 2.18, 1.5, 1.95, {"c": (110, 150, 230)}),
        ("box", 5.0, 2.18, 0.5, 0.45, {"h": 12, "c": WOOD}),
        ("wardrobe", 6.15, 2.18, 0.75, 1.4, {}),
        ("plant", 3.15, 4.35, 0.35, 0.35, {}),
        ("toilet", 8.3, 2.2, 0.5, 0.6, {}),
        ("sink", 7.2, 2.18, 0.6, 0.42, {}),
        ("bathtub", 8.0, 3.0, 0.85, 1.8, {}),
        ("counter", 9.15, 2.18, 1.7, 0.62, {}),
        ("stove", 10.9, 2.18, 0.75, 0.62, {}),
        ("fridge", 9.15, 3.45, 0.65, 0.7, {}),
        ("table", 10.15, 3.7, 0.95, 0.75, {"vase": True}),
        ("sofa", 3.2, 5.55, 0.85, 1.9, {"c": (88, 120, 172), "back": "y"}),
        ("table", 4.6, 6.1, 0.75, 0.75, {"h": 8}),
        ("tv", 6.95, 5.7, 0.5, 1.5, {}),
        ("plant", 7.4, 7.3, 0.4, 0.4, {}),
        ("desk", 10.55, 5.15, 1.3, 0.62, {"router": True}),
        ("chair", 10.95, 5.85, 0.45, 0.45, {"c": (60, 64, 80)}),
        ("bookshelf", 11.35, 6.7, 0.55, 1.15, {}),
        ("car", 12.35, 4.4, 1.4, 2.7, {"dir": "y", "c": (220, 70, 70)}),
        ("rack", 14.3, 4.25, 0.55, 1.3, {}),
        ("tree", 1.3, 1.3, 0, 0, {}), ("tree", 1.1, 6.9, 0, 0, {"r": 18}), ("tree", 14.4, 2.7, 0, 0, {}),
        ("tree", 15.2, 6.4, 0, 0, {"r": 17, "c": (90, 176, 80)}),
        ("bush", 2.3, 8.5, 0, 0, {}), ("bush", 4.2, 8.55, 0, 0, {}), ("bush", 7.2, 8.55, 0, 0, {}),
        ("bush", 11.3, 8.5, 0, 0, {}), ("bush", 0.8, 3.6, 0, 0, {}), ("bush", 5.0, 1.0, 0, 0, {"c": (110, 180, 90)}),
        ("mailbox", 6.6, 8.55, 0, 0, {}),
    ] + [("muro", i, 0.05, 1, 0.3, {}) for i in range(16)]
      + [("muro", 0.05, j, 0.3, 1, {}) for j in range(1, 9)]
      + [("muro", 15.65, j, 0.3, 1, {}) for j in range(1, 8)],
    lamps=[(2.0, 9.4), (9.6, 9.4), (15.2, 9.4)],
    npcs=[
        ("mom", [(5.7, 7.3), (6.5, 6.5), (9.5, 6.5), (9.5, 4.6), (10.4, 3.25), (9.5, 4.6), (9.5, 6.5), (6.5, 6.5)]),
        ("dad", [(8.7, 7.4), (10.9, 7.4), (10.3, 6.45)]),
        ("kid", [(4.4, 7.55), (6.2, 7.55)]),
    ],
    cars=[(10.55, 1), (11.45, -1)],
    measures=[
        M("fechadura", "Fechadura inteligente", "Fechadura digital com senha e registro de acessos. Muito mais difícil de arrombar que a chave comum.", "lock", C_BLUE),
        M("grade", "Grade + sensor na janela", "Grades impedem a passagem e o sensor de abertura avisa se alguém forçar a janela.", "bars", C_GRAY),
        M("detector", "Detector de fumaça e gás", "Dispara um alarme logo no início de um vazamento de gás ou de um princípio de incêndio.", "smoke", C_ORANGE),
        M("camera", "Câmera de segurança", "Câmera com visão noturna e alerta no celular. Inibe ladrões e grava tudo.", "camera", C_TEAL),
        M("wifi", "Wi-Fi com senha forte", "Senha longa, criptografia WPA3 e roteador atualizado impedem invasões pela rede.", "wifi", C_PURPLE),
        M("luz", "Iluminação com sensor", "Refletor que acende ao detectar movimento. Ninguém gosta de ser visto pulando o muro!", "bulb", C_YELLOW),
        M("alarme", "Alarme residencial", "Central de alarme com sirene. Ajuda, mas sozinho não impede a entrada.", "siren", C_RED),
        M("extintor", "Extintor de incêndio", "Combate princípios de incêndio, mas só funciona se alguém perceber o fogo a tempo.", "extinguisher", (220, 60, 60)),
    ],
    spots=[
        dict(id="porta", name="Porta da frente", desc="Principal entrada da casa, de frente para a rua.",
             pos=(5.5, 8.45), ideal="fechadura", ok=["alarme", "camera"], threat="thief",
             threat_name="Ladrão tentando arrombar a porta", path=[(5.5, 11.6)], breach=(5.5, 7.0)),
        dict(id="janela", name="Janela do quarto", desc="Janela lateral, escondida da rua.",
             pos=(2.55, 3.5), ideal="grade", ok=["alarme"], threat="intruder",
             threat_name="Invasor entrando pela janela", path=[(0.6, 10.4), (1.9, 8.6), (2.4, 5.0)], breach=(3.6, 3.5)),
        dict(id="cozinha", name="Fogão da cozinha", desc="Botijão e fogão: risco de vazamento de gás e fogo.",
             pos=(11.32, 3.1), ideal="detector", ok=["extintor"], threat="fire",
             threat_name="Vazamento de gás e princípio de incêndio"),
        dict(id="garagem", name="Garagem", desc="Carro e ferramentas, com portão para a rua.",
             pos=(13.5, 8.45), ideal="camera", ok=["luz", "alarme"], threat="thief",
             threat_name="Tentativa de furto do carro", path=[(15.7, 11.0), (15.2, 9.4)], breach=(13.9, 7.4)),
        dict(id="wifi", name="Roteador Wi-Fi", desc="Rede da casa: celulares, câmeras e computadores.",
             pos=(11.2, 6.15), ideal="wifi", ok=[], threat="virus",
             threat_name="Hacker tentando invadir a rede"),
        dict(id="quintal", name="Muro do quintal", desc="Fundos da casa, escuros e sem movimento à noite.",
             pos=(8.0, 1.15), ideal="luz", ok=["camera", "alarme"], threat="intruder",
             threat_name="Invasor pulando o muro", path=[(11.8, 0.2), (11.4, 0.9)], hop=True, breach=(6.6, 1.5)),
    ],
)

# -------------------------------- HOSPITAL --------------------------------
LOCATIONS["hospital"] = dict(
    name="Hospital", art="o", gender="o", color=(72, 166, 234), icon="hospital",
    tagline="Pacientes, dados e medicamentos",
    wall=(234, 244, 242),
    ground=[("road", 0, 10, 16, 2), ("sidewalk", 0, 9, 16, 1), ("sidewalk", 12, 0, 1, 9), ("parking", 13, 0, 3, 9)],
    rooms=[
        ("TI", 1, 1, 3, 3, ("tile", (168, 178, 196), (156, 166, 186))),
        ("Enfermaria", 4, 1, 5, 3, ("lino", (214, 230, 244), (200, 218, 236))),
        ("Gases", 9, 1, 3, 3, ("concrete", (190, 194, 200), (182, 186, 192))),
        ("Recepção", 1, 4, 5, 4, ("lino", (210, 236, 228), (196, 226, 218))),
        ("Farmácia", 6, 4, 3, 4, ("tile", (240, 246, 244), (214, 232, 226))),
        ("Berçário", 9, 4, 3, 4, ("carpet", (246, 218, 226), (240, 210, 220))),
    ],
    doors=[("x", 3, 8), ("x", 4, 8), ("x", 2, 4), ("x", 5, 4), ("y", 6, 6), ("x", 8, 4), ("y", 9, 2),
           ("y", 9, 6), ("x", 10, 4), ("y", 12, 6), ("y", 12, 2)],
    decor=[("window", "x", 5, 1), ("window", "x", 6, 1), ("window", "x", 7, 1), ("window", "x", 2, 1),
           ("window", "y", 1, 5), ("window", "y", 1, 6), ("window", "x", 10, 1)],
    decals=[("rug", 3.6, 4.5, 2.0, 2.4, (170, 214, 206)), ("cross", 3.6, 8.6, 0.8, 0.8, (230, 60, 70))],
    props=[
        ("server", 1.15, 1.15, 0.55, 0.7, {}), ("server", 1.75, 1.15, 0.55, 0.7, {}), ("server", 2.35, 1.15, 0.55, 0.7, {}),
        ("monitors", 3.0, 1.2, 0.85, 0.55, {}),
        ("hbed", 4.35, 1.15, 0.85, 1.6, {}), ("hbed", 5.85, 1.15, 0.85, 1.6, {}), ("hbed", 7.35, 1.15, 0.85, 1.6, {}),
        ("oxygen", 9.15, 1.15, 1.6, 0.8, {}),
        ("box", 11.25, 1.15, 0.6, 0.45, {"h": 36, "c": (124, 134, 150), "bands": [(20, 24, (230, 60, 60))]}),
        ("reception", 1.4, 4.6, 2.0, 0.6, {"L": 0.9}),
        ("bench", 3.9, 5.0, 1.4, 0.42, {"c": (90, 150, 200)}), ("bench", 3.9, 6.0, 1.4, 0.42, {"c": (90, 150, 200)}),
        ("plant", 5.35, 4.2, 0.4, 0.4, {}), ("plant", 1.2, 7.3, 0.4, 0.4, {}),
        ("cabinet", 6.12, 4.12, 1.75, 0.5, {}),
        ("counter", 6.3, 6.9, 2.2, 0.55, {"c": (240, 244, 246), "top": (80, 170, 150)}),
        ("crib", 9.3, 4.3, 0.55, 0.75, {"c": (250, 190, 210)}), ("crib", 10.15, 4.3, 0.55, 0.75, {"c": (170, 210, 250)}),
        ("crib", 11.0, 4.3, 0.55, 0.75, {"c": (250, 230, 150)}),
        ("chair", 11.2, 6.9, 0.5, 0.5, {"c": (220, 150, 170)}),
        ("ambulance", 13.25, 1.2, 1.15, 2.4, {"dir": "y"}),
        ("car", 14.55, 4.6, 1.05, 2.0, {"dir": "y", "c": (70, 120, 200)}),
        ("tree", 0.5, 2.5, 0, 0, {"r": 17}), ("tree", 0.5, 6.4, 0, 0, {"r": 17}), ("tree", 0.6, 9.3, 0, 0, {"r": 16}),
        ("bush", 6.5, 8.5, 0, 0, {}), ("bush", 9.5, 8.5, 0, 0, {}), ("bush", 11.0, 8.5, 0, 0, {}),
        ("bench", 7.6, 8.45, 1.1, 0.38, {}),
    ],
    lamps=[(6.0, 9.4), (12.5, 9.4), (15.6, 4.5)],
    npcs=[
        ("nurse", [(4.6, 3.35), (8.3, 3.35)]),
        ("nurse", [(2.3, 4.3), (3.4, 4.3)]),
        ("doctor", [(2.6, 6.9), (5.6, 6.9), (6.6, 6.5), (7.8, 6.3), (6.6, 6.5), (5.6, 6.9)]),
        ("nurse", [(9.6, 7.3), (10.8, 7.4)]),
    ],
    cars=[(10.55, 1), (11.45, -1)],
    measures=[
        M("acesso", "Controle de acesso com crachá", "Catracas e crachás garantem que só pacientes, visitantes cadastrados e equipe entrem.", "badge", C_BLUE),
        M("biometria", "Armário com biometria", "Medicamentos controlados só saem com a digital de um profissional autorizado.", "fingerprint", C_TEAL),
        M("firewall", "Firewall + backup", "Bloqueia ataques e mantém cópias seguras dos prontuários. Contra ransomware é essencial.", "shield", C_PURPLE),
        M("sprinkler", "Detector + sprinklers", "Detecta fumaça e libera água automaticamente, vital perto de gases inflamáveis.", "sprinkler", C_SKY),
        M("pulseira", "Pulseira RFID", "Mãe e bebê usam pulseiras pareadas: se o bebê sair da ala sem autorização, as portas travam.", "bracelet", C_PINK),
        M("camera", "Câmeras CFTV", "Monitoramento 24h com gravação. Inibe vandalismo e ajuda a identificar responsáveis.", "camera", C_GREEN),
        M("vigilante", "Vigilante 24h", "Um profissional faz rondas. Ajuda em várias áreas, mas não pode estar em todo lugar.", "guard", C_GRAY),
        M("extintor", "Extintor de incêndio", "Útil em princípios de incêndio, mas precisa de alguém por perto para usar.", "extinguisher", C_RED),
    ],
    spots=[
        dict(id="entrada", name="Entrada principal", desc="Porta de acesso de pacientes e visitantes.",
             pos=(4.0, 7.5), ideal="acesso", ok=["vigilante"], threat="intruder",
             threat_name="Pessoa sem identificação tentando entrar", path=[(4.0, 11.6)], breach=(3.2, 6.6)),
        dict(id="farmacia", name="Farmácia", desc="Armários com medicamentos controlados.",
             pos=(7.0, 5.3), ideal="biometria", ok=["camera"], threat="thief",
             threat_name="Furto de medicamentos controlados", path=[(5.2, 3.5), (8.5, 3.5), (8.5, 4.5)], breach=(7.6, 6.4)),
        dict(id="ti", name="Servidor de prontuários", desc="Dados de todos os pacientes do hospital.",
             pos=(2.0, 2.45), ideal="firewall", ok=[], threat="virus",
             threat_name="Ransomware tentando sequestrar os prontuários"),
        dict(id="gases", name="Central de gases", desc="Cilindros de oxigênio: material altamente inflamável.",
             pos=(10.6, 2.85), ideal="sprinkler", ok=["extintor"], threat="fire",
             threat_name="Incêndio na central de gases"),
        dict(id="bercario", name="Berçário", desc="Ala dos recém-nascidos.",
             pos=(10.5, 6.0), ideal="pulseira", ok=["vigilante", "acesso"], threat="intruder",
             threat_name="Pessoa não autorizada no berçário", path=[(13.0, 11.4), (12.6, 6.5)], breach=(12.6, 6.6)),
        dict(id="estacionamento", name="Estacionamento", desc="Ambulâncias e carros de funcionários.",
             pos=(13.8, 7.6), ideal="camera", ok=["vigilante"], threat="vandal",
             threat_name="Vandalismo nas ambulâncias", path=[(15.6, 11.4), (14.2, 9.2)], breach=(13.9, 4.2)),
    ],
)

# -------------------------------- INDUSTRIA --------------------------------
LOCATIONS["industria"] = dict(
    name="Indústria", art="a", gender="a", color=(244, 182, 52), icon="factory",
    tagline="Máquinas, químicos e cargas",
    wall=(204, 212, 220),
    ground=[("asphalt", 0, 7, 16, 3), ("grass", 0, 0, 2, 7), ("concrete", 13, 0, 3, 7), ("road", 0, 10, 16, 2)],
    rooms=[
        ("Controle", 2, 1, 3, 3, ("tile", (150, 165, 185), (140, 155, 176))),
        ("Produção", 5, 1, 8, 3, ("concrete", (180, 184, 190), (172, 176, 182))),
        ("Tanques", 2, 4, 4, 3, ("concrete", (186, 190, 176), (178, 182, 168))),
        ("Almoxarifado", 6, 4, 4, 3, ("concrete", (186, 182, 174), (178, 174, 166))),
        ("Doca", 10, 4, 3, 3, ("concrete", (162, 166, 172), (154, 158, 164))),
    ],
    doors=[("y", 5, 2), ("x", 3, 4), ("y", 6, 5), ("x", 9, 4), ("y", 10, 5), ("x", 11, 4),
           ("x", 7, 7), ("x", 4, 7), ("x", 10, 7), ("x", 11, 7), ("x", 12, 7)],
    decor=[("window", "x", 3, 1), ("window", "x", 6, 1), ("window", "x", 8, 1), ("window", "x", 10, 1),
           ("window", "x", 12, 1), ("window", "y", 2, 2), ("window", "y", 2, 5)],
    decals=[("line", 5.2, 2.05, 7.6, 0.06, (250, 210, 60)), ("line", 5.2, 3.05, 7.6, 0.06, (250, 210, 60)),
            ("line", 9.9, 7.15, 0.07, 2.7, (250, 210, 60)), ("line", 13.1, 7.15, 0.07, 2.7, (250, 210, 60)),
            ("hazard", 2.3, 6.55, 3.4, 0.25, (250, 210, 60))],
    props=[
        ("monitors", 2.25, 1.2, 2.0, 0.55, {}), ("server", 2.15, 2.6, 0.55, 0.7, {}),
        ("machine", 5.6, 1.15, 1.0, 0.85, {"c": (245, 190, 50)}), ("machine", 8.4, 1.15, 1.2, 0.85, {"c": (240, 140, 60), "h": 40}),
        ("machine", 11.2, 1.15, 1.1, 0.85, {"c": (245, 190, 50)}),
        ("conveyor", 5.4, 2.25, 2.3, 0.6, {}), ("conveyor", 7.7, 2.25, 2.3, 0.6, {}), ("conveyor", 10.0, 2.25, 2.6, 0.6, {}),
        ("tank", 2.95, 5.0, 0, 0, {"r": 0.5, "h": 56, "c": (140, 170, 192)}), ("tank", 4.55, 5.0, 0, 0, {"r": 0.5, "h": 56, "c": (172, 190, 150)}),
        ("rack", 6.15, 4.15, 1.3, 0.5, {}), ("rack", 7.6, 4.15, 1.25, 0.5, {}),
        ("barrel", 6.5, 5.8, 0, 0, {}), ("barrel", 6.98, 5.75, 0, 0, {}), ("barrel", 6.72, 6.25, 0, 0, {"c": (60, 110, 200)}),
        ("pallet", 8.95, 6.0, 0.8, 0.8, {}),
        ("pallet", 10.25, 4.25, 0.8, 0.8, {}), ("pallet", 11.25, 4.25, 0.8, 0.8, {"h": 26, "c": (150, 190, 220)}),
        ("forklift", 12.15, 4.6, 0.6, 1.0, {}),
        ("booth", 3.3, 7.9, 1.0, 0.9, {}), ("barrier", 4.55, 9.05, 2.3, 0.2, {}),
        ("truck", 13.6, 3.4, 1.2, 3.2, {}),
        ("crate", 13.4, 0.9, 0.7, 0.7, {}), ("crate", 14.2, 0.9, 0.7, 0.7, {"h": 24}), ("crate", 13.4, 1.7, 0.7, 0.7, {"h": 12}),
        ("crate", 15.0, 1.0, 0.7, 0.7, {"h": 18, "c": (150, 180, 210)}),
        ("tree", 0.9, 1.5, 0, 0, {}), ("tree", 1.0, 4.1, 0, 0, {"r": 18}), ("tree", 0.8, 6.3, 0, 0, {"r": 16}),
    ] + [("fence", i, 9.0, 1, 0.1, {"dir": "x"}) for i in (0, 1, 2, 13, 14, 15)],
    lamps=[(2.6, 9.3), (9.0, 8.8), (15.4, 8.8)],
    npcs=[
        ("worker", [(5.6, 3.5), (7.9, 3.5)]),
        ("worker2", [(10.0, 3.55), (12.4, 3.55)]),
        ("worker", [(7.0, 6.6), (9.4, 6.65)]),
        ("operator", [(2.6, 3.2), (2.6, 2.1)]),
    ],
    cars=[(10.55, 1), (11.45, -1)],
    measures=[
        M("acesso", "Portaria com controle de acesso", "Cancela, cadastro de visitantes e crachá: ninguém entra sem identificação.", "badge", C_BLUE),
        M("epi", "EPI + proteção de máquinas", "Capacete, luvas, óculos e sensores de parada de emergência (NR-12) evitam acidentes.", "helmet", C_YELLOW),
        M("gas", "Detector de gás", "Mede a concentração de gases tóxicos e dispara alerta antes que vire perigo.", "gauge", C_GREEN),
        M("firewall", "Firewall industrial", "Isola a rede das máquinas (SCADA) da internet e bloqueia ataques.", "shield", C_PURPLE),
        M("sprinkler", "Sistema de sprinklers", "Chuveiros automáticos que apagam o fogo no início, essenciais onde há inflamáveis.", "sprinkler", C_SKY),
        M("camera", "Câmeras CFTV", "Monitoram a doca e o pátio com gravação 24h.", "camera", C_TEAL),
        M("vigilante", "Vigilante", "Rondas pelo pátio. Ajuda, mas sozinho não cobre tudo.", "guard", C_GRAY),
        M("evacuacao", "Alarme de evacuação", "Avisa todos para sair. Salva vidas, mas não impede o problema.", "siren", C_RED),
    ],
    spots=[
        dict(id="portaria", name="Portaria", desc="Única entrada de veículos e pessoas.",
             pos=(5.7, 9.45), ideal="acesso", ok=["vigilante", "camera"], threat="intruder",
             threat_name="Invasor tentando passar pela portaria", path=[(5.7, 11.7)], breach=(5.7, 7.6)),
        dict(id="producao", name="Linha de produção", desc="Máquinas pesadas operando o dia todo.",
             pos=(9.0, 3.45), ideal="epi", ok=[], threat="accident",
             threat_name="Risco de acidente na máquina"),
        dict(id="tanques", name="Tanques químicos", desc="Produtos tóxicos armazenados sob pressão.",
             pos=(3.75, 6.25), ideal="gas", ok=["evacuacao"], threat="gas",
             threat_name="Vazamento de gás tóxico"),
        dict(id="controle", name="Sala de controle", desc="Computadores que comandam as máquinas (SCADA).",
             pos=(3.6, 2.9), ideal="firewall", ok=[], threat="virus",
             threat_name="Ataque hacker ao sistema das máquinas"),
        dict(id="almox", name="Almoxarifado", desc="Estoque de tambores e produtos inflamáveis.",
             pos=(8.3, 5.6), ideal="sprinkler", ok=["evacuacao"], threat="fire",
             threat_name="Incêndio no estoque de inflamáveis"),
        dict(id="doca", name="Doca de carga", desc="Área de carga e descarga de caminhões.",
             pos=(11.5, 7.5), ideal="camera", ok=["vigilante"], threat="thief",
             threat_name="Roubo de carga na doca", path=[(15.6, 11.2), (13.0, 8.4)], breach=(11.6, 5.9)),
    ],
)

# --------------------------------- MERCADO ---------------------------------
LOCATIONS["mercado"] = dict(
    name="Mercado", art="o", gender="o", color=(76, 196, 124), icon="cart",
    tagline="Caixas, estoque e clientes",
    wall=(246, 238, 224),
    ground=[("road", 0, 10, 16, 2), ("sidewalk", 0, 8, 16, 2), ("asphalt", 14, 0, 2, 8)],
    rooms=[
        ("Padaria", 1, 1, 4, 2, ("tile", (246, 226, 196), (232, 208, 172))),
        ("Escritório", 5, 1, 3, 2, ("wood", (176, 128, 88), (164, 118, 80))),
        ("Câmara fria", 8, 1, 3, 2, ("tile", (226, 240, 250), (206, 226, 242))),
        ("Salão", 1, 3, 10, 5, ("tile", (246, 244, 236), (226, 222, 210))),
        ("Depósito", 11, 1, 3, 7, ("concrete", (180, 178, 172), (172, 170, 164))),
    ],
    doors=[("x", 2, 8), ("x", 3, 8), ("x", 7, 8), ("x", 2, 3), ("x", 6, 3), ("x", 9, 3), ("y", 11, 5),
           ("y", 14, 2), ("y", 14, 3)],
    decor=[("window", "x", 2, 1), ("window", "x", 6, 1), ("window", "y", 1, 4), ("window", "y", 1, 6),
           ("window", "x", 12, 1)],
    decals=[("line", 14.9, 0.4, 0.07, 7.2, (250, 250, 250))],
    props=[
        ("oven", 1.15, 1.12, 1.1, 0.75, {}),
        ("shelf", 2.6, 1.12, 1.5, 0.45, {"h": 30, "c": (200, 160, 110), "bands": [(6, 11, (196, 136, 66)), (15, 20, (222, 172, 92)), (24, 28, (188, 118, 58))]}),
        ("counter", 3.0, 2.25, 1.8, 0.5, {"top": (200, 150, 100)}),
        ("desk", 5.25, 1.15, 1.3, 0.55, {}), ("safe", 7.2, 1.15, 0.6, 0.55, {}),
        ("freezer", 8.15, 1.12, 1.3, 0.6, {}), ("freezer", 9.5, 1.12, 1.35, 0.6, {}),
        ("gondola", 2.4, 3.6, 0.55, 2.3, {}), ("gondola", 4.0, 3.6, 0.55, 2.3, {}), ("gondola", 5.6, 3.6, 0.55, 2.3, {}),
        ("gondola", 7.2, 3.6, 0.55, 2.3, {}), ("gondola", 8.8, 3.6, 0.55, 2.3, {}),
        ("checkout", 5.0, 6.6, 0.6, 1.0, {}), ("checkout", 6.6, 6.6, 0.6, 1.0, {}), ("checkout", 8.3, 6.6, 0.6, 1.0, {}),
        ("freezer", 9.6, 6.7, 1.1, 0.7, {}),
        ("pallet", 11.25, 1.25, 0.85, 0.85, {"h": 22}), ("pallet", 12.35, 1.25, 0.85, 0.85, {"h": 30, "c": (150, 190, 220)}),
        ("pallet", 11.3, 6.6, 0.85, 0.85, {"h": 18}), ("pallet", 12.5, 6.6, 0.85, 0.85, {"h": 26, "c": (230, 150, 120)}),
        ("forklift", 12.6, 4.0, 0.6, 1.0, {}),
        ("crate", 15.05, 0.6, 0.7, 0.7, {"h": 20}), ("crate", 15.05, 1.45, 0.7, 0.7, {"h": 12}),
        ("tree", 0.5, 1.8, 0, 0, {"r": 16}), ("tree", 0.5, 5.4, 0, 0, {"r": 17}),
        ("plant", 5.4, 8.25, 0.35, 0.35, {}), ("plant", 10.3, 8.25, 0.35, 0.35, {}),
        ("bench", 11.4, 8.4, 1.2, 0.38, {}),
    ],
    lamps=[(4.5, 9.45), (12.6, 9.45)],
    npcs=[
        ("cashier", [(6.3, 6.9), (6.3, 7.35)]),
        ("shopper", [(3.45, 4.0), (3.45, 6.2), (1.6, 6.2), (1.6, 4.0)]),
        ("shopper", [(6.6, 3.4), (10.2, 3.4), (10.2, 6.2), (6.6, 6.2)]),
        ("baker", [(3.1, 1.9), (4.6, 1.9)]),
    ],
    cars=[(10.55, 1), (11.45, -1)],
    measures=[
        M("antena", "Antena antifurto", "Etiquetas nos produtos disparam o alarme se passarem pela saída sem pagar.", "antenna", C_BLUE),
        M("panico", "Botão de pânico", "Aciona a central de segurança e a polícia em silêncio durante um assalto.", "panic", C_RED),
        M("camera", "Câmeras CFTV", "Cobrem os corredores e ajudam a flagrar furtos escondidos.", "camera", C_TEAL),
        M("acesso", "Porta com senha", "Só funcionários autorizados abrem a porta da doca e do estoque.", "keypad", C_SKY),
        M("extintor", "Extintor + detector de fumaça", "Detecta fumaça no forno da padaria e permite combater o fogo no início.", "extinguisher", (220, 60, 60)),
        M("rede", "Rede segura + antivírus", "Protege as maquininhas e o sistema de pagamento contra golpes digitais.", "shield", C_PURPLE),
        M("vigilante", "Fiscal de prevenção", "Fiscal circulando pela loja. Ajuda, mas não vê tudo ao mesmo tempo.", "guard", C_GRAY),
        M("alarme", "Alarme com sirene", "Faz barulho e assusta, mas sozinho não impede a ação.", "siren", C_ORANGE),
    ],
    spots=[
        dict(id="entrada", name="Entrada / saída", desc="Por onde clientes entram e saem com as compras.",
             pos=(3.0, 7.55), ideal="antena", ok=["camera"], threat="shoplifter",
             threat_name="Furto de produtos na saída", path=[(3.45, 4.6), (3.45, 6.4)], breach=(3.0, 10.8)),
        dict(id="caixa", name="Caixas", desc="Onde fica o dinheiro das vendas.",
             pos=(7.75, 7.15), ideal="panico", ok=["vigilante", "camera"], threat="robber",
             threat_name="Assalto ao caixa", path=[(7.6, 11.6), (7.6, 8.4)], breach=(7.6, 10.8)),
        dict(id="corredor", name="Corredores", desc="Gôndolas altas que escondem quem está atrás.",
             pos=(5.08, 4.75), ideal="camera", ok=["vigilante"], threat="shoplifter",
             threat_name="Furto escondido nos corredores", path=[(2.9, 11.6), (3.0, 8.4), (3.4, 6.4), (5.08, 6.3)], breach=(5.08, 3.3)),
        dict(id="doca", name="Doca de recebimento", desc="Porta dos fundos por onde chegam as mercadorias.",
             pos=(14.45, 3.0), ideal="acesso", ok=["camera", "alarme"], threat="intruder",
             threat_name="Invasão pela doca de recebimento", path=[(15.6, 11.0), (15.3, 6.0)], breach=(12.9, 3.0)),
        dict(id="padaria", name="Forno da padaria", desc="Forno a gás ligado desde a madrugada.",
             pos=(1.8, 2.35), ideal="extintor", ok=["alarme"], threat="fire",
             threat_name="Incêndio no forno da padaria"),
        dict(id="pagamentos", name="Sistema de pagamentos", desc="Computador que controla as maquininhas de cartão.",
             pos=(6.1, 2.3), ideal="rede", ok=[], threat="virus",
             threat_name="Golpe digital nas maquininhas"),
    ],
)

# ---------------------------------- MUSEU ----------------------------------
LOCATIONS["museu"] = dict(
    name="Museu", art="o", gender="o", color=(168, 116, 232), icon="museum",
    tagline="Obras de arte e acervo histórico",
    wall=(150, 56, 70),
    ground=[("road", 0, 10, 16, 2), ("plaza", 0, 8, 16, 2), ("path", 6, 8, 2, 2)],
    rooms=[
        ("Galeria", 1, 1, 6, 3, ("wood", (186, 140, 96), (174, 130, 88))),
        ("Joias", 7, 1, 3, 3, ("carpet", (62, 72, 124), (58, 68, 118))),
        ("Reserva", 10, 1, 3, 3, ("concrete", (178, 180, 184), (170, 172, 176))),
        ("Controle", 1, 4, 3, 4, ("tile", (170, 178, 196), (158, 166, 186))),
        ("Hall", 4, 4, 6, 4, ("marble", (240, 236, 228), (224, 218, 208))),
        ("Esculturas", 10, 4, 3, 4, ("marble", (234, 232, 238), (218, 216, 224))),
    ],
    doors=[("x", 6, 8), ("x", 7, 8), ("x", 5, 4), ("x", 8, 4), ("y", 4, 6), ("y", 10, 6), ("x", 11, 4), ("y", 7, 2)],
    decor=[("painting", "x", 2, 1, (70, 130, 200)), ("bigpainting", "x", 3, 1, (220, 150, 70)),
           ("painting", "x", 5, 1, (110, 170, 110)), ("painting", "y", 1, 2, (200, 90, 110)),
           ("painting", "x", 8, 1, (90, 80, 160)), ("window", "y", 1, 5), ("window", "y", 1, 6)],
    decals=[("rug", 5.2, 4.3, 3.6, 3.4, (170, 50, 62))],
    props=[
        ("rope", 2.8, 1.95, 1.4, 0, {}), ("bench", 2.6, 3.1, 1.5, 0.4, {}), ("bench", 5.0, 2.7, 1.2, 0.4, {}),
        ("plant", 6.3, 1.2, 0.4, 0.4, {}), ("statue", 1.3, 3.2, 0.5, 0.5, {}),
        ("display", 8.3, 1.95, 0.7, 0.7, {}), ("display", 7.3, 1.2, 0.55, 0.55, {}), ("display", 9.25, 1.2, 0.55, 0.55, {}),
        ("archive", 10.15, 1.12, 1.3, 0.5, {}), ("archive", 11.55, 1.12, 1.3, 0.5, {}),
        ("flatfile", 10.3, 2.4, 0.9, 0.6, {}), ("crate", 12.2, 1.8, 0.6, 0.55, {}),
        ("monitors", 1.2, 4.2, 2.2, 0.55, {}), ("server", 1.15, 5.4, 0.55, 0.7, {}),
        ("reception", 8.6, 6.6, 1.2, 0.5, {"c": (60, 50, 70), "top": (200, 170, 110)}),
        ("column", 5.6, 7.5, 0, 0, {}), ("column", 8.4, 7.5, 0, 0, {}),
        ("statue", 6.6, 5.0, 0.6, 0.6, {"c": (200, 190, 160)}),
        ("statue", 10.4, 4.4, 0.55, 0.55, {}), ("statue", 12.2, 4.4, 0.55, 0.55, {"c": (170, 150, 120)}),
        ("statue", 12.2, 7.0, 0.55, 0.55, {"c": (150, 160, 180)}),
        ("fountain", 11.8, 9.0, 0, 0, {}),
        ("tree", 0.5, 1.5, 0, 0, {"r": 16}), ("tree", 0.5, 5.2, 0, 0, {"r": 16}), ("tree", 14.4, 2.5, 0, 0, {}),
        ("tree", 14.6, 6.0, 0, 0, {"r": 18}), ("tree", 15.2, 9.0, 0, 0, {"r": 17}),
        ("bench", 2.0, 8.6, 1.2, 0.38, {}), ("bush", 4.6, 8.4, 0, 0, {}), ("bush", 9.5, 8.4, 0, 0, {}),
    ],
    lamps=[(3.2, 9.45), (9.0, 9.45), (13.6, 9.45)],
    npcs=[
        ("guide", [(2.0, 3.75), (6.3, 3.75)]),
        ("visitor", [(4.8, 4.6), (9.3, 4.6), (9.3, 5.9), (4.8, 5.9)]),
        ("operator", [(2.0, 7.2), (3.3, 7.2)]),
        ("visitor", [(10.5, 6.9), (11.6, 7.4), (10.5, 5.2)]),
    ],
    cars=[(10.55, 1), (11.45, -1)],
    measures=[
        M("metal", "Detector de metais", "Pórtico na entrada que identifica objetos metálicos e proibidos.", "metal", C_BLUE),
        M("proximidade", "Sensor de proximidade", "Dispara alerta se alguém ultrapassar a distância segura da obra.", "radar", C_TEAL),
        M("vidro", "Vidro blindado", "Vitrine com vidro laminado resistente a impactos e martelos.", "glass", C_SKY),
        M("gas_supp", "Supressão por gás inerte", "Apaga o fogo sem água: o papel e as telas do acervo não são molhados.", "cylinder", C_ORANGE),
        M("laser", "Barreira laser", "Feixes invisíveis cruzam a claraboia; qualquer interrupção dispara o alarme.", "laser", C_RED),
        M("firewall", "Firewall", "Protege o sistema que controla câmeras e alarmes contra invasões digitais.", "shield", C_PURPLE),
        M("camera", "Câmeras CFTV", "Gravação de todas as salas. Inibe, mas não impede sozinha.", "camera", C_GREEN),
        M("vigilante", "Vigilante", "Segurança fazendo rondas pelas galerias.", "guard", C_GRAY),
    ],
    spots=[
        dict(id="entrada", name="Entrada principal", desc="Recebe centenas de visitantes por dia.",
             pos=(7.0, 7.45), ideal="metal", ok=["vigilante"], threat="smuggler",
             threat_name="Visitante com objeto proibido", path=[(7.0, 11.6)], breach=(6.1, 6.3)),
        dict(id="galeria", name="Galeria de pinturas", desc="Obra mais famosa do museu, ao alcance das mãos.",
             pos=(3.5, 2.45), ideal="proximidade", ok=["camera", "vigilante"], threat="vandal",
             threat_name="Vandalismo contra a obra de arte", path=[(5.9, 11.6), (6.3, 8.6), (6.0, 6.5), (5.5, 4.4), (4.2, 3.0)], breach=(3.5, 1.7)),
        dict(id="joias", name="Vitrine das joias", desc="Coroa de ouro e pedras preciosas.",
             pos=(8.65, 3.2), ideal="vidro", ok=["camera"], threat="thief",
             threat_name="Ladrão de joias", path=[(7.6, 11.6), (7.6, 8.4), (8.1, 6.4), (8.5, 4.4)], breach=(8.65, 2.4)),
        dict(id="reserva", name="Reserva técnica", desc="Documentos e telas raras guardados fora de exposição.",
             pos=(11.7, 3.1), ideal="gas_supp", ok=[], threat="fire",
             threat_name="Incêndio no acervo"),
        dict(id="claraboia", name="Claraboia (teto)", desc="Janela de vidro no teto da sala de esculturas.",
             pos=(12.1, 5.5), z=96, ideal="laser", ok=["camera"], threat="roof", skylight=True,
             threat_name="Ladrão descendo pela claraboia", breach=(11.3, 6.6)),
        dict(id="controle", name="Sala de controle", desc="Sistema que liga câmeras, alarmes e portas.",
             pos=(2.5, 5.9), ideal="firewall", ok=[], threat="virus",
             threat_name="Hacker tentando desligar as câmeras"),
    ],
)

LOC_ORDER = ["casa", "hospital", "industria", "mercado", "museu"]


# Detalhes extras de decoração (luminárias acendem à noite)
LOCATIONS["casa"]["props"] += [("floorlamp", 7.62, 5.35, 0, 0, {}), ("floorlamp", 5.78, 2.42, 0, 0, {}),
                               ("floorlamp", 8.35, 5.35, 0, 0, {}), ("plant", 9.9, 7.35, 0.4, 0.4, {})]
LOCATIONS["hospital"]["props"] += [("floorlamp", 5.6, 7.45, 0, 0, {}), ("plant", 8.5, 4.3, 0.35, 0.35, {})]
LOCATIONS["museu"]["props"] += [("floorlamp", 9.55, 4.4, 0, 0, {}), ("floorlamp", 4.4, 4.4, 0, 0, {})]
LOCATIONS["mercado"]["props"] += [("plant", 1.3, 7.4, 0.4, 0.4, {})]

# Pistas do botão "Dica": orientam sem entregar o nome da medida (a medida certa é destacada na lista)
HINTS = {
    ("casa", "porta"): "A porta da frente é o alvo nº 1 de arrombamento. Procure algo que impeça a abertura sem a senha ou a chave certa.",
    ("casa", "janela"): "Janelas escondidas da rua são a entrada preferida de invasores. O ideal é bloquear a passagem e avisar se alguém forçar.",
    ("casa", "cozinha"): "Gás e fogo começam em silêncio. O melhor é ser avisado logo no início, antes de virar incêndio.",
    ("casa", "garagem"): "Ladrões fogem de quem pode identificá-los. Algo que registre tudo e mande alerta protege o carro.",
    ("casa", "wifi"): "Este risco é digital: nenhuma tranca física para um hacker. A proteção precisa estar na própria rede.",
    ("casa", "quintal"): "A escuridão ajuda quem pula o muro. Iluminar a área quando alguém se aproxima espanta o invasor.",
    ("hospital", "entrada"): "Um hospital recebe muita gente. O essencial é saber quem está entrando: identificação logo na porta.",
    ("hospital", "farmacia"): "Remédios controlados só podem sair com um profissional autorizado. Pense numa tranca que reconhece a pessoa.",
    ("hospital", "ti"): "Ransomware sequestra dados. A defesa é bloquear o ataque e ter cópias de segurança guardadas.",
    ("hospital", "gases"): "Oxigênio alimenta o fogo. Aqui o combate precisa ser automático, mesmo sem ninguém por perto.",
    ("hospital", "bercario"): "No berçário o risco é um bebê sair sem autorização. Existe tecnologia que trava as portas na hora.",
    ("hospital", "estacionamento"): "Ao ar livre, quem vandaliza conta em não ser identificado. Monitorar e gravar inibe e serve de prova.",
    ("industria", "portaria"): "Toda indústria precisa controlar quem entra no pátio. Cadastro e identificação resolvem.",
    ("industria", "producao"): "Acidentes com máquinas se previnem protegendo o trabalhador e usando sensores de parada (NR-12).",
    ("industria", "tanques"): "Gás tóxico é invisível. Você precisa de algo que meça o ar e avise antes do perigo.",
    ("industria", "controle"): "Os computadores que comandam as máquinas são alvo de hackers. A proteção aqui é digital.",
    ("industria", "almox"): "Inflamáveis e fogo são uma combinação perigosa. Combate automático com água logo no início é essencial.",
    ("industria", "doca"): "Roubo de carga acontece rápido. Vigiar e gravar a doca o tempo todo é a melhor defesa.",
    ("mercado", "entrada"): "Produtos saindo sem pagar? Existe um sistema que apita quando a etiqueta passa pela porta.",
    ("mercado", "caixa"): "Num assalto, reagir é perigoso. O certo é pedir ajuda em silêncio, sem o assaltante perceber.",
    ("mercado", "corredor"): "Gôndolas altas criam pontos cegos. É preciso enxergar todos os corredores.",
    ("mercado", "doca"): "A porta dos fundos deve abrir só para funcionários autorizados.",
    ("mercado", "padaria"): "Forno a gás ligado o tempo todo: detecte a fumaça cedo e tenha como apagar o fogo.",
    ("mercado", "pagamentos"): "Golpes nas maquininhas são digitais. Proteja a rede e o computador do caixa.",
    ("museu", "entrada"): "Objetos proibidos precisam ser barrados antes de entrar. Uma revista eletrônica na porta resolve.",
    ("museu", "galeria"): "A obra precisa avisar quando alguém chega perto demais, antes mesmo do toque.",
    ("museu", "joias"): "Ladrões de joias quebram o vidro em segundos. A vitrine precisa resistir ao impacto.",
    ("museu", "reserva"): "Água destrói papel e telas antigas! Procure um jeito de apagar o fogo sem molhar o acervo.",
    ("museu", "claraboia"): "Uma janela no teto é uma entrada esquecida. Feixes invisíveis detectam qualquer passagem.",
    ("museu", "controle"): "Se o sistema das câmeras cair, o museu fica cego. Proteja-o contra invasões digitais.",
}
for _k, _loc in LOCATIONS.items():
    for _sp in _loc["spots"]:
        _sp["hint"] = HINTS.get((_k, _sp["id"]), "Pense em qual tipo de ameaça ataca este ponto.")

FACTS = [
    "Muitos arrombamentos acontecem pela porta da frente: fechaduras melhores fazem diferença.",
    "Senhas longas, como frases, são bem mais difíceis de quebrar do que senhas curtas com símbolos.",
    "Luzes com sensor de presença desestimulam invasões noturnas: ninguém quer ser visto.",
    "Extintores têm classes: água nunca deve ser usada em fogo com eletricidade ou óleo.",
    "Câmeras visíveis inibem crimes; câmeras gravando ajudam a identificar os responsáveis.",
    "Backups guardados fora da rede são uma das melhores defesas contra ransomware.",
    "A NR-12 é a norma brasileira que define proteções obrigatórias em máquinas.",
    "Detectores de fumaça devem ser testados todo mês para garantir que funcionam.",
    "Segurança boa é feita em camadas: uma medida cobre a falha da outra.",
    "Botões de pânico silenciosos pedem ajuda sem que o criminoso perceba.",
    "Museus usam gás inerte para apagar fogo sem danificar papel e telas antigas.",
    "Atualizar o roteador e os aparelhos fecha brechas que hackers conhecem bem.",
]


# ---------------------------------------------------------------------------
# Mundo isométrico
# ---------------------------------------------------------------------------
GROUND_COLORS = {
    "grass": ((116, 188, 96), (142, 208, 112)),
    "road": ((70, 74, 86), (76, 80, 92)),
    "sidewalk": ((214, 214, 220), (202, 202, 210)),
    "asphalt": ((100, 104, 116), (108, 112, 124)),
    "parking": ((88, 92, 104), (94, 98, 110)),
    "concrete": ((186, 186, 192), (176, 176, 184)),
    "path": ((206, 192, 166), (196, 182, 156)),
    "plaza": ((230, 220, 200), (220, 210, 190)),
}
GROUND_Z = {"sidewalk": 2, "plaza": 2, "path": 1}


def gnoise(x, y):
    return clamp(0.5 + 0.22 * math.sin(x * 0.9 + y * 0.35) + 0.18 * math.cos(y * 1.15 - x * 0.45)
                 + 0.1 * math.sin((x + y) * 2.1), 0.0, 1.0)


class Spot:
    def __init__(self, d, idx, world):
        self.idx = idx
        self.d = d
        self.id = d["id"]
        self.name = d["name"]
        self.desc = d.get("desc", "")
        self.x, self.y = d["pos"]
        self.z = d.get("z", 50)
        self.ideal = d["ideal"]
        self.ok = d.get("ok", [])
        self.threat = d["threat"]
        self.threat_name = d["threat_name"]
        self.hint = d.get("hint", "")
        self.path = d.get("path")
        self.breach = d.get("breach")
        self.hop = d.get("hop", False)
        self.skylight = d.get("skylight", False)
        self.fz = world.floor_z(self.x, self.y)
        self.pop = 9.0
        self.hover = 0.0
        self.flash = 0.0
        self.status = None
        self.scorch = 0.0
        self.persist = None

    def floor_pos(self):
        return iso(self.x, self.y, self.fz)

    def badge_pos(self, t):
        bx, by = iso(self.x, self.y, self.fz + self.z)
        return bx, by + math.sin(t * 2.4 + self.idx) * S(3)

    def level(self, mid):
        if mid == self.ideal:
            return 1.0
        if mid in self.ok:
            return 0.5
        return 0.0


class WorldStatic:
    """Parte estática (pré-renderizada) de um local. Construída uma vez e reutilizada."""

    def __init__(self, key):
        loc = LOCATIONS[key]
        self.loc = loc
        self.cells = {}
        for ri, r in enumerate(loc["rooms"]):
            _, x, y, w, d, _f = r
            for cx in range(x, x + w):
                for cy in range(y, y + d):
                    self.cells[(cx, cy)] = ri
        self.ground = {}
        for t, x, y, w, d in loc["ground"]:
            for cx in range(x, x + w):
                for cy in range(y, y + d):
                    self.ground[(cx, cy)] = t
        self.indoor_lamps = []
        rng = random.Random(sum(ord(ch) for ch in loc["name"]))
        props = self.build_props()
        self.base = self.build_base(rng)
        self.bake_shadows(props)
        self.props = topo_sort(props)

    def floor_z(self, x, y):
        c = (int(math.floor(x)), int(math.floor(y)))
        if c in self.cells:
            return FLOOR_Z
        return GROUND_Z.get(self.ground.get(c, "grass"), 0)

    # ---------------- terreno + pisos ----------------
    def build_base(self, rng):
        s = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        off = (0, 0)

        def P(a, b, c=0):
            return _pt(a, b, c, off)

        # sombra suave do diorama flutuando
        bot = iso(GW, GH, 0)[1]
        sh = pygame.Surface((MAP_W, S(180)), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (30, 50, 100, 60), (int(MAP_W * 0.12), S(40), int(MAP_W * 0.76), S(100)))
        s.blit(blur_surface(sh, 10), (0, int(bot - S(70))))
        # laterais da plataforma em camadas (grama, terra, pedra)
        bands = [(0, -4, (96, 164, 84)), (-4, -12, (138, 98, 66)), (-12, -22, (120, 102, 88)), (-22, -32, (96, 82, 74))]
        for z0, z1, c in bands:
            poly(s, [P(0, GH, z0), P(GW, GH, z0), P(GW, GH, z1), P(0, GH, z1)], shade(c, 0.96))
            poly(s, [P(GW, 0, z0), P(GW, GH, z0), P(GW, GH, z1), P(GW, 0, z1)], shade(c, 0.76))
        for i in range(90):
            left = rng.random() < 0.6
            u = rng.random()
            z = rng.uniform(-30, -13)
            p = P(u * GW, GH, z) if left else P(GW, u * GH, z)
            rr = rng.uniform(1.4, 3.6) * K
            base_c = (150, 134, 118) if rng.random() < 0.5 else (104, 92, 82)
            col = shade(base_c, 0.96 if left else 0.78)
            gfx.filled_ellipse(s, p[0], p[1], max(1, int(rr * 1.7)), max(1, int(rr)), col)
        for i in range(40):
            left = rng.random() < 0.6
            u = rng.random()
            p = P(u * GW, GH, -4) if left else P(GW, u * GH, -4)
            ln = rng.uniform(2, 6) * K
            pygame.draw.line(s, (78, 140, 70) if left else (64, 118, 58), p, (p[0], int(p[1] + ln)), max(1, int(K)))
        pygame.draw.aaline(s, (170, 220, 140), P(0, GH, 0), P(GW, GH, 0))
        pygame.draw.aaline(s, (150, 200, 120), P(GW, 0, 0), P(GW, GH, 0))
        # células do terreno (de trás para frente)
        order = sorted(((gx, gy) for gx in range(GW) for gy in range(GH)), key=lambda c: (c[0] + c[1], c[0]))
        for gx, gy in order:
            if (gx, gy) in self.cells:
                continue
            t = self.ground.get((gx, gy), "grass")
            z = GROUND_Z.get(t, 0)
            c1, c2 = GROUND_COLORS.get(t, GROUND_COLORS["grass"])
            if t == "grass":
                col = mix(c1, c2, gnoise(gx, gy))
            elif t in ("sidewalk", "plaza", "concrete"):
                col = c1 if (gx + gy) % 2 == 0 else c2
            else:
                col = mix(c1, c2, rng.random())
            cell = [P(gx, gy, z), P(gx + 1, gy, z), P(gx + 1, gy + 1, z), P(gx, gy + 1, z)]
            poly(s, cell, col)
            if t in ("sidewalk", "plaza"):
                gfx.aapolygon(s, cell, shade(col, 0.88))
                pygame.draw.aaline(s, shade(col, 0.92), P(gx + 0.5, gy, z), P(gx + 0.5, gy + 1, z))
                pygame.draw.aaline(s, shade(col, 0.92), P(gx, gy + 0.5, z), P(gx + 1, gy + 0.5, z))
            elif t == "concrete":
                gfx.aapolygon(s, cell, shade(col, 0.92))
            elif t in ("road", "asphalt", "parking"):
                for _ in range(7):
                    p = P(gx + rng.random(), gy + rng.random(), z)
                    gfx.pixel(s, p[0], p[1], shade(col, rng.choice((0.8, 1.25))))
                if t == "parking":
                    pygame.draw.line(s, (236, 236, 240), P(gx, gy + 0.1, z), P(gx, gy + 0.9, z), max(2, S(2)))
            elif t == "path":
                for _ in range(3):
                    px, py = gx + 0.2 + rng.random() * 0.6, gy + 0.2 + rng.random() * 0.6
                    p = P(px, py, z)
                    gfx.filled_ellipse(s, p[0], p[1], S(7), S(3.5), shade(col, 1.08))
                    gfx.aaellipse(s, p[0], p[1], S(7), S(3.5), shade(col, 0.85))
        # meio-fio das calçadas elevadas
        for gx, gy in order:
            if (gx, gy) in self.cells:
                continue
            t = self.ground.get((gx, gy), "grass")
            z = GROUND_Z.get(t, 0)
            if z <= 0:
                continue
            col = GROUND_COLORS[t][0]
            for nx, ny, face in ((gx, gy + 1, "L"), (gx + 1, gy, "R")):
                if not (0 <= nx < GW and 0 <= ny < GH) or (nx, ny) in self.cells:
                    continue
                nz = GROUND_Z.get(self.ground.get((nx, ny), "grass"), 0)
                if nz >= z:
                    continue
                if face == "L":
                    q = [P(gx, gy + 1, z), P(gx + 1, gy + 1, z), P(gx + 1, gy + 1, nz), P(gx, gy + 1, nz)]
                    poly(s, q, shade(col, 0.78))
                else:
                    q = [P(gx + 1, gy, z), P(gx + 1, gy + 1, z), P(gx + 1, gy + 1, nz), P(gx + 1, gy, nz)]
                    poly(s, q, shade(col, 0.62))
        # detalhes da grama (tufos e flores)
        for gx, gy in order:
            if (gx, gy) in self.cells or self.ground.get((gx, gy), "grass") != "grass":
                continue
            for _ in range(rng.randint(2, 5)):
                p = P(gx + 0.1 + rng.random() * 0.8, gy + 0.1 + rng.random() * 0.8)
                gc = (88, 156, 76) if rng.random() < 0.6 else (164, 220, 128)
                lw = max(1, int(K))
                pygame.draw.line(s, gc, p, (p[0] + S(2), p[1] - S(4)), lw)
                pygame.draw.line(s, gc, p, (p[0] - S(2), p[1] - S(3)), lw)
            if rng.random() < 0.4:
                fc = rng.choice([(255, 255, 255), (255, 222, 90), (255, 150, 182), (196, 166, 255)])
                cx_, cy_ = gx + 0.2 + rng.random() * 0.6, gy + 0.2 + rng.random() * 0.6
                for k in range(rng.randint(1, 3)):
                    p = P(cx_ + rng.uniform(-0.08, 0.08), cy_ + rng.uniform(-0.08, 0.08))
                    gfx.filled_circle(s, p[0], p[1], max(1, S(2)), fc)
        # faixas da rua
        rows = sorted({gy for (gx, gy), t in self.ground.items() if t == "road"})
        if len(rows) >= 2:
            yc = (rows[0] + rows[-1] + 1) / 2.0
            xx = 0.15
            while xx < GW:
                q = [P(xx, yc - 0.035), P(xx + 0.45, yc - 0.035), P(xx + 0.45, yc + 0.035), P(xx, yc + 0.035)]
                poly(s, q, (244, 214, 110))
                xx += 1.0
            for yy in (rows[0] + 0.07, rows[-1] + 1 - 0.07):
                pygame.draw.aaline(s, (206, 208, 214), P(0, yy), P(GW, yy))
        # pisos dos cômodos
        rooms = sorted(self.loc["rooms"], key=lambda r: r[1] + r[2])
        for name, x, y, w, d, fl in rooms:
            kind, c1, c2 = fl
            draw_box(s, x, y, 0, w, d, FLOOR_Z, shade(c1, 0.86), off, top=c1, edge=False, ao=False)
            for cx in range(x, x + w):
                for cy in range(y, y + d):
                    self.draw_floor_cell(s, kind, cx, cy, c1, c2, rng, off)
        # decalques (tapetes, faixas)
        for dec in self.loc.get("decals", []):
            kind, x, y, w, d, col = dec
            z = self.floor_z(x + w / 2, y + d / 2) + 0.2
            q = [P(x, y, z), P(x + w, y, z), P(x + w, y + d, z), P(x, y + d, z)]
            if kind == "rug":
                poly(s, q, shade(col, 0.85))
                m = 0.08
                q2 = [P(x + m, y + m, z), P(x + w - m, y + m, z), P(x + w - m, y + d - m, z), P(x + m, y + d - m, z)]
                poly(s, q2, col)
                m = 0.2
                q3 = [P(x + m, y + m, z), P(x + w - m, y + m, z), P(x + w - m, y + d - m, z), P(x + m, y + d - m, z)]
                gfx.aapolygon(s, q3, lighten(col, 0.4))
                cxr, cyr = x + w / 2, y + d / 2
                dm = [P(cxr, cyr - d * 0.22, z), P(cxr + w * 0.22, cyr, z), P(cxr, cyr + d * 0.22, z), P(cxr - w * 0.22, cyr, z)]
                gfx.aapolygon(s, dm, lighten(col, 0.4))
            elif kind == "line":
                poly(s, q, col)
            elif kind == "hazard":
                poly(s, q, col)
                n = int(w / 0.25)
                for i in range(0, n, 2):
                    qq = [P(x + i * 0.25, y, z), P(x + i * 0.25 + 0.12, y, z), P(x + i * 0.25 + 0.25, y + d, z), P(x + i * 0.25 + 0.13, y + d, z)]
                    poly(s, qq, (40, 40, 44))
            elif kind == "cross":
                poly(s, [P(x + w * 0.38, y, z), P(x + w * 0.62, y, z), P(x + w * 0.62, y + d, z), P(x + w * 0.38, y + d, z)], col)
                poly(s, [P(x, y + d * 0.38, z), P(x + w, y + d * 0.38, z), P(x + w, y + d * 0.62, z), P(x, y + d * 0.62, z)], col)
        return s

    def draw_floor_cell(self, s, kind, cx, cy, c1, c2, rng, off):
        z = FLOOR_Z

        def P(a, b):
            return _pt(a, b, z, off)

        cell = [P(cx, cy), P(cx + 1, cy), P(cx + 1, cy + 1), P(cx, cy + 1)]
        if kind == "tile":
            col = c1 if (cx + cy) % 2 == 0 else c2
            poly(s, cell, col)
            gfx.aapolygon(s, cell, lighten(col, 0.35))
            gfx.filled_polygon(s, [P(cx + 0.08, cy + 0.08), P(cx + 0.45, cy + 0.08), P(cx + 0.08, cy + 0.45)], rgba(lighten(col, 0.5), 60))
        elif kind == "wood":
            for i in range(3):
                col = mix(c1, c2, ((cx * 3 + i + cy * 2) % 3) / 2.0)
                q = [P(cx, cy + i / 3), P(cx + 1, cy + i / 3), P(cx + 1, cy + (i + 1) / 3), P(cx, cy + (i + 1) / 3)]
                poly(s, q, col)
                pygame.draw.aaline(s, shade(c2, 0.84), P(cx, cy + (i + 1) / 3), P(cx + 1, cy + (i + 1) / 3))
                j = (cx * 7 + cy * 3 + i * 5) % 4 / 4.0 + 0.12
                pygame.draw.aaline(s, shade(c2, 0.86), P(cx + j, cy + i / 3), P(cx + j, cy + (i + 1) / 3))
        elif kind == "carpet":
            col = mix(c1, c2, rng.random() * 0.6)
            poly(s, cell, col)
            for _ in range(3):
                p = P(cx + rng.random(), cy + rng.random())
                gfx.pixel(s, p[0], p[1], shade(col, 0.9))
        elif kind == "concrete":
            col = c1 if (cx + cy) % 2 == 0 else c2
            poly(s, cell, col)
            gfx.aapolygon(s, cell, shade(col, 0.92))
            for _ in range(3):
                p = P(cx + rng.random(), cy + rng.random())
                gfx.pixel(s, p[0], p[1], shade(col, 0.85))
        elif kind == "marble":
            col = c1 if (cx + cy) % 2 == 0 else c2
            poly(s, cell, col)
            gfx.aapolygon(s, cell, shade(col, 0.9))
            a = (cx + rng.random() * 0.5, cy + rng.random())
            b = (cx + 0.5 + rng.random() * 0.5, cy + rng.random())
            pygame.draw.aaline(s, shade(col, 0.86), P(*a), P(*b))
            gfx.filled_polygon(s, [P(cx + 0.1, cy + 0.1), P(cx + 0.5, cy + 0.1), P(cx + 0.1, cy + 0.5)], rgba((255, 255, 255), 55))
        elif kind == "lino":
            col = c1 if cy % 2 == 0 else c2
            poly(s, cell, col)
            gfx.aapolygon(s, cell, lighten(col, 0.3))
        else:
            poly(s, cell, c1)

    # ---------------- sombras assadas no chão ----------------
    def bake_shadows(self, props):
        cast = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        ao = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        for p in props:
            if p.h < 3:
                continue
            x0, x1, y0, y1 = p.fp
            z = max(p.z0, self.floor_z((x0 + x1) / 2, (y0 + y1) / 2))
            L = min(1.7, p.h / 46.0)
            if p.tag == "round":
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                r = p.round_r or 0.4
                sx, sy = iso(cx + 0.42 * L, cy + 0.18 * L, z)
                rx, ry = r * HW * 1.5, r * HH * 1.5
                pygame.draw.ellipse(cast, (0, 0, 0, 78), (int(sx - rx), int(sy - ry), max(2, int(2 * rx)), max(2, int(2 * ry))))
                ax, ay = iso(cx, cy, z)
                pygame.draw.ellipse(ao, (0, 0, 0, 110), (int(ax - HW * 0.25), int(ay - HH * 0.25), max(2, int(HW * 0.5)), max(2, int(HH * 0.5))))
                continue
            e = 0.05
            q = [iso(x0 - e, y0 - e, z), iso(x1 + e, y0 - e, z), iso(x1 + e, y1 + e, z), iso(x0 - e, y1 + e, z)]
            pygame.draw.polygon(ao, (0, 0, 0, 115), q)
            dx, dy = 0.5 * L, 0.22 * L
            hexa = [(x0, y0), (x1, y0), (x1 + dx, y0 + dy), (x1 + dx, y1 + dy), (x0 + dx, y1 + dy), (x0, y1)]
            pygame.draw.polygon(cast, (0, 0, 0, 66), [iso(a, b, z) for a, b in hexa])
        cast = blur_surface(cast, max(3.0, 6 * K))
        ao = blur_surface(ao, max(2.0, 3 * K))
        mask = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 0))
        pygame.draw.polygon(mask, (255, 255, 255, 255), [iso(0, 0, 2), iso(GW, 0, 2), iso(GW, GH, 2), iso(0, GH, 2)])
        cast.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        ao.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self.base.blit(cast, (0, 0))
        self.base.blit(ao, (0, 0))

    # ---------------- objetos (paredes + móveis) ----------------
    def build_props(self):
        props = []
        loc = self.loc
        wall = loc["wall"]
        doors = set((d[0], d[1], d[2]) for d in loc.get("doors", []))
        decor = {}
        for dc in loc.get("decor", []):
            decor[(dc[1], dc[2], dc[3])] = dc
        segs = set()
        for _, x, y, w, d, _f in loc["rooms"]:
            for i in range(w):
                segs.add(("x", x + i, y))
                segs.add(("x", x + i, y + d))
            for j in range(d):
                segs.add(("y", x, y + j))
                segs.add(("y", x + w, y + j))
        TALL, MID, LOW = 58, 22, 8
        t = 0.07
        for seg in segs:
            if seg in doors:
                continue
            o, sx, sy = seg
            if o == "x":
                a, b = (sx, sy - 1) in self.cells, (sx, sy) in self.cells
            else:
                a, b = (sx - 1, sy) in self.cells, (sx, sy) in self.cells
            if b and not a:
                hgt = TALL
            elif a and not b:
                hgt = LOW
            else:
                hgt = MID
            topc = shade(wall, 0.62)
            bands = [(0, 5, shade(wall, 0.78)), (5, 6, shade(wall, 0.9))] if hgt == TALL else None
            if o == "x":
                parts = [("box", sx - t, sy - t, 0, 1 + 2 * t, 2 * t, hgt + FLOOR_Z, wall, {"top": topc, "bands": bands})]
                fp = (sx - t, sx + 1 + t, sy - t, sy + t)
            else:
                parts = [("box", sx - t, sy - t, 0, 2 * t, 1 + 2 * t, hgt + FLOOR_Z, wall, {"top": topc, "bands": bands})]
                fp = (sx - t, sx + t, sy - t, sy + 1 + t)
            dc = decor.get(seg)
            if dc and hgt == TALL:
                parts.extend(self.wall_decor(dc, o, sx, sy, t))
            props.append(Prop(parts, fp, outline=False, tag="wall"))
        round_kinds = {"tree": 21, "bush": 12, "plant": 11}
        for p in loc["props"]:
            kind, x, y, w, d = p[:5]
            o = dict(p[5]) if len(p) > 5 else {}
            if kind == "tree" and "pine" not in o:
                o["pine"] = int(x * 7 + y * 13) % 3 == 0
            z = self.floor_z(x + w / 2, y + d / 2)
            parts, fp = furniture(kind, x, y, w, d, o, z)
            seg_kind = kind in ("muro", "fence", "hedge")
            tag = "round" if kind in round_kinds else None
            rr = (o.get("r", round_kinds.get(kind, 12)) / 42.0) if tag else None
            if kind == "floorlamp":
                self.indoor_lamps.append((x, y))
            props.append(Prop(parts, fp, outline=not seg_kind, tag=tag, round_r=rr))
        for lx, ly in self.loc.get("lamps", []):
            parts, fp = furniture("lamp", lx, ly, 0, 0, {}, self.floor_z(lx, ly))
            props.append(Prop(parts, fp))
        return props

    def wall_decor(self, dc, o, sx, sy, t):
        kind = dc[0]
        e = t + 0.01
        z0 = FLOOR_Z

        def quad(a0, a1, h0, h1):
            if o == "x":
                return [(sx + a0, sy + e, z0 + h0), (sx + a1, sy + e, z0 + h0), (sx + a1, sy + e, z0 + h1), (sx + a0, sy + e, z0 + h1)]
            return [(sx + e, sy + a0, z0 + h0), (sx + e, sy + a1, z0 + h0), (sx + e, sy + a1, z0 + h1), (sx + e, sy + a0, z0 + h1)]

        out = []
        if kind == "window":
            out.append(("flat", quad(0.14, 0.86, 17, 49), (250, 250, 252)))
            out.append(("flat", quad(0.2, 0.8, 21, 45), (150, 200, 236)))
            out.append(("flat", quad(0.2, 0.8, 33, 45), (186, 222, 248)))
            out.append(("flat", quad(0.24, 0.36, 36, 44), (230, 245, 255)))
            out.append(("flat", quad(0.485, 0.515, 21, 45), (250, 250, 252)))
            out.append(("flat", quad(0.2, 0.8, 32, 33.5), (250, 250, 252)))
            out.append(("flat", quad(0.1, 0.9, 15, 17), (210, 212, 218)))
        elif kind == "painting":
            col = dc[4] if len(dc) > 4 else (90, 140, 200)
            out.append(("flat", quad(0.2, 0.8, 20, 46), (196, 160, 70)))
            out.append(("flat", quad(0.26, 0.74, 24, 42), lighten(col, 0.35)))
            out.append(("flat", quad(0.26, 0.74, 24, 31), col))
            out.append(("flat", quad(0.45, 0.6, 31, 37), shade(col, 0.7)))
        elif kind == "bigpainting":
            col = dc[4] if len(dc) > 4 else (220, 150, 70)
            out.append(("flat", quad(0.06, 0.94, 14, 52), (222, 182, 70)))
            out.append(("flat", quad(0.12, 0.88, 18, 48), (60, 90, 150)))
            out.append(("flat", quad(0.12, 0.88, 18, 30), shade(col, 0.8)))
            out.append(("flat", quad(0.55, 0.75, 34, 44), (255, 230, 150)))
            out.append(("flat", quad(0.22, 0.42, 26, 38), (40, 60, 40)))
        return out

    def render(self, extra_npcs=None):
        """Composição estática (para a prévia do menu)."""
        s = self.base.copy()
        dyn = extra_npcs or []
        World.render_props(self.props, s, (0, 0), dyn)
        return s


def get_static(key):
    st = _STATIC_WORLDS.get(key)
    if st is None:
        st = WorldStatic(key)
        _STATIC_WORLDS[key] = st
    return st


class World:
    def __init__(self, key):
        st = get_static(key)
        self.static = st
        self.loc = st.loc
        self.cells = st.cells
        self.ground = st.ground
        self.base = st.base
        self.props = st.props
        self.indoor_lamps = st.indoor_lamps
        self.spots = [Spot(s, i, self) for i, s in enumerate(self.loc["spots"])]
        self.npcs = [Walker(self, sty, route) for sty, route in self.loc.get("npcs", [])]
        self.cars = [AmbientCar(self, ly, dr) for ly, dr in self.loc.get("cars", [])]
        self.lamps = self.loc.get("lamps", [])

    def floor_z(self, x, y):
        return self.static.floor_z(x, y)

    @staticmethod
    def render_props(props, surf, off, dyn):
        inserts = {}
        for o in dyn:
            r = o.srect
            fp = o.fp
            idx = 0
            for i, p in enumerate(props):
                if p.rect.colliderect(r) and behind(p.fp, fp):
                    idx = i + 1
            inserts.setdefault(idx, []).append(o)
        for i, p in enumerate(props):
            lst = inserts.get(i)
            if lst:
                for o in sorted(lst, key=lambda q: q.depth):
                    o.draw(surf, off)
            surf.blit(p.surf, (p.pos[0] + off[0], p.pos[1] + off[1]))
        lst = inserts.get(len(props))
        if lst:
            for o in sorted(lst, key=lambda q: q.depth):
                o.draw(surf, off)

    def render_sorted(self, surf, off, dyn):
        World.render_props(self.props, surf, off, dyn)


# ---------------------------------------------------------------------------
# Ameaças
# ---------------------------------------------------------------------------
FAMILY_TEXT = {
    "walker": ("BLOQUEADO!", "INVADIDO!"),
    "fire": ("CONTIDO!", "FORA DE CONTROLE!"),
    "gas": ("DETECTADO!", "VAZAMENTO!"),
    "virus": ("BLOQUEADO!", "SISTEMA INVADIDO!"),
    "accident": ("EVITADO!", "ACIDENTE!"),
    "roof": ("BLOQUEADO!", "INVADIDO!"),
}


def family(kind):
    return kind if kind in ("fire", "gas", "virus", "accident", "roof") else "walker"


class Threat:
    def __init__(self, scene, spot, level, delay):
        self.sc = scene
        self.spot = spot
        self.level = level
        self.kind = spot.threat
        self.fam = family(self.kind)
        self.t = -delay
        self.state = "wait"
        self.st_t = 0.0
        self.alpha = 0.0
        self.done = False
        self.size = 0.0
        self.z = 0.0
        self.facing = 1
        self.moving = False
        self.outcome = None
        self.surf = char_surface()
        self.last_img = None
        self.last_pos = None
        self.style = THREATS.get(self.kind, THREATS["intruder"])
        self.fx_t = 0.0
        sx, sy = spot.x, spot.y
        if self.fam == "walker":
            pts = [tuple(p) for p in (spot.path or [(sx, GH - 0.4)])]
            pts.append((sx, sy))
            self.path = pts
            self.x, self.y = pts[0]
            self.pi = 1
        elif self.fam == "virus":
            self.p0 = (sx - 4.5, sy - 3.5, 240)
            self.x, self.y, self.z = self.p0
        elif self.fam == "roof":
            self.x, self.y, self.z = sx, sy, 250
        else:
            self.x, self.y = sx, sy
        self.fz = scene.world.floor_z(self.x, self.y) if self.fam not in ("virus", "roof") else spot.fz
        self.flee_pts = []

    # --- protocolo de desenho ordenado ---
    @property
    def fp(self):
        return (self.x - 0.2, self.x + 0.2, self.y - 0.2, self.y + 0.2)

    @property
    def depth(self):
        return self.x + self.y

    @property
    def srect(self):
        sx, sy = iso(self.x, self.y, self.fz + self.z)
        return pygame.Rect(int(sx - S(32)), int(sy - S(96)), S(64), S(104))

    @property
    def visible(self):
        return self.state != "wait"

    @property
    def airborne(self):
        return self.state not in ("wait", "gone") and self.fam in ("roof", "virus") and self.z > 12

    def set_state(self, s):
        self.state = s
        self.st_t = 0.0

    def screen_feet(self):
        return iso(self.x, self.y, self.fz + self.z)

    def move_to(self, tx, ty, speed, dt):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d < 1e-6:
            return True
        step = speed * dt
        if abs(dx - dy) > 0.01:
            self.facing = 1 if dx - dy > 0 else -1
        if step >= d:
            self.x, self.y = tx, ty
            return True
        self.x += dx / d * step
        self.y += dy / d * step
        return False

    def update(self, dt):
        self.t += dt
        self.st_t += dt
        self.fx_t += dt
        if self.state == "wait":
            if self.t >= 0:
                self.set_state("enter")
            return
        getattr(self, "_" + self.fam)(dt)

    def resolve(self):
        if self.level >= 1:
            self.outcome = "ok"
        elif self.level > 0:
            self.outcome = "partial"
        else:
            self.outcome = "fail"
        self.sc.on_resolve(self, self.outcome)

    # --- invasores a pe ---
    def _walker(self, dt):
        sc = self.sc
        self.fz = approach(self.fz, sc.world.floor_z(self.x, self.y), dt, 10)
        if self.state == "enter":
            self.alpha = min(1.0, self.alpha + dt * 3)
            self.moving = True
            if self.spot.hop and self.pi == 1:
                self.z = math.sin(math.pi * clamp(self.st_t / 0.55, 0, 1)) * 26
            else:
                self.z = 0
            tx, ty = self.path[self.pi]
            if self.move_to(tx, ty, 1.9, dt):
                self.pi += 1
                if self.pi >= len(self.path):
                    self.z = 0
                    self.set_state("attempt")
                    self.spot.flash = 1.0
        elif self.state == "attempt":
            self.moving = False
            if self.st_t > (1.3 if self.level == 0.5 else 0.9):
                self.resolve()
                if self.outcome == "ok":
                    self.set_state("repel")
                elif self.outcome == "partial":
                    self.set_state("struggle")
                else:
                    self.set_state("breach")
                self.flee_pts = list(reversed(self.path[:-1]))
        elif self.state == "repel":
            px, py = self.path[-2] if len(self.path) >= 2 else (self.x, self.y + 1)
            self.move_to(px, py, 3.2 * (1 - self.st_t / 0.3), dt)
            if self.st_t > 0.3:
                self.set_state("flee")
        elif self.state == "struggle":
            self.moving = False
            if self.st_t > 0.7:
                self.set_state("flee")
        elif self.state == "flee":
            self.moving = True
            spd = 2.7 if self.outcome == "ok" else 1.8
            if self.flee_pts:
                if self.move_to(self.flee_pts[0][0], self.flee_pts[0][1], spd, dt):
                    self.flee_pts.pop(0)
            self.alpha = max(0.0, self.alpha - dt * 0.75)
            if self.alpha <= 0:
                self.done = True
        elif self.state == "breach":
            self.moving = True
            bx, by = self.spot.breach or (self.x, self.y - 1.0)
            self.move_to(bx, by, 1.5, dt)
            if self.st_t > 0.9:
                self.alpha = max(0.0, self.alpha - dt * 0.9)
            if self.alpha <= 0:
                self.done = True

    # --- ladrao pelo teto (claraboia) ---
    def _roof(self, dt):
        if self.state == "enter":
            self.alpha = min(1.0, self.alpha + dt * 3)
            self.z = 250 - (250 - 124) * ease_out_cubic(self.st_t / 1.5)
            if self.st_t > 1.5:
                self.set_state("attempt")
                self.spot.flash = 1.0
        elif self.state == "attempt":
            if self.st_t > (1.3 if self.level == 0.5 else 0.9):
                self.resolve()
                self.set_state({"ok": "climb", "partial": "half", "fail": "drop"}[self.outcome])
        elif self.state == "climb":
            self.z += dt * 160
            self.alpha = max(0.0, self.alpha - dt * 0.8)
            if self.alpha <= 0:
                self.done = True
        elif self.state == "half":
            if self.st_t < 0.6:
                self.z = 124 - 58 * ease_out_cubic(self.st_t / 0.6)
            else:
                self.z += dt * 140
                self.alpha = max(0.0, self.alpha - dt * 0.7)
                if self.alpha <= 0:
                    self.done = True
        elif self.state == "drop":
            self.z = max(0.0, 124 * (1 - ease_in_out(self.st_t / 0.8)))
            if self.st_t > 0.8:
                self.z = 0
                self.set_state("breach")
        elif self.state == "breach":
            self.moving = True
            bx, by = self.spot.breach or (self.x + 0.8, self.y + 0.5)
            self.move_to(bx, by, 1.4, dt)
            if self.st_t > 0.8:
                self.alpha = max(0.0, self.alpha - dt * 0.9)
            if self.alpha <= 0:
                self.done = True

    # --- incendio ---
    def _fire(self, dt):
        sc = self.sc
        fx, fy = self.spot.floor_pos()
        if self.fx_t > 0.06 and self.size > 0.05:
            self.fx_t = 0
            sc.particles.append(Particle(fx + random.uniform(-10, 10) * self.size, fy - 30 * self.size,
                                         random.uniform(-6, 6), random.uniform(-40, -26), random.uniform(0.8, 1.4),
                                         (120, 120, 130), random.uniform(5, 9) * self.size, -6, 0.2))
            if random.random() < 0.5:
                sc.particles.append(Particle(fx + random.uniform(-8, 8) * self.size, fy - 12 * self.size,
                                             random.uniform(-14, 14), random.uniform(-70, -40), random.uniform(0.4, 0.8),
                                             (255, 190, 80), 2, 30))
        if self.state == "enter":
            self.size = min(0.55, self.size + dt * 0.42)
            if self.st_t > 1.4:
                self.set_state("attempt")
                self.spot.flash = 1.0
        elif self.state == "attempt":
            if self.st_t > 0.5:
                self.resolve()
                self.set_state({"ok": "out", "partial": "grow_out", "fail": "burn"}[self.outcome])
        elif self.state in ("out", "grow_out"):
            if self.state == "grow_out" and self.st_t < 0.8:
                self.size = min(0.85, self.size + dt * 0.5)
            else:
                self.spray(dt)
                self.size = max(0.0, self.size - dt * (0.7 if self.state == "out" else 0.5))
                if self.size <= 0:
                    self.spot.scorch = 0.45 if self.state == "out" else 0.8
                    self.done = True
                    self.state = "gone"
        elif self.state == "burn":
            self.size = min(1.6, self.size + dt * 0.6)
            if self.st_t > 1.4:
                self.done = True

    def spray(self, dt):
        bx, by = self.spot.badge_pos(self.sc.t)
        fx, fy = self.spot.floor_pos()
        for _ in range(3):
            tx = fx + random.uniform(-14, 14)
            ty = fy - random.uniform(0, 20)
            vx, vy = (tx - bx) * 2.2, (ty - by) * 2.2
            self.sc.particles.append(Particle(bx, by + 14, vx, vy, 0.45, (170, 220, 255), random.uniform(2, 4), 60))

    # --- vazamento de gas ---
    def _gas(self, dt):
        if self.state == "enter":
            self.size = min(0.6, self.size + dt * 0.45)
            if self.st_t > 1.4:
                self.set_state("attempt")
                self.spot.flash = 1.0
        elif self.state == "attempt":
            if self.st_t > 0.5:
                self.resolve()
                self.set_state({"ok": "out", "partial": "grow_out", "fail": "spread"}[self.outcome])
        elif self.state in ("out", "grow_out"):
            if self.state == "grow_out" and self.st_t < 0.8:
                self.size = min(0.9, self.size + dt * 0.5)
            else:
                self.size = max(0.0, self.size - dt * 0.55)
                if self.size <= 0:
                    self.done = True
                    self.state = "gone"
        elif self.state == "spread":
            self.size = min(1.5, self.size + dt * 0.6)
            if self.st_t > 1.4:
                self.done = True

    # --- ataque digital ---
    def _virus(self, dt):
        sc = self.sc
        sx, sy = self.spot.x, self.spot.y
        if self.state in ("enter", "attempt", "bounce") and self.fx_t > 0.04:
            self.fx_t = 0
            px, py = iso(self.x, self.y, self.fz + self.z)
            sc.particles.append(Particle(px, py, random.uniform(-10, 10), random.uniform(-10, 10), 0.5,
                                         random.choice([(200, 80, 255), (255, 90, 170)]), 3))
        if self.state == "enter":
            self.alpha = min(1.0, self.alpha + dt * 3)
            p = ease_in_out(self.st_t / 1.7)
            x0, y0, z0 = self.p0
            self.x = x0 + (sx - x0) * p
            self.y = y0 + (sy - y0) * p
            self.z = z0 + (46 - z0) * p + math.sin(p * math.pi) * 40
            if self.st_t > 1.7:
                self.set_state("attempt")
                self.spot.flash = 1.0
        elif self.state == "attempt":
            self.z = 46 + math.sin(self.st_t * 10) * 3
            if self.st_t > 0.55:
                self.resolve()
                if self.outcome == "ok":
                    px, py = iso(self.x, self.y, self.fz + self.z)
                    sc.burst(px, py, (200, 90, 255), 26, 160)
                    self.done = True
                    self.state = "gone"
                else:
                    self.set_state("bounce" if self.outcome == "partial" else "dive")
        elif self.state == "bounce":
            self.z = 46 + 50 * math.sin(clamp(self.st_t / 0.6, 0, 1) * math.pi * 0.5)
            self.alpha = max(0.0, self.alpha - dt * 0.9)
            if self.alpha <= 0:
                self.done = True
                self.state = "gone"
        elif self.state == "dive":
            self.z = max(0.0, 46 * (1 - self.st_t / 0.4))
            if self.st_t > 0.4:
                px, py = iso(self.x, self.y, self.fz)
                sc.burst(px, py, (255, 60, 90), 22, 120)
                self.spot.persist = "glitch"
                self.done = True
                self.state = "gone"

    # --- acidente de trabalho ---
    def _accident(self, dt):
        sc = self.sc
        fx, fy = self.spot.floor_pos()
        if self.state in ("enter", "attempt") and self.fx_t > 0.05:
            self.fx_t = 0
            for _ in range(2):
                sc.particles.append(Particle(fx + random.uniform(-14, 14), fy - 22 + random.uniform(-6, 6),
                                             random.uniform(-80, 80), random.uniform(-110, -30), 0.5,
                                             random.choice([(255, 210, 80), (255, 150, 40)]), 2, 260))
        if self.state == "enter":
            self.size = min(1.0, self.size + dt * 0.9)
            if self.st_t > 1.3:
                self.set_state("attempt")
                self.spot.flash = 1.0
        elif self.state == "attempt":
            if self.st_t > 0.45:
                self.resolve()
                self.set_state("fade" if self.outcome != "fail" else "hurt")
        elif self.state == "fade":
            self.size = max(0.0, self.size - dt * (1.1 if self.outcome == "ok" else 0.7))
            if self.size <= 0:
                self.done = True
                self.state = "gone"
        elif self.state == "hurt":
            if self.st_t > 0.6:
                self.spot.persist = "injury"
                self.done = True
                self.state = "gone"

    # --- desenho ---
    def draw(self, surf, off):
        if self.state in ("wait", "gone"):
            return
        fam = self.fam
        t = self.sc.t
        if fam in ("walker", "roof"):
            if self.alpha <= 0.01:
                return
            sx, sy = iso(self.x, self.y, self.fz + self.z)
            wig = math.sin(self.st_t * 40) * S(2) if self.state in ("attempt", "struggle") else 0
            if fam == "roof":
                top_y = iso(self.x, self.y, self.fz + 330)[1]
                pygame.draw.line(surf, (70, 58, 44), (int(sx + off[0]), int(top_y + off[1])),
                                 (int(sx + off[0]), int(sy - S(34) + off[1])), max(2, S(2)))
            if self.z < 6:
                draw_char_shadow(surf, sx + off[0], sy + off[1], 80 * self.alpha)
            self.surf.fill((0, 0, 0, 0))
            arms = self.state in ("attempt", "struggle") or (fam == "roof" and self.state in ("enter", "attempt", "climb", "half"))
            moving = (self.moving and fam == "walker") or self.state == "breach"
            draw_person(self.surf, S(CHAR_FEET[0]), S(CHAR_FEET[1]), self.style, self.t, moving, arms_up=arms)
            img = add_outline(self.surf, color=(60, 10, 18), alpha=210)
            if self.facing < 0:
                img = pygame.transform.flip(img, True, False)
            if self.alpha < 1:
                img.set_alpha(int(255 * self.alpha))
            pos = (int(sx - S(CHAR_FEET[0]) + off[0] + wig), int(sy - S(CHAR_FEET[1]) + off[1]))
            surf.blit(img, pos)
            self.last_img, self.last_pos = img, pos
        elif fam == "fire":
            fx, fy = iso(self.x, self.y, self.fz)
            draw_fire(surf, fx + off[0], fy + off[1], self.size, t)
        elif fam == "gas":
            fx, fy = iso(self.x, self.y, self.fz)
            draw_gas(surf, fx + off[0], fy + off[1], self.size, t)
        elif fam == "virus":
            px, py = iso(self.x, self.y, self.fz + self.z)
            draw_virus(surf, px + off[0], py + off[1], t, 1.0, int(255 * self.alpha))
        elif fam == "accident":
            fx, fy = iso(self.x, self.y, self.fz)
            k = ease_out_back(self.size) if self.state == "enter" else self.size
            if k > 0.05:
                col = (255, 200, 40)
                if self.outcome == "ok":
                    col = GREEN
                elif self.outcome == "partial":
                    col = AMBER
                elif self.outcome == "fail":
                    col = RED
                sz = max(4, int(S(40) * k))
                ic = pygame.transform.smoothscale(icon("warning", 40, col), (sz, sz))
                surf.blit(ic, ic.get_rect(center=(int(fx + off[0]), int(fy - S(36) + off[1] + math.sin(t * 6) * S(2)))))

    def draw_overlay(self, surf, off):
        """Silhueta (visível mesmo atrás de paredes) + marcador de perigo."""
        if self.state in ("wait", "gone"):
            return
        if self.fam in ("walker", "roof") and self.last_img is not None and self.alpha > 0.05:
            ghost = self.last_img.copy()
            ghost.set_alpha(int(85 * self.alpha))
            surf.blit(ghost, self.last_pos)
            if self.state in ("enter", "attempt"):
                sx, sy = iso(self.x, self.y, self.fz + self.z)
                cx, cy = int(sx + off[0]), int(sy - S(78) + off[1] + math.sin(self.sc.t * 8) * S(2))
                a, b = S(9), S(8)
                gfx.filled_trigon(surf, cx - a, cy + b - S(1), cx + a, cy + b - S(1), cx, cy - b - S(2), RED)
                gfx.aatrigon(surf, cx - a, cy + b - S(1), cx + a, cy + b - S(1), cx, cy - b - S(2), RED)
                draw_text(surf, "!", 13, (255, 255, 255), (cx, cy + S(2)), bold=True, anchor="center")


# ---------------------------------------------------------------------------
# Widgets de interface
# ---------------------------------------------------------------------------
_MOUSE_OFF = [0, 0, 1.0]     # deslocamento e escala da imagem do jogo dentro da tela
HINTS_PER_GAME = 3


def screen_to_canvas(p):
    return (int((p[0] - _MOUSE_OFF[0]) / _MOUSE_OFF[2]), int((p[1] - _MOUSE_OFF[1]) / _MOUSE_OFF[2]))


def mouse_pos():
    return screen_to_canvas(pygame.mouse.get_pos())


def layout_blocks(specs, width):
    """specs: (texto, tamanho, cor, negrito, espaço_antes). Quebra linhas para caber em `width` px."""
    laid, total = [], 0
    for txt, size, color, bold, gap in specs:
        lines = wrap(txt, size, width, bold) or [""]
        lh = font(size, bold).get_height()
        laid.append((lines, size, color, bold, S(gap), lh))
        total += S(gap) + lh * len(lines)
    return laid, total


def draw_blocks(surf, x, y, laid, alpha=255):
    for lines, size, color, bold, gap, lh in laid:
        y += gap
        for ln in lines:
            draw_text(surf, ln, size, color, (x, y), bold=bold, alpha=alpha)
            y += lh
    return y


def text_box(surf, anchor_xy, width, specs, accent=None, alpha=255, where="above", bounds=None, border=(58, 70, 116)):
    """Caixa de texto que sempre cabe no conteúdo e dentro de `bounds`."""
    pad = S(14)
    laid, th = layout_blocks(specs, width - 2 * pad)
    box = pygame.Rect(0, 0, width, th + 2 * pad)
    ax, ay = anchor_xy
    if where == "above":
        box.midbottom = (int(ax), int(ay))
    elif where == "right":
        box.midleft = (int(ax), int(ay))
    elif where == "left":
        box.midright = (int(ax), int(ay))
    else:
        box.midtop = (int(ax), int(ay))
    if bounds is not None:
        box.clamp_ip(bounds)
    draw_panel(surf, box, (16, 22, 44), radius=S(12), shadow=True, alpha=int(245 * alpha / 255), border=border, top=(28, 36, 66))
    if accent:
        pygame.draw.rect(surf, accent, (box.x, box.y + S(12), S(4), max(S(4), box.h - S(24))), border_radius=S(2))
    draw_blocks(surf, box.x + pad + (S(4) if accent else 0), box.y + pad - S(2), laid, alpha)
    return box


def R(x, y, w, h):
    """Retângulo em unidades de projeto -> pixels de tela."""
    return pygame.Rect(S(x), S(y), S(w), S(h))


class Button:
    def __init__(self, rect, text, color=ACCENT, icon_kind=None, size=17, text_color=(255, 255, 255), radius=None):
        self.rect = R(*rect)
        self.text = text
        self.color = color
        self.icon_kind = icon_kind
        self.size = size
        self.text_color = text_color
        self.hover = 0.0
        self.press = 0.0
        self.shake = 0.0
        self.enabled = True
        self.radius = S(radius) if radius is not None else self.rect.h // 2

    def update(self, dt, mouse):
        hov = self.rect.collidepoint(mouse) and self.enabled
        self.hover = approach(self.hover, 1.0 if hov else 0.0, dt, 14)
        self.press = approach(self.press, 0.0, dt, 9)
        self.shake = max(0.0, self.shake - dt * 2.5)

    def hit(self, pos):
        if self.rect.collidepoint(pos):
            if self.enabled:
                self.press = 1.0
                return True
            self.shake = 1.0
        return False

    def draw(self, surf, alpha=255):
        dx = math.sin(self.shake * 30) * S(6) * self.shake
        r = self.rect.move(int(dx), int(-S(2) * self.hover + S(2) * self.press))
        col = lighten(self.color, 0.1 * self.hover) if self.enabled else (78, 86, 112)
        draw_panel(surf, r, shade(col, 0.88), radius=self.radius, shadow=True,
                   shadow_alpha=int(60 + 70 * self.hover) if self.enabled else 30, alpha=alpha, top=lighten(col, 0.16))
        if self.enabled:
            inset = max(self.radius * 0.7, S(6))
            pygame.draw.line(surf, lighten(col, 0.5), (int(r.x + inset), r.y + max(1, S(1))), (int(r.right - inset), r.y + max(1, S(1))), max(1, S(1)))
        tc = self.text_color if self.enabled else (164, 172, 196)
        iw, ic = 0, None
        if self.icon_kind:
            ic = icon(self.icon_kind, self.size, tc)
            iw = ic.get_width() + (S(9) if self.text else 0)
        if self.text:
            txt, tsz = fit_text(self.text, self.size, r.w - S(26) - iw, True, 10)
            ts = text_surf(txt, tsz, tc, True)
        else:
            ts = None
        tw = ts.get_width() if ts else 0
        x0 = r.centerx - (tw + iw) // 2
        if ic:
            surf.blit(ic, (x0, r.centery - ic.get_height() // 2))
        if ts:
            surf.blit(ts, (x0 + iw, r.centery - ts.get_height() // 2))


def draw_status_icon(surf, cx, cy, status, r):
    col = {"ok": GREEN, "partial": AMBER, "fail": RED}.get(status, MUTED)
    kind = {"ok": "check", "partial": "bang", "fail": "cross"}.get(status, "bang")
    gfx.filled_circle(surf, int(cx), int(cy), int(r), col)
    gfx.aacircle(surf, int(cx), int(cy), int(r), shade(col, 0.85))
    ic = icon(kind, max(6, r * 1.15 / K))
    surf.blit(ic, ic.get_rect(center=(int(cx), int(cy))))


def draw_logo(surf, cx, cy, scale=1.0, t=0.0):
    sc = scale * K
    blit_add_glow(surf, cx, cy, int(70 * sc), (40, 70, 130))
    pts = [(0, -38), (32, -26), (30, 2), (0, 38), (-30, 2), (-32, -26)]
    P = [(int(cx + a * sc), int(cy + b * sc)) for a, b in pts]
    poly(surf, P, (58, 126, 236))
    P2 = [(int(cx + a * sc), int(cy + b * sc)) for a, b in [(0, -38), (32, -26), (30, 2), (0, 38)]]
    poly(surf, P2, (92, 172, 255))
    P3 = [(int(cx + a * sc), int(cy + b * sc)) for a, b in [(0, -32), (-26, -22), (-24, 0), (0, 31)]]
    pygame.draw.aalines(surf, (150, 205, 255), False, P3)
    ic = icon("lock", 34 * scale)
    surf.blit(ic, ic.get_rect(center=(cx, cy + int(2 * sc))))


def icon_tile(kind, color, size, radius=11, dim=False):
    """Ícone branco sobre um quadrado arredondado com degradê (cacheado)."""
    key = ("tile", kind, color, size, radius, dim)
    s = _GRAD_CACHE.get(key)
    if s is None:
        col = mix(color, (84, 90, 112), 0.55) if dim else color
        px = S(size)
        s = grad_rect(px, px, lighten(col, 0.22), shade(col, 0.78), S(radius)).copy()
        pygame.draw.line(s, rgba(lighten(col, 0.55), 200), (S(radius) // 2 + 1, max(1, S(1))), (px - S(radius) // 2 - 1, max(1, S(1))), max(1, S(1)))
        ic = icon(kind, size * 0.6)
        if dim:
            ic = ic.copy()
            ic.set_alpha(170)
        s.blit(ic, ic.get_rect(center=(px // 2, px // 2)))
        _GRAD_CACHE[key] = s
    return s


def pill(surf, rect, color, alpha=255, border=None):
    draw_panel(surf, rect, color, radius=rect.h // 2, shadow=False, alpha=alpha, border=border)


THREAT_INFO = {
    "thief": ("Ladrão", (255, 122, 122)), "intruder": ("Invasor", (255, 152, 110)), "vandal": ("Vândalo", (255, 172, 80)),
    "robber": ("Assalto", (255, 100, 122)), "shoplifter": ("Furto", (255, 192, 100)), "smuggler": ("Objeto proibido", (240, 162, 120)),
    "roof": ("Ladrão pelo teto", (255, 120, 152)), "fire": ("Incêndio", (255, 140, 60)), "gas": ("Gás tóxico", (130, 222, 100)),
    "virus": ("Ataque hacker", (200, 122, 255)), "accident": ("Acidente de trabalho", (255, 212, 80)),
}
PREVIEW_BOX = (600, 410)


def get_preview(key):
    p = _PREVIEWS.get(key)
    if p is None:
        st = get_static(key)
        npcs = []
        for sty, route in st.loc.get("npcs", []):
            w_ = Walker(st, sty, route)
            w_.moving = False
            w_.t = 0.0
            npcs.append(w_)
        full = st.render(npcs)
        br = full.get_bounding_rect(min_alpha=40)
        img = pygame.Surface((max(1, br.w), max(1, br.h)), pygame.SRCALPHA)
        img.blit(full, (0, 0), br)
        bw, bh = S(PREVIEW_BOX[0]), S(PREVIEW_BOX[1])
        k = min(bw / img.get_width(), bh / img.get_height())
        p = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k))))
        _PREVIEWS[key] = p
    return p


def make_vignette(size, strength=80, color=(8, 10, 30)):
    sw, sh = 64, 36
    small = pygame.Surface((sw, sh), pygame.SRCALPHA)
    for y in range(sh):
        for x in range(sw):
            dx = (x + 0.5) / sw * 2 - 1
            dy = (y + 0.5) / sh * 2 - 1
            d = min(1.0, math.sqrt(dx * dx * 0.8 + dy * dy * 0.9) / 1.15)
            small.set_at((x, y), (color[0], color[1], color[2], int(strength * d ** 2.4)))
    return pygame.transform.smoothscale(small, (max(1, size[0]), max(1, size[1])))


# ---------------------------------------------------------------------------
# Cenas
# ---------------------------------------------------------------------------
class Scene:
    def __init__(self, game):
        self.game = game
        self.t = 0.0

    def handle(self, e):
        pass

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        pass


# ------------------------------ CARREGAMENTO ------------------------------
class LoadingScene(Scene):
    def __init__(self, game, next_factory):
        super().__init__(game)
        self.next = next_factory
        self.todo = [("w", k) for k in LOC_ORDER] + [("p", k) for k in LOC_ORDER]
        self.total = len(self.todo)
        self.done = 0
        self.started = False
        self.bg = vgradient(W, H, (13, 17, 40), (32, 24, 66), mid=(20, 22, 52))
        self.fact = random.choice(FACTS)

    def update(self, dt):
        super().update(dt)
        if self.t < 0.12:
            return
        if self.todo:
            kind, key = self.todo.pop(0)
            if kind == "w":
                get_static(key)
            else:
                get_preview(key)
            self.done += 1
        elif not self.started:
            self.started = True
            self.game.switch(self.next)

    def draw(self, surf):
        surf.blit(self.bg, (0, 0))
        cy = H // 2
        draw_logo(surf, W // 2, cy - S(80), 1.3, self.t)
        draw_text(surf, "GUARDIÃO", 42, TEXT, (W // 2, cy + S(4)), bold=True, anchor="center")
        draw_text(surf, "Preparando os cenários...", 16, MUTED, (W // 2, cy + S(46)), anchor="center")
        bar = pygame.Rect(0, 0, S(380), S(10))
        bar.center = (W // 2, cy + S(84))
        pygame.draw.rect(surf, (36, 44, 78), bar, border_radius=bar.h // 2)
        fr = bar.copy()
        fr.w = max(bar.h, int(bar.w * self.done / max(1, self.total)))
        pygame.draw.rect(surf, ACCENT, fr, border_radius=bar.h // 2)
        laid, th = layout_blocks([("VOCÊ SABIA?", 13, (150, 182, 246), True, 0), (self.fact, 16, MUTED, False, 6)], S(640))
        y = H - S(70) - th
        for lines, size, color, bold, gap, lh in laid:
            y += gap
            for ln in lines:
                draw_text(surf, ln, size, color, (W // 2, y), bold=bold, anchor="midtop")
                y += lh


# --------------------------------- MENU -----------------------------------
class MenuScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.bg = vgradient(W, H, (13, 17, 40), (32, 24, 66), mid=(20, 22, 52))
        self.name = game.player
        self.sel = game.loc_key
        self.rows = [R(56, 316 + i * 62, 500, 54) for i in range(len(LOC_ORDER))]
        self.row_h = [0.0] * len(LOC_ORDER)
        self.row_s = [0.0] * len(LOC_ORDER)
        self.input_rect = R(56, 222, 500, 54)
        self.btn = Button((56, 632, 336, 56), "Começar missão", GREEN, "play", 19, radius=16)
        self.btn_fs = Button((404, 632, 152, 56), "Tela cheia", PANEL_3, "expand", 15, radius=16)
        self.panel = R(600, 34, 644, 652)
        self.hint = ""
        self.hint_t = 0.0
        self.cur_key = self.sel or LOC_ORDER[0]
        self.prev_key = None
        self.fade_t = 1.0
        rng = random.Random(7)
        self.floaters = [dict(x=rng.uniform(0, W), y=rng.uniform(0, H), s=rng.uniform(16, 56) * K, v=rng.uniform(8, 24) * K,
                              a=rng.uniform(16, 42), c=rng.choice([(86, 168, 255), (170, 120, 255), (80, 220, 170), (255, 170, 90)]),
                              ph=rng.uniform(0, 6)) for _ in range(20)]
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    def valid(self):
        return bool(self.name.strip()) and self.sel is not None

    def try_start(self):
        if not self.name.strip():
            self.hint = "Digite seu nome para começar."
            self.hint_t = 2.5
            self.btn.shake = 1.0
            return
        if self.sel is None:
            self.hint = "Escolha sua área de atuação."
            self.hint_t = 2.5
            self.btn.shake = 1.0
            return
        self.game.player = self.name.strip()
        self.game.loc_key = self.sel
        key = self.sel
        self.game.switch(lambda: PlayScene(self.game, key))

    def handle(self, e):
        if e.type == pygame.TEXTINPUT:
            for ch in e.text:
                if (ch.isalnum() or ch in " -._'") and len(self.name) < 16:
                    if ch == " " and (not self.name or self.name.endswith(" ")):
                        continue
                    self.name += ch
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.try_start()
            elif e.key == pygame.K_ESCAPE:
                self.game.quit()
            elif e.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                i = LOC_ORDER.index(self.sel) if self.sel in LOC_ORDER else -1
                i = (i + (1 if e.key in (pygame.K_DOWN, pygame.K_RIGHT) else -1)) % len(LOC_ORDER)
                self.sel = LOC_ORDER[i]
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.rows):
                if r.collidepoint(e.pos):
                    self.sel = LOC_ORDER[i]
                    self.row_s[i] = 1.25
                    return
            if self.btn.rect.collidepoint(e.pos):
                self.btn.press = 1.0
                self.try_start()
            elif self.btn_fs.hit(e.pos):
                self.game.toggle_fullscreen()

    def target_key(self, mouse):
        for i, r in enumerate(self.rows):
            if r.collidepoint(mouse):
                return LOC_ORDER[i]
        if self.sel:
            return self.sel
        return LOC_ORDER[int(self.t / 4.0) % len(LOC_ORDER)]

    def update(self, dt):
        super().update(dt)
        mouse = mouse_pos()
        self.btn.color = GREEN if self.valid() else (82, 96, 134)
        self.btn.update(dt, mouse)
        self.btn_fs.text = "Janela" if self.game.fullscreen else "Tela cheia"
        self.btn_fs.icon_kind = "compress" if self.game.fullscreen else "expand"
        self.btn_fs.update(dt, mouse)
        for i, r in enumerate(self.rows):
            self.row_h[i] = approach(self.row_h[i], 1.0 if r.collidepoint(mouse) else 0.0, dt, 12)
            if self.row_s[i] > 1.0:
                self.row_s[i] = max(1.0, self.row_s[i] - dt * 2.2)
            else:
                self.row_s[i] = approach(self.row_s[i], 1.0 if self.sel == LOC_ORDER[i] else 0.0, dt, 10)
        tk = self.target_key(mouse)
        if tk != self.cur_key:
            self.prev_key, self.cur_key = self.cur_key, tk
            self.fade_t = 0.0
        self.fade_t = min(1.0, self.fade_t + dt / 0.35)
        self.hint_t = max(0.0, self.hint_t - dt)
        for f in self.floaters:
            f["y"] -= f["v"] * dt
            if f["y"] < -S(80):
                f["y"] = H + S(80)
                f["x"] = random.uniform(0, W)

    def draw(self, surf):
        surf.blit(self.bg, (0, 0))
        t = self.t
        col = LOCATIONS[self.cur_key]["color"]
        gl = glow_surf(S(380), col, 0.16)
        surf.blit(gl, gl.get_rect(center=self.panel.center))
        for f in self.floaters:
            x = f["x"] + math.sin(t * 0.5 + f["ph"]) * S(20)
            y = f["y"]
            sz = f["s"]
            pts = [(int(x), int(y - sz / 2)), (int(x + sz), int(y)), (int(x), int(y + sz / 2)), (int(x - sz), int(y))]
            gfx.filled_polygon(surf, pts, rgba(f["c"], f["a"] * 0.35))
            gfx.aapolygon(surf, pts, rgba(f["c"], f["a"]))
        # título
        ty = S(84) + math.sin(t * 1.6) * S(3)
        draw_logo(surf, S(92), int(ty), 0.95, t)
        draw_text(surf, "GUARDIÃO", 52, (255, 255, 255), (S(140), ty - S(8)), bold=True, anchor="midleft", shadow=(8, 10, 26))
        draw_text(surf, "MISSÃO SEGURANÇA", 15, (130, 192, 255), (S(143), ty + S(30)), bold=True, anchor="midleft")
        for i, ln in enumerate(wrap("Escolha as medidas certas e enfrente as ameaças da noite.", 16, S(500))):
            draw_text(surf, ln, 16, MUTED, (S(56), S(146) + i * S(22)))
        # nome
        ir = self.input_rect
        draw_text(surf, "Seu nome", 15, (210, 220, 244), (ir.x + S(2), ir.y - S(25)), bold=True)
        draw_panel(surf, ir, (26, 34, 64), radius=S(14), shadow=True, shadow_alpha=80, top=(34, 44, 80))
        glow = 0.6 + 0.4 * math.sin(t * 3)
        pygame.draw.rect(surf, mix((60, 80, 140), ACCENT, glow), ir, max(2, S(2)), border_radius=S(14))
        pi = icon("person", 22, (140, 160, 210))
        surf.blit(pi, (ir.x + S(16), ir.centery - pi.get_height() // 2))
        if self.name:
            ts = text_surf(self.name, 22, TEXT, True)
            surf.blit(ts, (ir.x + S(50), ir.centery - ts.get_height() // 2))
            cx = ir.x + S(52) + ts.get_width()
        else:
            ts = text_surf("Digite seu nome...", 20, (122, 132, 170))
            surf.blit(ts, (ir.x + S(50), ir.centery - ts.get_height() // 2))
            cx = ir.x + S(50)
        if int(t * 2) % 2 == 0:
            pygame.draw.line(surf, ACCENT, (cx + S(2), ir.centery - S(13)), (cx + S(2), ir.centery + S(13)), max(2, S(2)))
        # lista de locais
        draw_text(surf, "Escolha sua área de atuação", 15, (210, 220, 244), (S(58), S(291)), bold=True)
        for i, key in enumerate(LOC_ORDER):
            self.draw_row(surf, i, key)
        self.btn.draw(surf)
        self.btn_fs.draw(surf)
        if self.hint_t > 0:
            a = int(255 * min(1.0, self.hint_t * 2))
            txt, sz = fit_text(self.hint, 15, S(500), True, 11)
            draw_text(surf, txt, sz, (255, 196, 126), (S(306), S(704)), bold=True, anchor="center", alpha=a)
        else:
            txt, sz = fit_text("Enter começa  •  setas trocam o local  •  F11 tela cheia", 13, S(500), False, 10)
            draw_text(surf, txt, sz, SUBTLE, (S(306), S(704)), anchor="center")
        self.draw_preview_panel(surf)

    def draw_row(self, surf, i, key):
        loc = LOCATIONS[key]
        r0 = self.rows[i]
        h = self.row_h[i]
        s = self.row_s[i]
        sel = self.sel == key
        col = loc["color"]
        r = r0.move(int(S(8) * h), 0)
        base = mix((30, 38, 68), (44, 56, 96), h * 0.6)
        if sel:
            base = mix(base, col, 0.16)
            gl = glow_surf(S(90), col, 0.25)
            surf.blit(pygame.transform.smoothscale(gl, (r.w + S(40), r.h + S(50))), (r.x - S(20), r.y - S(25)))
        draw_panel(surf, r, base, radius=S(14), shadow=h > 0.05 or sel, shadow_alpha=int(60 + 60 * h), top=lighten(base, 0.07))
        if sel:
            pygame.draw.rect(surf, col, r, max(2, S(2)), border_radius=S(14))
        elif h > 0.05:
            pygame.draw.rect(surf, mix(base, col, 0.6 * h), r, max(1, S(1)), border_radius=S(14))
        tile = icon_tile(loc["icon"], col, 40, 11)
        pop = 1.0 + 0.12 * max(0.0, s - 1.0)
        if pop > 1.01:
            tile = pygame.transform.smoothscale(tile, (int(tile.get_width() * pop), int(tile.get_height() * pop)))
        surf.blit(tile, tile.get_rect(center=(r.x + S(28), r.centery)))
        avail = r.w - S(60) - S(52)
        nm, nsz = fit_text(loc["name"], 19, avail, True, 13)
        draw_text(surf, nm, nsz, TEXT, (r.x + S(60), r.y + S(7)), bold=True)
        tg, tsz = fit_text(loc["tagline"], 13, avail, False, 11)
        draw_text(surf, tg, tsz, MUTED, (r.x + S(61), r.y + S(31)))
        if sel:
            gfx.filled_circle(surf, r.right - S(26), r.centery, S(13), GREEN)
            gfx.aacircle(surf, r.right - S(26), r.centery, S(13), shade(GREEN, 0.8))
            ci = icon("check", 15)
            surf.blit(ci, ci.get_rect(center=(r.right - S(26), r.centery)))
        else:
            ic = icon("play", 12, mix(SUBTLE, TEXT, h))
            surf.blit(ic, ic.get_rect(center=(r.right - S(24) + int(S(3) * h), r.centery)))

    def draw_preview_panel(self, surf):
        pr = self.panel
        draw_panel(surf, pr, (18, 24, 48), radius=S(24), shadow=True, shadow_alpha=130, border=(54, 66, 112), alpha=235, top=(30, 38, 74))
        p = ease_out_cubic(self.fade_t)
        prev_clip = surf.get_clip()
        surf.set_clip(pr.inflate(-S(4), -S(4)))
        if self.prev_key and p < 1:
            self.draw_loc_info(surf, self.prev_key, 1 - p, -S(10) * p)
        self.draw_loc_info(surf, self.cur_key, p, S(14) * (1 - p))
        surf.set_clip(prev_clip)

    def draw_loc_info(self, surf, key, a, dy):
        if a <= 0.01:
            return
        loc = LOCATIONS[key]
        pr = self.panel
        al = int(255 * a)
        col = loc["color"]
        dy = int(dy)
        tile = icon_tile(loc["icon"], col, 54, 15)
        if al < 255:
            tile = tile.copy()
            tile.set_alpha(al)
        surf.blit(tile, (pr.x + S(26), pr.y + S(24) + dy))
        chips = ["%d pontos de risco" % len(loc["spots"]), "%d medidas" % len(loc["measures"])]
        x = pr.right - S(24)
        for ch in reversed(chips):
            tw = font(13, True).size(ch)[0]
            rr = pygame.Rect(0, 0, tw + S(26), S(28))
            rr.topright = (x, pr.y + S(30) + dy)
            pill(surf, rr, (38, 48, 84), al, border=(64, 78, 126))
            draw_text(surf, ch, 13, TEXT, rr.center, bold=True, anchor="center", alpha=al)
            x = rr.x - S(8)
        avail = x - (pr.x + S(94)) - S(8)
        nm, nsz = fit_text(loc["name"], 30, avail, True, 18)
        draw_text(surf, nm, nsz, TEXT, (pr.x + S(94), pr.y + S(22) + dy), bold=True, alpha=al)
        tg, tsz = fit_text(loc["tagline"], 15, avail, False, 11)
        draw_text(surf, tg, tsz, MUTED, (pr.x + S(95), pr.y + S(60) + dy), alpha=al)
        img = get_preview(key)
        cx = pr.centerx
        cy = pr.y + S(108) + S(PREVIEW_BOX[1]) // 2 + dy + int(math.sin(self.t * 1.2) * S(5))
        gl = glow_surf(S(250), col, 0.22)
        if al < 255:
            gl = gl.copy()
            gl.set_alpha(al)
        surf.blit(gl, gl.get_rect(center=(cx, cy)))
        if al < 255:
            img = img.copy()
            img.set_alpha(al)
        surf.blit(img, img.get_rect(center=(cx, cy)))
        # ameaças do local
        draw_text(surf, "AMEAÇAS QUE VOCÊ VAI ENFRENTAR", 13, (150, 178, 236), (pr.x + S(28), pr.bottom - S(106) + dy), bold=True, alpha=al)
        seen, labels = set(), []
        for sp in loc["spots"]:
            lab, tcol = THREAT_INFO.get(sp["threat"], ("Ameaça", RED))
            if lab not in seen:
                seen.add(lab)
                labels.append((lab, tcol))
        x, y = pr.x + S(28), pr.bottom - S(80) + dy
        for lab, tcol in labels:
            lab = ellipsize(lab, 13, pr.w - S(90), True)
            tw = font(13, True).size(lab)[0]
            w = tw + S(34)
            if x + w > pr.right - S(24):
                x = pr.x + S(28)
                y += S(36)
                if y + S(30) > pr.bottom - S(6):
                    break
            rr = pygame.Rect(x, y, w, S(30))
            pill(surf, rr, (36, 44, 80), al, border=(62, 76, 124))
            gfx.filled_circle(surf, rr.x + S(15), rr.centery, S(5), rgba(tcol, al))
            draw_text(surf, lab, 13, TEXT, (rr.x + S(26), rr.centery), bold=True, anchor="midleft", alpha=al)
            x += w + S(8)


# --------------------------------- JOGO -----------------------------------
class PlayScene(Scene):
    def __init__(self, game, key, placements=None, hints_left=HINTS_PER_GAME):
        super().__init__(game)
        self.key = key
        self.loc = LOCATIONS[key]
        self.world = World(key)
        self.measures = self.loc["measures"]
        self.mby = {m["id"]: m for m in self.measures}
        self.spots = self.world.spots
        self.place = dict(placements or {})
        self.phase = "build"
        self.bg_day = self.make_sky(True)
        self.bg_night = self.make_sky(False)
        self.vignette = make_vignette(MAP_AREA.size, 75)
        self.top_bg = vgradient(W, TOP_H, (24, 30, 58), (13, 16, 32))
        self.side_bg = vgradient(SIDE_W, H - TOP_H, (26, 32, 60), (15, 19, 38))
        self.red_surf = pygame.Surface(MAP_AREA.size)
        self.red_surf.fill((200, 20, 40))
        cloud = self.make_cloud()
        self.clouds = []
        for _ in range(5):
            sc = random.uniform(0.7, 1.4)
            self.clouds.append(dict(x=random.uniform(0, MAP_AREA.w), y=random.uniform(S(30), S(520)), v=random.uniform(6, 14) * K,
                                    img=pygame.transform.smoothscale(cloud, (int(cloud.get_width() * sc), int(cloud.get_height() * sc)))))
        self.birds = []
        self.bird_t = 2.0
        self.stars = [(random.uniform(0, MAP_AREA.w), random.uniform(0, MAP_AREA.h * 0.8), random.uniform(0, 6.28)) for _ in range(26)]
        self.cards = [R(954, 118 + i * 65, 312, 59) for i in range(len(self.measures))]
        self.card_h = [0.0] * len(self.measures)
        self.btn_start = Button((954, 652, 312, 52), "Iniciar simulação", GREEN, "play", 18, radius=14)
        self.btn_menu = Button((1162, 14, 104, 36), "Menu", PANEL_3, "back", 15, radius=12)
        self.btn_fs = Button((1112, 14, 40, 36), "", PANEL_3, "expand", 16, radius=12)
        self.btn_speed = Button((956, 14, 146, 36), "Velocidade 1x", PANEL_3, "ff", 14, radius=12)
        self.btn_hint = Button((768, 664, 160, 44), "Dica (3)", (226, 146, 38), "bulb", 15, radius=22)
        self.hints_left = hints_left
        self.hint = None
        self.toast = None
        self.fact = random.choice(FACTS)
        self.tips = ["Clique direito remove  •  Arraste uma medida colocada para trocar de lugar",
                     "Passe o mouse sobre um ponto ou uma medida para ver a explicação"] + ["Você sabia? " + f for f in random.sample(FACTS, len(FACTS))]
        self.modal = None
        self.m_yes = Button((0, 0, 210, 48), "Iniciar mesmo assim", (236, 120, 60), None, 15, radius=12)
        self.m_no = Button((0, 0, 200, 48), "Voltar e proteger", PANEL_3, None, 15, radius=12)
        self.drag = None
        self.hover_card = None
        self.hover_card_t = 0.0
        self.hover_spot = None
        self.coach = 1.0
        self.first_done = bool(self.place)
        self.intro = 0.0
        self.shake = 0.0
        self.red_flash = 0.0
        self.night = 0.0
        self.particles = []
        self.texts = []
        self.shields = []
        self.threats = []
        self.log = []
        self.integrity = 100.0
        self.integrity_target = 100.0
        self.speed = 1
        self.def_t = 0.0
        self.finish_t = None
        self.side_anim = 0.0
        self.banner_t = None
        self.night_overlay = None
        self.map_off = (MAP_AREA.centerx - MAP_W // 2, MAP_AREA.centery - MAP_H // 2 + S(4))

    # ------------------------- cenário -------------------------
    def make_sky(self, day):
        w, h = MAP_AREA.size
        if day:
            s = vgradient(w, h, (108, 176, 244), (222, 240, 252), mid=(158, 208, 250))
            g = glow_surf(S(340), (255, 244, 214), 0.5)
            s.blit(g, g.get_rect(center=(S(30), S(0))))
            g = glow_surf(S(120), (255, 252, 236), 0.75)
            s.blit(g, g.get_rect(center=(S(30), S(0))))
        else:
            s = vgradient(w, h, (10, 14, 42), (52, 44, 100), mid=(22, 26, 72))
            rng = random.Random(3)
            for _ in range(140):
                x, y = rng.uniform(0, w), rng.uniform(0, h * 0.85)
                a = rng.randint(60, 200)
                gfx.filled_circle(s, int(x), int(y), max(1, int(rng.choice((0.6, 1, 1, 1.4)) * K)), (255, 255, 255, a))
            mx, my = w - S(130), S(90)
            blit_add_glow(s, mx, my, S(150), (60, 60, 70))
            gfx.filled_circle(s, mx, my, S(24), (242, 238, 220))
            gfx.aacircle(s, mx, my, S(24), (250, 248, 236))
            for cx, cy, r in ((-7, -5, 5), (6, 7, 4), (8, -8, 3), (-4, 9, 3)):
                gfx.filled_circle(s, mx + S(cx), my + S(cy), S(r), (222, 218, 200))
        return s

    def make_cloud(self):
        w, h = S(230), S(96)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for cx, cy, r in ((60, 58, 32), (102, 44, 42), (148, 54, 34), (184, 62, 24), (112, 64, 32)):
            pygame.draw.circle(s, (226, 236, 250, 200), (S(cx), S(cy) + S(4)), S(r))
        for cx, cy, r in ((60, 58, 32), (102, 44, 42), (148, 54, 34), (184, 62, 24), (112, 64, 32)):
            pygame.draw.circle(s, (255, 255, 255, 220), (S(cx), S(cy) - S(2)), S(r) - S(3))
        return blur_surface(s, 3)

    def build_night(self):
        m = S(30)
        size = (MAP_AREA.w + 2 * m, MAP_AREA.h + 2 * m)
        ox = self.map_off[0] - MAP_AREA.x + m
        oy = self.map_off[1] - MAP_AREA.y + m

        def P(gx, gy, gz):
            x, y = iso(gx, gy, gz)
            return (int(x + ox), int(y + oy))

        light = pygame.Surface(size, pygame.SRCALPHA)
        warm = pygame.Surface(size)
        warm.fill((0, 0, 0))
        for name, x, y, w, d, fl in self.loc["rooms"]:
            top = FLOOR_Z + 66
            hexa = [P(x, y, top), P(x + w, y, top), P(x + w, y, 0), P(x + w, y + d, 0), P(x, y + d, 0), P(x, y + d, top)]
            pygame.draw.polygon(light, (0, 0, 0, 150), hexa)
            pygame.draw.polygon(warm, (30, 22, 8), hexa)

        def hole(px, py, r, flat=1.0, strength=1.0, wc=None):
            g = glow_surf(r, (0, 0, 0), strength)
            if flat != 1.0:
                g = pygame.transform.smoothscale(g, (g.get_width(), max(1, int(g.get_height() * flat))))
            light.blit(g, g.get_rect(center=(int(px), int(py))), special_flags=pygame.BLEND_RGBA_MAX)
            if wc:
                blit_add_glow(warm, px, py, r, wc, flat)

        for lx, ly in self.world.lamps:
            fz = self.world.floor_z(lx, ly)
            hole(*P(lx, ly, fz), S(105), 0.55, 0.95, (70, 56, 26))
            hole(*P(lx, ly, fz + 64), S(36), 1.0, 1.0, (90, 76, 40))
        for lx, ly in self.world.indoor_lamps:
            hole(*P(lx, ly, FLOOR_Z + 30), S(60), 0.8, 0.8, (60, 44, 16))
        for sp in self.spots:
            if self.place.get(sp.idx) == "luz":
                hole(*P(sp.x, sp.y, sp.fz), S(130), 0.55, 1.0, (90, 80, 40))
        light = blur_surface(light, max(3.0, 6 * K))
        warm = blur_surface(warm, max(3.0, 6 * K))
        overlay = pygame.Surface(size, pygame.SRCALPHA)
        overlay.fill((8, 12, 40, 200))
        overlay.blit(light, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        # a escuridão só cobre o diorama: o céu noturno já é escuro e estrelado
        hull = pygame.Surface(size, pygame.SRCALPHA)
        hull.fill((255, 255, 255, 0))
        up = 130
        hp = [P(0, 0, up), P(GW, 0, up), P(GW, 0, 0), P(GW, GH, -36), P(0, GH, -36), P(0, GH, up)]
        pygame.draw.polygon(hull, (255, 255, 255, 255), hp)
        hull = blur_surface(hull, max(3.0, 8 * K))
        overlay.blit(hull, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self.night_overlay = overlay
        self.night_warm = warm
        self.night_m = m
        self.warm_levels = {}

    def warm_level(self, q):
        s = self.warm_levels.get(q)
        if s is None:
            s = self.night_warm.copy()
            v = int(255 * q)
            s.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            self.warm_levels[q] = s
        return s

    # ------------------------- utilidades -------------------------
    def offset(self):
        ox, oy = self.map_off
        p = clamp(self.intro / 0.9, 0, 1)
        oy += int((1 - ease_out_back(p)) * S(70))
        if self.shake > 0:
            ox += random.uniform(-1, 1) * S(9) * self.shake
            oy += random.uniform(-1, 1) * S(6) * self.shake
        return (int(ox), int(oy))

    def placed_measure_spot(self, mid):
        for si, m in self.place.items():
            if m == mid:
                return si
        return None

    def spot_at(self, pos):
        off = self.offset()
        best, bd = None, 1e9
        for sp in self.spots:
            fx, fy = sp.floor_pos()
            bx, by = sp.badge_pos(self.t)
            fx += off[0]
            fy += off[1]
            bx += off[0]
            by += off[1]
            d1 = math.hypot(pos[0] - bx, pos[1] - by)
            dx, dy = (pos[0] - fx) / (S(28)), (pos[1] - fy) / (S(15))
            d2 = math.hypot(dx, dy) * S(22)
            d = min(d1, d2)
            if d < S(26) and d < bd:
                best, bd = sp.idx, d
        return best

    def card_at(self, pos):
        if self.phase != "build":
            return None
        for i, r in enumerate(self.cards):
            if r.collidepoint(pos):
                return i
        return None

    def burst(self, x, y, color, n=18, speed=120, life=0.7, size=3.5, g=120):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(0.3, 1.0) * speed
            self.particles.append(Particle(x, y, math.cos(a) * v, math.sin(a) * v - speed * 0.3, random.uniform(life * 0.6, life),
                                           color, random.uniform(size * 0.6, size), g, 1.5))

    # ------------------------- eventos -------------------------
    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.modal:
                self.modal = None
            elif self.drag:
                self.drag = None
            return
        if e.type == pygame.MOUSEBUTTONDOWN:
            self.on_down(e.pos, e.button)
        elif e.type == pygame.MOUSEBUTTONUP:
            self.on_up(e.pos, e.button)

    def on_down(self, pos, button):
        if self.modal:
            if button == 1:
                if self.m_yes.hit(pos):
                    self.modal = None
                    self.start_defense()
                elif self.m_no.hit(pos):
                    self.modal = None
            return
        if button == 1 and self.btn_menu.hit(pos):
            self.game.switch(lambda: MenuScene(self.game))
            return
        if button == 1 and self.btn_fs.hit(pos):
            self.game.toggle_fullscreen()
            return
        if self.phase == "defense":
            if button == 1 and self.btn_speed.hit(pos):
                self.speed = 2 if self.speed == 1 else 1
                self.btn_speed.text = "Velocidade %dx" % self.speed
            return
        if button == 3:
            if self.drag:
                self.drag = None
                return
            si = self.spot_at(pos)
            if si is not None and si in self.place:
                mid = self.place.pop(si)
                bx, by = self.spots[si].badge_pos(self.t)
                o = self.offset()
                self.burst(bx, by, self.mby[mid]["color"], 10, 80)
            return
        if button != 1:
            return
        if self.btn_start.hit(pos):
            self.request_start()
            return
        if self.btn_hint.rect.collidepoint(pos) and not self.drag:
            self.btn_hint.press = 1.0
            self.use_hint()
            return
        if self.drag and self.drag["sticky"]:
            si = self.spot_at(pos)
            if si is not None:
                self.drop_on(si)
                return
            if self.card_at(pos) is None:
                self.drag = None
                return
        ci = self.card_at(pos)
        if ci is not None:
            mid = self.measures[ci]["id"]
            origin = "card"
            si = self.placed_measure_spot(mid)
            if si is not None:
                del self.place[si]
                origin = si
            self.drag = dict(mid=mid, origin=origin, sticky=False, start=pos)
            return
        si = self.spot_at(pos)
        if si is not None and si in self.place:
            mid = self.place.pop(si)
            self.drag = dict(mid=mid, origin=si, sticky=False, start=pos)

    def on_up(self, pos, button):
        if button != 1 or not self.drag or self.drag["sticky"] or self.phase != "build":
            return
        si = self.spot_at(pos)
        if si is not None:
            self.drop_on(si)
            return
        moved = math.hypot(pos[0] - self.drag["start"][0], pos[1] - self.drag["start"][1]) > S(8)
        if not moved:
            self.drag["sticky"] = True
            return
        self.drag = None

    def drop_on(self, si):
        mid = self.drag["mid"]
        origin = self.drag["origin"]
        prev = self.place.get(si)
        self.place[si] = mid
        if prev and prev != mid:
            if isinstance(origin, int) and origin != si and origin not in self.place:
                self.place[origin] = prev
                self.spots[origin].pop = 0.0
        sp = self.spots[si]
        sp.pop = 0.0
        bx, by = sp.badge_pos(self.t)
        self.burst(bx, by, self.mby[mid]["color"], 22, 140)
        self.burst(bx, by, (255, 255, 255), 8, 90, size=2.5)
        self.drag = None
        self.first_done = True

    @property
    def hints_used(self):
        return HINTS_PER_GAME - self.hints_left

    def show_toast(self, text, color=TEXT):
        self.toast = dict(text=text, color=color, t=0.0)

    def use_hint(self):
        wrong = [sp for sp in self.spots if sp.idx in self.place and self.place[sp.idx] != sp.ideal]
        empty = [sp for sp in self.spots if sp.idx not in self.place]
        cands = wrong + empty
        if not cands:
            self.show_toast("Tudo protegido com a medida certa! Pode iniciar a simulação.", (136, 226, 166))
            return
        if self.hint and any(sp.idx == self.hint["si"] for sp in cands):
            self.hint["t"] = 0.0
            return
        if self.hints_left <= 0:
            self.btn_hint.shake = 1.0
            self.show_toast("Você já usou as %d dicas desta partida." % HINTS_PER_GAME, (255, 196, 126))
            return
        sp = cands[0]
        self.hints_left -= 1
        self.hint = dict(si=sp.idx, t=0.0, wrong=sp.idx in self.place)
        self.first_done = True
        bx, by = sp.badge_pos(self.t)
        self.burst(bx, by, GOLD, 16, 110)

    def request_start(self):
        missing = len(self.spots) - len(self.place)
        if missing > 0:
            self.modal = dict(t=0.0, missing=missing)
        else:
            self.start_defense()

    # ------------------------- defesa -------------------------
    def start_defense(self):
        self.phase = "defense"
        self.drag = None
        self.hint = None
        self.def_t = 0.0
        self.banner_t = 0.0
        self.build_night()
        order = list(range(len(self.spots)))
        random.shuffle(order)
        self.threats = []
        for k, si in enumerate(order):
            sp = self.spots[si]
            lvl = sp.level(self.place.get(si))
            self.threats.append(Threat(self, sp, lvl, 2.2 + k * 1.7))

    def on_resolve(self, th, outcome):
        sp = th.spot
        sp.status = outcome
        sp.flash = 1.0
        n = len(self.spots)
        self.integrity_target = max(0.0, self.integrity_target - (1 - th.level) / n * 100)
        ok_t, fail_t = FAMILY_TEXT[th.fam]
        bx, by = sp.badge_pos(self.t)
        fx, fy = sp.floor_pos()
        mid = self.place.get(sp.idx)
        mname = self.mby[mid]["name"] if mid else None
        if outcome == "ok":
            self.texts.append(FloatText(ok_t, (120, 255, 170), bx, by - S(32)))
            self.shields.append(Shield(fx, fy, GREEN, False, 40 if sp.skylight else 48))
            self.burst(bx, by, GREEN, 20, 130)
            detail = "%s impediu a ameaça." % mname
        elif outcome == "partial":
            self.texts.append(FloatText("PARCIAL!", (255, 210, 110), bx, by - S(32)))
            self.shields.append(Shield(fx, fy, AMBER, True))
            self.burst(bx, by, AMBER, 14, 110)
            detail = "%s ajudou, mas não era a medida ideal." % mname
        else:
            self.texts.append(FloatText(fail_t, (255, 120, 120), bx, by - S(32), 23))
            self.shake = 0.7
            self.red_flash = 1.0
            self.burst(fx, fy - S(20), RED, 26, 150)
            detail = ("%s não protege contra isso." % mname) if mname else "Nenhuma medida neste ponto."
        self.log.append(dict(status=outcome, title=sp.threat_name, place=sp.name, detail=detail, t=0.0))

    # ------------------------- update -------------------------
    def update(self, dt):
        super().update(dt)
        self.intro += dt
        mouse = mouse_pos()
        gdt = dt * (self.speed if self.phase == "defense" else 1)
        self.btn_fs.icon_kind = "compress" if self.game.fullscreen else "expand"
        self.btn_hint.text = "Dica (%d)" % self.hints_left
        self.btn_hint.color = (226, 146, 38) if self.hints_left > 0 else (110, 100, 90)
        for b in (self.btn_start, self.btn_menu, self.btn_speed, self.btn_fs, self.btn_hint):
            b.update(dt, mouse)
        if self.toast:
            self.toast["t"] += dt
            if self.toast["t"] > 3.2:
                self.toast = None
        if self.hint:
            self.hint["t"] += dt
            sp = self.spots[self.hint["si"]]
            if self.place.get(sp.idx) == sp.ideal:
                bx, by = sp.badge_pos(self.t)
                self.burst(bx, by, GOLD, 26, 150)
                self.show_toast("Boa! Essa é a medida ideal para %s." % sp.name.lower(), (136, 226, 166))
                self.hint = None
            elif self.hint["t"] > 16:
                self.hint = None
        if self.modal:
            self.modal["t"] += dt
            self.m_yes.update(dt, mouse)
            self.m_no.update(dt, mouse)
        for npc in self.world.npcs:
            npc.update(gdt)
        for car in self.world.cars:
            car.update(gdt)
        for c in self.clouds:
            c["x"] += c["v"] * dt
            if c["x"] > MAP_AREA.w + S(120):
                c["x"] = -S(260)
        self.update_birds(dt)
        for sp in self.spots:
            sp.pop = min(9.0, sp.pop + dt)
            sp.flash = max(0.0, sp.flash - dt * 1.6)
            sp.hover = approach(sp.hover, 1.0 if self.hover_spot == sp.idx else 0.0, dt, 14)
        self.particles = [p for p in self.particles if p.update(gdt)]
        self.texts = [t for t in self.texts if t.update(gdt)]
        self.shields = [s for s in self.shields if s.update(gdt)]
        self.shake = max(0.0, self.shake - dt * 1.6)
        self.red_flash = max(0.0, self.red_flash - dt * 1.8)
        if self.phase == "build":
            self.update_build(dt, mouse)
        else:
            self.update_defense(dt, gdt)

    def update_birds(self, dt):
        if self.night < 0.3:
            self.bird_t -= dt
            if self.bird_t <= 0:
                self.bird_t = random.uniform(6, 12)
                n = random.randint(3, 5)
                y = random.uniform(S(40), S(200))
                self.birds.append(dict(x=-S(40), y=y, v=random.uniform(40, 60) * K,
                                       mem=[(-i * S(16), (i % 2) * S(9) + i * S(3), random.uniform(0, 6)) for i in range(n)]))
        for b in self.birds:
            b["x"] += b["v"] * dt
        self.birds = [b for b in self.birds if b["x"] < MAP_AREA.w + S(120)]

    def update_build(self, dt, mouse):
        self.hover_spot = self.spot_at(mouse) if not self.modal else None
        hc = self.card_at(mouse) if not self.modal else None
        if hc != self.hover_card:
            self.hover_card = hc
            self.hover_card_t = 0.0
        else:
            self.hover_card_t += dt
        for i in range(len(self.cards)):
            self.card_h[i] = approach(self.card_h[i], 1.0 if hc == i else 0.0, dt, 14)
        if self.first_done or self.t > 9:
            self.coach = max(0.0, self.coach - dt * 1.5)
        self.btn_start.color = GREEN if len(self.place) == len(self.spots) else (60, 160, 120)

    def update_defense(self, dt, gdt):
        self.def_t += gdt
        self.side_anim = min(1.0, self.side_anim + dt * 2.5)
        self.night = ease_in_out(self.def_t / 1.6)
        self.hover_spot = None
        if self.banner_t is not None:
            self.banner_t += dt
        for th in self.threats:
            th.update(gdt)
        for e in self.log:
            e["t"] += dt
        self.integrity = approach(self.integrity, self.integrity_target, dt, 4)
        if self.threats and all(th.done for th in self.threats):
            if self.finish_t is None:
                self.finish_t = 0.0
            self.finish_t += dt
            if self.finish_t > 2.3:
                self.finish_t = -999
                self.go_results()
        for sp in self.spots:
            if sp.persist == "glitch" and random.random() < 0.15:
                fx, fy = sp.floor_pos()
                self.particles.append(Particle(fx + random.uniform(-16, 16) * K, fy - random.uniform(0, 30) * K, 0, -20, 0.5,
                                               random.choice([(255, 60, 90), (200, 80, 255)]), 2.5))

    def go_results(self):
        results = []
        for sp in self.spots:
            mid = self.place.get(sp.idx)
            results.append(dict(spot=sp.name, threat=sp.threat_name, measure=self.mby[mid]["name"] if mid else None,
                                measure_icon=self.mby[mid]["icon"] if mid else None,
                                measure_color=self.mby[mid]["color"] if mid else None,
                                ideal=self.mby[sp.ideal]["name"], ideal_desc=self.mby[sp.ideal]["desc"],
                                hint=sp.hint, level=sp.level(mid)))
        score = int(round(sum(r["level"] for r in results) / len(results) * 100))
        snap = pygame.Surface((W, H))
        self.draw(snap)
        key, game, used = self.key, self.game, self.hints_used
        self.game.switch(lambda: ResultScene(game, key, results, score, snap, used))

    # ------------------------- desenho -------------------------
    def draw(self, surf):
        surf.set_clip(MAP_AREA)
        surf.blit(self.bg_day, MAP_AREA.topleft)
        if self.night > 0.01:
            self.bg_night.set_alpha(int(255 * self.night))
            surf.blit(self.bg_night, MAP_AREA.topleft)
            for x, y, ph in self.stars:
                a = int(self.night * (120 + 120 * math.sin(self.t * 2.2 + ph)))
                gfx.filled_circle(surf, int(MAP_AREA.x + x), int(MAP_AREA.y + y), max(1, S(1.5)), (255, 255, 255, max(0, a)))
        for c in self.clouds:
            img = c["img"]
            if self.night > 0.01:
                img = img.copy()
                img.set_alpha(int(255 * (1 - 0.75 * self.night)))
            surf.blit(img, (int(MAP_AREA.x + c["x"]), int(MAP_AREA.y + c["y"])))
        for b in self.birds:
            for dx, dy, ph in b["mem"]:
                x, y = MAP_AREA.x + b["x"] + dx, MAP_AREA.y + b["y"] + dy
                f = math.sin(self.t * 9 + ph) * S(4)
                pts = [(int(x - S(6)), int(y - f)), (int(x), int(y)), (int(x + S(6)), int(y - f))]
                pygame.draw.lines(surf, (54, 74, 106), False, pts, max(1, S(1.6)))
        surf.set_clip(None)
        self.draw_map(surf)
        self.draw_topbar(surf)
        self.draw_sidebar(surf)
        if self.phase == "build":
            self.draw_build_overlays(surf)
        else:
            self.draw_defense_overlays(surf)
        if self.modal:
            self.draw_modal(surf)

    def draw_map(self, surf):
        off = self.offset()
        t = self.t
        surf.set_clip(MAP_AREA)
        surf.blit(self.world.base, off)
        for sp in self.spots:
            fx, fy = sp.floor_pos()
            fx += off[0]
            fy += off[1]
            if sp.scorch > 0:
                gfx.filled_ellipse(surf, int(fx), int(fy), int((26 * sp.scorch + 6) * K), int((13 * sp.scorch + 3) * K), (30, 24, 20, 120))
            mid = self.place.get(sp.idx)
            if self.phase == "build":
                if self.drag:
                    pulse = 0.5 + 0.5 * math.sin(t * 6)
                    r = 0.42 + 0.06 * pulse + 0.1 * sp.hover
                    col = (255, 255, 255) if sp.hover < 0.5 else (120, 230, 255)
                    draw_iso_ring(surf, fx, fy, r, col, 150 + 100 * sp.hover, 0.3, 2 + int(sp.hover * 2))
                elif mid:
                    draw_iso_ring(surf, fx, fy, 0.42 + 0.04 * sp.hover, self.mby[mid]["color"], 210, 0.3)
                else:
                    pulse = 0.5 + 0.5 * math.sin(t * 4 + sp.idx)
                    draw_iso_ring(surf, fx, fy, 0.36 + 0.08 * pulse + 0.06 * sp.hover, (255, 110, 60), 205 + 50 * sp.hover, 0.38, 3)
            else:
                col = {"ok": GREEN, "partial": AMBER, "fail": RED}.get(sp.status)
                if col:
                    pulse = 0.5 + 0.5 * math.sin(t * 5)
                    draw_iso_ring(surf, fx, fy, 0.44 + (0.05 * pulse if sp.status == "fail" else 0), col, 215, 0.3)
                elif mid:
                    draw_iso_ring(surf, fx, fy, 0.42, self.mby[mid]["color"], 180, 0.25)
                else:
                    draw_iso_ring(surf, fx, fy, 0.4, (255, 120, 70), 160, 0.2)
        if self.hint:
            sp = self.spots[self.hint["si"]]
            fx, fy = sp.floor_pos()
            pulse = 0.5 + 0.5 * math.sin(t * 6)
            draw_iso_ring(surf, fx + off[0], fy + off[1], 0.5 + 0.12 * pulse, GOLD, 230, 0.35, 3)
            draw_iso_ring(surf, fx + off[0], fy + off[1], 0.75 + 0.2 * pulse, GOLD, 120 * (1 - pulse), 0.0, 2)
        dyn = list(self.world.npcs) + list(self.world.cars) + [th for th in self.threats if th.visible and not th.airborne]
        self.world.render_sorted(surf, off, dyn)
        for sp in self.spots:
            if sp.skylight:
                self.draw_skylight(surf, sp, off)
        for th in self.threats:
            if th.airborne:
                th.draw(surf, off)
        if self.night > 0.01 and self.night_overlay is not None:
            dx, dy = off[0] - self.map_off[0], off[1] - self.map_off[1]
            ov = self.night_overlay
            ov.set_alpha(int(255 * self.night))
            surf.blit(ov, (MAP_AREA.x - self.night_m + dx, MAP_AREA.y - self.night_m + dy))
            q = round(self.night * 4) / 4.0
            if q > 0:
                surf.blit(self.warm_level(q), (MAP_AREA.x - self.night_m + dx, MAP_AREA.y - self.night_m + dy),
                          special_flags=pygame.BLEND_RGB_ADD)
            self.draw_night_lights(surf, off)
        if self.red_flash > 0:
            self.red_surf.set_alpha(int(70 * self.red_flash))
            surf.blit(self.red_surf, MAP_AREA.topleft)
        for th in self.threats:
            th.draw_overlay(surf, off)
        for s in self.shields:
            s.draw(surf, off)
        for sp in self.spots:
            fx, fy = sp.floor_pos()
            if sp.persist == "glitch":
                cx, cy = fx + off[0] + S(18), fy - S(20) + off[1] + math.sin(t * 5) * S(3)
                pr = S(16) + S(6) * (0.5 + 0.5 * math.sin(t * 6))
                gfx.aacircle(surf, int(cx), int(cy), int(pr), (255, 60, 100, 160))
                draw_virus(surf, cx, cy, t, 0.75, 255)
            if sp.persist == "injury":
                cx, cy = int(fx + off[0]), int(fy - S(30) + off[1] + math.sin(t * 4) * S(2))
                gfx.filled_circle(surf, cx, cy, S(13), (255, 255, 255))
                gfx.aacircle(surf, cx, cy, S(13), (220, 220, 230))
                pygame.draw.rect(surf, RED, (cx - S(3), cy - S(9), S(6), S(18)))
                pygame.draw.rect(surf, RED, (cx - S(9), cy - S(3), S(18), S(6)))
        for p in self.particles:
            p.draw(surf, off)
        if self.hint:
            sp = self.spots[self.hint["si"]]
            fx, fy = sp.floor_pos()
            bx, by = sp.badge_pos(t)
            wv = S(16) + S(4) * math.sin(t * 5)
            beam = [(int(fx + off[0] - wv), int(fy + off[1])), (int(fx + off[0] + wv), int(fy + off[1])),
                    (int(bx + off[0] + wv * 0.6), int(by + off[1])), (int(bx + off[0] - wv * 0.6), int(by + off[1]))]
            gfx.filled_polygon(surf, beam, (255, 214, 90, 46))
        self.draw_badges(surf, off)
        for tx in self.texts:
            tx.draw(surf, off)
        surf.blit(self.vignette, MAP_AREA.topleft)
        surf.set_clip(None)

    def draw_skylight(self, surf, sp, off):
        o = (-off[0], -off[1])
        z = sp.fz + 66
        fz = sp.fz
        x, y, h = sp.x, sp.y, 0.72

        def P(a, b, c):
            return _pt(a, b, c, o)

        n = self.night
        lc = mix((255, 246, 214), (160, 190, 255), n)
        floor = [P(x - h, y - h, fz), P(x + h, y - h, fz), P(x + h, y + h, fz), P(x - h, y + h, fz)]
        f1 = [P(x - h, y + h, z), P(x + h, y + h, z), P(x + h, y + h, fz), P(x - h, y + h, fz)]
        f2 = [P(x + h, y - h, z), P(x + h, y + h, z), P(x + h, y + h, fz), P(x + h, y - h, fz)]
        gfx.filled_polygon(surf, floor, rgba(lc, 70))
        gfx.filled_polygon(surf, f1, rgba(lc, 34))
        gfx.filled_polygon(surf, f2, rgba(lc, 26))
        frame = (100, 112, 138)
        gfx.filled_polygon(surf, [P(x - h, y + h, z - 5), P(x + h, y + h, z - 5), P(x + h, y + h, z), P(x - h, y + h, z)], shade(frame, 0.9))
        gfx.filled_polygon(surf, [P(x + h, y - h, z - 5), P(x + h, y + h, z - 5), P(x + h, y + h, z), P(x + h, y - h, z)], shade(frame, 0.72))
        outer = [P(x - h, y - h, z), P(x + h, y - h, z), P(x + h, y + h, z), P(x - h, y + h, z)]
        poly(surf, outer, frame)
        i = h - 0.1
        inner = [P(x - i, y - i, z), P(x + i, y - i, z), P(x + i, y + i, z), P(x - i, y + i, z)]
        broken = sp.status == "fail"
        gfx.filled_polygon(surf, inner, (40, 50, 70, 210) if broken else (172, 216, 248, 200))
        pygame.draw.aaline(surf, frame, P(x, y - i, z), P(x, y + i, z))
        pygame.draw.aaline(surf, frame, P(x - i, y, z), P(x + i, y, z))
        if not broken:
            pygame.draw.aaline(surf, (240, 250, 255), P(x - i + 0.12, y - i + 0.45, z), P(x - i + 0.45, y - i + 0.12, z))
            pygame.draw.aaline(surf, (240, 250, 255), P(x + 0.12, y + 0.45, z), P(x + 0.45, y + 0.12, z))
        else:
            c = P(x, y, z)
            for a in range(0, 360, 60):
                e = (c[0] + math.cos(math.radians(a)) * S(22), c[1] + math.sin(math.radians(a)) * S(11))
                pygame.draw.aaline(surf, (200, 220, 240), c, e)
        if self.place.get(sp.idx) == "laser" and (self.phase == "defense" or sp.hover > 0.1 or sp.pop < 1.0):
            k = 1.0 if sp.flash > 0 else 0.5 + 0.5 * math.sin(self.t * 8)
            col = (255, 40, 80, int(110 + 140 * k))
            for j in range(5):
                a = P(x - i, y - i + j * (2 * i) / 4, z - 7)
                b = P(x + i, y - i + j * (2 * i) / 4, z - 7)
                gfx.line(surf, a[0], a[1], b[0], b[1], col)
                gfx.line(surf, a[0], a[1] + 1, b[0], b[1] + 1, col)

    def draw_night_lights(self, surf, off):
        n = self.night
        for car in self.world.cars:
            if car.alpha() > 0.1:
                hx, hy = car.head()
                blit_add_glow(surf, hx + off[0], hy + off[1], S(44), (120, 108, 64), 0.6, n * car.alpha())
        for sp in self.spots:
            mid = self.place.get(sp.idx)
            if mid:
                bx, by = sp.badge_pos(self.t)
                blit_add_glow(surf, bx + off[0], by + off[1], S(48), shade(self.mby[mid]["color"], 0.45), 1.0, n)
        for th in self.threats:
            if th.state in ("wait", "gone"):
                continue
            if th.fam == "fire" and th.size > 0.05:
                fx, fy = iso(th.x, th.y, th.fz)
                blit_add_glow(surf, fx + off[0], fy - S(16) + off[1], int((60 + 70 * th.size) * K), (170, 84, 20), 1.0, n)
            elif th.fam == "gas" and th.size > 0.05:
                fx, fy = iso(th.x, th.y, th.fz)
                blit_add_glow(surf, fx + off[0], fy - S(12) + off[1], int((50 + 50 * th.size) * K), (40, 120, 30), 0.7, n)
            elif th.fam == "virus":
                px, py = iso(th.x, th.y, th.fz + th.z)
                blit_add_glow(surf, px + off[0], py + off[1], S(36), (100, 30, 120), 1.0, n)

    def draw_badges(self, surf, off):
        t = self.t
        for sp in self.spots:
            bx, by = sp.badge_pos(t)
            bx += off[0]
            by += off[1]
            mid = self.place.get(sp.idx)
            fx, fy = sp.floor_pos()
            fx, fy = int(fx + off[0]), int(fy + off[1])
            stem = (255, 255, 255, 160 if self.phase == "build" else 100)
            if by + S(20) < fy:
                for k in range(max(2, S(2))):
                    gfx.line(surf, fx + k, fy, int(bx) + k, int(by + S(18)), stem)
            gfx.filled_circle(surf, fx, fy, max(2, S(3)), (255, 255, 255, 220))
            if self.hint and self.hint["si"] == sp.idx:
                pr = S(30) + S(4) * math.sin(t * 6)
                for k in range(max(2, S(3))):
                    gfx.aacircle(surf, int(bx), int(by), int(pr) + k, rgba(GOLD, 230))
            if mid:
                m = self.mby[mid]
                sc = ease_out_back(sp.pop / 0.45) if sp.pop < 0.45 else 1.0
                sc *= 1.0 + 0.12 * sp.hover + 0.25 * sp.flash
                ring = None
                if self.phase == "defense" and sp.status:
                    ring = {"ok": GREEN, "partial": AMBER, "fail": RED}[sp.status]
                draw_badge(surf, bx, by, m, sc, 255, ring)
                if self.phase == "defense" and sp.status == "fail":
                    gfx.filled_circle(surf, int(bx + S(16)), int(by - S(15)), S(9), RED)
                    ic = icon("cross", 11)
                    surf.blit(ic, ic.get_rect(center=(int(bx + S(16)), int(by - S(15)))))
            else:
                if self.phase == "build":
                    if self.drag:
                        draw_alert_bubble(surf, int(bx), int(by), t, (70, 190, 255) if sp.hover < 0.5 else (60, 220, 160), "+")
                    else:
                        draw_alert_bubble(surf, int(bx), int(by), t)
                elif sp.status == "fail":
                    draw_alert_bubble(surf, int(bx), int(by), t, RED, "x")
                elif sp.status is None:
                    draw_alert_bubble(surf, int(bx), int(by), t, (204, 112, 70))

    def draw_topbar(self, surf):
        surf.blit(self.top_bg, (0, 0))
        line = pygame.Surface((W, max(1, S(2))), pygame.SRCALPHA)
        line.fill(rgba(ACCENT, 70))
        surf.blit(line, (0, TOP_H - line.get_height()))
        draw_logo(surf, S(34), S(32), 0.6, self.t)
        gt, gsz = fit_text("Olá, %s!" % self.game.player, 19, S(340), True, 13)
        draw_text(surf, gt, gsz, TEXT, (S(62), S(9)), bold=True)
        col = self.loc["color"]
        label = "%s  •  %s" % (self.loc["name"], "Fase de preparação" if self.phase == "build" else "Simulação noturna")
        label = ellipsize(label, 13, S(300), True)
        tw = font(13, True).size(label)[0]
        chip = pygame.Rect(S(62), S(35), tw + S(30), S(22))
        pill(surf, chip, mix((34, 42, 74), col, 0.25), 255, border=mix((60, 72, 116), col, 0.5))
        gfx.filled_circle(surf, chip.x + S(11), chip.centery, S(4), col)
        draw_text(surf, label, 13, TEXT, (chip.x + S(20), chip.centery), bold=True, anchor="midleft")
        cx = S(560)
        if self.phase == "build":
            n, tot = len(self.place), len(self.spots)
            label, frac = "Pontos protegidos", n / tot
            bcol = GREEN if n == tot else ACCENT
            val = "%d/%d" % (n, tot)
        else:
            res = sum(1 for th in self.threats if th.outcome)
            tot = len(self.threats)
            label, frac, bcol = "Ameaças enfrentadas", res / max(1, tot), AMBER
            val = "%d/%d" % (res, tot)
        draw_text(surf, label, 13, MUTED, (cx - S(130), S(11)), bold=True)
        bar = pygame.Rect(cx - S(130), S(34), S(230), S(12))
        pygame.draw.rect(surf, (34, 42, 74), bar, border_radius=bar.h // 2)
        if frac > 0:
            fr = bar.copy()
            fr.w = max(bar.h, int(bar.w * frac))
            surf.blit(grad_rect(fr.w, fr.h, lighten(bcol, 0.3), bcol, fr.h // 2), fr.topleft)
        draw_text(surf, val, 19, TEXT, (bar.right + S(12), bar.centery), bold=True, anchor="midleft")
        if self.phase == "defense":
            self.btn_speed.draw(surf)
        self.btn_fs.draw(surf)
        self.btn_menu.draw(surf)

    def draw_sidebar(self, surf):
        r = pygame.Rect(MAP_AREA.right, TOP_H, SIDE_W, H - TOP_H)
        surf.blit(self.side_bg, r.topleft)
        pygame.draw.line(surf, (50, 62, 102), (r.x, r.y), (r.x, r.bottom), max(1, S(1)))
        if self.phase == "build":
            self.draw_cards(surf, r)
        else:
            self.draw_log(surf, r)

    def draw_cards(self, surf, r):
        draw_text(surf, "MEDIDAS DE SEGURANÇA", 14, (150, 182, 246), (r.x + S(18), S(77)), bold=True)
        draw_text(surf, "Arraste cada uma até um ponto  !  do mapa", 13, MUTED, (r.x + S(18), S(96)))
        for i, m in enumerate(self.measures):
            cr = self.cards[i]
            h = self.card_h[i]
            used_si = self.placed_measure_spot(m["id"])
            dragging = self.drag and self.drag["mid"] == m["id"]
            rr = cr.move(int(-S(5) * h), 0)
            base = (36, 44, 76) if used_si is None else (28, 34, 60)
            col = mix(base, (50, 62, 104), h)
            border = m["color"] if dragging else (mix((52, 62, 100), m["color"], 0.6) if h > 0.3 else (46, 56, 92))
            draw_panel(surf, rr, col, radius=S(12), shadow=h > 0.05, shadow_alpha=int(90 * h), top=lighten(col, 0.07), border=border)
            pygame.draw.rect(surf, m["color"], (rr.x, rr.y + S(12), S(4), rr.h - S(24)), border_radius=S(2))
            hinted = bool(self.hint and self.spots[self.hint["si"]].ideal == m["id"])
            if hinted:
                k = 0.5 + 0.5 * math.sin(self.t * 6)
                pygame.draw.rect(surf, mix(GOLD, (255, 255, 255), 0.4 * k), rr.inflate(S(4), S(4)), max(2, S(3)), border_radius=S(14))
            dim = used_si is not None or dragging
            tile = icon_tile(m["icon"], m["color"], 42, 12, dim)
            surf.blit(tile, (rr.x + S(13), rr.centery - tile.get_height() // 2))
            name, nsz = fit_text(m["name"], 16, rr.w - S(78), True, 13)
            draw_text(surf, name, nsz, TEXT if not dim else (176, 184, 206), (rr.x + S(66), rr.y + S(8) + S(16 - nsz)), bold=True)
            if used_si is not None:
                gfx.filled_circle(surf, rr.x + S(73), rr.y + S(41), S(7), GREEN)
                ic = icon("check", 10)
                surf.blit(ic, ic.get_rect(center=(rr.x + S(73), rr.y + S(41))))
                draw_text(surf, ellipsize("Em: " + self.spots[used_si].name, 13, rr.w - S(96)), 13, (136, 226, 166), (rr.x + S(85), rr.y + S(32)))
            elif dragging:
                draw_text(surf, "Solte num ponto do mapa...", 13, (156, 206, 255), (rr.x + S(66), rr.y + S(32)))
            elif hinted:
                ht = ellipsize("Dica: use em " + self.spots[self.hint["si"]].name, 13, rr.w - S(78), True)
                draw_text(surf, ht, 13, GOLD, (rr.x + S(66), rr.y + S(32)), bold=True)
            else:
                draw_text(surf, ellipsize(m["desc"], 13, rr.w - S(78)), 13, MUTED, (rr.x + S(66), rr.y + S(32)))
        self.btn_start.draw(surf)

    def draw_log(self, surf, r):
        a = ease_out_cubic(self.side_anim)
        draw_text(surf, "RELATÓRIO DA NOITE", 14, (150, 182, 246), (r.x + S(18), S(77)), bold=True, alpha=int(255 * a))
        draw_text(surf, "O que aconteceu em cada ponto", 13, MUTED, (r.x + S(18), S(96)), alpha=int(255 * a))
        y = S(120)
        for e in self.log:
            p = ease_out_cubic(e["t"] / 0.45)
            col = {"ok": GREEN, "partial": AMBER, "fail": RED}[e["status"]]
            box = pygame.Rect(r.x + S(14) + int((1 - p) * S(60)), y, r.w - S(28), S(68))
            draw_panel(surf, box, PANEL_2, radius=S(12), shadow=False, alpha=int(255 * p), top=(40, 50, 84), border=(48, 58, 96))
            pygame.draw.rect(surf, col, (box.x, box.y + S(10), S(4), box.h - S(20)), border_radius=S(2))
            draw_status_icon(surf, box.x + S(27), box.y + S(23), e["status"], S(12))
            al = int(255 * p)
            draw_text(surf, ellipsize(e["title"], 14, box.w - S(60), True), 14, TEXT, (box.x + S(47), box.y + S(7)), bold=True, alpha=al)
            draw_text(surf, ellipsize(e["place"], 13, box.w - S(60), True), 13, col, (box.x + S(47), box.y + S(26)), bold=True, alpha=al)
            draw_text(surf, ellipsize(e["detail"], 13, box.w - S(60)), 13, MUTED, (box.x + S(47), box.y + S(45)), alpha=al)
            y += S(74)
        pending = len(self.threats) - len(self.log)
        if pending > 0 and y < S(560):
            draw_text(surf, "Aguardando %d ameaça(s)..." % pending, 13, SUBTLE, (r.x + S(18), y + S(6)))
        # cartão "Você sabia?" quando há espaço
        laid, th = layout_blocks([("VOCÊ SABIA?", 12, GOLD, True, 0), (self.fact, 13, MUTED, False, 4)], r.w - S(28) - S(54))
        card_h = th + S(24)
        cy0 = y + (S(34) if pending > 0 else S(6))
        if cy0 + card_h < H - S(124):
            fbox = pygame.Rect(r.x + S(14), cy0, r.w - S(28), card_h)
            draw_panel(surf, fbox, (34, 36, 56), radius=S(12), shadow=False, border=(96, 84, 46), alpha=int(255 * a), top=(44, 44, 62))
            ic = icon("bulb", 20, GOLD)
            surf.blit(ic, (fbox.x + S(14), fbox.y + S(13)))
            draw_blocks(surf, fbox.x + S(44), fbox.y + S(10), laid, int(255 * a))
        box = pygame.Rect(r.x + S(14), H - S(114), r.w - S(28), S(100))
        draw_panel(surf, box, PANEL_2, radius=S(14), shadow=False, top=(42, 52, 88), border=(50, 60, 100))
        v = self.integrity
        col = GREEN if v >= 80 else AMBER if v >= 50 else RED
        pct = draw_text(surf, "%d%%" % int(round(v)), 32, col, (box.right - S(16), box.y + S(6)), bold=True, anchor="topright")
        lt, lsz = fit_text("Integridade do local", 14, pct.x - (box.x + S(16)) - S(10), True, 10)
        draw_text(surf, lt, lsz, MUTED, (box.x + S(16), box.y + S(14)), bold=True)
        bar = pygame.Rect(box.x + S(16), box.y + S(62), box.w - S(32), S(16))
        pygame.draw.rect(surf, (26, 32, 56), bar, border_radius=bar.h // 2)
        fr = bar.copy()
        fr.w = max(bar.h, int(bar.w * v / 100))
        surf.blit(grad_rect(fr.w, fr.h, lighten(col, 0.3), col, fr.h // 2), fr.topleft)

    def draw_build_overlays(self, surf):
        mouse = mouse_pos()
        off = self.offset()
        bounds = MAP_AREA.inflate(-S(16), -S(16))
        if self.coach > 0.01:
            a = int(255 * self.coach)
            msg, msz = fit_text("Arraste as medidas da direita até os pontos de alerta do mapa", 15, MAP_AREA.w - S(140), True, 11)
            tw = font(msz, True).size(msg)[0]
            box = pygame.Rect(0, 0, tw + S(72), S(46))
            box.midtop = (MAP_AREA.centerx, MAP_AREA.y + S(14) + int(math.sin(self.t * 3) * S(3)))
            draw_panel(surf, box, (18, 24, 46), radius=box.h // 2, shadow=True, alpha=int(235 * self.coach), top=(30, 38, 70))
            draw_alert_bubble(surf, box.x + S(27), box.centery - S(2), self.t)
            draw_text(surf, msg, msz, TEXT, (box.x + S(50), box.centery), bold=True, anchor="midleft", alpha=a)
        # rodapé com dicas que se alternam
        period = 8.0
        idx = int(self.t / period) % len(self.tips)
        ph = (self.t % period) / period
        ta = clamp(min(ph / 0.06, (1 - ph) / 0.06), 0, 1)
        tip = self.tips[idx]
        maxw = self.btn_hint.rect.x - MAP_AREA.x - S(12) - S(36)
        ttxt, tsz = fit_text(tip, 13, maxw, False, 11)
        tw = font(tsz).size(ttxt)[0]
        tb = pygame.Rect(MAP_AREA.x + S(12), self.btn_hint.rect.centery - S(14), tw + S(40), S(28))
        pill(surf, tb, (16, 22, 44), 180)
        is_fact = tip.startswith("Você sabia?")
        ic = icon("bulb" if is_fact else "chat", 14, GOLD if is_fact else (150, 182, 246))
        surf.blit(ic, (tb.x + S(10), tb.centery - ic.get_height() // 2))
        draw_text(surf, ttxt, tsz, (220, 228, 248), (tb.x + S(30), tb.centery), anchor="midleft", alpha=int(255 * ta))
        self.btn_hint.draw(surf)
        # balão da dica
        if self.hint:
            sp = self.spots[self.hint["si"]]
            bx, by = sp.badge_pos(self.t)
            a = int(255 * clamp(self.hint["t"] / 0.25, 0, 1) * clamp((16 - self.hint["t"]) / 0.6, 0, 1))
            specs = [("DICA  •  " + sp.name.upper(), 13, GOLD, True, 0),
                     (sp.hint, 15, TEXT, False, 6)]
            if self.hint.get("wrong"):
                specs.append(("A medida colocada aqui não é a ideal.", 13, (255, 176, 128), True, 6))
            specs.append(("A medida certa está piscando na lista à direita.", 13, (150, 182, 246), False, 6))
            ax = bx + off[0] + S(36)
            where = "right"
            if ax + S(330) > MAP_AREA.right - S(8):
                ax, where = bx + off[0] - S(36), "left"
            text_box(surf, (ax, by + off[1]), S(330), specs, accent=GOLD, alpha=a, where=where, bounds=bounds, border=(150, 120, 50))
        # tooltip do ponto
        if self.hover_spot is not None and not self.drag and not (self.hint and self.hint["si"] == self.hover_spot):
            sp = self.spots[self.hover_spot]
            bx, by = sp.badge_pos(self.t)
            mid = self.place.get(sp.idx)
            specs = [(sp.name, 17, TEXT, True, 0), ("Risco: " + sp.threat_name, 13, (255, 176, 128), True, 4),
                     (sp.desc, 14, MUTED, False, 6)]
            if mid:
                specs.append(("Medida: " + self.mby[mid]["name"], 13, (136, 226, 166), True, 6))
            text_box(surf, (bx + off[0], by + off[1] - S(32)), S(310), specs, alpha=255, where="above", bounds=bounds)
        # tooltip da medida
        if self.hover_card is not None and not self.drag and self.hover_card_t > 0.25:
            m = self.measures[self.hover_card]
            cr = self.cards[self.hover_card]
            a = int(255 * clamp((self.hover_card_t - 0.25) / 0.2, 0, 1))
            text_box(surf, (cr.x - S(14), cr.centery), S(310), [(m["name"], 16, TEXT, True, 0), (m["desc"], 14, MUTED, False, 6)],
                     accent=m["color"], alpha=a, where="left", bounds=pygame.Rect(S(8), TOP_H + S(8), W - S(16), H - TOP_H - S(16)))
        # aviso rápido
        if self.toast:
            tt = self.toast["t"]
            a = int(255 * clamp(tt / 0.2, 0, 1) * clamp((3.2 - tt) / 0.4, 0, 1))
            msg, msz = fit_text(self.toast["text"], 16, MAP_AREA.w - S(120), True, 11)
            tw = font(msz, True).size(msg)[0]
            box = pygame.Rect(0, 0, tw + S(50), S(46))
            box.midbottom = (MAP_AREA.centerx, self.btn_hint.rect.y - S(14) - int((1 - ease_out_cubic(tt / 0.3)) * S(12)))
            draw_panel(surf, box, (16, 22, 44), radius=box.h // 2, shadow=True, alpha=int(240 * a / 255), border=(70, 84, 130), top=(30, 38, 70))
            draw_text(surf, msg, msz, self.toast["color"], box.center, bold=True, anchor="center", alpha=a)
        # medida sendo arrastada
        if self.drag:
            m = self.mby[self.drag["mid"]]
            mx, my = mouse
            gfx.filled_ellipse(surf, mx, my + S(26), S(16), S(6), (0, 0, 0, 60))
            draw_badge(surf, mx, my, m, 1.12)
            lab = text_surf(m["name"], 14, (255, 255, 255), True)
            lr = lab.get_rect(midtop=(mx, my + S(32)))
            draw_panel(surf, lr.inflate(S(18), S(10)), (16, 22, 44), radius=S(10), shadow=False, alpha=225)
            surf.blit(lab, lr)

    def draw_defense_overlays(self, surf):
        if self.banner_t is not None and self.banner_t < 3.0:
            p = self.banner_t
            a = clamp(p / 0.4, 0, 1) * clamp((3.0 - p) / 0.6, 0, 1)
            y = MAP_AREA.y + S(36) + int((1 - ease_out_cubic(p / 0.5)) * -S(30))
            msg, msz = fit_text("A noite caiu... as ameaças estão chegando!", 20, MAP_AREA.w - S(160), True, 12)
            tw = font(msz, True).size(msg)[0]
            box = pygame.Rect(0, 0, tw + S(84), S(56))
            box.midtop = (MAP_AREA.centerx, y)
            draw_panel(surf, box, (14, 18, 42), radius=box.h // 2, shadow=True, alpha=int(235 * a), top=(30, 34, 70), border=(80, 70, 130))
            ic = icon("warning", 26, AMBER).copy()
            ic.set_alpha(int(255 * a))
            surf.blit(ic, (box.x + S(24), box.centery - ic.get_height() // 2))
            draw_text(surf, msg, msz, TEXT, (box.x + S(60), box.centery), bold=True, anchor="midleft", alpha=int(255 * a))
        if self.finish_t is not None and self.finish_t > 0:
            a = clamp(self.finish_t / 0.5, 0, 1)
            msg, msz = fit_text("Simulação concluída! Calculando pontuação...", 18, MAP_AREA.w - S(120), True, 12)
            tw = font(msz, True).size(msg)[0]
            box = pygame.Rect(0, 0, tw + S(52), S(50))
            box.midbottom = (MAP_AREA.centerx, H - S(20))
            draw_panel(surf, box, (14, 18, 42), radius=box.h // 2, shadow=True, alpha=int(235 * a), top=(30, 34, 70))
            draw_text(surf, msg, msz, TEXT, box.center, bold=True, anchor="center", alpha=int(255 * a))

    def draw_modal(self, surf):
        p = ease_out_back(self.modal["t"] / 0.3)
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((6, 8, 20, int(165 * clamp(self.modal["t"] / 0.2, 0, 1))))
        surf.blit(dim, (0, 0))
        w, h = int(S(500) * p), int(S(236) * p)
        if w < S(20):
            return
        box = pygame.Rect(0, 0, w, h)
        box.center = (W // 2, H // 2)
        draw_panel(surf, box, PANEL, radius=S(18), shadow=p >= 0.98, shadow_alpha=140, border=(62, 74, 120), top=(34, 42, 76))
        if p < 0.9:
            return
        ic = icon("warning", 36, AMBER)
        surf.blit(ic, (box.x + S(26), box.y + S(24)))
        mt, msz = fit_text("Ainda há pontos desprotegidos", 21, w - S(100), True, 13)
        draw_text(surf, mt, msz, TEXT, (box.x + S(76), box.y + S(26)), bold=True)
        n = self.modal["missing"]
        msg = "%d ponto%s sem nenhuma medida. As ameaças poderão entrar por %s." % (n, "" if n == 1 else "s", "ele" if n == 1 else "eles")
        for i, ln in enumerate(wrap(msg, 15, w - S(104))[:3]):
            draw_text(surf, ln, 15, MUTED, (box.x + S(76), box.y + S(62) + i * font(15).get_height()))
        self.m_no.rect.topleft = (box.x + S(24), box.bottom - S(72))
        self.m_yes.rect.topright = (box.right - S(24), box.bottom - S(72))
        self.m_no.draw(surf)
        self.m_yes.draw(surf)


# ------------------------------- RESULTADO --------------------------------
class ResultScene(Scene):
    def __init__(self, game, key, results, score, snap, hints_used=0):
        super().__init__(game)
        self.key = key
        self.loc = LOCATIONS[key]
        self.results = results
        self.score = score
        self.hints_used = hints_used
        self.row_rects = []
        self.hover_row = None
        if snap.get_size() != (W, H):
            snap = pygame.transform.smoothscale(snap, (W, H))
        self.bg = blur_surface(snap, 10)
        dark = pygame.Surface((W, H), pygame.SRCALPHA)
        dark.fill((8, 10, 26, 175))
        self.bg.blit(dark, (0, 0))
        self.invaded = [r for r in results if r["level"] == 0]
        self.partials = [r for r in results if r["level"] == 0.5]
        self.panel = R(120, 150 if self.invaded else 104, 1040, 500)
        bx, by = self.panel.centerx, self.panel.bottom + S(16)
        self.btn_retry = Button((0, 0, 224, 52), "Tentar novamente", GREEN, "replay", 16, radius=14)
        self.btn_menu = Button((0, 0, 224, 52), "Trocar de local", ACCENT, "grid", 16, radius=14)
        self.btn_quit = Button((0, 0, 194, 52), "Sair do jogo", PANEL_3, "exit", 16, radius=14)
        self.btn_fs = Button((0, 0, 52, 52), "", PANEL_3, "expand", 18, radius=14)
        x = bx - (S(224) * 2 + S(194) + S(52) + S(36)) // 2
        for b in (self.btn_retry, self.btn_menu, self.btn_quit, self.btn_fs):
            b.rect.topleft = (x, by)
            x += b.rect.w + S(12)
        self.confetti = []
        self.stars_shown = 0
        self.banner_glow = pygame.transform.smoothscale(glow_surf(S(160), RED, 0.4), (S(1120), S(164)))
        if score >= 100:
            for _ in range(140):
                self.spawn_confetti(random.uniform(0, W), random.uniform(-H, 0))

    def spawn_confetti(self, x, y):
        self.confetti.append(dict(x=x, y=y, vx=random.uniform(-30, 30) * K, vy=random.uniform(60, 160) * K,
                                  r=random.uniform(0, 6.3), vr=random.uniform(-6, 6), s=random.uniform(5, 10) * K,
                                  c=random.choice([GREEN, GOLD, ACCENT, (255, 120, 170), (180, 130, 255), (255, 160, 70)])))

    def grade(self):
        n = self.game.player
        s = self.score
        place = "%s %s" % (self.loc["art"], self.loc["name"].lower())
        if s >= 100:
            return "Segurança impecável!", "Perfeito, %s! Cada ponto vulnerável recebeu a medida certa e nenhuma ameaça passou. %s está totalmente protegid%s." % (n, place[0].upper() + place[1:], self.loc["gender"])
        if s >= 75:
            return "Muito bom!", "Ótimo trabalho, %s! Quase tudo protegido. Ajuste os pontos marcados ao lado para chegar a 100%%." % n
        if s >= 50:
            return "Dá para melhorar", "%s, sua segurança segurou parte das ameaças, mas algumas brechas foram exploradas." % n
        return "Local vulnerável", "%s, %s ficou muito expost%s. Veja as medidas ideais ao lado e tente de novo!" % (n, place, self.loc["gender"])

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn_retry.hit(e.pos):
                key = self.key
                self.game.switch(lambda: PlayScene(self.game, key))
            elif self.btn_menu.hit(e.pos):
                self.game.switch(lambda: MenuScene(self.game))
            elif self.btn_quit.hit(e.pos):
                self.game.quit()
            elif self.btn_fs.hit(e.pos):
                self.game.toggle_fullscreen()
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                key = self.key
                self.game.switch(lambda: PlayScene(self.game, key))
            elif e.key == pygame.K_ESCAPE:
                self.game.switch(lambda: MenuScene(self.game))

    def update(self, dt):
        super().update(dt)
        mouse = mouse_pos()
        self.btn_fs.icon_kind = "compress" if self.game.fullscreen else "expand"
        for b in (self.btn_retry, self.btn_menu, self.btn_quit, self.btn_fs):
            b.update(dt, mouse)
        self.hover_row = None
        for i, rr in enumerate(self.row_rects):
            if rr and rr.collidepoint(mouse) and self.results[i]["level"] < 1:
                self.hover_row = i
        for c in self.confetti:
            c["x"] += c["vx"] * dt
            c["y"] += c["vy"] * dt
            c["r"] += c["vr"] * dt
            if c["y"] > H + S(20):
                c["y"] = random.uniform(-S(80), -S(10))
                c["x"] = random.uniform(0, W)

    def shown_score(self):
        return self.score * ease_out_cubic((self.t - 0.4) / 1.6)

    def draw(self, surf):
        surf.blit(self.bg, (0, 0))
        t = self.t
        if self.invaded:
            self.draw_banner(surf)
        p = ease_out_back((t - 0.1) / 0.5)
        pr = self.panel.copy()
        pr.y += int((1 - p) * S(40))
        a = int(255 * clamp((t - 0.05) / 0.3, 0, 1))
        draw_panel(surf, pr, PANEL, radius=S(22), shadow=True, shadow_alpha=150, border=(54, 66, 108), alpha=max(1, int(248 * a / 255)), top=(32, 40, 72))
        if a < 30:
            return
        lx = pr.x + S(200)
        at, asz = fit_text("AGENTE %s" % self.game.player.upper(), 15, S(350), True, 11)
        draw_text(surf, at, asz, (150, 182, 246), (lx, pr.y + S(26)), bold=True, anchor="center", alpha=a)
        sub = self.loc["name"]
        if self.hints_used:
            sub += "  •  %d dica%s usada%s" % (self.hints_used, "" if self.hints_used == 1 else "s", "" if self.hints_used == 1 else "s")
        draw_text(surf, ellipsize(sub, 14, S(350)), 14, MUTED, (lx, pr.y + S(48)), anchor="center", alpha=a)
        val = self.shown_score()
        col = GREEN if self.score >= 80 else AMBER if self.score >= 50 else RED
        cy = pr.y + S(180)
        self.draw_ring(surf, lx, cy, S(104), S(18), val / 100.0, col)
        draw_text(surf, "%d%%" % int(round(val)), 54, TEXT, (lx, cy - S(6)), bold=True, anchor="center")
        draw_text(surf, "de segurança", 15, MUTED, (lx, cy + S(34)), anchor="center")
        for i, th in enumerate((34, 67, 100)):
            sx = lx - S(60) + i * S(60)
            sy = cy + S(140)
            filled = val >= th - 0.5
            gfx.filled_circle(surf, sx, sy, S(25), (30, 38, 66))
            gfx.aacircle(surf, sx, sy, S(25), (44, 54, 90))
            if filled:
                if i >= self.stars_shown:
                    self.stars_shown = i + 1
                    self.burst_star(sx, sy)
                ic = icon("star", 40, GOLD)
            else:
                ic = icon("star", 40, (60, 70, 106))
            surf.blit(ic, ic.get_rect(center=(sx, sy)))
        title, msg = self.grade()
        ta = int(255 * clamp((t - 1.6) / 0.4, 0, 1))
        tt, tsz = fit_text(title, 26, S(350), True, 16)
        draw_text(surf, tt, tsz, col if self.score < 100 else GOLD, (lx, cy + S(196)), bold=True, anchor="center", alpha=ta)
        lines = wrap(msg, 15, S(340))
        msz = 15
        while len(lines) > 3 and msz > 12:
            msz -= 1
            lines = wrap(msg, msz, S(340))
        for i, ln in enumerate(lines[:4]):
            draw_text(surf, ln, msz, (206, 214, 236), (lx, cy + S(226) + i * font(msz).get_height()), anchor="center", alpha=ta)
        rx = pr.x + S(410)
        pygame.draw.line(surf, (46, 56, 94), (rx - S(22), pr.y + S(26)), (rx - S(22), pr.bottom - S(26)), max(1, S(1)))
        draw_text(surf, "RESUMO DA DEFESA", 15, (150, 182, 246), (rx, pr.y + S(26)), bold=True)
        legend = [("ok", "Ideal 100%"), ("partial", "Parcial 50%"), ("fail", "Invadido 0%")]
        lgx = pr.right - S(28)
        for st, lab in reversed(legend):
            w_ = font(13).size(lab)[0]
            lgx -= w_
            draw_text(surf, lab, 13, MUTED, (lgx, pr.y + S(28)))
            draw_status_icon(surf, lgx - S(13), pr.y + S(37), st, S(8))
            lgx -= S(34)
        y = pr.y + S(60)
        rw = pr.right - S(28) - rx
        self.row_rects = [None] * len(self.results)
        for i, r in enumerate(self.results):
            rp = ease_out_cubic((t - 0.5 - i * 0.12) / 0.4)
            if rp <= 0:
                y += S(70)
                continue
            st = "ok" if r["level"] >= 1 else "partial" if r["level"] > 0 else "fail"
            colr = {"ok": GREEN, "partial": AMBER, "fail": RED}[st]
            box = pygame.Rect(rx + int((1 - rp) * S(40)), y, rw, S(64))
            draw_panel(surf, box, PANEL_2, radius=S(12), shadow=False, alpha=int(255 * rp), top=(40, 50, 84), border=(48, 58, 96))
            pygame.draw.rect(surf, colr, (box.x, box.y + S(10), S(4), box.h - S(20)), border_radius=S(2))
            draw_status_icon(surf, box.x + S(28), box.centery, st, S(14))
            al = int(255 * rp)
            self.row_rects[i] = box
            mx = box.x + S(352)
            left_w = mx - S(15) - S(12) - (box.x + S(54))
            sn, ssz = fit_text(r["spot"], 16, left_w, True, 12)
            draw_text(surf, sn, ssz, TEXT, (box.x + S(54), box.y + S(9)), bold=True, alpha=al)
            draw_text(surf, ellipsize(r["threat"], 13, left_w), 13, MUTED, (box.x + S(54), box.y + S(33)), alpha=al)
            q_w = S(30) if st != "ok" else 0
            tw_max = box.right - (mx + S(24)) - S(10) - q_w
            if st != "ok":
                qx, qy = box.right - S(20), box.centery
                hov = self.hover_row == i
                gfx.filled_circle(surf, qx, qy, S(11), (255, 205, 80) if hov else (60, 72, 112))
                gfx.aacircle(surf, qx, qy, S(11), (255, 205, 80) if hov else (90, 104, 150))
                draw_text(surf, "?", 14, (40, 30, 0) if hov else TEXT, (qx, qy + S(1)), bold=True, anchor="center", alpha=al)
            if r["measure"]:
                gfx.filled_circle(surf, mx, box.centery, S(15), r["measure_color"])
                gfx.aacircle(surf, mx, box.centery, S(15), shade(r["measure_color"], 0.85))
                ic = icon(r["measure_icon"], 18)
                surf.blit(ic, ic.get_rect(center=(mx, box.centery)))
                txt, tsz = fit_text(r["measure"], 14, tw_max, True, 12)
                draw_text(surf, txt, tsz, TEXT, (mx + S(24), box.y + S(11)), bold=True, alpha=al)
            else:
                gfx.aacircle(surf, mx, box.centery, S(15), (100, 110, 140))
                draw_text(surf, "Nenhuma medida", 14, (196, 136, 136), (mx + S(24), box.y + S(11)), bold=True, alpha=al)
            if st == "ok":
                draw_text(surf, "Medida ideal!", 13, (136, 226, 166), (mx + S(24), box.y + S(34)), alpha=al)
            else:
                txt, tsz = fit_text("Ideal: " + r["ideal"], 13, tw_max, False, 11)
                draw_text(surf, txt, tsz, (255, 208, 126), (mx + S(24), box.y + S(34)), alpha=al)
            y += S(70)
        for b in (self.btn_retry, self.btn_menu, self.btn_quit, self.btn_fs):
            b.draw(surf)
        if self.hover_row is not None and self.row_rects[self.hover_row]:
            r = self.results[self.hover_row]
            box = self.row_rects[self.hover_row]
            specs = [("Por que %s?" % r["ideal"], 15, GOLD, True, 0), (r["ideal_desc"], 14, TEXT, False, 6),
                     ("Pista: " + r["hint"], 13, MUTED, False, 8)]
            text_box(surf, (box.right - S(20), box.y - S(6)), S(380), specs, accent=GOLD, where="above",
                     bounds=pygame.Rect(S(8), S(8), W - S(16), H - S(16)), border=(150, 120, 50))
        elif t > 2.2 and (self.invaded or self.partials):
            hint = "Passe o mouse no  ?  para entender cada medida ideal"
            draw_text(surf, hint, 13, SUBTLE, (pr.right - S(28), pr.bottom - S(22)), anchor="topright")
        for c in self.confetti:
            s = c["s"]
            ang = c["r"]
            pts = []
            for dx, dy in ((-s, -s * 0.4), (s, -s * 0.4), (s, s * 0.4), (-s, s * 0.4)):
                pts.append((int(c["x"] + dx * math.cos(ang) - dy * math.sin(ang)), int(c["y"] + dx * math.sin(ang) * 0.6 + dy * math.cos(ang))))
            gfx.filled_polygon(surf, pts, c["c"])

    def burst_star(self, x, y):
        for _ in range(12):
            a = random.uniform(0, math.tau)
            self.spawn_confetti(x + math.cos(a) * S(10), y + math.sin(a) * S(10))
            c = self.confetti[-1]
            c["vx"] = math.cos(a) * 120 * K
            c["vy"] = (math.sin(a) * 120 + 40) * K
            c["s"] = 4 * K

    def draw_ring(self, surf, cx, cy, r, w, frac, color):
        pygame.draw.circle(surf, (32, 40, 70), (cx, cy), r, w)
        gfx.aacircle(surf, cx, cy, r, (32, 40, 70))
        gfx.aacircle(surf, cx, cy, r - w + 1, (32, 40, 70))
        if frac <= 0.002:
            return
        a0 = 90.0
        a1 = 90.0 - 360.0 * min(frac, 0.9999)
        n = max(8, int(abs(a1 - a0) / 3))
        pts = []
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
        for i in range(n, -1, -1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.append((cx + (r - w) * math.cos(a), cy - (r - w) * math.sin(a)))
        ip = [ipt(q) for q in pts]
        gfx.filled_polygon(surf, ip, color)
        gfx.aapolygon(surf, ip, color)
        for a in (a0, a1):
            rad = math.radians(a)
            px, py = cx + (r - w / 2) * math.cos(rad), cy - (r - w / 2) * math.sin(rad)
            gfx.filled_circle(surf, int(px), int(py), int(w / 2), color)
            gfx.aacircle(surf, int(px), int(py), int(w / 2), color)

    def draw_banner(self, surf):
        t = self.t
        p = ease_out_back((t - 0.25) / 0.5)
        if p <= 0:
            return
        box = R(120, 26, 1040, 104)
        box.y += int((1 - p) * -S(80))
        pulse = 0.5 + 0.5 * math.sin(t * 4)
        gl = self.banner_glow
        gl.set_alpha(int(150 + 105 * pulse))
        surf.blit(gl, gl.get_rect(center=box.center))
        draw_panel(surf, box, (118, 22, 38), radius=S(18), shadow=True, shadow_alpha=140, border=mix((200, 50, 70), (255, 120, 130), pulse), border_w=max(2, S(2)), top=(150, 34, 52))
        ic = icon("warning", 50, (255, 230, 120))
        surf.blit(ic, (box.x + S(26), box.centery - ic.get_height() // 2))
        title = "%s %s FOI INVADID%s!" % (self.loc["art"].upper(), self.loc["name"].upper(), self.loc["gender"].upper())
        tt, tsz = fit_text(title, 28, box.w - S(130), True, 16)
        draw_text(surf, tt, tsz, (255, 255, 255), (box.x + S(96), box.y + S(14)), bold=True, shadow=(70, 10, 20))
        n = len(self.invaded)
        names = ", ".join(r["threat"][0].lower() + r["threat"][1:] for r in self.invaded)
        msg = "%s, %d ameaça%s passou%s pela sua segurança: %s." % (
            self.game.player, n, "" if n == 1 else "s", "" if n == 1 else "ram", names)
        lines = wrap(msg, 15, box.w - S(130))
        if len(lines) > 2:
            lines = lines[:2]
            lines[1] = ellipsize(lines[1] + " ...", 15, box.w - S(130))
        for i, ln in enumerate(lines):
            draw_text(surf, ln, 15, (255, 220, 220), (box.x + S(96), box.y + S(52) + i * min(S(22), font(15).get_height())))


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------
class Game:
    def __init__(self, scale=None, fullscreen=False):
        pygame.init()
        self.forced = scale
        self.fullscreen = fullscreen
        self.rescale_to = None
        self.open_display()
        apply_scale(self.target_scale())
        pygame.display.set_caption("Guardião - Missão Segurança")
        try:
            pygame.key.set_repeat(380, 40)
        except Exception:
            pass
        self.setup_canvas()
        self.clock = pygame.time.Clock()
        self.player = ""
        self.loc_key = None
        self.fade = 1.0
        self.fade_dir = -1
        self.pending = None
        self.running = True
        self.scene = LoadingScene(self, lambda: MenuScene(self))

    @staticmethod
    def auto_scale():
        dw = dh = 0
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except Exception:
            try:
                info = pygame.display.Info()
                dw, dh = info.current_w, info.current_h
            except Exception:
                pass
        if not dw or not dh:
            return 1.0
        k = min(dw * 0.94 / BASE_W, (dh - 80) * 0.94 / BASE_H)
        return max(0.6, min(3.0, round(k * 20) / 20.0))

    def target_scale(self):
        if self.fullscreen:
            sw, sh = self.screen.get_size()
            return min(sw / BASE_W, sh / BASE_H)
        return self.forced or self.auto_scale()

    def open_display(self):
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            k = self.forced or self.auto_scale()
            self.screen = pygame.display.set_mode((int(round(BASE_W * k)), int(round(BASE_H * k))))

    def setup_canvas(self):
        sw, sh = self.screen.get_size()
        if (sw, sh) == (W, H):
            self.canvas = self.screen
            self.present = (0, 0, 1.0)
        else:
            self.canvas = pygame.Surface((W, H))
            if W <= sw and H <= sh:
                self.present = ((sw - W) // 2, (sh - H) // 2, 1.0)
            else:
                k = min(sw / W, sh / H)
                self.present = (int((sw - W * k) / 2), int((sh - H * k) / 2), k)
        _MOUSE_OFF[0], _MOUSE_OFF[1], _MOUSE_OFF[2] = self.present
        self.fade_surf = pygame.Surface((W, H))
        self.fade_surf.fill((6, 8, 18))

    def toggle_fullscreen(self):
        sc = self.scene
        rebuild = None
        if isinstance(sc, LoadingScene):
            rebuild = sc.next
        elif isinstance(sc, MenuScene):
            self.player, self.loc_key = sc.name, sc.sel
            rebuild = lambda: MenuScene(self)
        elif isinstance(sc, PlayScene) and sc.phase == "build" and not sc.modal:
            key, pl, hl = sc.key, dict(sc.place), sc.hints_left
            rebuild = lambda: PlayScene(self, key, pl, hl)
        self.fullscreen = not self.fullscreen
        self.open_display()
        new_k = self.target_scale()
        if rebuild is not None and self.pending is None:
            apply_scale(new_k)
            self.rescale_to = None
            self.setup_canvas()
            self.fade, self.fade_dir = 1.0, -1
            self.scene = LoadingScene(self, rebuild)
        else:
            # no meio da simulação/resultado: a imagem é ajustada agora e
            # a resolução nativa é aplicada na próxima troca de tela
            self.rescale_to = new_k
            self.setup_canvas()

    def switch(self, factory):
        if self.pending is not None:
            return
        self.pending = factory
        self.fade_dir = 1

    def quit(self):
        self.running = False

    def step(self, dt):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.quit()
                continue
            if e.type == pygame.KEYDOWN and (e.key == pygame.K_F11 or (
                    e.key == pygame.K_RETURN and getattr(e, "mod", 0) & pygame.KMOD_ALT)):
                self.toggle_fullscreen()
                continue
            if self.present != (0, 0, 1.0) and hasattr(e, "pos"):
                d = dict(e.dict)
                d["pos"] = screen_to_canvas(e.pos)
                e = pygame.event.Event(e.type, **d)
            if self.pending is None and self.fade_dir <= 0:
                self.scene.handle(e)
        self.scene.update(dt)
        self.scene.draw(self.canvas)
        if self.fade_dir != 0:
            self.fade += self.fade_dir * dt / 0.32
            if self.fade_dir > 0 and self.fade >= 1.0:
                self.fade = 1.0
                factory, self.pending = self.pending, None
                if self.rescale_to is not None:
                    apply_scale(self.rescale_to)
                    self.rescale_to = None
                    self.setup_canvas()
                    self.scene = LoadingScene(self, factory)
                else:
                    self.scene = factory()
                self.fade_dir = -1
            elif self.fade_dir < 0 and self.fade <= 0.0:
                self.fade = 0.0
                self.fade_dir = 0
        if self.fade > 0:
            self.fade_surf.set_alpha(int(255 * ease_in_out(self.fade)))
            self.canvas.blit(self.fade_surf, (0, 0))
        if self.canvas is not self.screen:
            self.screen.fill((0, 0, 0))
            ox, oy, k = self.present
            if k == 1.0:
                self.screen.blit(self.canvas, (ox, oy))
            else:
                self.screen.blit(pygame.transform.smoothscale(self.canvas, (int(W * k), int(H * k))), (ox, oy))
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self.step(dt)
        pygame.quit()


def main():
    scale = None
    args = sys.argv[1:]
    if "--escala" in args:
        try:
            scale = float(args[args.index("--escala") + 1].replace(",", "."))
        except (IndexError, ValueError):
            scale = None
    env = os.environ.get("GUARDIAO_ESCALA")
    if scale is None and env:
        try:
            scale = float(env.replace(",", "."))
        except ValueError:
            pass
    if scale is not None:
        scale = max(0.5, min(4.0, scale))
    full = "--tela-cheia" in args or os.environ.get("GUARDIAO_TELA_CHEIA") == "1"
    Game(scale, full).run()
    sys.exit(0)


if __name__ == "__main__":
    main()
