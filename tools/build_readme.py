#!/usr/bin/env python3
"""Génère les SVG de assets/ et le README.md du profil, au design system MERZA V2.

Usage :
    pip install fonttools uharfbuzz
    MERZA_DS=/chemin/vers/MERZA_DESIGN_SYSTEM_V2 python tools/build_readme.py

Le texte est converti en tracés, car un SVG chargé par <img> ne peut pas utiliser de
police externe. Aucun fichier de police n'est copié dans ce repo. Pour changer la
disponibilité ou le contenu, modifier les constantes ci-dessous puis relancer le script.
"""
from __future__ import annotations

import html
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

NB = " "  # espace insécable

# ---------------------------------------------------------------- contenu
# Mettre AVAILABLE à None retire le badge de disponibilité.
AVAILABLE = "mi-novembre 2026"
AVAILABLE_SHORT = "mi-novembre"

NAME = "Nicolas Duchemann"
ROLE = "Développeur full-stack senior · TypeScript, Python, LLM"
TITLE_LINES = ["Applications métier", "et IA, du cadrage", "à la production"]
LEAD = (
    "Sept ans d’ingénierie logicielle sur des plateformes SaaS, l’immobilier, l’industrie "
    "et l’IoT. J’interviens en mission, en full remote ou en hybride en France."
)

URL_CALL = "https://meetings-eu1.hubspot.com/nicolas-duchemann"
URL_WORK = "https://merza.fr/realisations"
URL_SITE = "https://merza.fr"
URL_MAIL = "mailto:nicolas@merza.fr"
URL_LINKEDIN = "https://www.linkedin.com/in/nicolas-duchemann-91087510b/"

METRICS = [
    ("Audit thermique", f"−70{NB}%", None, "de durée d’audit · IDELE, KeepCool"),
    ("Support client", f"5{NB}000+", "tickets", "sur environ 2 mois · agents IA SAV"),
    ("Supervision", "24/7", None, "surveillance IA · Tell Élevage"),
]

WORK_TITLE = "Quatre réalisations récentes"
WORK = [
    (
        "JeLotis",
        "Immobilier, valorisation foncière",
        "Parcours cartographique, moteur de valorisation foncière, intégration HubSpot "
        "et suivi des conversions avec PostHog.",
        "Next.js · NestJS · TypeScript",
    ),
    (
        "IDELE, KeepCool",
        "Élevage, diagnostic thermique",
        f"Diagnostic thermique des bâtiments d’élevage{NB}: plans interactifs, heatmaps, "
        "calculs THI/HLI et rapports PDF.",
        "Angular · NestJS",
    ),
    (
        "Agents IA pour le SAV",
        "Fabricant européen de signalétique",
        "Analyse des tickets Zendesk en temps réel, consultation des commandes et "
        "rédaction automatique des réponses.",
        "Vue.js · Nuxt · Fastify · RAG",
    ),
    (
        "Tell Élevage, TellCozy",
        "Élevage, supervision",
        f"Supervision IA des élevages{NB}: vision par ordinateur, surveillance 24/7 et "
        "rapports quotidiens.",
        "IA · Vision par ordinateur",
    ),
]

STACK_TITLE = "Stack technique, de l’interface au déploiement"
STACK = [
    ("Frontend", "TypeScript · React · Next.js · Angular · Vue.js"),
    ("Backend", "Node.js · NestJS · Python · FastAPI · Django"),
    ("IA", "LLM · RAG · Vision par ordinateur · PyTorch"),
    ("Données", "PostgreSQL · MongoDB · Redis · Kafka · RabbitMQ"),
    ("Cloud", "Docker · Kubernetes · Helm · AWS · Azure"),
    ("Qualité", "Jest · Vitest · Cypress · CI/CD"),
    ("Intégrations", "HubSpot · PostHog · Zendesk · n8n · Make"),
]

