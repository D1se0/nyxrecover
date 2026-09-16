"""NyxRecover TUI — dark neon glass interface (Textual).

Layout: sidebar with devices + FS info on the left, tabbed workspace on the
right (Dashboard · Recuperar · Analizar · Borrar · Registro). Every long
operation runs in a worker thread and streams progress to the UI. Destructive
actions go through typed-phrase confirmation screens.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (Button, DataTable, Footer, Header, Input, Label,
                             ProgressBar, RichLog, Select, Static, TabbedContent,
                             TabPane)

from nyx.nyxcore.version import APP_NAME, VERSION, TAGLINE
from nyx.nyxcore import device as devmod, safety, audit, report
from nyx.nyxcore.scan import scan_raw, shannon
from nyx.nyxcore.recovery import RecoveryEngine
from nyx.nyxcore.timeline import build_timeline, to_csv
from nyx.nyxcore.keywords import search as kw_search
from nyx.nyxcore.slack import collect as slack_collect
from nyx.nyxcore.cipher import detect as cipher_detect, entropy_map
from nyx.nyxcore.hdocs import find_office_in_buffer, analyze_pdf
from nyx.nyxcore.device import human_size
from nyx.nyxwipe.engine import wipe_device, wipe_freespace

ACCENT = "#22d3ee"

CSS = """
Screen { background: #070b14; }
#shell { height: 1fr; }
#sidebar {
    width: 40; min-width: 34; border-right: heavy #1f2a44;
    background: #0b1120; padding: 1;
}
#sidebar Title { color: $accent; }
#brand { height: 5; content-align: center middle; color: #e5e7eb;
         background: #0d1321; border: round #22d3ee; margin-bottom: 1; }
