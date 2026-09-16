"""
NyxRecover — Aplicación de escritorio con ventana propia (CustomTkinter).

Tema oscuro "dark-glass" coherente con la marca: fondo profundo, acentos
cian/violeta, tarjetas redondeadas. Las operaciones del núcleo corren en
hilos y se comunican con la UI mediante una cola de eventos que se drena
periódicamente (patrón thread-safe para tkinter).
"""
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from nyx.nyxcore.version import APP_NAME, VERSION, TAGLINE
from nyx.nyxcore import device as devmod, safety, audit
from nyx.nyxcore.recovery import RecoveryEngine
from nyx.nyxcore.timeline import build_timeline, to_csv
from nyx.nyxcore.keywords import search as kw_search
from nyx.nyxcore.cipher import detect as cipher_detect
from nyx.nyxwipe.engine import wipe_device, wipe_freespace

# ── paleta ────────────────────────────────────────────────────────────────
BG = "#070b14"
PANEL = "#0d1526"
CARD = "#101a30"
HOVER = "#16223c"
BORDER = "#1f2a44"
FG = "#e5e7eb"
MUTED = "#8b98ad"
CYAN = "#22d3ee"
VIOLET = "#a78bfa"
GREEN = "#34d399"
AMBER = "#fbbf24"
RED = "#f87171"

ctk.set_appearance_mode("dark")


class NyxApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"NyxRecover v{VERSION} — recuperacion forense y borrado seguro")
        self.geometry("1180x720")
        self.minsize(980, 620)
        self.configure(fg_color=BG)

        self.q: queue.Queue = queue.Queue()
        self.devices: list = []
        self.current = None
        self._busy = False

        self._build_sidebar()
        self._build_pages()
        self.after(200, self.refresh_devices)
        self.after(60, self._drain)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ═══════════════════════════ UI base ═══════════════════════════
    def _card(self, parent) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, corner_radius=14, fg_color=CARD,
                            border_width=1, border_color=BORDER)

    def _h(self, parent, text) -> ctk.CTkLabel:
        return ctk.CTkLabel(parent, text=text, font=("Segoe UI", 20, "bold"),
                            text_color=FG, anchor="w", justify="left")

    def _sub(self, parent, text) -> ctk.CTkLabel:
        return ctk.CTkLabel(parent, text=text, font=("Segoe UI", 11),
                            text_color=MUTED, anchor="w", justify="left")

    def _ghost_btn(self, parent, text, cmd, color=CYAN) -> ctk.CTkButton:
        return ctk.CTkButton(parent, text=text, command=cmd, height=34,
                             fg_color="#132035", hover_color=HOVER,
                             text_color=color, corner_radius=8)

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=PANEL)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        ctk.CTkLabel(sb, text="NyxRecover", font=("Segoe UI", 21, "bold"),
                     text_color=FG).pack(pady=(22, 0))
        ctk.CTkLabel(sb, text=f"v{VERSION}", font=("Segoe UI", 10),
                     text_color=CYAN).pack(pady=(0, 18))

        self._nav_btns = {}
        for pid, label in (("dash", "Panel"), ("rec", "Recuperar"),
                           ("ana", "Analizar"), ("wipe", "Borrar"),
                           ("log", "Registro")):
            b = ctk.CTkButton(sb, text=f"  {label}", anchor="w", height=42,
                              corner_radius=10, fg_color="transparent",
                              hover_color=HOVER, text_color=FG,
                              font=("Segoe UI", 13),
                              command=lambda p=pid: self.show(p))
            b.pack(fill="x", padx=12, pady=3)
            self._nav_btns[pid] = b

        ctk.CTkLabel(sb, text="").pack(expand=True)
        ctk.CTkLabel(sb, text="GPL v3 · sin telemetria", font=("Segoe UI", 9),
                     text_color=MUTED).pack(pady=(0, 6))
        self._ghost_btn(sb, "Refrescar discos", self.refresh_devices).pack(
            fill="x", padx=12, pady=(0, 14))

    def _build_pages(self):
        host = ctk.CTkFrame(self, fg_color=BG)
        host.pack(side="right", fill="both", expand=True)
        self.pages = {}
        for pid in ("dash", "rec", "ana", "wipe", "log"):
            f = ctk.CTkFrame(host, fg_color=BG)
            self.pages[pid] = f
        self._page_dash(self.pages["dash"])
        self._page_rec(self.pages["rec"])
        self._page_ana(self.pages["ana"])
        self._page_wipe(self.pages["wipe"])
        self._page_log(self.pages["log"])
        self.show("dash")

    def show(self, pid):
        for f in self.pages.values():
            f.pack_forget()
        self.pages[pid].pack(fill="both", expand=True)
        for k, b in self._nav_btns.items():
            b.configure(fg_color="#132035" if k == pid else "transparent",
                        text_color=CYAN if k == pid else FG)

    # ═══════════════════════════ páginas ═══════════════════════════
    def _page_dash(self, f):
        self._h(f, "Panel").pack(pady=(20, 2), padx=24, anchor="w")
        self._sub(f, "Dispositivos detectados — clic para seleccionar").pack(
            padx=24, anchor="w")

        kpis = ctk.CTkFrame(f, fg_color=BG)
        kpis.pack(fill="x", padx=24, pady=12)
        self.kpi_devs = self._kpi(kpis, "0", "dispositivos")
        self.kpi_node = self._kpi(kpis, "—", "seleccionado")
        self.kpi_fs = self._kpi(kpis, "—", "filesystem")
        self.kpi_risk = self._kpi(kpis, "—", "riesgo")

        self.dev_list = ctk.CTkScrollableFrame(f, fg_color=BG, height=300)
        self.dev_list.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        ctk.CTkLabel(self.dev_list, text="Buscando dispositivos…",
                     text_color=MUTED).pack(pady=20)

    def _kpi(self, parent, val, label):
        c = self._card(parent)
        c.pack(side="left", fill="x", expand=True, padx=4)
        v = ctk.CTkLabel(c, text=val, font=("Segoe UI", 22, "bold"),
                         text_color=CYAN)
        v.pack(pady=(10, 0))
        ctk.CTkLabel(c, text=label, font=("Segoe UI", 10),
                     text_color=MUTED).pack(pady=(0, 10))
        return v

    def _page_rec(self, f):
        self._h(f, "Recuperar datos borrados").pack(pady=(20, 2), padx=24, anchor="w")
        self._sub(f, "Parser de filesystem + carving por firmas · escribe siempre en otra carpeta").pack(
            padx=24, anchor="w")

        c = self._card(f)
        c.pack(fill="x", padx=24, pady=12)
        ctk.CTkLabel(c, text="Modo de recuperación", font=("Segoe UI", 12, "bold"),
                     text_color=FG).pack(pady=(14, 4), anchor="w", padx=16)
        self.rec_mode = ctk.CTkSegmentedButton(
            c, values=["Inteligente", "Solo FS", "Solo carving"],
            selected_color="#132035", selected_hover_color=HOVER,
            unselected_color=CARD, unselected_hover_color=HOVER,
            fg_color=CARD, text_color=FG)
        self.rec_mode.set("Inteligente")
        self.rec_mode.pack(anchor="w", padx=16, pady=(0, 10))

        self.rec_deleted = ctk.CTkSwitch(
            c, text="Solo archivos eliminados (ignorar vivos)",
            progress_color=CYAN, text_color=FG)
        self.rec_deleted.pack(anchor="w", padx=16, pady=(0, 12))

        row = ctk.CTkFrame(c, fg_color=CARD)
        row.pack(fill="x", padx=16, pady=(0, 16))
        self.rec_out = ctk.StringVar(value=os.path.expanduser("~/nyx_recuperados"))
        ctk.CTkEntry(row, textvariable=self.rec_out, width=420).pack(side="left", padx=(0, 8))
        self._ghost_btn(row, "Carpeta...", self._pick_out).pack(side="left")

        ctk.CTkButton(f, text="Iniciar recuperacion", height=46,
                      font=("Segoe UI", 14, "bold"),
                      fg_color=CYAN, hover_color="#0ea5c9", text_color="#04212b",
                      corner_radius=12, command=self._run_recover
                      ).pack(fill="x", padx=24)
        self.rec_bar = ctk.CTkProgressBar(f, progress_color=CYAN, fg_color=CARD, height=14)
        self.rec_bar.set(0)
        self.rec_bar.pack(fill="x", padx=24, pady=(8, 4))
        self.rec_lbl = ctk.CTkLabel(f, text="Listo.", text_color=MUTED, anchor="w")
        self.rec_lbl.pack(fill="x", padx=24)

    def _pick_out(self):
        d = filedialog.askdirectory(initialdir=self.rec_out.get())
        if d:
            self.rec_out.set(d)

    def _page_ana(self, f):
        self._h(f, "Analisis forense").pack(pady=(20, 2), padx=24, anchor="w")
        self._sub(f, "Timeline · keywords · cifrado — sobre el dispositivo seleccionado").pack(
            padx=24, anchor="w")

        row = ctk.CTkFrame(f, fg_color=BG)
        row.pack(fill="x", padx=24, pady=12)

        c1 = self._card(row)
        c1.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(c1, text="Linea temporal", font=("Segoe UI", 13, "bold"),
                     text_color=GREEN).pack(pady=(14, 2))
        ctk.CTkLabel(c1, text="Historial de creacion, modificacion\ny borrado de archivos.",
                     text_color=MUTED, justify="left").pack(padx=14)
        self._ghost_btn(c1, "Generar CSV", self._run_timeline, GREEN).pack(pady=10)

        c2 = self._card(row)
        c2.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(c2, text="Busqueda de texto", font=("Segoe UI", 13, "bold"),
                     text_color=CYAN).pack(pady=(14, 2))
        ctk.CTkLabel(c2, text="Contrasenas, nombres, DNI... en bytes crudos,\ncon offset y contexto.",
                     text_color=MUTED, justify="left").pack(padx=14)
        self.kw_entry = ctk.CTkEntry(c2, placeholder_text="palabras, separadas, por, comas")
        self.kw_entry.pack(fill="x", padx=14, pady=6)
        self._ghost_btn(c2, "Buscar en el disco", self._run_keywords).pack(pady=10)

        c3 = self._card(row)
        c3.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(c3, text="Cifrado", font=("Segoe UI", 13, "bold"),
                     text_color=RED).pack(pady=(14, 2))
        ctk.CTkLabel(c3, text="LUKS / BitLocker / VeraCrypt\n+ mapa de entropia.",
                     text_color=MUTED, justify="left").pack(padx=14)
        self._ghost_btn(c3, "Analizar cifrado", self._run_cipher, RED).pack(pady=10)

        self.ana_box = self._textbox(f)

    def _page_wipe(self, f):
        self._h(f, "Borrado seguro").pack(pady=(20, 2), padx=24, anchor="w")
        self._sub(f, "IRREVERSIBLE · verificacion por muestreo · certificado HTML").pack(
            padx=24, anchor="w")

        c = self._card(f)
        c.pack(fill="x", padx=24, pady=12)
        ctk.CTkLabel(c, text="Metodo de borrado", font=("Segoe UI", 12, "bold"),
                     text_color=FG).pack(pady=(14, 4), anchor="w", padx=16)
        self.wipe_method = ctk.CTkOptionMenu(
            c, values=["zero — NIST 800-88 (recomendado)", "dod5220 — DoD 5220.22-M",
                       "random — CSPRNG", "gutmann — 35 pasadas"],
            fg_color=CARD, button_color="#132035", button_hover_color=HOVER,
            text_color=FG)
        self.wipe_method.set("zero — NIST 800-88 (recomendado)")
        self.wipe_method.pack(anchor="w", padx=16, pady=(0, 10))

        self.wipe_verify = ctk.CTkSwitch(c, text="Verificar tras el borrado (muestreo)",
                                         progress_color=GREEN, text_color=FG)
        self.wipe_verify.select()
        self.wipe_verify.pack(anchor="w", padx=16, pady=(0, 6))

        self.wipe_free = ctk.CTkSwitch(c, text="Solo espacio libre (conserva tus archivos)",
                                       progress_color=AMBER, text_color=FG)
        self.wipe_free.pack(anchor="w", padx=16, pady=(0, 12))

        self.risk_lbl = ctk.CTkLabel(c, text="Selecciona un dispositivo en el Panel.",
                                     text_color=AMBER, justify="left", anchor="w",
                                     font=("Segoe UI", 11), wraplength=700)
        self.risk_lbl.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(f, text="Iniciar borrado", height=46,
                      font=("Segoe UI", 14, "bold"),
                      fg_color=RED, hover_color="#dc2626", text_color="#2b0505",
                      corner_radius=12, command=self._start_wipe
                      ).pack(fill="x", padx=24)
        self.wipe_bar = ctk.CTkProgressBar(f, progress_color=RED, fg_color=CARD, height=14)
        self.wipe_bar.set(0)
        self.wipe_bar.pack(fill="x", padx=24, pady=(8, 4))
        self.wipe_lbl = ctk.CTkLabel(f, text="Listo.", text_color=MUTED, anchor="w")
        self.wipe_lbl.pack(fill="x", padx=24)

    def _page_log(self, f):
        self._h(f, "Registro").pack(pady=(20, 2), padx=24, anchor="w")
        self._sub(f, "Todo lo que hace la aplicacion · journal con hash-chain SHA-256 (nyx audit)").pack(
            padx=24, anchor="w")
        self.logbox = self._textbox(f)

    def _textbox(self, parent) -> tk.Text:
        box = tk.Text(parent, height=13, bg="#0a0f1e", fg=FG,
                      insertbackground=FG, relief="flat", padx=12, pady=10,
                      font=("Consolas", 10))
        box.pack(fill="both", expand=True, padx=24, pady=12)
        for tag, col in (("cyan", CYAN), ("green", GREEN), ("amber", AMBER),
                         ("red", RED), ("violet", VIOLET), ("muted", MUTED)):
            box.tag_configure(tag, foreground=col)
        return box

    # ═══════════════════════ eventos en cola (thread-safe) ═════════════
    def _drain(self):
        try:
            while True:
                kind, a, b = self.q.get_nowait()
                if kind == "log":
                    self._log(a, b)
                elif kind == "prog":
                    (self.rec_bar if a == "rec" else self.wipe_bar).set(b)
                elif kind == "stat":
                    (self.rec_lbl if a == "rec" else self.wipe_lbl).configure(text=b)
        except queue.Empty:
            pass
        self.after(60, self._drain)

    def _log(self, tag, msg):
        box = getattr(self, "logbox", None)
        if not box:
            return
        color = {"app": "cyan", "rec": "green", "ana": "violet",
                 "wipe": "red", "warn": "amber"}.get(tag, "muted")
        ts = time.strftime("%H:%M:%S")
        try:
            box.insert("end", f"[{ts}] {tag:<5} ", color)
            box.insert("end", msg + "\n", "muted")
            box.see("end")
        except tk.TclError:
            pass

    # ═══════════════════════ dispositivos ═══════════════════════
    def refresh_devices(self):
        def worker():
            try:
                devs = devmod.list_devices()
            except Exception as e:
                devs = []
                self.q.put(("log", "warn", f"error listando discos: {e}"))
            self.after(0, lambda: self._render_devices(devs))

        threading.Thread(target=worker, daemon=True).start()

    def _render_devices(self, devs):
        self.devices = devs
        for w in self.dev_list.winfo_children():
            w.destroy()
        self.kpi_devs.configure(text=str(len(devs)))
        if not devs:
            ctk.CTkLabel(self.dev_list,
                         text="No hay dispositivos accesibles (prueba a ejecutar como root/administrador).",
                         text_color=MUTED).pack(pady=16)
            return
        for d in devs:
            icon = {"system": "SYS", "removable": "USB", "disk": "DISK"}[d.kind]
            color = {"system": RED, "removable": AMBER, "disk": CYAN}[d.kind]
            row = self._card(self.dev_list)
            row.pack(fill="x", pady=4, padx=2)
            ctk.CTkLabel(row, text=f"  {d.node}", font=("Consolas", 13, "bold"),
                         text_color=FG).pack(side="left", padx=14, pady=10)
            ctk.CTkLabel(row, text=f"{d.size_human} · {d.model or '?'} · {d.bus}",
                         text_color=MUTED).pack(side="left", padx=6)
            ctk.CTkLabel(row, text=icon, text_color=color,
                         font=("Segoe UI", 10, "bold")).pack(side="right", padx=14)
            for w in (row,) + tuple(row.winfo_children()):
                w.bind("<Button-1>", lambda e, dd=d: self._select(dd))
        pick = next((d for d in devs if d.kind == "removable"), devs[0])
        self._select(pick)

    def _select(self, d):
        self.current = d
        self.kpi_node.configure(text=d.node)
        self.kpi_fs.configure(text=(d.fstype or "—").upper())
        self.kpi_risk.configure(
            text={"system": "CRITICO", "disk": "ALTO", "removable": "MEDIO"}[d.kind],
            text_color={"system": RED, "disk": AMBER, "removable": GREEN}[d.kind])
        self.q.put(("log", "app", f"seleccionado {d.node} ({d.size_human}, {d.kind})"))
        self.risk_lbl.configure(
            text=f"Objetivo: {d.node} · {d.size_human} · riesgo {d.kind.upper()}\n"
                 f"La frase de confirmacion se pedira al pulsar Iniciar borrado.")

    # ═══════════════════════ operaciones ═══════════════════════
    def _ok(self):
        if not self.current:
            messagebox.showinfo("NyxRecover", "Selecciona un dispositivo en el Panel.")
            return False
        if self._busy:
            messagebox.showinfo("NyxRecover", "Ya hay una operacion en curso.")
            return False
        return True

    def _run_recover(self):
        if not self._ok():
            return
        self._busy = True
        mode = {"Inteligente": "smart", "Solo FS": "fs", "Solo carving": "carve"}[
            self.rec_mode.get()]
        only_deleted = bool(self.rec_deleted.get())
        out = self.rec_out.get().strip() or "~/nyx_recuperados"
        src = self.current.node

        def worker():
            try:
                self.q.put(("prog", "rec", 0.02))
                self.q.put(("stat", "rec", "Escaneando..."))
                eng = RecoveryEngine(src, os.path.expanduser(out))
                if mode == "carve":
                    res = eng.carve(progress=lambda d, t: self.q.put(
                        ("prog", "rec", min(1.0, d / max(t, 1)))))
                elif mode == "fs":
                    res = eng.recover_fs(include_alive=not only_deleted)
                else:
                    r1 = eng.recover_fs(include_alive=not only_deleted)
                    r2 = eng.carve(progress=lambda d, t: self.q.put(
                        ("prog", "rec", min(1.0, d / max(t, 1)))))
                    res = {"count": r1["count"] + r2["count"]}
                eng.write_manifest()
                count, sess = res.get("count", 0), str(eng.session)
                self.q.put(("prog", "rec", 1.0))
                self.q.put(("stat", "rec", f"OK  {count} elementos recuperados -> {sess}"))
                self.q.put(("log", "rec", f"OK {count} recuperados -> {sess}"))
                audit.log("gui-recover", {"source": src, "mode": mode, "count": count})
            except Exception as e:
                self.q.put(("stat", "rec", f"Error: {e}"))
                self.q.put(("log", "warn", f"recuperacion: {e}"))
            finally:
                self._busy = False

        self.q.put(("log", "rec", f"inicio recuperacion {mode} sobre {src}"))
        threading.Thread(target=worker, daemon=True).start()

    def _run_timeline(self):
        if not self._ok():
            return
        self._busy = True
        src = self.current.node

        def worker():
            try:
                evs = build_timeline(src)
                out = os.path.expanduser(
                    f"~/nyx_informes/timeline-{time.strftime('%Y%m%d-%H%M%S')}.csv")
                os.makedirs(os.path.dirname(out), exist_ok=True)
                to_csv(evs, out)
                self.q.put(("log", "ana", f"timeline: {len(evs)} eventos -> {out}"))
            except Exception as e:
                self.q.put(("log", "warn", f"timeline: {e}"))
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _run_keywords(self):
        if not self._ok():
            return
        kws = [k.strip() for k in self.kw_entry.get().split(",") if k.strip()]
        if not kws:
            messagebox.showinfo("NyxRecover", "Escribe al menos una palabra clave.")
            return
        self._busy = True
        src = self.current.node

        def worker():
            try:
                res = kw_search(src, kws)
                hits = res.get("hits", [])
                for h in hits[:10]:
                    self.q.put(("log", "ana",
                                f"{h['keyword']} @ 0x{h['offset']:x} · {(h['context'] or '')[:56]}"))
                if not hits:
                    self.q.put(("log", "ana", "sin coincidencias"))
                audit.log("gui-keywords", {"source": src, "hits": len(hits)})
            except Exception as e:
                self.q.put(("log", "warn", f"keywords: {e}"))
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _run_cipher(self):
        if not self._ok():
            return
        self._busy = True
        src = self.current.node

        def worker():
            try:
                c = cipher_detect(src)
                self.q.put(("log", "ana", f"cifrado: {c}"))
            except Exception as e:
                self.q.put(("log", "warn", f"cipher: {e}"))
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    # ═══════════════════════ borrado con doble alerta ═════════════════
    def _start_wipe(self):
        if not self._ok():
            return
        d = self.current
        free_only = bool(self.wipe_free.get())
        rep = safety.assess(d.node, wipe=not free_only)
        if rep.blocked:
            messagebox.showerror(
                "Operacion bloqueada",
                "La capa de seguridad bloquea esta operacion:\n\n"
                + "\n".join(rep.blockers))
            return
        method = self.wipe_method.get().split(" ")[0]
        verify = bool(self.wipe_verify.get())
        phrase = rep.confirm_phrase

        if not messagebox.askyesno(
                "Borrado irreversible",
                f"Dispositivo: {d.node} ({d.size_human})\nMetodo: {method}\n\n"
                + ("Se sobrescribira SOLO el espacio libre.\n\n" if free_only else
                   "TODOS los datos se perderan PARA SIEMPRE.\n\n")
                + "Continuar al paso de confirmacion?"):
            self.q.put(("log", "wipe", "cancelado en el primer aviso"))
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Confirmacion requerida")
        dlg.geometry("540x260")
        dlg.configure(fg_color=PANEL)
        dlg.transient(self)
        dlg.grab_set()
        dlg.attributes("-topmost", True)
        ctk.CTkLabel(dlg, text="Para confirmar, escribe EXACTAMENTE:",
                     text_color=FG).pack(pady=(24, 6))
        ctk.CTkLabel(dlg, text=phrase, font=("Consolas", 17, "bold"),
                     text_color=AMBER).pack(pady=(0, 14))
        entry = ctk.CTkEntry(dlg, width=320, font=("Consolas", 13), show="")
        entry.pack(pady=4)
        entry.focus_set()

        def confirm():
            if entry.get().strip().upper() != phrase:
                messagebox.showwarning("No coincide",
                                       "La frase no coincide — operacion cancelada.")
                dlg.destroy()
                return
            dlg.destroy()
            self._do_wipe(d, method, verify, free_only)

        ctk.CTkButton(dlg, text="Confirmar borrado", fg_color=RED,
                      hover_color="#dc2626", command=confirm).pack(pady=16)
        entry.bind("<Return>", lambda e: confirm())

    def _do_wipe(self, d, method, verify, free_only):
        self._busy = True

        def worker():
            try:
                if free_only:
                    mps = devmod.mounted_mountpoints(d.node)
                    if not mps and os.name == "nt":
                        mps = [os.environ.get("SystemDrive", "C:") + "\\"]
                    if not mps:
                        raise RuntimeError("El dispositivo no esta montado; usa borrado completo.")

                    def prog(w, _t):
                        self.q.put(("prog", "wipe", (w // (20 << 20) % 50) / 100))

                    res = wipe_freespace(mps[0], method=method, progress=prog)
                    gb = res["bytes_overwritten"] / 1e9
                    self.q.put(("prog", "wipe", 1.0))
                    self.q.put(("stat", "wipe", f"OK {gb:.2f} GB de espacio libre sobrescrito"))
                    self.q.put(("log", "wipe", f"OK espacio libre limpiado ({gb:.2f} GB)"))
                else:
                    if os.name != "nt":
                        um = safety.umount_all(d.node)
                        if um["failed"]:
                            raise RuntimeError("No se pudo desmontar: " + ", ".join(um["failed"]))
                    with safety.DeviceLock(d.node):
                        def prog(_p, _n, pos, sz):
                            self.q.put(("prog", "wipe", min(1.0, pos / max(sz, 1))))

                        cert = wipe_device(d.node, method=method, verify=verify, progress=prog)
                    ok = bool(cert["verify"].get("ok"))
                    self.q.put(("prog", "wipe", 1.0))
                    self.q.put(("stat", "wipe",
                                f"OK borrado {method} · verificacion: {ok}"))
                    self.q.put(("log", "wipe", f"OK borrado {method} · verificado: {ok}"))
                audit.log("gui-wipe", {"node": d.node, "method": method,
                                       "free_only": free_only})
            except Exception as e:
                self.q.put(("stat", "wipe", f"Error: {e}"))
                self.q.put(("log", "warn", f"wipe: {e}"))
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self):
        if self._busy and not messagebox.askyesno(
                "Operacion en curso", "Hay una operacion en curso. Salir de todos modos?"):
            return
        self.destroy()


def main():
    app = NyxApp()
    app.mainloop()


if __name__ == "__main__":
    main()