CAREER_TITLE = "Parcours depuis 2019"
CAREER_HEAD = ("Période", "Poste", "Entreprise")
CAREER = [
    (f"Depuis janv.{NB}2026", "Développeur full-stack senior, indépendant", "MERZA"),
    (f"août à déc.{NB}2025", "Développeur full-stack, ERP Millenium", "Emeria Technologies"),
    ("2023 à 2025", "CTO, vision par ordinateur pour Kruger et General Electric", "Technova Industries"),
    ("2022 à 2024", "Ingénieur logiciel freelance", "Ansys"),
    ("2022", "Développeur backend freelance", "Bouygues Telecom"),
    ("2022", "Ingénieur logiciel freelance", "Safran"),
    ("2019 à 2022", "Ingénieur logiciel", "REDLAB"),
]
EDUCATION = (
    f"Formation{NB}: diplôme d’ingénieur EFREI (2015 à 2019), MBA Management et Data Science, "
    "Paris Sorbonne (2025 à 2026)."
)

CONTACT_TITLE = "Parlons de votre besoin"
CONTACT_SUB = f"Premier retour structuré sous 48{NB}h."

# ---------------------------------------------------------------- tokens MERZA V2
# Une seule variante, sombre et opaque : elle reste lisible quel que soit le thème de la page.
# Un README ne peut pas suivre le thème GitHub de façon fiable : prefers-color-scheme suit le
# système, et GitHub ne tient plus compte des suffixes #gh-dark-mode-only (testé en novembre 2026).
THEME = dict(
    canvas="#0A0B0D", panel="#121419", subtle="#2A2F38", strong="#3D4350",
    text="#E7EAEF", text2="#AAB0BB", text3="#8A919E",
    gold="#E7B44C", on_gold="#0A0B0D",
    ok="#46C98B", ok_bg="#182A27", ok_line="#265944",
)
LOGO = "merza-wordmark-sur-sombre.svg"

ICONS = {
    "ok": '<circle cx="12" cy="12" r="8.5"/><path d="m8.3 12.3 2.6 2.6 4.9-5.4"/>',
    "external": '<path d="M8 16 16 8M9.5 8H16v6.5"/>',
    "mail": '<rect x="3.5" y="5.5" width="17" height="13"/><path d="m4 6.5 8 6 8-6"/>',
}

FONT_FILES = {
    "sans400": "InstrumentSans-400.ttf",
    "sans500": "InstrumentSans-500.ttf",
    "sans600": "InstrumentSans-600.ttf",
    "mono400": "IBMPlexMono-400.ttf",
    "mono500": "IBMPlexMono-500.ttf",
    "display600": "ClashDisplay-Semibold.ttf",
}


@dataclass(frozen=True)
class Style:
    font: str
    size: float
    lh: float
    ls: float = 0.0  # interlettrage en em
    upper: bool = False


DISPLAY_XL = Style("display600", 64, 60, -0.02)
DISPLAY_M = Style("display600", 34, 38, -0.015)
DISPLAY_S = Style("display600", 30, 34, -0.015)  # mobile : « Applications métier » tient sur une ligne
TITLE_M = Style("sans600", 22, 28, -0.01)
HEADING = Style("sans600", 15, 20, -0.005)
BODY_L = Style("sans400", 16, 24)
NATIVE_BODY = Style("sans400", 16, 22)
BODY_M = Style("sans400", 14, 20)
BODY_S = Style("sans400", 13, 18)
CAPTION = Style("sans400", 12, 16)
DATA_M = Style("mono400", 13, 18)
DATA_S = Style("mono400", 12, 16)
LABEL = Style("mono500", 11, 14, 0.06, True)
METRIC_V = Style("mono500", 24, 28, -0.02)
METRIC_U = Style("mono400", 13, 16)
BADGE = Style("sans500", 13, 16)
ROW_B = Style("sans500", 14, 18)


class Font:
    def __init__(self, path: Path):
        self.tt = TTFont(path)
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        self.asc = self.tt["hhea"].ascent
        self.desc = -self.tt["hhea"].descent
        self.hb = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self.path = path

    def shape(self, text: str, ls_em: float):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": ls_em == 0})
        out = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            if info.codepoint == 0:
                raise SystemExit(f"Glyphe manquant dans {self.path.name} pour : {text!r}")
            out.append((self.order[info.codepoint], pos.x_advance, pos.x_offset, pos.y_offset))
        return out