#devlist { height: 1fr; }
#devinfo { height: 14; border-top: heavy #1f2a44; padding-top: 1; }
#workspace { padding: 1 1 0 1; background: transparent; }
TabbedContent { background: transparent; }
Tabs { background: #0b1120; }
.card { border: round #1f2a44; background: #0b1120; padding: 1; margin-bottom: 1; }
.kpirow { height: auto; }
.kpi { width: 1fr; border: round #1f2a44; background: #0b1120; padding: 0 1; margin-right: 1; }
.kpi .val { color: $accent; text-style: bold; }
.row { height: auto; }
.grow { height: 1fr; }
.btnrow { height: auto; margin-top: 1; }
Button { margin-right: 1; min-width: 12; }
.btn-danger { background: #3f1d24; border: round #f87171; color: #fecaca; }
.btn-go { background: #10321f; border: round #34d399; color: #a7f3d0; }
Input, Select { margin-bottom: 1; }
#pbar { margin-top: 1; }
.log { border: round #1f2a44; background: #0b1120; }
#riskbox { border: round #fbbf24; background: #241c07; padding: 1; margin-bottom: 1; }
ModalScreen { align: center middle; }
.dialog { border: thick $accent; background: #0d1321; padding: 1 2; width: 72; }
.dialog Title { color: $accent; }
#phrase { margin-top: 1; }
.dim { color: #94a3b8; }
.warn { color: #fbbf24; }
.bad { color: #f87171; }
.ok { color: #34d399; }
"""


class PhraseScreen(ModalScreen[str]):
    """Typed-phrase confirmation for destructive operations."""

    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, title: str, body: str, phrase: str):
        super().__init__()
        self._title = title
        self._body = body
        self._phrase = phrase

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"[b]{self._title}[/b]", classes="dialog-title"),
            Static(self._body, markup=True),
            Static(f"Escribe [b]{self._phrase}[/b] para confirmar:", classes="warn"),
            Input(placeholder=self._phrase, id="phrase"),
            Horizontal(
                Button("Confirmar", variant="error", id="ok"),
                Button("Cancelar", id="no"),
                classes="btnrow",
            ),
            classes="dialog",
        )

    def on_input_submitted(self, ev) -> None:
        self.dismiss(ev.value.strip())

    def on_button_pressed(self, ev) -> None:
        if ev.button.id == "ok":
            self.dismiss(self.query_one("#phrase", Input).value.strip())
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Generic yes/no confirmation."""

    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, title: str, body: str, danger: bool = False):
        super().__init__()
        self._title, self._body, self._danger = title, body, danger

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"[b]{self._title}[/b]"),
            Static(self._body, markup=True),
            Horizontal(
                Button("Aceptar", variant="error" if self._danger else "success", id="ok"),
                Button("Cancelar", id="no"),
                classes="btnrow",
            ),
            classes="dialog",
        )

    def on_button_pressed(self, ev) -> None:
        self.dismiss(ev.button.id == "ok")

    def action_cancel(self) -> None:
        self.dismiss(False)


class InfoScreen(ModalScreen):
    """Scrollable info dialog."""

    BINDINGS = [("escape", "cancel", "Cerrar"), ("enter", "cancel", "Cerrar")]

    def __init__(self, title: str, body: str):
        super().__init__()
        self._title, self._body = title, body

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"[b]{self._title}[/b]"),
            VerticalScroll(Static(self._body, markup=True), classes="grow"),
            Button("Cerrar", id="ok", classes="btn-go"),
            classes="dialog",
        )

    def on_button_pressed(self, _ev) -> None:
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()


class NyxApp(App):
    TITLE = f"{APP_NAME} v{VERSION}"
    SUB_TITLE = TAGLINE
    CSS = CSS

    BINDINGS = [
        Binding("r", "refresh_devices", "Refrescar"),
        Binding("d", "focus_tab('dash')", "Panel", show=False),
        Binding("c", "focus_tab('rec')", "Recuperar", show=False),
        Binding("a", "focus_tab('ana')", "Analizar", show=False),
        Binding("w", "focus_tab('wipe')", "Borrar", show=False),
        Binding("l", "focus_tab('log')", "Registro", show=False),
        Binding("q", "quit", "Salir"),
    ]

    def __init__(self):
        super().__init__()
        self.selected_node: str | None = None
        self.devices: list = []
        self.cancel_event = threading.Event()
        self._last_scan = None

    # ── layout ───────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="shell"):
            with Vertical(id="sidebar"):
                yield Static(f"🜲 {APP_NAME}\nv{VERSION}", id="brand")
                yield Select([], prompt="Selecciona dispositivo…", id="devsel")
                yield Button("↻ Refrescar (r)", id="refresh")
                yield Static("—", id="devinfo", markup=True)
            with TabbedContent(id="workspace", initial="tab-dash"):
                with TabPane("◧ Panel", id="tab-dash"):
                    yield self._dash_pane()
                with TabPane("⟲ Recuperar", id="tab-rec"):
                    yield self._rec_pane()
                with TabPane("🔍 Analizar", id="tab-ana"):
                    yield self._ana_pane()
                with TabPane("🔥 Borrar", id="tab-wipe"):
                    yield self._wipe_pane()
                with TabPane("▤ Registro", id="tab-log"):
                    yield RichLog(highlight=False, markup=True, classes="log grow", id="mainlog")
        yield Footer()

    def _dash_pane(self) -> ComposeResult:
        with VerticalScroll(classes="grow"):
            with Horizontal(classes="kpirow"):
                yield Static("[b]0[/b]\ndispositivos", classes="kpi", id="kpi-devs")
                yield Static("[b]—[/b]\nseleccionado", classes="kpi", id="kpi-node")
                yield Static("[b]—[/b]\nfilesystem", classes="kpi", id="kpi-fs")
                yield Static("[b]—[/b]\nriesgo", classes="kpi", id="kpi-risk")
            yield Static("", id="dash-summary", classes="card", markup=True)
            yield Static("", id="dash-cipher", classes="card", markup=True)
            yield Static("Cadena de auditoría: —", id="dash-audit", classes="card", markup=True)

    def _rec_pane(self) -> ComposeResult:
        with Vertical(classes="grow"):
            yield Static("[b]Recuperación de datos[/b] — elige modo y destino",
                         classes="card", markup=True)
            yield Select(
                [("🧠 Inteligente (FS + carving)", "smart"),
                 ("🗂 Árbol del filesystem (borrados)", "fs"),
                 ("🪄 Solo carving por firmas", "carve")],
                prompt="Modo de recuperación", id="rec-mode")
            yield Input(placeholder="Ruta de salida (vacío = ./nyx_recuperados)",
                        id="rec-out")
            with Horizontal(classes="btnrow"):
                yield Button("▶ Escanear y recuperar", id="rec-go", classes="btn-go")
                yield Button("◻ Cancelar", id="rec-cancel")
            yield ProgressBar(id="rec-pbar", show_eta=False)
            yield RichLog(markup=True, classes="log grow", id="rec-log")

    def _ana_pane(self) -> ComposeResult:
        with Vertical(classes="grow"):
            yield Static("[b]Análisis forense[/b] — timeline, keywords, slack, cifrado",
                         classes="card", markup=True)
            yield Input(placeholder="Palabras clave separadas por coma (vacío = no buscar)",
                        id="ana-kw")
            with Horizontal(classes="btnrow"):
                yield Button("📅 Timeline", id="ana-tl")
                yield Button("🔎 Buscar claves", id="ana-kwgo")
                yield Button("🕳 Slack", id="ana-slack")
                yield Button("🔐 Cifrado", id="ana-cipher")
                yield Button("📄 Office/PDF ocultos", id="ana-hdocs")
            yield ProgressBar(id="ana-pbar", show_eta=False)
            yield RichLog(markup=True, classes="log grow", id="ana-log")

    def _wipe_pane(self) -> ComposeResult:
        with Vertical(classes="grow"):
            yield Static("[b]⚠ Borrado seguro[/b] — IRREVERSIBLE. Elige método y lee el aviso.",
                         classes="card", markup=True)
            yield Static("", id="riskbox", markup=True)
            yield Select(
                [("NIST 800-88 Clear — ceros (rápido, estándar)", "zero"),
                 ("DoD 5220.22-M — 3 pasadas", "dod5220"),
                 ("Aleatorio CSPRNG — 1 pasada", "random"),
                 ("Gutmann — 35 pasadas (muy lento)", "gutmann")],
                prompt="Método de borrado", id="wipe-method")
            with Horizontal(classes="row"):
                yield Switch(value=True, id="wipe-verify")
                yield Label("Verificar después del borrado (muestreo)")
            with Horizontal(classes="btnrow"):
                yield Button("🔥 BORRAR DISPOSITIVO", id="wipe-go", classes="btn-danger")
                yield Button("🧽 Libre espacio montado", id="wipe-free")
                yield Button("◻ Cancelar", id="wipe-cancel")
            yield ProgressBar(id="wipe-pbar", show_eta=False)
            yield RichLog(markup=True, classes="log grow", id="wipe-log")

    # ── helpers ──────────────────────────────────────────────────────────
    def nlog(self, where: str, line: str) -> None:
        w = {"rec": self.query_one("#rec-log", RichLog),
             "ana": self.query_one("#ana-log", RichLog),
             "wipe": self.query_one("#wipe-log", RichLog),
             "log": self.query_one("#mainlog", RichLog)}.get(where)
        if w:
            w.write(line)
        self.query_one("#mainlog", RichLog).write(line)

    def set_progress(self, which: str, done: float, total: float) -> None:
        pb = self.query_one(f"#{which}-pbar", ProgressBar)
        pb.total = max(total, 1)
        pb.update(progress=done)

    def selected_device(self):
        if not self.selected_node:
            self.notify("Selecciona un dispositivo primero", severity="warning")
            return None
        try:
            return devmod.get_device(self.selected_node)
        except FileNotFoundError:
            self.notify("El dispositivo ya no existe", severity="error")
            return None

    # ── devices ──────────────────────────────────────────────────────────
    def action_refresh_devices(self) -> None:
        self.refresh_devices()

    def on_mount(self) -> None:
        self.refresh_devices()
        ok = audit.verify()
        self.query_one("#dash-audit", Static).update(
            f"Cadena de auditoría: {'✓ íntegra' if ok['ok'] else '✗ ALTERADA línea ' + str(ok['first_bad'])}"
            f" · {ok['entries']} eventos hoy")
        audit.log("app.start", {"version": VERSION})

    def refresh_devices(self) -> None:
        self.devices = devmod.list_devices()
        opts = []
        for d in self.devices:
            icon = {"system": "🖥", "removable": "🔌", "disk": "💾"}[d.kind]
            opts.append((f"{icon} {d.node} — {d.size_human} — {d.model or d.bus}",
                         d.node))
        sel = self.query_one("#devsel", Select)
        sel.set_options(opts)
        k = self.query_one("#kpi-devs", Static)
        k.update(f"[b]{len(self.devices)}[/b]\ndispositivos")

    def on_select_changed(self, ev: Select.Changed) -> None:
        if ev.select.id != "devsel":
            return
        self.selected_node = ev.value
        self.update_device_info()

    def update_device_info(self) -> None:
        node = self.selected_node
        info = self.query_one("#devinfo", Static)
        kfs = self.query_one("#kpi-fs", Static)
        krisk = self.query_one("#kpi-risk", Static)
        knode = self.query_one("#kpi-node", Static)
        summary = self.query_one("#dash-summary", Static)
        cipherbox = self.query_one("#dash-cipher", Static)
        if not node:
            info.update("—")
            return
        try:
            d = devmod.get_device(node)
        except FileNotFoundError:
            info.update("[bad]desaparecido[/]")
            return
        parts = "\n".join(
            f"  • {p.node} {human_size(p.size)} {p.fstype or '?'}"
            f"{' @' + p.mountpoint if p.mountpoint else ''}" for p in d.partitions)
        info.update(
            f"[b]{d.node}[/b] ({d.kind})\n"
            f"modelo: {d.model or '?'}\nbus: {d.bus}  serie: {d.serial or '?'}\n"
            f"particiones:\n{parts or '  (ninguna)'}")
        knode.update(f"[b]{d.node}[/b]\nseleccionado")
        krisk.update(f"[b]{d.risk_label.split('—')[0].strip()}[/b]\nriesgo")
        # FS probe on a partition
        target = d.partitions[0].node if d.partitions else d.node
        fs_txt = "—"
        try:
            from nyx.nyxfs import fs_summary, UnknownFilesystem
            with open(target, "rb", buffering=0) as fh:
                s = fs_summary(fh)
            fs_txt = s["kind"]
            summary.update(
                f"[b]Filesystem en {target}[/b]\n"
                f"tipo: {s['kind']} · etiqueta: {s.get('label') or '—'} · estado: {s.get('state','—')}\n"
                f"tamaño: {human_size(s['size'])} · grupos/inodos: {s.get('groups','—')}/{s.get('inodes','—')}"
                + (f"\nmontado por última vez en: {s['last_mounted']}" if s.get('last_mounted') else ""))
        except (UnknownFilesystem, PermissionError, Exception) as e:
            summary.update(f"[b]Filesystem en {target}[/b]\n[dim]no reconocido ({type(e).__name__})[/]")
        kfs.update(f"[b]{fs_txt}[/b]\nfilesystem")
        try:
            c = cipher_detect(target)
            if c["encrypted"]:
                cipherbox.update(
                    f"[b]🔐 Cifrado detectado: {c['kind']}[/b]\n" +
                    "\n".join(f"{k}: {v}" for k, v in c["details"].items()))
            else:
                cipherbox.update(
                    f"[b]Cifrado:[/] no detectado · entropía inicial {c.get('entropy','—')}")
        except Exception:
            cipherbox.update("[b]Cifrado:[/] sin datos")

    # ── recovery ─────────────────────────────────────────────────────────
    def on_button_pressed(self, ev) -> None:
        bid = ev.button.id
        if bid == "refresh":
            self.refresh_devices()
        elif bid == "rec-go":
            self.run_recovery()
        elif bid == "rec-cancel":
            self.cancel_event.set()
            self.notify("Cancelando…", severity="warning")
        elif bid == "ana-tl":
            self.run_timeline()
        elif bid == "ana-kwgo":
            self.run_keywords()
        elif bid == "ana-slack":
            self.run_slack()
        elif bid == "ana-cipher":
            self.run_cipher_map()
        elif bid == "ana-hdocs":
            self.run_hdocs()
        elif bid == "wipe-go":
            self.run_wipe()
        elif bid == "wipe-free":
            self.run_wipe_free()
        elif bid == "wipe-cancel":
            self.cancel_event.set()
            self.notify("Cancelando…", severity="warning")

    @work(thread=True)
    def run_recovery(self) -> None:
        node = self.selected_node
        if not node:
            self.notify("Selecciona un dispositivo", severity="warning")
            return
        target = node
        d = devmod.get_device(node)
        if d.partitions and d.kind != "system":
            target = d.partitions[0].node
        mode = self.query_one("#rec-mode", Select).value
        outdir = self.query_one("#rec-out", Input).value.strip() or "nyx_recuperados"
        self.cancel_event.clear()
        self.call_from_thread(self.nlog, "rec",
                              f"[b]▶ Recuperación {mode} sobre {target}[/b]")
        eng = RecoveryEngine(target, outdir)
        eng.cancel = self.cancel_event

        def prog(done, total):
            self.call_from_thread(self.set_progress, "rec", done, total)

        try:
            if mode == "carve":
                res = eng.carve(progress=prog)
            elif mode == "fs":
                res = eng.recover_fs(progress=prog)
            else:
                res1 = eng.recover_fs(progress=prog)
                self.call_from_thread(self.nlog, "rec",
                                      f"FS: {res1['count']} recuperados; ahora carving…")
                res2 = eng.carve(progress=prog)
                res = {"session": eng.session and str(eng.session),
                       "count": res1["count"] + res2["count"],
                       "results": res1["results"] + res2["results"],
                       "stats": eng.stats}
            eng.write_manifest()
            self.call_from_thread(self.nlog, "rec",
                                  f"[ok]✔ {res['count']} archivos · {eng.stats['bytes']/1e6:.1f} MB[/]\n"
                                  f"sala: [u]{res.get('session', '')}[/u]\n"
                                  f"manifiesto: {eng.session / 'manifest.json' if eng.session else '—'}")
            audit.log("recover", {"target": target, "mode": mode, "count": res["count"]})
            self.call_from_thread(self.refresh_devices)
        except Exception as e:
            self.call_from_thread(self.nlog, "rec", f"[bad]✗ Error: {e}[/]")

    # ── analysis ─────────────────────────────────────────────────────────
    @work(thread=True)
    def run_timeline(self) -> None:
        if not (d := self.selected_device()):
            return
        target = d.partitions[0].node if d.partitions else d.node
        self.call_from_thread(self.nlog, "ana", f"[b]📅 Timeline de {target}[/b]")
        try:
            evs = build_timeline(target)
            n = len(evs)
            borra = sum(1 for e in evs if e["deleted"])
            self.call_from_thread(self.nlog, "ana",
                                  f"eventos: {n} · de elementos borrados: {borra}")
            for e in evs[:25]:
                self.call_from_thread(
                    self.nlog, "ana",
                    f"{e['iso']} [{e['type']}] {e['path']}"
                    + (" [bad](borrado)[/]" if e["deleted"] else ""))
            out = Path("nyx_informes") / f"timeline-{time.strftime('%Y%m%d-%H%M%S')}.csv"
            to_csv(evs, str(out))
            self.call_from_thread(self.nlog, "ana", f"[ok]CSV: {out}[/]")
            audit.log("timeline", {"target": target, "events": n})
        except Exception as e:
            self.call_from_thread(self.nlog, "ana", f"[bad]✗ {e}[/]")

    @work(thread=True)
    def run_keywords(self) -> None:
        if not (d := self.selected_device()):
            return
        raw = self.query_one("#ana-kw", Input).value
        kws = [k.strip() for k in raw.split(",") if k.strip()]
        if not kws:
            self.notify("Escribe palabras clave separadas por coma", severity="warning")
            return
        target = d.node if not d.partitions else d.partitions[0].node
        self.call_from_thread(self.nlog, "ana", f"[b]🔎 Buscando {kws} en {target}[/b]")
        self.cancel_event.clear()

        def prog(done, total):
            self.call_from_thread(self.set_progress, "ana", done, total)

        try:
            res = kw_search(target, kws, progress=prog, cancel=self.cancel_event)
            self.call_from_thread(self.nlog, "ana", f"coincidencias: {res['total']}")
            for h in res["hits"][:30]:
                ctx = h["context"].replace("\n", " ")[:90]
                self.call_from_thread(self.nlog, "ana",
                                      f"@0x{h['offset']:x} [acc]{h['keyword']}[/]: {ctx}")
            audit.log("keywords", {"target": target, "kws": kws, "hits": res["total"]})
        except PermissionError:
            self.call_from_thread(self.nlog, "ana", "[bad]✗ sin permisos (ejecuta con sudo)[/]")
        except Exception as e:
            self.call_from_thread(self.nlog, "ana", f"[bad]✗ {e}[/]")

    @work(thread=True)
    def run_slack(self) -> None:
        if not (d := self.selected_device()):
            return
        target = d.partitions[0].node if d.partitions else d.node
        out = Path("nyx_recuperados") / f"slack-{time.strftime('%Y%m%d-%H%M%S')}"
        self.call_from_thread(self.nlog, "ana", f"[b]🕳 Extrayendo slack de {target}[/b]")
        try:
            res = slack_collect(target, str(out))
            self.call_from_thread(self.nlog, "ana",
                                  f"[ok]{res['files']} zonas de slack extraídas → {out}[/]")
            for r in res["results"][:15]:
                self.call_from_thread(
                    self.nlog, "ana",
                    f"{r['path']} · {r['slack_bytes']}B ocultos · no-cero: {r['nonzero']}")
            audit.log("slack", {"target": target, "files": res["files"]})
        except Exception as e:
            self.call_from_thread(self.nlog, "ana", f"[bad]✗ {e}[/]")

    @work(thread=True)
    def run_cipher_map(self) -> None:
        if not (d := self.selected_device()):
            return
        target = d.node if d.kind != "system" else (d.partitions[0].node if d.partitions else d.node)
        self.call_from_thread(self.nlog, "ana", f"[b]🔐 Mapa de entropía de {target}[/b]")
        try:
            pts = entropy_map(target, sample=32768, max_points=80)
            bars = "".join("▁▂▃▄▅▆▇█"[min(7, int(p["entropy"] * 2.5))] for p in pts)
            self.call_from_thread(self.nlog, "ana", f"entropía: {bars}")
            c = cipher_detect(target)
            if c["encrypted"]:
                self.call_from_thread(self.nlog, "ana",
                                      f"[warn]⚠ cifrado detectado: {c['kind']}[/]")
            audit.log("entropy", {"target": target})
        except Exception as e:
            self.call_from_thread(self.nlog, "ana", f"[bad]✗ {e}[/]")

    @work(thread=True)
    def run_hdocs(self) -> None:
        if not (d := self.selected_device()):
            return
        target = d.partitions[0].node if d.partitions else d.node
        self.call_from_thread(self.nlog, "ana", f"[b]📄 Rastreando Office/PDF en {target}[/b]")
        try:
            found = []
            with open(target, "rb", buffering=0) as fh:
                size = fh.seek(0, 2)
                fh.seek(0)
                CHUNK = 8 << 20
                off = 0
                while off < size:
                    buf = fh.read(CHUNK)
                    if not buf:
                        break
                    for f in find_office_in_buffer(buf):
                        found.append({"kind": f["kind"], "offset": off + f["offset"]})
                    off += len(buf)
            ole = sum(1 for f in found if f["kind"] == "ole")
            pdf = sum(1 for f in found if f["kind"] == "pdf")
            self.call_from_thread(self.nlog, "ana",
                                  f"OLE/Office: {ole} · PDF: {pdf}")
            for f in found[:20]:
                self.call_from_thread(self.nlog, "ana", f"  @0x{f['offset']:x} {f['kind']}")
            audit.log("hdocs", {"target": target, "ole": ole, "pdf": pdf})
        except Exception as e:
            self.call_from_thread(self.nlog, "ana", f"[bad]✗ {e}[/]")

    # ── wipe ─────────────────────────────────────────────────────────────
    def run_wipe(self) -> None:
        if not (d := self.selected_device()):
            return
        node = d.node
        rep = safety.assess(node, wipe=True)
        rb = self.query_one("#riskbox", Static)
        rb.update(f"[warn]Riesgo: {rep.label}[/]\n" +
                  "\n".join(rep.warnings) +
                  (("\n[bad]Bloqueos: " + "; ".join(rep.blockers) + "[/]") if rep.blockers else ""))
        if rep.blocked:
            self.query_one("#wipe-log", RichLog).write(
                f"[bad]✗ Operación bloqueada: {'; '.join(rep.blockers)}[/]")
            return
        method = self.query_one("#wipe-method", Select).value
        body = (f"Dispositivo: [b]{node}[/b] ({d.size_human})\n"
                f"Modelo: {d.model or '?'}\nMétodo: {method}\n"
                f"[bad]TODOS los datos se perderán PARA SIEMPRE. "
                f"No existe vuelta atrás.[/]")
        self.push_screen(PhraseScreen("🔥 Confirmar borrado", body,
                                      rep.confirm_phrase), self._phrase_result)

    def run_wipe_free(self) -> None:
        if not (d := self.selected_device()):
            return
        mps = devmod.mounted_mountpoints(d.partitions[0].node if d.partitions else d.node)
        if not mps:
            self.query_one("#wipe-log", RichLog).write(
                "[bad]✗ la partición no está montada; móntala para limpiar espacio libre[/]")
            return
        mp = mps[0]
        body = (f"Se sobrescribirá el ESPACIO LIBRE de [b]{mp}[/b] con datos "
                f"aleatorios.\n[warn]Los ficheros borrados dejarán de ser "
                f"recuperables.[/] Los ficheros existentes no se tocan.")
        self.push_screen(ConfirmScreen("🧽 Limpiar espacio libre", body,
                                       danger=True), self._free_result)

    def _free_result(self, ok: bool) -> None:
        if not ok:
            self.query_one("#wipe-log", RichLog).write("[dim]Cancelado.[/]")
            return
        self._do_wipe_free()

    @work(thread=True)
    def _do_wipe_free(self) -> None:
        d = devmod.get_device(self.selected_node)
        mp = devmod.mounted_mountpoints(d.partitions[0].node if d.partitions else d.node)[0]
        self.call_from_thread(self.nlog, "wipe", f"[b]🧽 Limpiando espacio libre en {mp}[/b]")
        self.cancel_event.clear()

        def prog(written, _t):
            self.call_from_thread(self.set_progress, "wipe", written % (100 << 20), 100 << 20)

        try:
            res = wipe_freespace(mp, method="random", progress=prog,
                                 cancel=self.cancel_event)
            self.call_from_thread(self.nlog, "wipe",
                                  f"[ok]✔ {res['bytes_overwritten']/1e9:.2f} GB sobrescritos · {res['fill_files']} ficheros temporales[/]")
            audit.log("wipe-free", {"mountpoint": mp, "bytes": res["bytes_overwritten"]})
        except Exception as e:
            self.call_from_thread(self.nlog, "wipe", f"[bad]✗ {e}[/]")

    def _phrase_result(self, typed):
        if not typed:
            self.query_one("#wipe-log", RichLog).write("[dim]Cancelado.[/]")
            return
        self._do_wipe(typed)

    @work(thread=True)
    def _do_wipe(self, typed: str) -> None:
        node = self.selected_node
        rep = safety.assess(node, wipe=True)
        try:
            safety.require_phrase(rep, typed)
        except safety.SafetyError as e:
            self.call_from_thread(self.nlog, "wipe", f"[bad]✗ {e}[/]")
            return
        method = self.call_from_thread(lambda: self.query_one("#wipe-method", Select).value)
        verify = self.call_from_thread(lambda: self.query_one("#wipe-verify", Switch).value)
        self.call_from_thread(self.nlog, "wipe", f"[b]🔥 Borrando {node} con {method}…[/b]")
        self.cancel_event.clear()
        start = time.time()

        def prog(pi, npass, pos, size):
            self.call_from_thread(self.set_progress, "wipe", pos, size)
            if pos % (256 << 20) < (8 << 20):
                self.call_from_thread(
                    self.nlog, "wipe",
                    f"pasada {pi}/{npass} · {human_size(pos)} ({pos*100//max(size,1)}%)")

        try:
            with safety.DeviceLock(node):
                um = safety.umount_all(node)
                if um["failed"]:
                    self.call_from_thread(self.nlog, "wipe", f"[warn]no se pudo desmontar: {um['failed']}[/]")
                    return
                cert = wipe_device(node, method=method, progress=prog, verify=verify)
            out = Path("nyx_informes") / f"certificado-borrado-{time.strftime('%Y%m%d-%H%M%S')}.html"
            report.generate({
                "title": "Certificado de borrado seguro",
                "subtitle": f"{node} · {method} · {cert['standard']}",
                "sections": [
                    {"title": "Resumen", "kpis": [
                        ("Dispositivo", node), ("Tamaño", human_size(cert["size"])),
                        ("Método", cert["method"]), ("Estándar", cert["standard"]),
                        ("Pasadas", cert["passes"]),
                        ("Duración", f"{cert['duration_s']} s"),
                        ("Verificación", "OK" if cert["verify"].get("ok") else "REVISAR"),
                        ("Errores escritura", cert["write_errors_total"]),
                    ]},
                ]}, str(out))
            self.call_from_thread(self.nlog, "wipe",
                                  f"[ok]✔ Borrado completado y verificado. Certificado: {out}[/]")
            audit.log("wipe", {"node": node, "method": method, "cert": str(out)})
        except Exception as e:
            self.call_from_thread(self.nlog, "wipe", f"[bad]✗ {e}[/]")

    # ── tab focus helper ─────────────────────────────────────────────────
    def action_focus_tab(self, tab: str) -> None:
        tabs = self.query_one("#workspace", TabbedContent)
        mapping = {"dash": "tab-dash", "rec": "tab-rec", "ana": "tab-ana",
                   "wipe": "tab-wipe", "log": "tab-log"}
        tabs.active = mapping.get(tab, "tab-dash")


def main():
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("⚠ Sin privilegios de root: la lectura de dispositivos fallará. "
              "Ejecuta:  sudo nyx")
    NyxApp().run()


if __name__ == "__main__":
    main()
