
import os
import os
import re
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import platform
import subprocess
import webbrowser

# ---------- External libs ----------
try:
    import fitz  # PyMuPDF
except Exception as e:
    raise SystemExit("PyMuPDF (fitz) este necesar. Instalează cu: pip install pymupdf") from e

# rectpack (compat, diferite versiuni)
try:
    import rectpack
    from rectpack import newPacker
    try:
        from rectpack import PackingMode, PackingBin
    except Exception:
        PackingMode = type("PM", (), {"Offline": 0, "Online": 1})
        PackingBin = type("PB", (), {"Global": 0})
    def _get(obj, name):
        return getattr(rectpack, name, None)
    ALGO_NAMES = [
        # MaxRects
        "MaxRectsBl","MaxRectsBssf","MaxRectsBaf","MaxRectsBlsf",
        # Skyline
        "SkylineBl","SkylineBlWm","SkylineMwf","SkylineMwfl","SkylineMwfWm","SkylineMwflWm",
        # Guillotine
        "GuillotineBssfSas","GuillotineBssfLas","GuillotineBssfSlas","GuillotineBssfLlas","GuillotineBssfMaxas","GuillotineBssfMinas",
        "GuillotineBlsfSas","GuillotineBlsfLas","GuillotineBlsfSlas","GuillotineBlsfLlas","GuillotineBlsfMaxas","GuillotineBlsfMinas",
        "GuillotineBafSas","GuillotineBafLas","GuillotineBafSlas","GuillotineBafLlas","GuillotineBafMaxas","GuillotineBafMinas",
    ]
    PACK_ALGOS = [ _get(rectpack, n) for n in ALGO_NAMES if _get(rectpack, n) is not None ]
    if not PACK_ALGOS:
        for n in ["MaxRectsBssf","MaxRectsBlsf","SkylineBl"]:
            a = _get(rectpack, n)
            if a: PACK_ALGOS.append(a)
    SORT_ALGOS = [ _get(rectpack, n) for n in ["SORT_AREA","SORT_PERI","SORT_RATIO","SORT_LSIDE","SORT_SSIDE","SORT_DIFF"] if _get(rectpack, n) is not None ]
    BIN_ALGOS  = []
    for n in ["BBF","BFF","BNF","Global"]:
        try:
            BIN_ALGOS.append(getattr(PackingBin, n))
        except Exception:
            pass
    if not BIN_ALGOS:
        BIN_ALGOS = [getattr(PackingBin, "Global", 0)]
except Exception as e:
    raise SystemExit("rectpack este necesar. Instalează cu: pip install rectpack") from e

# ---------- Units ----------
PT_PER_MM = 72.0 / 25.4
def mm_to_pt(mm: float) -> float: return float(mm) * PT_PER_MM
def cm_to_mm(cm: float) -> float: return float(cm) * 10.0

# ---------- Files pattern ----------
RE_REPS = re.compile(r"(?:_)?#(\d+)\.pdf$", re.I)

# ---------- Sheet presets ----------
PREDEFINED_SHEETS_MM = {
    "70x50 cm": (700.0, 500.0),
    "100x70 cm": (1000.0, 700.0),
    "64x45 cm": (640.0, 450.0),
    "64x44 cm": (640.0, 440.0),
    "50x35 cm": (500.0, 350.0),
    "48.7x32 cm": (487.0, 320.0),
    "A2 (594x420 mm)": (594.0, 420.0),
    "A1 (841x594 mm)": (841.0, 594.0),
    "A4 29.7x21 cm": (297.0, 210.0),
    "Custom (cm)": None,
}

MODE_FRONTS_ONLY = "fronts_only"
MODE_FRONTS_BACKS_SEPARATE = "fronts_backs_separate"
MODE_PAIRED_SAME_PAGE = "paired_same_page"

# ---------- Loading PDFs ----------
def gather_leaves(folder):
    leaves = []
    for fname in os.listdir(folder):
        if not fname.lower().endswith(".pdf"):
            continue
        m = RE_REPS.search(fname)
        if not m:
            continue
        reps = int(m.group(1))
        path = os.path.join(folder, fname)
        try:
            doc = fitz.open(path)
        except Exception as e:
            print("[WARN] cannot open", fname, e)
            continue
        base = RE_REPS.sub(".pdf", fname).lower()
        w0 = float(doc[0].rect.width); h0 = float(doc[0].rect.height)
        for _ in range(reps):
            leaves.append({"path": path, "page": 0, "w": w0, "h": h0, "is_back": False, "base": base})
        if doc.page_count >= 2:
            w1 = float(doc[1].rect.width); h1 = float(doc[1].rect.height)
            for _ in range(reps):
                leaves.append({"path": path, "page": 1, "w": w1, "h": h1, "is_back": True, "base": base})
        doc.close()
    return leaves

# ---------- Rendering ----------
def draw_sheet(doc, page_w, page_h):
    return doc.new_page(width=page_w, height=page_h)

def _draw_all_slot_trims_outside_only(page, placements, margin_left, margin_top, bleed_pt, crop_len_pt, line_w_pt):
    rects = []
    for pl in placements:
        x = margin_left + pl["x"]; y = margin_top + pl["y"]
        rects.append((x, y, x + pl["w"], y + pl["h"]))
    for (x0,y0,x1,y1) in rects:
        b = bleed_pt; L = crop_len_pt
        TLx, TLy = x0 + b, y0 + b
        TRx, TRy = x1 - b, y0 + b
        BLx, BLy = x0 + b, y1 - b
        BRx, BRy = x1 - b, y1 - b
        shape = page.new_shape()
        shape.draw_line(fitz.Point(TLx - L, TLy), fitz.Point(TLx, TLy))
        shape.draw_line(fitz.Point(TLx, TLy - L), fitz.Point(TLx, TLy))
        shape.draw_line(fitz.Point(TRx, TRy), fitz.Point(TRx + L, TRy))
        shape.draw_line(fitz.Point(TRx, TRy - L), fitz.Point(TRx, TRy))
        shape.draw_line(fitz.Point(BLx - L, BLy), fitz.Point(BLx, BLy))
        shape.draw_line(fitz.Point(BLx, BLy), fitz.Point(BLx, BLy + L))
        shape.draw_line(fitz.Point(BRx, BRy), fitz.Point(BRx + L, BRy))
        shape.draw_line(fitz.Point(BRx, BRy), fitz.Point(BRx, BRy + L))
        shape.finish(color=(0,0,0), width=line_w_pt)
        shape.commit()

def render_placements(doc, placements, margin_left, margin_top, bleed_pt, crop_len_pt, line_w_pt, extra_deg=0):
    page = doc[-1]
    _draw_all_slot_trims_outside_only(page, placements, margin_left, margin_top, bleed_pt, crop_len_pt, line_w_pt)
    for pl in placements:
        x = margin_left + pl["x"]; y = margin_top + pl["y"]
        src = fitz.open(pl["path"])
        dst = fitz.Rect(x, y, x + pl["w"], y + pl["h"])
        if "deg" in pl:
            deg = int(pl["deg"]) % 360
        else:
            base_deg = 90 if pl.get("rot", False) else 0
            deg = (base_deg + (extra_deg or 0)) % 360
        page.show_pdf_page(dst, src, pl["page"], rotate=deg)
        src.close()

def _white_mm_for_page(placements, inner_w, inner_h, m_left, m_right, m_top, m_bottom):
    if not placements:
        return (0.0,0.0,0.0,0.0)
    min_x = min(pl["x"] for pl in placements)
    min_y = min(pl["y"] for pl in placements)
    max_x = max(pl["x"]+pl["w"] for pl in placements)
    max_y = max(pl["y"]+pl["h"] for pl in placements)
    left_in = max(0.0, min_x)
    right_in = max(0.0, inner_w - max_x)
    top_in = max(0.0, min_y)
    bottom_in = max(0.0, inner_h - max_y)
    L = (m_left   + left_in)  / PT_PER_MM
    R = (m_right  + right_in) / PT_PER_MM
    T = (m_top    + top_in)   / PT_PER_MM
    B = (m_bottom + bottom_in)/ PT_PER_MM
    return (L,R,T,B)

# ---------- Enumerare variante ----------
def _placements_signature(placements, round_to=0.1):
    sig = []
    for pl in placements:
        w = round(pl["w"], 1) if round_to == 0.1 else round(pl["w"]/round_to)*round_to
        h = round(pl["h"], 1) if round_to == 0.1 else round(pl["h"]/round_to)*round_to
        x = round(pl["x"], 1); y = round(pl["y"], 1)
        sig.append((w,h,bool(pl["rot"]),x,y))
    sig.sort()
    return tuple(sig)

def _scale_items(items, s):
    out = []
    for it in items:
        t = dict(it); t["w"] = it["w"] * s; t["h"] = it["h"] * s
        out.append(t)
    return out

def _center_x(placements, inner_w):
    if not placements: return placements
    min_x = min(pl["x"] for pl in placements)
    max_x = max(pl["x"] + pl["w"] for pl in placements)
    layout_w = max_x - min_x
    dx = max(0.0, (inner_w - layout_w) * 0.5) - min_x
    out = []
    for pl in placements:
        p2 = dict(pl); p2["x"] = pl["x"] + dx; out.append(p2)
    return out


def _validate_layout(placements, inner_w, inner_h, gap):
    """
    Valid if:
      - every piece is fully inside [0..inner_w] x [0..inner_h]
      - no two pieces overlap when each piece is expanded by gap/2 on all sides
        (this enforces at least `gap` clearance horizontally/vertically)
    """
    if not placements:
        return False
    eps = 1e-6
    # Bounds check
    for p in placements:
        try:
            x = float(p['x']); y = float(p['y']); w = float(p['w']); h = float(p['h'])
        except Exception:
            return False
        if x < -eps or y < -eps or x + w > inner_w + eps or y + h > inner_h + eps:
            return False
    ex = max(0.0, float(gap)) * 0.5
    n = len(placements)
    for i in range(n):
        pi = placements[i]
        ax1 = float(pi['x']) - ex; ay1 = float(pi['y']) - ex
        ax2 = ax1 + float(pi['w']) + 2*ex; ay2 = ay1 + float(pi['h']) + 2*ex
        for j in range(i+1, n):
            pj = placements[j]
            bx1 = float(pj['x']) - ex; by1 = float(pj['y']) - ex
            bx2 = bx1 + float(pj['w']) + 2*ex; by2 = by1 + float(pj['h']) + 2*ex
            if not (ax2 <= bx1 + eps or bx2 <= ax1 + eps or ay2 <= by1 + eps or by2 <= ay1 + eps):
                return False
    return True