def num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class Type:
    """Mesure, coupe et trace le texte à partir des polices du design system."""

    def __init__(self, fonts_dir: Path):
        self.fonts = {k: Font(fonts_dir / v) for k, v in FONT_FILES.items()}

    def _text(self, text: str, st: Style) -> str:
        return text.upper() if st.upper else text

    def width(self, text: str, st: Style) -> float:
        f = self.fonts[st.font]
        scale = st.size / f.upem
        run = f.shape(self._text(text, st), st.ls)
        return sum(a * scale + st.ls * st.size for _, a, _, _ in run)

    def baseline(self, top: float, st: Style) -> float:
        f = self.fonts[st.font]
        scale = st.size / f.upem
        return top + (st.lh - (f.asc + f.desc) * scale) / 2 + f.asc * scale

    def wrap(self, text: str, st: Style, width: float) -> list[str]:
        # Un séparateur « · » reste en fin de ligne, jamais en début.
        words = text.replace(" · ", f"{NB}· ").split(" ")
        lines, cur = [], ""
        for w in words:
            trial = f"{cur} {w}" if cur else w
            if cur and self.width(trial, st) > width:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        if cur:
            lines.append(cur)
        return lines


class Svg:
    def __init__(self, ty: Type, w: float, t: dict, ds: Path, defs: dict | None = None):
        self.ty, self.w, self.t, self.ds = ty, w, t, ds
        self.h = 0.0
        self.parts: list[str] = []
        # Chaque glyphe n'est tracé qu'une fois, y compris entre les sections d'une même image.
        self.defs: dict[tuple[str, str], tuple[str, str]] = {} if defs is None else defs

    def _glyph(self, font: str, name: str) -> str | None:
        key = (font, name)
        if key not in self.defs:
            f = self.ty.fonts[font]
            pen = SVGPathPen(f.glyphs, ntos=num)
            f.glyphs[name].draw(pen)
            self.defs[key] = (f"g{len(self.defs)}", pen.getCommands())
        gid, d = self.defs[key]
        return gid if d else None

    def at_baseline(self, text, x, baseline, st, color):
        f = self.ty.fonts[st.font]
        k = st.size / f.upem
        cur, uses = 0.0, []
        for name, adv, ox, oy in f.shape(self.ty._text(text, st), st.ls):
            gid = self._glyph(st.font, name)
            if gid:
                y = f' y="{oy}"' if oy else ""
                uses.append(f'<use href="#{gid}" x="{round(cur + ox)}"{y}/>')
            cur += adv + st.ls * f.upem
        self.parts.append(
            f'<g fill="{color}" transform="translate({num(x)} {num(baseline)}) scale({k:.5f} {-k:.5f})">'
            + "".join(uses) + "</g>"
        )

    def text(self, text, x, top, st, color, anchor="start"):
        if anchor == "end":
            x -= self.ty.width(text, st)
        elif anchor == "middle":
            x -= self.ty.width(text, st) / 2
        self.at_baseline(text, x, self.ty.baseline(top, st), st, color)

    def para(self, text, x, top, st, color, width) -> float:
        lines = self.ty.wrap(text, st, width)
        for i, line in enumerate(lines):
            self.text(line, x, top + i * st.lh, st, color)
        return len(lines) * st.lh

    def para_height(self, text, st, width) -> float:
        return len(self.ty.wrap(text, st, width)) * st.lh

    def box(self, x, y, w, h, r, fill=None, stroke=None):
        fill_attr = f'fill="{fill}"' if fill else 'fill="none"'
        stroke_attr = f' stroke="{stroke}"' if stroke else ""
        self.parts.append(
            f'<rect x="{num(x + .5)}" y="{num(y + .5)}" width="{num(w - 1)}" height="{num(h - 1)}" '
            f'rx="{num(max(r - .5, 0))}" {fill_attr}{stroke_attr}/>'
        )

    def hline(self, x1, x2, y, color):
        self.parts.append(f'<rect x="{num(x1)}" y="{num(y)}" width="{num(x2 - x1)}" height="1" fill="{color}"/>')

    def vline(self, x, y1, y2, color):
        self.parts.append(f'<rect x="{num(x)}" y="{num(y1)}" width="1" height="{num(y2 - y1)}" fill="{color}"/>')

    def panel(self, x, y, w, h, r):
        self.box(x, y, w, h, r, self.t["panel"], self.t["subtle"])
        # shadow-raised du thème sombre : arête claire de 1 px
        self.parts.append(
            f'<rect x="{num(x + r)}" y="{num(y + 1)}" width="{num(w - 2 * r)}" height="1" '
            'fill="#fff" fill-opacity=".04"/>'
        )

    def icon(self, name, x, y, size, color, stroke=1.5):
        k = size / 24
        self.parts.append(
            f'<g transform="translate({num(x)} {num(y)}) scale({k:.4f})" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="square" stroke-linejoin="miter">{ICONS[name]}</g>'
        )

    def logo(self, x, y, h):
        src = (self.ds / "assets" / "logos" / LOGO).read_text(encoding="utf-8")
        inner = re.sub(r"<title>.*?</title>", "", re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1), flags=re.S)
        w = h * 3917.1 / 670
        self.parts.append(
            f'<svg x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" viewBox="0 0 3917.1 670">{inner}</svg>'
        )

    def render(self, title: str, sheet: "Device | None" = None) -> str:
        """Assemble le SVG. Avec `sheet`, le contenu est posé sur un fond opaque et arrondi."""
        body = "".join(self.parts)
        width, height = self.w, self.h
        if sheet:
            width, height = sheet.total, self.h + 2 * sheet.pad_y
            backdrop = Svg(self.ty, width, self.t, self.ds)
            backdrop.box(0, 0, width, height, sheet.sheet_radius, self.t["canvas"], self.t["subtle"])
            body = (
                "".join(backdrop.parts)
                + f'<g transform="translate({sheet.pad} {sheet.pad_y})">{body}</g>'
            )
        w, h = num(width), num(height)
        defs = "".join(f'<path id="{gid}" d="{d}"/>' for gid, d in self.defs.values() if d)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{html.escape(title)}"><title>{html.escape(title)}</title>'
            f"<defs>{defs}</defs>{body}</svg>\n"
        )


# ---------------------------------------------------------------- tranches
@dataclass(frozen=True)
class Device:
    name: str
    w: int              # largeur du contenu
    gap: int            # espace entre sections
    radius: int         # rayon des panneaux
    mobile: bool
    pad: int            # marges horizontales du fond
    pad_y: int          # marges verticales du fond
    sheet_radius: int   # rayon du fond

    @property
    def total(self) -> int:
        return self.w + 2 * self.pad


DESKTOP = Device("desktop", 784, 56, 6, False, 32, 40, 10)  # 848 px, la colonne GitHub du profil en fait 846
MOBILE = Device("mobile", 292, 40, 10, True, 16, 24, 14)    # 324 px, la colonne GitHub sur un écran de 390 px


def hero(s: Svg, d: Device):
    t = s.t
    s.logo(0, (24 - (18 if d.mobile else 20)) / 2, 18 if d.mobile else 20)
    if AVAILABLE:
        label = f"Disponible · {AVAILABLE_SHORT if d.mobile else AVAILABLE}"
        bw = 1 + 6 + 12 + 4 + s.ty.width(label, BADGE) + 8 + 1
        bx = d.w - bw
        s.box(bx, 0, bw, 24, 2, t["ok_bg"], t["ok_line"])
        s.icon("ok", bx + 7, 6, 12, t["ok"], 1.8)
        s.text(label, bx + 7 + 12 + 4, 4, BADGE, t["ok"])
    y = 24 + (40 if d.mobile else 64)
    s.text(NAME, 0, y, TITLE_M, t["text"])
    y += TITLE_M.lh + 4
    role_st = NATIVE_BODY if d.mobile else BODY_L
    y += s.para(ROLE, 0, y, role_st, t["text2"], d.w)
    y += 16 if d.mobile else 20
    h1 = DISPLAY_S if d.mobile else DISPLAY_XL
    for line in TITLE_LINES:
        s.text(line, 0, y, h1, t["text"])
        y += h1.lh
    y += 16 if d.mobile else 20
    y += s.para(LEAD, 0, y, BODY_L, t["text2"], d.w if d.mobile else 640)
    s.h = y