def _align_left_x(placements):
    if not placements:
        return placements
    min_x = min(pl['x'] for pl in placements)
    if abs(min_x) <= 1e-6:
        return placements
    out = []
    for pl in placements:
        p2 = dict(pl); p2['x'] = pl['x'] - min_x; out.append(p2)
    return out

def _align_right_x(placements, inner_w):
    if not placements:
        return placements
    max_x = max(pl['x'] + pl['w'] for pl in placements)
    dx = inner_w - max_x
    if abs(dx) <= 1e-6:
        return placements
    out = []
    for pl in placements:
        p2 = dict(pl); p2['x'] = pl['x'] + dx; out.append(p2)
    return out


def _center_placements(pls, inner_w, inner_h):
    if not pls:
        return pls
    min_x = min(p["x"] for p in pls)
    min_y = min(p["y"] for p in pls)
    max_x = max(p["x"] + p["w"] for p in pls)
    max_y = max(p["y"] + p["h"] for p in pls)
    layout_w = max_x - min_x
    layout_h = max_y - min_y
    dx = max(0.0, (inner_w - layout_w) * 0.5) - min_x
    dy = max(0.0, (inner_h - layout_h) * 0.5) - min_y
    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
        for p in pls:
            p["x"] = float(p["x"]) + dx
            p["y"] = float(p["y"]) + dy
    return pls


def _build_from_rectpack_result(result, items_by_id, allow_rot, gap):
    placements = []
    for (_, x, y, w, h, rid) in result:
        it = items_by_id[rid]
        # Detect rotation considering inflated rects (gap added during packing)
        rot_hyp = (abs(w - (it["h"] + gap)) < 0.5 and abs(h - (it["w"] + gap)) < 0.5)
        rot = bool(rot_hyp) if allow_rot else False
        eff_w = it["h"] if rot else it["w"]
        eff_h = it["w"] if rot else it["h"]
        placements.append({
            "path": it["path"], "page": it["page"], "base": it["base"],
            "x": float(x), "y": float(y), "w": float(eff_w), "h": float(eff_h),
            "rot": rot
        })
    return placements

def safe_new_packer(*, mode=None, pack_algo=None, sort_algo=None, bin_algo=None, rotation=False):
    try:
        return newPacker(mode=mode, pack_algo=pack_algo, sort_algo=sort_algo, bin_algo=bin_algo, rotation=rotation)
    except Exception:
        pass
    try:
        return newPacker(mode=mode, pack_algo=pack_algo, sort_algo=sort_algo, rotation=rotation)
    except Exception:
        pass
    try:
        return newPacker(mode=mode, pack_algo=pack_algo, rotation=rotation)
    except Exception:
        pass
    try:
        return newPacker(pack_algo=pack_algo, rotation=rotation)
    except Exception:
        pass
    return newPacker(rotation=rotation)

def generate_variants_enumerated(items, inner_w, inner_h, allow_rot, max_variants, limit_combos, rng_seed, gap):
    rng = random.Random(rng_seed)
    items_by_id = {i: it for i,it in enumerate(items)}
    variants = []; seen = set()

    pack_algos = PACK_ALGOS or [None]
    sort_algos = SORT_ALGOS or [None]
    bin_algos  = BIN_ALGOS or [getattr(PackingBin, "Global", 0)]
    rotations  = [False, True] if allow_rot else [False]
    modes      = [getattr(PackingMode,"Offline",0), getattr(PackingMode,"Online",1)]

    combos = []
    for A in pack_algos:
        for S in sort_algos:
            for B in bin_algos:
                for R in rotations:
                    for M in modes:
                        combos.append((A,S,B,R,M))
    rng.shuffle(combos)
    if limit_combos and limit_combos > 0:
        combos = combos[:limit_combos]

    for (A,S,B,R,M) in combos:
        try:
            p = safe_new_packer(mode=M, pack_algo=A, sort_algo=S, bin_algo=B, rotation=R)
            p.add_bin(inner_w, inner_h)
            for rid, it in items_by_id.items():
                p.add_rect(it["w"] + gap, it["h"] + gap, rid)
            p.pack()
            rs = p.rect_list()
        except Exception:
            continue

        if len(rs) != len(items_by_id):
            continue

        pls = _build_from_rectpack_result(rs, items_by_id, allow_rot=R, gap=gap)
        pls = _center_placements(pls, inner_w, inner_h)
        sig = _placements_signature(pls, 0.1)
        if sig in seen:
            continue
        seen.add(sig)
        variants.append(pls)
        if len(variants) >= max_variants:
            break

    return variants


def _candidate_positions(placements):
    pos = {(0.0, 0.0)}
    for pl in placements:
        pos.add((pl["x"] + pl["w"], pl["y"]))
        pos.add((pl["x"], pl["y"] + pl["h"]))
        pos.add((pl["x"] + pl["w"], pl["y"] + pl["h"]))
    return pos


def _rects_overlap(ax, ay, aw, ah, bx, by, bw, bh, eps=1e-6):
    return not (ax + aw <= bx + eps or bx + bw <= ax + eps or ay + ah <= by + eps or by + bh <= ay + eps)


def generate_variants_backtracking(items, inner_w, inner_h, allow_rot, max_variants, gap):
    """
    Exhaustive-ish search based on corner placements.
    Places each rectangle at candidate corners derived from existing placements.
    This can find layouts that rectpack sometimes misses for small item counts.
    """
    if not items:
        return []
    if len(items) > 9:
        return []

    variants = []
    seen = set()

    inflated = []
    for it in items:
        inflated.append({
            "path": it["path"], "page": it["page"], "base": it["base"],
            "w": it["w"] + gap, "h": it["h"] + gap
        })

    def _place(i, placements):
        if len(variants) >= max_variants:
            return
        if i >= len(inflated):
            pls = []
            for pl in placements:
                eff_w = pl["w"] - gap
                eff_h = pl["h"] - gap
                pls.append({
                    "path": pl["path"], "page": pl["page"], "base": pl["base"],
                    "x": pl["x"], "y": pl["y"], "w": eff_w, "h": eff_h, "rot": pl["rot"]
                })
            sig = _placements_signature(pls, 0.1)
            if sig not in seen:
                seen.add(sig)
                variants.append(pls)
            return

        it = inflated[i]
        rotations = [(it["w"], it["h"], False)]
        if allow_rot and abs(it["w"] - it["h"]) > 1e-6:
            rotations.append((it["h"], it["w"], True))

        for (w, h, rot) in rotations:
            for (x, y) in sorted(_candidate_positions(placements)):
                if x < -1e-6 or y < -1e-6:
                    continue
                if x + w > inner_w + 1e-6 or y + h > inner_h + 1e-6:
                    continue
                overlap = False
                for pl in placements:
                    if _rects_overlap(x, y, w, h, pl["x"], pl["y"], pl["w"], pl["h"]):
                        overlap = True
                        break
                if overlap:
                    continue
                placements.append({
                    "path": it["path"], "page": it["page"], "base": it["base"],
                    "x": x, "y": y, "w": w, "h": h, "rot": rot
                })
                _place(i + 1, placements)
                placements.pop()

    _place(0, [])
    return variants





# ---------- Custom Layout Editor (drag/rotate/snap + red overlaps + block save) ----------
import tkinter as tk
from tkinter import ttk, messagebox