def metrics(s: Svg, d: Device):
    t = s.t
    top = 0
    n = len(METRICS)
    cw = d.w if d.mobile else d.w / n
    tw = cw - 2 - 32 if d.mobile else cw - 32

    def cell_h(item):
        return 12 + LABEL.lh + 6 + METRIC_V.lh + 6 + s.para_height(item[3], CAPTION, tw) + 12

    heights = [cell_h(m) for m in METRICS]
    total = sum(heights) + 2 if d.mobile else max(heights) + 2
    s.panel(0, top, d.w, total, d.radius)
    y = top + 1
    for i, (label, value, unit, desc) in enumerate(METRICS):
        x = 1 + 16 if d.mobile else i * cw + 16 + (1 if i == 0 else 0)
        cy = y if d.mobile else top + 1
        if i:
            if d.mobile:
                s.hline(1, d.w - 1, cy - 0.5, t["subtle"])
            else:
                s.vline(i * cw, top + 1, top + total - 1, t["subtle"])
        s.text(label, x, cy + 12, LABEL, t["text3"])
        vy = cy + 12 + LABEL.lh + 6
        base = s.ty.baseline(vy, METRIC_V)
        s.at_baseline(value, x, base, METRIC_V, t["text"])
        if unit:
            s.at_baseline(unit, x + s.ty.width(value, METRIC_V) + 8, base, METRIC_U, t["text3"])
        s.para(desc, x, vy + METRIC_V.lh + 6, CAPTION, t["text3"], tw)
        if d.mobile:
            y += heights[i]
    s.h = top + total


def heading(s: Svg, d: Device, title: str) -> float:
    return s.para(title, 0, 0, TITLE_M, s.t["text"], d.w)


def work(s: Svg, d: Device):
    t = s.t
    y = heading(s, d, WORK_TITLE) + (12 if d.mobile else 16)
    gap = 12 if d.mobile else 16
    cols = 1 if d.mobile else 2
    cw = (d.w - gap * (cols - 1)) / cols
    inner = cw - 2 - 32
    desc_st = BODY_M if d.mobile else BODY_S

    def card_h(c):
        return 1 + 16 + HEADING.lh + 2 + CAPTION.lh + 12 + s.para_height(c[2], desc_st, inner) + 12 + DATA_S.lh + 16 + 1

    for r in range(0, len(WORK), cols):
        row = WORK[r:r + cols]
        h = max(card_h(c) for c in row)
        for i, (name, sector, desc, tech) in enumerate(row):
            x = i * (cw + gap)
            s.panel(x, y, cw, h, d.radius)
            ix, iy = x + 17, y + 17
            s.text(name, ix, iy, HEADING, t["text"])
            s.text(sector, ix, iy + HEADING.lh + 2, CAPTION, t["text3"])
            s.icon("external", x + cw - 17 - 16, iy, 16, t["text3"])
            s.para(desc, ix, iy + HEADING.lh + 2 + CAPTION.lh + 12, desc_st, t["text2"], inner)
            s.text(tech, ix, y + h - 17 - DATA_S.lh, DATA_S, t["text3"])
        y += h + gap
    s.h = y - gap


def stack(s: Svg, d: Device):
    t = s.t
    y = heading(s, d, STACK_TITLE) + (12 if d.mobile else 16)
    if d.mobile:
        tw = d.w - 2 - 32
        rows = [12 + LABEL.lh + 4 + s.para_height(v, DATA_M, tw) + 12 for _, v in STACK]
        total = sum(rows) + 2
        s.panel(0, y, d.w, total, d.radius)
        cy = y + 1
        for i, (k, v) in enumerate(STACK):
            if i:
                s.hline(1, d.w - 1, cy - 0.5, t["subtle"])
            s.text(k, 17, cy + 12, LABEL, t["text3"])
            s.para(v, 17, cy + 12 + LABEL.lh + 4, DATA_M, t["text"], tw)
            cy += rows[i]
    else:
        total = len(STACK) * 40 + 2
        s.panel(0, y, d.w, total, d.radius)
        for i, (k, v) in enumerate(STACK):
            ry = y + 1 + i * 40
            if i:
                s.hline(1, d.w - 1, ry - 0.5, t["subtle"])
            s.text(k, 1 + 12, ry + (40 - LABEL.lh) / 2, LABEL, t["text3"])
            s.text(v, 1 + 152 + 12, ry + (40 - DATA_M.lh) / 2, DATA_M, t["text"])
    s.h = y + total


def career(s: Svg, d: Device):
    t = s.t
    y = heading(s, d, CAREER_TITLE) + (12 if d.mobile else 16)
    if d.mobile:
        tw = d.w - 2 - 24
        rows = [12 + ROW_B.lh + 4 + s.para_height(r[1], BODY_S, tw) + 12 for r in CAREER]
        total = sum(rows) + 2
        s.panel(0, y, d.w, total, d.radius)
        cy = y + 1
        for i, (period, role, company) in enumerate(CAREER):
            if i:
                s.hline(1, d.w - 1, cy - 0.5, t["subtle"])
            s.text(company, 13, cy + 12, ROW_B, t["text"])
            s.text(period, d.w - 13, cy + 12 + 1, DATA_S, t["text3"], "end")
            s.para(role, 13, cy + 12 + ROW_B.lh + 4, BODY_S, t["text2"], tw)
            cy += rows[i]
    else:
        total = 32 + len(CAREER) * 40 + 2
        s.panel(0, y, d.w, total, d.radius)
        col = [1, 1 + 172, d.w - 1 - 184]
        for x, label in zip(col, CAREER_HEAD):
            s.text(label, x + 12, y + 1 + (32 - LABEL.lh) / 2, LABEL, t["text3"])
        s.hline(1, d.w - 1, y + 1 + 31, t["strong"])
        for i, (period, role, company) in enumerate(CAREER):
            ry = y + 1 + 32 + i * 40
            if i:
                s.hline(1, d.w - 1, ry - 0.5, t["subtle"])
            s.text(period, col[0] + 12, ry + (40 - DATA_M.lh) / 2, DATA_M, t["text"])
            s.text(role, col[1] + 12, ry + (40 - BODY_S.lh) / 2, BODY_S, t["text"])
            s.text(company, col[2] + 12, ry + (40 - BODY_S.lh) / 2, BODY_S, t["text"])
    y += total + 12
    y += s.para(EDUCATION, 0, y, CAPTION, t["text3"], d.w)
    s.h = y


def body(s: Svg, d: Device):
    """Résultats, réalisations, stack et parcours sur un seul fond, sans coupure entre sections."""
    y = 0.0
    for i, section in enumerate((metrics, work, stack, career)):
        part = Svg(s.ty, d.w, s.t, s.ds, s.defs)
        section(part, d)
        y += d.gap if i else 0
        s.parts.append(f'<g transform="translate(0 {num(y)})">{"".join(part.parts)}</g>')
        y += part.h
    s.h = y


def contact(s: Svg, d: Device):
    t = s.t
    y = s.para(CONTACT_TITLE, 0, 0, DISPLAY_S if d.mobile else DISPLAY_M, t["text"], d.w)
    y += 8
    y += s.para(CONTACT_SUB, 0, y, BODY_L, t["text2"], d.w)
    s.h = y


SECTIONS = {"hero": hero, "body": body, "contact": contact}

BUTTONS = {
    "btn-call": ("Réserver un appel", None, True),
    "btn-work": ("Voir les réalisations", None, False),
    "btn-mail": ("nicolas@merza.fr", "mail", False),
    "btn-site": ("merza.fr", "external", False),
    "btn-linkedin": ("LinkedIn", "external", False),
}


def button(s: Svg, d: Device, label: str, icon: str | None, primary: bool):
    t = s.t
    size = 16 if d.mobile else 14
    st = Style("sans600" if primary else "sans500", size, 16)
    tw = s.ty.width(label, st)
    content = tw + (16 + 6 if icon else 0)
    fg = t["on_gold"] if primary else t["text"]
    # Le canevas fait 48 px de haut : c'est la zone cliquable, à la taille tactile du système.
    if d.mobile:
        bw, by, bh, r = d.total, 0, 48, 10
    else:
        bw, by, bh, r = content + 2 + 32, 4, 40, 4
    s.w = d.total if d.mobile else bw + 4  # 4 px + l'espace HTML donnent l'écart de 8 px entre boutons
    s.h = 48
    if primary:
        s.parts.append(
            f'<rect x="0" y="{by}" width="{num(bw)}" height="{bh}" rx="{r}" fill="{t["gold"]}"/>'
        )
    else:  # fond opaque : le libellé reste lisible sur une page claire comme sombre
        s.box(0, by, bw, bh, r, t["canvas"], t["strong"])
    x = (bw - content) / 2
    if icon:
        s.icon(icon, x, by + (bh - 16) / 2, 16, fg)
        x += 16 + 6
    s.text(label, x, by + (bh - st.lh) / 2, st, fg)