class CustomLayoutEditor(tk.Toplevel):
    """
    Include: overflow mov, interior coală gri, coală la ~2 cm de top, centrare orizontală,
    cadru vizibil cât coala, reset poziții.
    Rotire robustă la dublu‑click.
    Nou: Buton „Aliniază piesele” – realizează o așezare compactă pe rânduri (stil „shelf”),
         păstrând orientarea fiecărei piese și ordinea aproximativă dată de utilizator.
         Respectă «Gap» și centrează orizontal rezultatul.
    """
    def __init__(self, master, items, inner_w, inner_h, margin_left_pt, margin_top_pt, gap_pt, preview_scale_pct, on_save, mode=None, paired_left_w=None, paired_gutter=None):
        # Optional paired-mode context


        super().__init__(master)
        self.title("Custom layout – aranjare manuală")

        # === Tema & culori uniforme (mov deschis) ===
        self.bg_color = "#D9C3F0"     # fundal aplicație (și overflow)
        self.sheet_fill = "#E6E6E6"   # gri doar pentru interiorul colii

        self.configure(bg=self.bg_color)
        style = ttk.Style(self)
        style.configure("Custom.TFrame", background=self.bg_color)
        style.configure("Custom.TLabel", background=self.bg_color)
        style.configure("Custom.TButton", padding=6)

        # model
        self.items = [dict(it) for it in items]
        # Snapshot inițial pentru reset
        self._initial_items = [dict(it) for it in self.items]

        self.inner_w = float(inner_w)
        self.inner_h = float(inner_h)
        self.margin_left = float(margin_left_pt)
        self.margin_top = float(margin_top_pt)
        self.gap_pt = float(gap_pt)
        self.scale = max(0.1, min(1.0, float(preview_scale_pct)/100.0))
        self.on_save = on_save

        # Paired mode context for showing backs preview
        self.mode = mode
        try:
            self.paired_left_w = None if paired_left_w is None else float(paired_left_w)
        except Exception:
            self.paired_left_w = None
        try:
            self.paired_gutter = None if paired_gutter is None else float(paired_gutter)
        except Exception:
            self.paired_gutter = None

        # culori selecție
        self.FILL_NORMAL = "#e6f0ff"
        self.FILL_SELECTED = "#ffccd5"

        # permite tras în afara colii
        self.overflow_pt = max(self.inner_w, self.inner_h) * 0.4

        # === containere cu stilul mov ===
        top = ttk.Frame(self, padding=10, style="Custom.TFrame")
        top.pack(fill="both", expand=True)

        toolbar = ttk.Frame(top, style="Custom.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Resetează pozițiile", command=self._reset_positions, style="Custom.TButton").pack(side="left")
        ttk.Button(toolbar, text="Aliniază piesele", command=self._auto_align, style="Custom.TButton").pack(side="left", padx=(8,0))
        self.btn_save = ttk.Button(toolbar, text="Salvează varianta Custom", command=self._save, style="Custom.TButton")
        self.btn_save.pack(side="right")
        ttk.Button(toolbar, text="Anulează", command=self.destroy, style="Custom.TButton").pack(side="right", padx=(0, 8))

        # === container pentru canvas ===
        canvas_container = tk.Frame(top, bg=self.bg_color)
        canvas_container.pack(fill="both", expand=True)

        # dimensiunea zonei interioare (scalată)
        self.cw = int(self.inner_w * self.scale) + 2
        self.ch = int(self.inner_h * self.scale) + 2

        # --- Pad-uri: sus ~2 cm, stânga/dreapta/jos pentru overflow ---
        try:
            dpi = self.winfo_fpixels('1i')  # pixeli / inch
        except Exception:
            dpi = 96
        two_cm_in = 3.0 / 2.54
        self.pad_top_px = max(0, int(dpi * two_cm_in))  # ~2 cm
        self.pad_side_px = int(self.overflow_pt * self.scale) + 20   # stânga/dreapta overflow
        self.pad_bottom_px = int(self.overflow_pt * self.scale) + 20 # jos overflow

        canvas_w = self.cw + self.pad_side_px * 2 + 2
        canvas_h = self.ch + self.pad_top_px + self.pad_bottom_px + 2

        # Canvas: overflow mov
        self.canvas = tk.Canvas(
            canvas_container,
            background=self.bg_color,
            highlightthickness=0,
            relief="flat",
            bd=0,
            width=canvas_w,
            height=canvas_h
        )
        # Poziționare: sus (y=0), centrat orizontal
        self.canvas.place(x=0, y=0)

        def _place_canvas(event=None):
            W = canvas_container.winfo_width()
            x = max((W - canvas_w) // 2, 0)
            self.canvas.place(x=x, y=0)
        canvas_container.bind("<Configure>", _place_canvas)
        self.after(50, _place_canvas)

        # === Sheet (interior gri) + contur sheet ===
        self.sheet_id = self.canvas.create_rectangle(
            1 + self.pad_side_px, 1 + self.pad_top_px,
            self.cw + 1 + self.pad_side_px, self.ch + 1 + self.pad_top_px,
            outline="", fill=self.sheet_fill, tags=("sheet",)
        )
        self.bg_id = self.canvas.create_rectangle(
            1 + self.pad_side_px, 1 + self.pad_top_px,
            self.cw + 1 + self.pad_side_px, self.ch + 1 + self.pad_top_px,
            outline="#777", width=1, tags=("sheet",)
        )

        # mapări canvas<->model
        self.item_map = {}     # cid -> idx în self.items
        self.cid_by_idx = {}   # idx -> cid

        # stare drag
        self.sel_idx = None
        self.active_cid = None
        self.drag_start_px = None
        self.item_start_pt = None

        # overlays suprapuneri
        self.overlap_ids = []
        self.has_overlaps = False

        self._draw_all()

        # ordine straturi + bind-uri
        self.canvas.lower("sheet")
        self.canvas.tag_raise("shape")

        # mouse
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        # Rotire pe dublu-click: doar pe canvas; handlerul identifică forma corectă
        self.canvas.bind("<Double-Button-1>", self._on_double)

        # Tag-binds pentru forme (fără dublu-click aici, evităm conflicte)
        self.canvas.tag_bind("shape", "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind("shape", "<Leave>", lambda e: self.canvas.configure(cursor=""))
        self.canvas.tag_bind("shape", "<Button-1>", self._on_press)
        self.canvas.tag_bind("shape", "<B1-Motion>", self._on_drag)
        self.canvas.tag_bind("shape", "<ButtonRelease-1>", self._on_release)

        # tastatură
        self.bind("<Key-r>", self._on_key_rotate)
        self.bind("<Key-R>", self._on_key_rotate)

        # fereastră ~50% din ecran
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * 0.4), int(sh * 0.45)
        x = (sw - w)//2; y = (sh - h)//2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.canvas.focus_set()

        # scrollregion egal cu întreg canvasul
        self.canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))

        # calculează suprapunerile inițiale
        self._update_overlaps_view()

    # ---------- UI helpers ----------
    def _reset_positions(self):
        """Readuce toate piesele la pozițiile inițiale (x, y, w, h, rot)."""
        try:
            src = self._initial_items
        except AttributeError:
            return
        for i in range(min(len(self.items), len(src))):
            for k in ("x", "y", "w", "h", "rot"):
                if k in src[i]:
                    self.items[i][k] = src[i][k]
        self.sel_idx = None
        self.active_cid = None
        self.drag_start_px = None
        self.item_start_pt = None
        self._draw_all()
        self._update_overlaps_view()
        try:
            self.canvas.configure(cursor="")
        except Exception:
            pass

    def _save(self):
        if self.has_overlaps:
            messagebox.showerror(
                "Nu pot salva",
                "Ai PDF-uri care se suprapun. Te rog aranjează-le astfel încât să nu mai existe suprapuneri."
            )
            return
        self.on_save(self.items)
        self.destroy()

    # ---------- Helpers coordonate (model->canvas cu offset) ----------
    def _coords_from_model(self, pl):
        x = int(pl["x"] * self.scale) + 1 + self.pad_side_px
        y = int(pl["y"] * self.scale) + 1 + self.pad_top_px
        w = max(1, int(pl["w"] * self.scale))
        h = max(1, int(pl["h"] * self.scale))
        return (x, y, x+w, y+h)

    def _update_canvas_item_from_model(self, idx):
        if idx not in self.cid_by_idx:
            return
        cid = self.cid_by_idx[idx]
        self.canvas.coords(cid, *self._coords_from_model(self.items[idx]))

    def _create_rect_from_model(self, pl):
        x0, y0, x1, y1 = self._coords_from_model(pl)
        return self.canvas.create_rectangle(
            x0, y0, x1, y1,
            outline="#000",
            fill=self.FILL_NORMAL,
            tags=("shape",)
        )

    def _draw_all(self):
        # șterge doar shape-urile, nu și sheet-ul
        for cid in list(self.item_map.keys()):
            try:
                self.canvas.delete(cid)
            except Exception:
                pass
        self.item_map.clear()
        self.cid_by_idx.clear()

        for idx, pl in enumerate(self.items):
            cid = self._create_rect_from_model(pl)
            self.item_map[cid] = idx
            self.cid_by_idx[idx] = cid

        # Draw ghost BACKS on the right half if paired mode is active
        if getattr(self, 'mode', None) == 'paired_same_page' and self.paired_left_w is not None and self.paired_gutter is not None:
            if self.items:
                min_front_x = min(p['x'] for p in self.items)
            else:
                min_front_x = 0.0
            for pl in self.items:
                axis_inner = float(self.paired_left_w) + float(self.paired_gutter) * 0.5
                bx = (2 * axis_inner) - (pl['x'] + pl['w'])
                by = pl['y']
                bw, bh = pl['w'], pl['h']
                # Convert to canvas coords
                x0 = int(bx * self.scale) + 1 + self.pad_side_px
                y0 = int(by * self.scale) + 1 + self.pad_top_px
                x1 = int((bx + bw) * self.scale) + 1 + self.pad_side_px
                y1 = int((by + bh) * self.scale) + 1 + self.pad_top_px
                try:
                    self.canvas.create_rectangle(x0, y0, x1, y1, outline="#000", fill="#dfeadf", stipple="gray25", tags=("ghost_back",), state="disabled")
                except Exception:
                    pass

        if self.sel_idx is not None:
            self._highlight_selection()

        # sheet în spate, shapes în față
        self.canvas.lower("sheet")
        self.canvas.tag_raise("shape")

    def _highlight_selection(self):
        for cid in self.item_map.keys():
            self.canvas.itemconfig(cid, outline="#000", width=1, fill=self.FILL_NORMAL)
        if self.sel_idx is not None and self.sel_idx in self.cid_by_idx:
            sel_cid = self.cid_by_idx[self.sel_idx]
            self.canvas.itemconfig(sel_cid, outline="#1f6feb", width=2, fill=self.FILL_SELECTED)
            self.canvas.tag_raise(sel_cid)

    def _clear_selection(self):
        self.sel_idx = None
        self.active_cid = None
        self.drag_start_px = None
        self.item_start_pt = None
        self._highlight_selection()

    # ---------- Overlaps ----------
    def _calc_intersections_model(self):
        inters = []
        n = len(self.items)
        for i in range(n):
            a = self.items[i]; ax0, ay0, ax1, ay1 = a["x"], a["y"], a["x"]+a["w"], a["y"]+a["h"]
            for j in range(i+1, n):
                b = self.items[j]; bx0, by0, bx1, by1 = b["x"], b["y"], b["x"]+b["w"], b["y"]+b["h"]
                ix0 = max(ax0, bx0); iy0 = max(ay0, by0)
                ix1 = min(ax1, bx1); iy1 = min(ay1, by1)
                if ix1 > ix0 and iy1 > iy0:
                    inters.append((ix0, iy0, ix1, iy1))
        return inters

    def _update_overlaps_view(self):
        for oid in self.overlap_ids:
            try:
                self.canvas.delete(oid)
            except Exception:
                pass
        self.overlap_ids.clear()

        inters = self._calc_intersections_model()
        self.has_overlaps = bool(inters)

        for (x0,y0,x1,y1) in inters:
            cx0 = int(x0 * self.scale) + 1 + self.pad_side_px
            cy0 = int(y0 * self.scale) + 1 + self.pad_top_px
            cx1 = int(x1 * self.scale) + 1 + self.pad_side_px
            cy1 = int(y1 * self.scale) + 1 + self.pad_top_px
            oid = self.canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                outline="#ff0000",
                fill="#ff4d4d",
                stipple="gray25",
                width=1,
                tags=("overlap",),
                state="disabled"
            )
            self.overlap_ids.append(oid)

        try:
            self.btn_save.state(["!disabled"] if not self.has_overlaps else ["disabled"])
        except Exception:
            self.btn_save.configure(state=("normal" if not self.has_overlaps else "disabled"))

        # straturi: sheet jos, shapes, apoi overlap sus
        self.canvas.lower("sheet")
        self.canvas.tag_raise("shape")
        for oid in self.overlap_ids:
            self.canvas.tag_raise(oid)

    # ---------- Events ----------
    def _on_press(self, ev):
        cur = self.canvas.find_withtag("current")
        cid = cur[0] if cur else None
        if cid not in self.item_map:
            cid = self._pick_top_shape(ev.x, ev.y)
        if cid is None:
            self._clear_selection()
            try:
                self.canvas.configure(cursor="")
            except Exception:
                pass
            return
        self.active_cid = cid
        self.sel_idx = self.item_map[cid]
        self.drag_start_px = (ev.x, ev.y)
        pl = self.items[self.sel_idx]
        self.item_start_pt = (pl["x"], pl["y"])
        self.canvas.tag_raise(cid)
        self._highlight_selection()
        try:
            self.canvas.configure(cursor="fleur")
        except Exception:
            pass

    def _on_drag(self, ev):
        if self.sel_idx is None or self.active_cid is None or self.drag_start_px is None or self.item_start_pt is None:
            return
        dx_px = ev.x - self.drag_start_px[0]
        dy_px = ev.y - self.drag_start_px[1]
        dx_pt = dx_px / self.scale
        dy_pt = dy_px / self.scale

        pl = self.items[self.sel_idx]

        # permite ieșirea din coală: [-overflow, inner + overflow]
        min_x = -self.overflow_pt
        max_x = self.inner_w - pl["w"] + self.overflow_pt
        min_y = -self.overflow_pt
        max_y = self.inner_h - pl["h"] + self.overflow_pt

        new_x = min(max(self.item_start_pt[0] + dx_pt, min_x), max_x)
        new_y = min(max(self.item_start_pt[1] + dy_pt, min_y), max_y)
        pl["x"], pl["y"] = new_x, new_y

        self._update_canvas_item_from_model(self.sel_idx)
        self._update_overlaps_view()

    def _on_release(self, ev):
        if self.sel_idx is None:
            return
        pl = self.items[self.sel_idx]
        if self._snap_position(pl, self.sel_idx):
            self._update_canvas_item_from_model(self.sel_idx)

        self.active_cid = None
        self.drag_start_px = None
        self.item_start_pt = None
        try:
            self.canvas.configure(cursor="")
        except Exception:
            pass

        self._update_overlaps_view()

    def _on_double(self, ev):
        """Rotire la dublu-click robustă: ia top-most shape sub cursor și rotește."""
        # căutăm toate item-ele sub cursor
        hits = self.canvas.find_overlapping(ev.x, ev.y, ev.x, ev.y)
        # păstrăm doar formele noastre (cele din item_map); ordinea find_overlapping e de jos în sus
        shapes = [cid for cid in hits if cid in self.item_map]
        if not shapes:
            return "break"
        cid = shapes[-1]  # top-most
        self.sel_idx = self.item_map[cid]
        self._rotate_item(self.sel_idx)
        self._update_canvas_item_from_model(self.sel_idx)
        self._highlight_selection()
        self._update_overlaps_view()
        return "break"

    def _on_key_rotate(self, ev):
        if self.sel_idx is None:
            return
        self._rotate_item(self.sel_idx)
        self._update_canvas_item_from_model(self.sel_idx)
        self._highlight_selection()
        self._update_overlaps_view()

    def _pick_top_shape(self, x, y):
        # ținem cont de offset-urile pad (sus și lateral)
        x -= self.pad_side_px
        y -= self.pad_top_px
        for idx in reversed(range(len(self.items))):
            pl = self.items[idx]
            x0 = int(pl["x"] * self.scale) + 1
            y0 = int(pl["y"] * self.scale) + 1
            w  = max(1, int(pl["w"] * self.scale))
            h  = max(1, int(pl["h"] * self.scale))
            if x0 <= x <= x0 + w and y0 <= y <= y0 + h:
                cid = self.cid_by_idx.get(idx)
                if cid:
                    return cid
                return None
        return None

    # ---------- Model ops ----------
    def _rotate_item(self, idx):
        pl = self.items[idx]
        cx = pl["x"] + pl["w"]/2.0
        cy = pl["y"] + pl["h"]/2.0
        pl["w"], pl["h"] = pl["h"], pl["w"]
        pl["rot"] = not bool(pl.get("rot", False))
        pl["x"] = cx - pl["w"]/2.0
        pl["y"] = cy - pl["h"]/2.0
        # limite largi (permite în afară)
        pl["x"] = min(max(pl["x"], -self.overflow_pt), self.inner_w - pl["w"] + self.overflow_pt)
        pl["y"] = min(max(pl["y"], -self.overflow_pt), self.inner_h - pl["h"] + self.overflow_pt)
        self._snap_position(pl, idx)

    def _snap_position(self, pl, idx):
        """Snap la margini și vecini cu gap fix. Toleranță = 1.5 * gap. Permite și în afara colii."""
        tol = self.gap_pt * 1.5
        x, y, w, h = pl["x"], pl["y"], pl["w"], pl["h"]
        changed = False

        # margini coală interioară
        if abs(x - 0.0) <= tol:                     x, changed = 0.0, True
        if abs(y - 0.0) <= tol:                     y, changed = 0.0, True
        if abs((self.inner_w - (x + w))) <= tol:    x, changed = self.inner_w - w, True
        if abs((self.inner_h - (y + h))) <= tol:    y, changed = self.inner_h - h, True

        # snap la vecini (păstrând gap)
        for j, other in enumerate(self.items):
            if j == idx: continue
            ox, oy, ow, oh = other["x"], other["y"], other["w"], other["h"]
            overlap_y = not (y+h <= oy or oy+oh <= y)
            overlap_x = not (x+w <= ox or ox+ow <= x)

            # stânga/dreapta
            tx = ox + ow + self.gap_pt
            if overlap_y and abs(x - tx) <= tol: x, changed = tx, True
            tx = ox - self.gap_pt - w
            if overlap_y and abs(x - tx) <= tol: x, changed = tx, True
            # sus/jos
            ty = oy - self.gap_pt - h
            if overlap_x and abs(y - ty) <= tol: y, changed = ty, True
            ty = oy + oh + self.gap_pt
            if overlap_x and abs(y - ty) <= tol: y, changed = ty, True

        # limite largi (permite în afară)
        x = min(max(x, -self.overflow_pt), self.inner_w - w + self.overflow_pt)
        y = min(max(y, -self.overflow_pt), self.inner_h - h + self.overflow_pt)

        pl["x"], pl["y"] = x, y
        return changed

    # ---------- Auto align (shelf) ----------
    def _auto_align(self):
        def __run_once():
            """Pas pregătitor (curățare selecții)."""
            self._clear_selection()
            self._highlight_selection()

        NumarDeRulari = 1
        for __i in range(NumarDeRulari):
            __run_once()

        def to_mm(v_pt: float) -> float:
            return float(v_pt) / PT_PER_MM

        def expand_rect(r, gap):
            x, y, w, h = r
            return (x - gap, y - gap, w + 2*gap, h + 2*gap)

        def intersects(r1, r2):
            x1, y1, w1, h1 = r1
            x2, y2, w2, h2 = r2
            return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)

        def place_left_then_up(w, h, placed, inner_w, inner_h, gap):
            """Găsește o poziție (x,y) validă pentru o piesă (w,h),
            mutând-o cât mai la stânga (x minim) unde există o poziție validă,
            iar pentru acel x minim alege cel mai mic y (cât mai sus).
            Folosește candidați de y pe grila derivată din piesele plasate + 0.
            """
            # Set de candidați pentru y
            y_candidates = {0.0}
            for (px, py, pw, ph) in placed:
                y_candidates.add(max(0.0, py - gap - h))
                y_candidates.add(max(0.0, py + ph + gap))
            y_candidates = sorted([y for y in y_candidates if y <= inner_h - h + 1e-6])

            best = None  # (x,y)

            for y in y_candidates:
                # calculează x minim permis de fiecare piesă existentă ce se suprapune pe verticală (cu gap)
                x_min = 0.0
                for (px, py, pw, ph) in placed:
                    # dacă se suprapun pe verticală ținând cont de gap
                    if not (y + h <= py - gap or py + ph + gap <= y):
                        x_min = max(x_min, px + pw + gap)
                # limitează în interior
                if x_min > inner_w - w + 1e-6:
                    continue
                # verifică coliziuni reale la (x_min, y)
                cand = (x_min, y, w, h)
                ok = True
                for other in placed:
                    if intersects(expand_rect(cand, gap), other):
                        ok = False
                        break
                if not ok:
                    continue
                # păstrează cel mai mic x; la egalitate, pe cel mai mic y
                if best is None or x_min < best[0] - 1e-6 or (abs(x_min - best[0]) <= 1e-6 and y < best[1] - 1e-6):
                    best = (x_min, y)
            if best is None:
                # fallback: dacă nu am găsit poziție (de ex. gap foarte mare)
                if w <= inner_w + 1e-6 and h <= inner_h + 1e-6:
                    best = (0.0, 0.0)
                else:
                    best = (max(0.0, inner_w - w), max(0.0, inner_h - h))
            return best

        def show_top_message(msg_text: str):
            # fereastră deasupra tuturor, legată de Custom Layout, MODALĂ
            win = tk.Toplevel(self)
            win.title("Info")
            win.configure(bg="#fff7cc")
            win.transient(self)  # Custom Layout rămâne în spate
            win.lift()
            win.attributes("-topmost", True)
            # eliberează topmost după ce a apărut
            win.after(250, lambda: win.attributes("-topmost", False))

            frm = tk.Frame(win, bg="#fff7cc", padx=14, pady=12)
            frm.pack(fill="both", expand=True)
            lbl = tk.Label(frm, text=msg_text, bg="#fff7cc", justify="left", anchor="w")
            lbl.pack(fill="both", expand=True)
            ttk.Button(frm, text="OK", command=lambda: self._final_ok(win)).pack(pady=(8,0), anchor="e")

            # dimensionare și poziționare
            try:
                self.update_idletasks()
                sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
                w, h = int(sw*0.32), int(sh*0.16)
                x, y = (sw - w)//2, (sh - h)//2
                win.geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                pass

            # transformăm fereastra în modală și blocăm execuția până la OK
            try:
                win.focus_force()
                win.grab_set()
            except Exception:
                pass
            self.wait_window(win)

        def enforce_window_order_for_message():
            """Asigură ordinea: 1) mesaj; 2) Custom Layout (self); 3) Variante; 4) App inițial."""
            try:
                app = self._root()              # fereastra inițială (App)
                variante = self.master          # fereastra „Variante impoziție” (părinte)
                # ordonăm: app jos, apoi variante, apoi custom
                app.lower()
                variante.lift(app)
                self.lift(variante)
            except Exception:
                pass

        # 1) ID-uri unice
        next_id = 1
        for it in self.items:
            if "uid" not in it:
                it["uid"] = next_id
                next_id += 1

        # 2) & 3) scoruri
        self.piece_scores = {}
        for it in self.items:
            x_mm = to_mm(float(it.get("x", 0.0)))
            y_mm = to_mm(float(it.get("y", 0.0)))
            score = 2.0 * x_mm + y_mm
            self.piece_scores[it["uid"]] = score
            it["_score"] = score  # păstrăm și pe item pt sortare

        # 4) mută toate piesele în afara colii, cât mai la dreapta
        for it in self.items:
            it["x"] = float(self.inner_w)  # sigur în afara laturii drepte
        # redesenare
        for i in range(len(self.items)):
            self._update_canvas_item_from_model(i)
        self._update_overlaps_view()

        # 5) mesaj de confirmare, cu ordonarea cerută a ferestrelor (modal)
        #enforce_window_order_for_message()
        #show_top_message("Am mutat piesele în afara colii.")

        # 6) parcurge piesele după scor (crescător) și plasează-le
        gap = float(self.gap_pt)
        inner_w = float(self.inner_w)
        inner_h = float(self.inner_h)

        # listă de piese deja plasate (recte ca (x,y,w,h))
        placed_rects = []

        # ordonare după scor; la egalitate, după ID (stabil)
        order = sorted(self.items, key=lambda it: (it.get("_score", 0.0), it["uid"]))

        for it in order:
            w = float(it["w"])
            h = float(it["h"])
            # 6.a + 6.b: calculează poziția „cât mai la stânga”, apoi „cât mai sus” pentru acel x
            x, y = place_left_then_up(w, h, placed_rects, inner_w, inner_h, gap)
            it["x"], it["y"] = x, y

            # fixează pe model și canvas
            idx = self.items.index(it)
            self._update_canvas_item_from_model(idx)
            # adaugăm în lista plasate
            placed_rects.append((x, y, w, h))

            # 6.c: mesaj per piesă (modal)
            #sc = self.piece_scores.get(it["uid"], 0.0)
            #show_top_message(f"Piesa cu ID-ul: {it['uid']} a fost mutată pe coală.\nPunctaj: {sc:.3f}")

        # 7) & 8) aliniere finală (centrare globală sau aliniere în jumătatea stângă)
        if self.items:
            min_x = min(p["x"] for p in self.items)
            min_y = min(p["y"] for p in self.items)
            max_x = max(p["x"] + p["w"] for p in self.items)
            max_y = max(p["y"] + p["h"] for p in self.items)
            layout_w = max_x - min_x
            layout_h = max_y - min_y

            if getattr(self, "mode", None) == "paired_same_page" and self.paired_left_w is not None and self.paired_gutter is not None:
                left_w = float(self.paired_left_w)
                target_min_x = max(0.0, left_w - layout_w)
                dx = target_min_x - min_x
            else:
                dx = max(0.0, (inner_w - layout_w) * 0.5) - min_x
            dy = max(0.0, (inner_h - layout_h) * 0.5) - min_y

            if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                for it in self.items:
                    it["x"] += dx
                    it["y"] += dy
                for i in range(len(self.items)):
                    self._update_canvas_item_from_model(i)

        # Validare suprapuneri + highlight
        self._highlight_selection()
        self._update_overlaps_view()