# ---------------------------------------------------------------- README
def alt_text() -> dict[str, str]:
    status = f"Disponible {AVAILABLE}. " if AVAILABLE else ""
    return {
        "hero": f"MERZA. {status}{NAME}, {ROLE}. {' '.join(TITLE_LINES)}. {LEAD}",
        "body": " ".join((
            " ".join(f"{k} : {v}{' ' + u if u else ''} {x}." for k, v, u, x in METRICS),
            f"{WORK_TITLE}.", " ".join(f"{a}, {b}. {c} {e}." for a, b, c, e in WORK),
            f"{STACK_TITLE}.", " ".join(f"{k} : {v}." for k, v in STACK),
            f"{CAREER_TITLE}.", " ".join(f"{a} : {b}, {c}." for a, b, c in CAREER), EDUCATION,
        )),
        "contact": f"{CONTACT_TITLE}. {CONTACT_SUB}",
    }


def picture(name: str, alt: str, size_attr: str) -> str:
    return (
        "<picture>"
        f'<source media="(max-width: 600px)" srcset="assets/mobile/{name}.svg">'
        f'<img src="assets/desktop/{name}.svg" alt="{html.escape(alt)}" {size_attr}>'
        "</picture>"
    )


def link(url: str, name: str, alt: str, size_attr: str) -> str:
    return f'<a href="{url}">{picture(name, alt, size_attr)}</a>'


def readme() -> str:
    alts = alt_text()
    full = 'width="100%"'
    btn = 'height="48"'

    def section(name, url):
        return f"<p>\n{link(url, name, alts[name], full)}\n</p>\n"

    def buttons(*items):
        rows = "\n".join(link(url, name, BUTTONS[name][0], btn) for name, url in items)
        return f"<p>\n{rows}\n</p>\n"

    blocks = [
        section("hero", URL_SITE),
        buttons(("btn-call", URL_CALL), ("btn-work", URL_WORK)),
        section("body", URL_WORK),
        section("contact", URL_CALL),
        buttons(("btn-mail", URL_MAIL), ("btn-site", URL_SITE), ("btn-linkedin", URL_LINKEDIN)),
    ]
    return "<!-- Généré par tools/build_readme.py. Modifier le script, pas ce fichier. -->\n\n" + "\n".join(blocks)


def main() -> None:
    ds_env = os.environ.get("MERZA_DS")
    if not ds_env:
        sys.exit("Définir MERZA_DS avec le chemin du dossier MERZA_DESIGN_SYSTEM_V2.")
    ds = Path(ds_env)
    repo = Path(__file__).resolve().parent.parent
    ty = Type(ds / "fonts" / "native")
    out = repo / "assets"
    if out.exists():
        shutil.rmtree(out)
    alts = alt_text()
    for d in (DESKTOP, MOBILE):
        folder = out / d.name
        folder.mkdir(parents=True)
        for name, fn in SECTIONS.items():
            s = Svg(ty, d.w, THEME, ds)
            fn(s, d)
            (folder / f"{name}.svg").write_text(s.render(alts[name], d), encoding="utf-8", newline="\n")
        for name, (label, icon, primary) in BUTTONS.items():
            s = Svg(ty, d.w, THEME, ds)
            button(s, d, label, icon, primary)
            (folder / f"{name}.svg").write_text(s.render(label), encoding="utf-8", newline="\n")
    (repo / "README.md").write_text(readme(), encoding="utf-8", newline="\n")
    print("README.md et", sum(1 for _ in out.rglob("*.svg")), "SVG générés.")


if __name__ == "__main__":
    main()