class PreviewWindow(tk.Toplevel):

    def __init__(self, master, variants, inner_w, inner_h, preview_scale_pct, on_choose, margin_left_pt, margin_top_pt, gap_pt, mode=None, paired_left_w=None, paired_gutter=None):
        super().__init__(master)
                
        # culori de temă (mov unitar pentru fereastră)
        bg_color = "#D9C3F0"            # fundal fereastră
        
        self.configure(bg=bg_color)

        # culori carduri (variante)
        self.bg_color = bg_color
        self.card_bg ="#F7F7F7"
        self.card_sel_bg = "#d7d7d7"
        self.card_border = "#BBA3EA"
        self.card_sel_border = "#5B3AB3"

        
        self.title("Variante impoziție – preview")
        self.configure(bg=bg_color)
        self.variants = variants
        self.inner_w = inner_w
        self.inner_h = inner_h
        self.preview_scale = float(preview_scale_pct)/100.0
        self.on_choose = on_choose
        self.margin_left = margin_left_pt
        self.margin_top = margin_top_pt
        self.gap_pt = gap_pt
        self.mode = mode
        self.paired_left_w = paired_left_w
        self.paired_gutter = paired_gutter

        self.selected_idx = None
        self.canvases = []

        # ---------- Cadru principal ----------
        top = ttk.Frame(self, padding=10)
        top.pack(fill="both", expand=True)
        top.configure(style="Preview.TFrame")

        style = ttk.Style(self)
        style.configure("Preview.TFrame", background=bg_color)
        style.configure("Preview.TButton", font=("TkDefaultFont", 10, "bold"))
        style.configure("Preview.TLabel", background=bg_color)

        # ---------- Header ----------
        header = ttk.Frame(top, style="Preview.TFrame")
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(
            header,
            text=f"Am găsit {len(variants)} variante:",
            font=("TkDefaultFont", 12, "bold"),
            style="Preview.TLabel"
        ).pack(anchor="center", pady=(0, 6))

        # ---------- Container principal ----------
        container = ttk.Frame(top, style="Preview.TFrame")
        container.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            container,
            background=bg_color,
            highlightthickness=1,
            relief="sunken",
            borderwidth=0
        )
        vs = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # inner frame cu același fundal
        self.inner = ttk.Frame(self.canvas, style="Preview.TFrame")
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self._build_grid()

        # ---------- Butoane jos ----------
        btns = ttk.Frame(top, style="Preview.TFrame")
        btns.pack(fill="x", pady=(12, 10))

        inner_btns = ttk.Frame(btns, style="Preview.TFrame")
        inner_btns.pack(anchor="center")

        ttk.Button(
            inner_btns,
            text="Folosește varianta selectată",
            command=self._accept,
            style="Preview.TButton"
        ).pack(side="left", padx=10)

        ttk.Button(
            inner_btns,
            text="+ Creează variantă Custom (manual)",
            command=self._open_custom,
            style="Preview.TButton"
        ).pack(side="left", padx=10)

        ttk.Button(
            inner_btns,
            text="Renunță",
            command=self.destroy,
            style="Preview.TButton"
        ).pack(side="left", padx=10)

        # ---------- Layout fereastră ----------
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * 0.62), int(sh * 0.75)
        x = (sw - w)//2
        y = (sh - h)//2
        self.geometry(f"{w}x{h}+{x}+{y}")




    def _build_grid(self):
        for w in self.inner.grid_slaves():
            w.destroy()
        self.canvases.clear()
        

        pw = int(self.inner_w * self.preview_scale)
        ph = int(self.inner_h * self.preview_scale)
        cols = 3

        for i, pllist in enumerate(self.variants):
            r = i // cols
            c = i % cols
            frame = ttk.Frame(self.inner, padding=8, style="Preview.TFrame")

            
            frame.grid(row=r, column=c, sticky="n")

            lbl = ttk.Label(frame, text=f"Var. {i + 1}", font=("TkDefaultFont", 11, "bold" ), background="#D9C3F0")
           
            
            
            lbl.pack(anchor="center", pady=(0,4))

            cnv = tk.Canvas(
                frame,
                width=pw + 2,
                height=ph + 2,
                background=self.card_bg,
                highlightthickness=2,
                highlightbackground=self.card_border,
                relief="ridge",
                borderwidth=2,
            )

            cnv.pack()
            cnv.bind("<Button-1>", lambda e, idx=i: self._select_variant(idx))
            self.canvases.append(cnv)

            self._draw_variant_on_canvas(cnv, pllist, pw, ph)

        for j in range(cols):
            self.inner.grid_columnconfigure(j, weight=1)

        self.inner.update_idletasks()
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)

    def _draw_variant_on_canvas(self, cnv, pllist, pw, ph):
        cnv.delete("all")
        cnv.create_rectangle(1, 1, pw+1, ph+1, outline="#777")
        # Draw fronts (left half or full area depending on mode)
        for pl in pllist:
            x = int(pl["x"] * self.preview_scale) + 1
            y = int(pl["y"] * self.preview_scale) + 1
            w = max(1, int(pl["w"] * self.preview_scale))
            h = max(1, int(pl["h"] * self.preview_scale))
            cnv.create_rectangle(x, y, x+w, y+h, outline="#000", fill="#d0d0d0")
        # If paired same page, also preview mirrored backs on the right half
        try:
            if self.mode == "paired_same_page" and self.paired_left_w is not None and self.paired_gutter is not None:
                left_w = float(self.paired_left_w)
                gutter = float(self.paired_gutter)
                # Mirror backs across vertical axis at sheet center
                axis_inner = left_w + gutter * 0.5
                for pl in pllist:
                    mirrored_x = (2 * axis_inner) - (pl['x'] + pl['w'])
                    x = int(mirrored_x * self.preview_scale) + 1
                    y = int(pl['y'] * self.preview_scale) + 1
                    w = max(1, int(pl['w'] * self.preview_scale))
                    h = max(1, int(pl['h'] * self.preview_scale))
                    cnv.create_rectangle(x, y, x+w, y+h, outline="#000", fill="#e0e0e0")
        except Exception:
            pass


    def _select_variant(self, idx):
        self.selected_idx = idx
        # colorează canvasurile: selectat mai închis
        for i, cnv in enumerate(self.canvases):
            if i == idx:
                cnv.configure(background="#bcd4ff", highlightbackground="#0040ff")
            else:
                cnv.configure(background="#F7F7F7", highlightbackground="#aaaaaa")                
                               

    def _open_custom(self):
        if not self.variants:
            try:
                app = self.master._root()
                app.lower()
                self.lift(app)
            except Exception:
                pass
            messagebox.showwarning("Atenție", "Nu există variante disponibile.", parent=self)
            try:
                app = self.master._root()
                app.lower()
                self.lift(app)
            except Exception:
                pass
            return
        idx = self.selected_idx if self.selected_idx is not None else 0
        if idx < 0 or idx >= len(self.variants):
            idx = 0
        base = self.variants[idx]
        items = [dict(p) for p in base]

        def _save_custom(pls):
            if not _validate_layout(pls, self.inner_w, self.inner_h, self.gap_pt):
                messagebox.showwarning("Variantă invalidă", "Piesele se suprapun sau depășesc interiorul colii.")
                return
            self.variants.append([dict(p) for p in pls])
            self._build_grid()
            self.selected_idx = len(self.variants)-1
            self._select_variant(self.selected_idx)
            messagebox.showinfo("Custom", "Varianta Custom a fost adăugată și selectată.", parent=self)

        CustomLayoutEditor(
            self, items,
            self.inner_w, self.inner_h,
            self.margin_left, self.margin_top,
            self.gap_pt, self.preview_scale*100.0,
            _save_custom,
            mode=self.mode,
            paired_left_w=self.paired_left_w,
            paired_gutter=self.paired_gutter
        )

    def _accept(self):

        idx = self.selected_idx
        if idx is None or not (0 <= idx < len(self.variants)):
            # Keep preview window visible and on top for the warning,
            # without messing with the root/app window order.
            try:
                self.attributes('-topmost', True)
            except Exception:
                pass
            try:
                messagebox.showwarning("Atenție", "Selectează o variantă prin click.", parent=self)
            finally:
                try:
                    self.attributes('-topmost', False)
                except Exception:
                    pass
                try:
                    self.deiconify(); self.lift(); self.focus_force()
                except Exception:
                    pass
            return
        self.on_choose(self.variants[idx])
        self.destroy()





# ---------- Main App ----------
class App(tk.Tk):
   
    def __init__(self):
        super().__init__()
        
        self.title("Imposition Star by IB v47.12.1 - 22.10.2025")
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # === Fundal global mov deschis ===
        app_bg = "#D9C3F0"
        self.configure(bg=app_bg)
        style.configure("TFrame", background=app_bg)
        style.configure("TLabel", background=app_bg)
        style.configure("TCheckbutton", background=app_bg)
        style.configure("TRadiobutton", background=app_bg)
        style.configure("TButton", padding=6)



        #---- Setari Parametri (Variabile) ----
        self.folder_var = tk.StringVar()
        self.sheet_var = tk.StringVar(value="70x50 cm")
        self.custom_w_cm = tk.StringVar(value="70.0")
        self.custom_h_cm = tk.StringVar(value="50.0")
        self.gap_var = tk.DoubleVar(value=3.0)
        self.cropbox_var = tk.StringVar(value="0")  # Cropbox (mm)
        self.margin_var = tk.DoubleVar(value=5.0)          # stânga/dreapta/sus
        self.bottom_margin_var = tk.DoubleVar(value=12.0)   # jos (clapa/gripper)
        self.bleed_var = tk.DoubleVar(value=3.0)
        self.crop_len_var = tk.DoubleVar(value=3.0)
        self.crop_width_mm = tk.DoubleVar(value=0.3)
        self.scale_pct = tk.DoubleVar(value=100.0)
        self.allow_rot = tk.BooleanVar(value=True)
        self.mode_var = tk.StringVar(value=MODE_FRONTS_BACKS_SEPARATE)

        self.preview_pct = tk.DoubleVar(value=23.0)
        self.num_variants = tk.IntVar(value=100)
        self.limit_combos = tk.IntVar(value=1200)
        self.rng_seed = tk.IntVar(value=2025)

        self._chosen_fronts_layout = None

        try:
            cwd = os.getcwd()
            auto_folder = os.path.join(cwd, "PDF-uri de impozat")
            if os.path.isdir(auto_folder):
                self.folder_var.set(auto_folder)
        except Exception:
            pass

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        def row(lbl, widget):
            r = row.idx
            ttk.Label(root, text=lbl).grid(column=0, row=r, sticky="w", padx=(0,8), pady=4)
            widget.grid(column=1, row=r, sticky="w", pady=4)
            row.idx += 1
        row.idx = 0

        ttk.Label(root, text="Folder cu PDF-uri (#N):").grid(column=0, row=row.idx, sticky="w", padx=(0,8), pady=4)
        rowf = ttk.Frame(root)
        ent_path = ttk.Entry(rowf, textvariable=self.folder_var, width=60)
        ent_path.grid(column=0, row=0, sticky="we")
        ttk.Button(rowf, text="Alege...", command=self.choose_folder).grid(column=1, row=0, padx=(6,0))
        rowf.grid_columnconfigure(0, weight=1)
        rowf.grid(column=1, row=row.idx, sticky="we", pady=4)
        row.idx += 1

        ttk.Label(root, text="Format coală:").grid(column=0, row=row.idx, sticky="w", padx=(0,8), pady=4)
        rowfmt = ttk.Frame(root)
        cb = ttk.Combobox(rowfmt, values=list(PREDEFINED_SHEETS_MM.keys()), textvariable=self.sheet_var, state="readonly")
        cb.grid(column=0, row=0, sticky="w")

        ttk.Label(rowfmt, text="Lățime coală (cm):").grid(column=1, row=0, sticky="w", padx=(16,6))
        ent_w = ttk.Entry(rowfmt, textvariable=self.custom_w_cm, width=8, justify="center")
        ent_w.grid(column=2, row=0, sticky="w")

        ttk.Label(rowfmt, text="Înălțime coală (cm):").grid(column=3, row=0, sticky="w", padx=(16,6))
        ent_h = ttk.Entry(rowfmt, textvariable=self.custom_h_cm, width=8, justify="center")
        ent_h.grid(column=4, row=0, sticky="w")
        rowfmt.grid(column=1, row=row.idx, sticky="w", pady=4)
        row.idx += 1

        def _on_sheet_change(event=None):
            key = self.sheet_var.get()
            dims = PREDEFINED_SHEETS_MM.get(key)
            if dims is None:
                self.custom_w_cm.set("")
                self.custom_h_cm.set("")
                ent_w.focus_set(); ent_w.select_range(0, 'end')
            else:
                w_mm, h_mm = dims
                self.custom_w_cm.set(f"{w_mm/10.0:g}")
                self.custom_h_cm.set(f"{h_mm/10.0:g}")
        cb.bind("<<ComboboxSelected>>", _on_sheet_change)

        def small_entry(var): return ttk.Entry(root, textvariable=var, width=8, justify="center")
        row("Gap (mm):", small_entry(self.gap_var))
        # Cropbox (mm) – combobox (0..5)
        cmb_crop = ttk.Combobox(root, values=["0","1","1.5","2","3"], textvariable=self.cropbox_var, state="readonly", width=6)
        cmb_crop.bind("<<ComboboxSelected>>", self._on_cropbox_change)
        row("Cropbox (mm):", cmb_crop)
        row("Margine (mm):", small_entry(self.margin_var))
        row("Marginea de jos (Clapa/Gripper) (mm):", small_entry(self.bottom_margin_var))
        row("Bleed (mm) slot:", small_entry(self.bleed_var))
        row("Lungime crop (mm):", small_entry(self.crop_len_var))
        row("Grosime linie crop (mm):", small_entry(self.crop_width_mm))
        row("Scalare piese (%):", small_entry(self.scale_pct))

        ttk.Checkbutton(root, text="Permite rotire", variable=self.allow_rot).grid(column=0, row=row.idx, sticky="w", pady=(6,2), columnspan=2)
        row.idx += 1

        ttk.Label(root, text="Mod impoziție:").grid(column=0, row=row.idx, sticky="w", pady=(6,2))
        row.idx += 1
        ttk.Radiobutton(root, text="Față pe pagina 1, Verso pe pagina 2", variable=self.mode_var, value=MODE_FRONTS_BACKS_SEPARATE).grid(column=0, row=row.idx, sticky="w", columnspan=2)
        row.idx += 1
        ttk.Radiobutton(root, text="Față + Verso în aceeași pagină (slot împărțit pe înălțime)", variable=self.mode_var, value=MODE_PAIRED_SAME_PAGE).grid(column=0, row=row.idx, sticky="w", columnspan=2)
        row.idx += 1
        ttk.Radiobutton(root, text="Doar Față", variable=self.mode_var, value=MODE_FRONTS_ONLY).grid(column=0, row=row.idx, sticky="w", columnspan=2)
        row.idx += 1

        ttk.Label(root, text="Explorare (enumerare compat)").grid(column=0, row=row.idx, sticky="w", pady=(10,2), columnspan=2)
        row.idx += 1
        row("Număr variante (2–100):", small_entry(self.num_variants))
        row("Limită combinații testate:", small_entry(self.limit_combos))
        row("Scară preview (%):", small_entry(self.preview_pct))
        row("Seed (random):", small_entry(self.rng_seed))

        btns = ttk.Frame(root)
        btns.grid(column=0, row=row.idx, columnspan=2, pady=(10,0))
        ttk.Button(btns, text="Generează VARIANTE (preview)", command=self.preview_variants).pack(side="left", padx=(0,8))
        ttk.Button(btns, text="Generează PDF final (cu varianta selectată)", command=self.run_final).pack(side="left")
        row.idx += 1

        self.update_idletasks()
        req_w = root.winfo_reqwidth() + 30
        req_h = root.winfo_reqheight() + 30
        self.geometry(f"{req_w}x{req_h}")
        self._center_window(self)

    def _center_window(self, win):
        try:
            win.update_idletasks()
            w = win.winfo_width()
            h = win.winfo_height()
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            win.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def _sheet_size_mm(self):
        key = self.sheet_var.get()
        if PREDEFINED_SHEETS_MM.get(key) is None:
            w_str = (self.custom_w_cm.get() or "").strip()
            h_str = (self.custom_h_cm.get() or "").strip()
            if not w_str or not h_str:
                raise ValueError("Pentru format Custom, completați Lățime și Înălțime (cm).")
            try:
                w = float(w_str); h = float(h_str)
            except Exception:
                raise ValueError("Valorile pentru Lățime/Înălțime trebuie să fie numerice (cm).")
            return (cm_to_mm(w), cm_to_mm(h))
        return PREDEFINED_SHEETS_MM[key]

    def _open_file(self, path):
        try:
            if platform.system() == "Windows":
                os.startfile(path)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            try:
                webbrowser.open(path)
            except Exception:
                pass

    # ---------- CROPBOX Apply ----------
    def _on_cropbox_change(self, event=None):
        """Când se schimbă valoarea din combobox, aplică noul CropBox (mm) tuturor PDF-urilor din folder."""
        try:
            #mm_val = int(float(self.cropbox_var.get() or 0))
            mm_val = float(self.cropbox_var.get() or 0)
        except Exception:
            mm_val = 0
        self._apply_cropbox_to_folder(mm_val)

    def update_bleed_from_cropbox(self):
        """Actualizează bleed_var = 3 - cropbox_var"""
        try:
            crop_val = float(self.cropbox_var.get() or 0)
        except ValueError:
            crop_val = 0.0
        new_bleed = 3.0 - crop_val
        self.bleed_var.set(new_bleed)


    def _apply_cropbox_to_folder(self, mm_value: int):
        
        self.update_bleed_from_cropbox()
    
        folder = (self.folder_var.get() or "").strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Eroare", "Alege un folder valid înainte de a seta Cropbox.", parent=self)
            return

        inset_pt = mm_to_pt(max(0.0, float(mm_value)))
        changed_files = 0
        errors = []

        for fname in os.listdir(folder):
            if not fname.lower().endswith(".pdf"):  # ignoră non-PDF
                continue
            if "#" not in fname:
                continue
            path = os.path.join(folder, fname)
            try:
                doc = fitz.open(path)
            except Exception as e:
                errors.append(f"{fname}: nu pot deschide ({e})")
                continue

            try:
                # Pentru fiecare pagină: setează CropBox bazat pe MediaBox original
                for pg in doc:
                    # MediaBox de bază (format pagină), nu cumulăm insetări succesive
                    mb = pg.mediabox if hasattr(pg, "mediabox") else pg.rect
                    # Calculează noul crop, asigurându-ne că rămânem pozitivi
                    x0 = float(mb.x0) + inset_pt
                    y0 = float(mb.y0) + inset_pt
                    x1 = float(mb.x1) - inset_pt
                    y1 = float(mb.y1) - inset_pt
                    # Protecție: minim 10pt lățime/înălțime
                    if x1 - x0 < 10: 
                        cx = (mb.x0 + mb.x1) * 0.5
                        x0, x1 = cx - 5, cx + 5
                    if y1 - y0 < 10:
                        cy = (mb.y0 + mb.y1) * 0.5
                        y0, y1 = cy - 5, cy + 5

                    new_rect = fitz.Rect(x0, y0, x1, y1)
                    try:
                        pg.set_cropbox(new_rect)
                    except Exception:
                        # Fallback vechi: direct pe atribut, unde e permis de PyMuPDF
                        try:
                            pg.cropbox = new_rect
                        except Exception as e2:
                            raise RuntimeError(f"Nu pot seta CropBox: {e2}")

                # Salvează incremental dacă se poate, altfel rescrie
                try:
                    doc.saveIncr()
                except Exception:
                    doc.save(path, incremental=False)
                changed_files += 1
            except Exception as e:
                errors.append(f"{fname}: {e}")
            finally:
                try:
                    doc.close()
                except Exception:
                    pass

        if changed_files > 0 and not errors:
            messagebox.showinfo("Cropbox", f"Am setat CropBox = {mm_value} mm pentru {changed_files} fișier(e).", parent=self)
        elif changed_files > 0 and errors:
            messagebox.showwarning("Cropbox", f"Am setat CropBox = {mm_value} mm pentru {changed_files} fișier(e).\n\nErori la:\n- " + "\n- ".join(errors), parent=self)
        else:
            messagebox.showwarning("Cropbox", "Nu am modificat niciun fișier. Verifică folderul și permisiunile.", parent=self)

    # ---------- PREVIEW flow ----------
    def preview_variants(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Eroare", "Alege un folder valid.", parent=self)
            return

        leaves = gather_leaves(folder)
        if not leaves:
            messagebox.showerror("Eroare", "Nu s-au găsit PDF-uri cu sufixul #N (ex. Fisier#3.pdf).", parent=self)
            return

        try:
            sw_mm, sh_mm = self._sheet_size_mm()
        except ValueError as e:
            messagebox.showerror("Eroare", str(e), parent=self)
            return

        page_w = mm_to_pt(sw_mm); page_h = mm_to_pt(sh_mm)
        margin_common = mm_to_pt(self.margin_var.get())
        bottom_margin = mm_to_pt(self.bottom_margin_var.get())
        margin_left = margin_common
        margin_right = margin_common
        margin_top = margin_common
        margin_bottom = bottom_margin

        inner_w = page_w - (margin_left + margin_right)
        inner_h = page_h - (margin_top + margin_bottom)
        gap = mm_to_pt(self.gap_var.get())

        allow_rot = bool(self.allow_rot.get())
        try:
            pct = float(self.scale_pct.get())
        except Exception:
            pct = 100.0
        pct = max(1.0, pct)
        scale = pct / 100.0

        nvar = max(2, min(100, int(self.num_variants.get() or 0)))
        limit = max(0, int(self.limit_combos.get() or 0))
        seed = int(self.rng_seed.get() or 0)
        mode = self.mode_var.get()

        if mode == MODE_PAIRED_SAME_PAGE:
            gutter = gap
            left_w = max(0.0, (inner_w - gutter) * 0.5)
            items = [d for d in leaves if not d["is_back"]]
            items = _scale_items(items, scale)
            for it in items:
                it.setdefault("x", 0.0); it.setdefault("y", 0.0); it.setdefault("rot", False)
            variants = generate_variants_enumerated(items, left_w, inner_h, allow_rot, nvar, limit, seed, gap)
            variants = [ _align_right_x(v, left_w) for v in variants ]
            variants = [ v for v in variants if _validate_layout(v, left_w, inner_h, gap) ]
        else:
            items = [d for d in leaves if not d["is_back"]]
            items = _scale_items(items, scale)
            for it in items:
                it.setdefault("x", 0.0); it.setdefault("y", 0.0); it.setdefault("rot", False)
            variants = generate_variants_enumerated(items, inner_w, inner_h, allow_rot, nvar, limit, seed, gap)
            variants = [ _center_x(v, inner_w) for v in variants ]
            variants = [ v for v in variants if _validate_layout(v, inner_w, inner_h, gap) ]

        if len(variants) < nvar:
            if mode == MODE_PAIRED_SAME_PAGE:
                extra_variants = generate_variants_backtracking(items, left_w, inner_h, allow_rot, nvar, gap)
                extra_variants = [ _align_right_x(v, left_w) for v in extra_variants ]
                extra_variants = [ v for v in extra_variants if _validate_layout(v, left_w, inner_h, gap) ]
            else:
                extra_variants = generate_variants_backtracking(items, inner_w, inner_h, allow_rot, nvar, gap)
                extra_variants = [ _center_x(v, inner_w) for v in extra_variants ]
                extra_variants = [ v for v in extra_variants if _validate_layout(v, inner_w, inner_h, gap) ]

            seen = { _placements_signature(v, 0.1) for v in variants }
            for v in extra_variants:
                sig = _placements_signature(v, 0.1)
                if sig in seen:
                    continue
                seen.add(sig)
                variants.append(v)
                if len(variants) >= nvar:
                    break

        total_variants = len(variants)
        if total_variants == 0:
            messagebox.showwarning("Nicio variantă", "Nu am găsit nicio aranjare pe coală. Încercați o coală mai mare sau un gap mai mic.", parent=self)
            return

# === Post-procesare: shuffle al rândurilor distincte (fără suprapuneri pe verticală) ===
        import itertools as _it

        def _rows_from_layout(pls):
            if not pls:
                return []
            tiny = 0.5  # toleranță pt. margini
            idxs = sorted(range(len(pls)), key=lambda i: pls[i]['y'])
            rows = []
            cur = [idxs[0]]
            cur_min = pls[idxs[0]]['y']
            cur_max = pls[idxs[0]]['y'] + pls[idxs[0]]['h']
            for i in idxs[1:]:
                y0 = pls[i]['y']; y1 = y0 + pls[i]['h']
                # dacă NU se suprapune cu banda curentă -> nou rând
                if (y0 >= cur_max - tiny) or (y1 <= cur_min + tiny):
                    rows.append(cur)
                    cur = [i]; cur_min = y0; cur_max = y1
                else:
                    cur.append(i)
                    if y0 < cur_min: cur_min = y0
                    if y1 > cur_max: cur_max = y1
            rows.append(cur)
            return rows

        def _permute_rows(pls):
            rows = _rows_from_layout(pls)
            if len(rows) < 2:
                return []
            # y-top inițiale, sortate (nu schimbăm spațierea totală a layout-ului)
            row_tops = [min(pls[i]['y'] for i in r) for r in rows]
            row_tops_sorted = sorted(row_tops)
            # offset relativ în interiorul fiecărui rând
            row_offs = [{i: (pls[i]['y'] - row_tops[idx]) for i in rows[idx]} for idx in range(len(rows))]

            new_list = []
            rcount = len(rows)
            if rcount <= 6:  # limităm factorialul
                perms = _it.permutations(range(rcount), rcount)
            else:
                perms = []

            for perm in perms:
                clone = [dict(p) for p in pls]
                for k, r_idx in enumerate(perm):
                    y_top = row_tops_sorted[k]
                    offs = row_offs[r_idx]
                    for i in rows[r_idx]:
                        clone[i]['y'] = y_top + offs[i]
                new_list.append(clone)
            return new_list

        try:
            seen = { _placements_signature(v, 0.1) for v in variants }
            extra = []
            for base in variants:
                for nv in _permute_rows(base):
                    sig = _placements_signature(nv, 0.1)
                    if sig in seen: 
                        continue
                    seen.add(sig)
                    extra.append(nv)
            if extra:
                variants.extend(extra)
        except Exception:
            pass



        def _store_choice(pls):
            self._chosen_fronts_layout = pls


        if mode == MODE_PAIRED_SAME_PAGE:
            # Filtru FINAL (ambele moduri)
            try:
                if mode == MODE_PAIRED_SAME_PAGE:
                    variants = [v for v in variants if _validate_layout(v, left_w, inner_h, gap)]
                else:
                    variants = [v for v in variants if _validate_layout(v, inner_w, inner_h, gap)]
            except Exception:
                pass
            PreviewWindow(self, variants, inner_w, inner_h, self.preview_pct.get(), _store_choice, margin_left, margin_top, gap, mode=MODE_PAIRED_SAME_PAGE, paired_left_w=left_w, paired_gutter=gap)
        else:
            # Filtru FINAL (ambele moduri)
            try:
                variants = [v for v in variants if _validate_layout(v, inner_w, inner_h, gap)]
            except Exception:
                pass
            PreviewWindow(self, variants, inner_w, inner_h, self.preview_pct.get(), _store_choice, margin_left, margin_top, gap)
# ---------- FINAL PDF flow ----------
    def run_final(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Eroare", "Alege un folder valid.", parent=self)
            return

        leaves = gather_leaves(folder)
        if not leaves:
            messagebox.showerror("Eroare", "Nu s-au găsit PDF-uri cu sufixul #N (ex. Fisier#3.pdf).", parent=self)
            return

        try:
            sw_mm, sh_mm = self._sheet_size_mm()
        except ValueError as e:
            messagebox.showerror("Eroare", str(e), parent=self)
            return

        page_w = mm_to_pt(sw_mm); page_h = mm_to_pt(sh_mm)
        margin_common = mm_to_pt(self.margin_var.get())
        bottom_margin = mm_to_pt(self.bottom_margin_var.get())
        margin_left = margin_common
        margin_right = margin_common
        margin_top = margin_common
        margin_bottom = bottom_margin

        inner_w = page_w - (margin_left + margin_right)
        inner_h = page_h - (margin_top + margin_bottom)

        gap = mm_to_pt(self.gap_var.get())
        bleed_pt = mm_to_pt(self.bleed_var.get())
        crop_len_pt = mm_to_pt(self.crop_len_var.get() + 3.0)
        line_w_pt = mm_to_pt(self.crop_width_mm.get())
        allow_rot = bool(self.allow_rot.get())

        try:
            pct = float(self.scale_pct.get())
        except Exception:
            pct = 100.0
        pct = max(1.0, pct)
        scale = pct / 100.0
        eff_bleed = bleed_pt * scale

        mode = self.mode_var.get()
        if self._chosen_fronts_layout is None:
            messagebox.showwarning("Atenție", "Nu ai selectat nicio variantă. Apasă întâi „Generează VARIANTE (preview)”.", parent=self)
            return

        layouts = self._chosen_fronts_layout
        if not _validate_layout(layouts, inner_w, inner_h, gap):
            messagebox.showerror("Variantă invalidă", "Piesele se suprapun, nu respectă gap-ul sau depășesc interiorul colii.", parent=self)
            return
        doc = fitz.open()
        whites_summary = {}

        if mode == MODE_FRONTS_BACKS_SEPARATE:
            draw_sheet(doc, page_w, page_h)
            render_placements(doc, layouts, margin_left, margin_top, eff_bleed, crop_len_pt, line_w_pt, extra_deg=0)
            L,R,T,B = _white_mm_for_page(layouts, inner_w, inner_h, margin_left, margin_right, margin_top, margin_bottom)
            whites_summary[1] = (L,R,T,B)

            backs = [d for d in leaves if d["is_back"]]
            if backs:
                from collections import defaultdict, deque
                qbacks = defaultdict(deque)
                for d in backs:
                    qbacks[d["base"]].append(d)
                pls_b = []
                for pf in layouts:
                    base = pf["base"]
                    if qbacks.get(base):
                        b = qbacks[base].popleft()
                        same_rot = pf["rot"]
                        eff_w = (b["w"] if not same_rot else b["h"]) * scale
                        eff_h = (b["h"] if not same_rot else b["w"]) * scale
                        mx = inner_w - pf["x"] - eff_w
                        my = pf["y"]
                        pls_b.append({"path": b["path"], "page": b["page"], "base": base,
                                      "x": mx, "y": my, "w": eff_w, "h": eff_h, "rot": False, "deg": (270 if same_rot else 0)})
                if pls_b:
                    draw_sheet(doc, page_w, page_h)
                    render_placements(doc, pls_b, margin_left, margin_top, eff_bleed, crop_len_pt, line_w_pt, extra_deg=0)
                    L2,R2,T2,B2 = _white_mm_for_page(pls_b, inner_w, inner_h, margin_left, margin_right, margin_top, margin_bottom)
                    whites_summary[2] = (L2,R2,T2,B2)

        elif mode == MODE_PAIRED_SAME_PAGE:
            # Render FRONTS left (right-aligned within left half) / BACKS right (left-aligned) on the same page
            from collections import defaultdict, deque
            fronts_by = defaultdict(list)
            backs_by = defaultdict(deque)
            for d in leaves:
                (backs_by if d['is_back'] else fronts_by)[d['base']].append(d)

            gutter = gap
            left_w = max(0.0, (inner_w - gutter) * 0.5)
            right_x0 = margin_left + left_w + gutter

            # Ensure chosen fronts layout is right-aligned in the left half
            layouts = _align_right_x(layouts, left_w)
            # Precompute left alignment reference for backs (min x of fronts group)
            min_front_x = min(pf['x'] for pf in layouts) if layouts else 0.0

            # 1) Compute all placements geometrically (without drawing content) to place crop marks UNDER pieces
            combined_pls = []
            for pf in layouts:
                # Front placement (left half, already right-aligned)
                combined_pls.append({'x': pf['x'], 'y': pf['y'], 'w': pf['w'], 'h': pf['h']})
                # Back placement (right half, left-aligned as a group)
                axis_inner = left_w + gutter * 0.5
                bx = (2 * axis_inner) - (pf['x'] + pf['w'])
                combined_pls.append({'x': bx, 'y': pf['y'], 'w': pf['w'], 'h': pf['h']})

            # 2) Draw the crop marks UNDER the artwork
            draw_sheet(doc, page_w, page_h)
            page = doc[-1]
            _draw_all_slot_trims_outside_only(page, combined_pls, margin_left, margin_top, eff_bleed, crop_len_pt, line_w_pt)

            # 3) Now place PDF content on top of the already drawn trims
            for pf in layouts:
                # Front
                fl = fronts_by.get(pf['base'], [])
                if fl:
                    f0 = fl.pop(0)
                    src = fitz.open(f0['path'])
                    xL = margin_left + pf['x']
                    yL = margin_top + pf['y']
                    dstF = fitz.Rect(xL, yL, xL + pf['w'], yL + pf['h'])
                    page.show_pdf_page(dstF, src, f0['page'], rotate=(90 if pf.get('rot') else 0))
                    src.close()
                # Back (right half, left-aligned group)
                qb = backs_by.get(pf['base']) if backs_by.get(pf['base']) else deque()
                if qb:
                    b0 = qb.popleft()
                    same_rot = bool(pf.get('rot'))
                    axis_inner = left_w + gutter * 0.5
                    xR = margin_left + (2 * axis_inner - (pf['x'] + pf['w']))
                    yR = margin_top + pf['y']
                    src2 = fitz.open(b0['path'])
                    deg = 270 if same_rot else 0
                    dstB = fitz.Rect(xR, yR, xR + pf['w'], yR + pf['h'])
                    page.show_pdf_page(dstB, src2, b0['page'], rotate=deg)
                    src2.close()

            # White margins report (based on combined placements over full inner area)
            L,R,T,B = _white_mm_for_page(combined_pls, inner_w, inner_h, margin_left, margin_right, margin_top, margin_bottom)
            whites_summary[1] = (L,R,T,B)


        else:  # MODE_FRONTS_ONLY
            draw_sheet(doc, page_w, page_h)
            render_placements(doc, layouts, margin_left, margin_top, eff_bleed, crop_len_pt, line_w_pt, extra_deg=0)
            L,R,T,B = _white_mm_for_page(layouts, inner_w, inner_h, margin_left, margin_right, margin_top, margin_bottom)
            whites_summary[1] = (L,R,T,B)

        
        # --- Denumire inteligentă a fișierului final ---
        from datetime import datetime
        def _fmt_val(s):
            try:
                v = float(str(s).replace(",", ".").strip())
                # folosim %g ca să eliminăm zecimalele inutile
                return ("%g" % v)
            except Exception:
                return str(s).strip()
        try:
            w_cm = _fmt_val(self.custom_w_cm.get())
            h_cm = _fmt_val(self.custom_h_cm.get())
            fmt_coala = f"{w_cm}x{h_cm}"
        except Exception:
            fmt_coala = "NAxNA"
        today = datetime.now().strftime("%Y.%m.%d_%H.%M")
        suffix = "_La2RanduriDePlaci" if int(getattr(doc, "page_count", len(doc))) >= 2 else "_La1RandDePlaci"
        out_name = f"{today}_Impozitie_coala{fmt_coala}{suffix}.pdf"
        out_path = os.path.join(folder, out_name)
        try:
            doc.save(out_path)
            doc.close()
        finally:
            pass

        self._open_file(out_path)
        self.after(120, lambda: self._show_final_dialog(out_path, whites_summary))




    def _final_ok(self, win):
        try:
            win.destroy()
        except Exception:
            pass
        try:
            # Trimite fereastra principală în spate după ce PDF-ul e deja deschis
            self.lower()
            try:
                self.attributes("-topmost", False)
            except Exception:
                pass
            try:
                self.iconify()
                self.deiconify()
                self.lower()
            except Exception:
                pass
        except Exception:
            pass

    def _show_final_dialog(self, out_path, whites_summary_dict):
        TEAL = "#b8efe6"
        win = tk.Toplevel(self)
        win.title("Gata")
        win.configure(bg=TEAL)

        # —— apare deasupra tuturor ferestrelor
        win.transient(self)         # o leagă de fereastra principală
        win.lift()                  # o ridică deasupra
        win.attributes("-topmost", True)
        win.after(250, lambda: win.attributes("-topmost", False))  # eliberează topmost după afișare
        try:
            win.focus_force()
        except Exception:
            pass

        frm = tk.Frame(win, bg=TEAL, padx=16, pady=16, highlightthickness=0, bd=0)
        frm.pack(fill="both", expand=True)

        lines = [f"S-a generat:\n{out_path}\n", "Margini albe coala:"]
        for pg in sorted(whites_summary_dict.keys()):
            L, R, T, B = whites_summary_dict[pg]
            lines.append(f"Pag.{pg} Stânga/Dreapta: {L:.1f} / {R:.1f} mm   Sus/Jos: {T:.1f} / {B:.1f} mm")
        msg = "\n".join(lines)

        lbl = tk.Label(frm, text=msg, justify="left", anchor="w", bg=TEAL, wraplength=700)
        lbl.pack(fill="both", expand=True)

        ttk.Button(frm, text="OK", command=lambda: self._final_ok(win)).pack(pady=(8,0), anchor="e")

        self._center_window(win)




if __name__ == "__main__":
    App().mainloop()
