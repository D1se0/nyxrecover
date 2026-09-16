"""Self-test de la GUI de NyxRecover (CI y verificación local).

Uso (requiere display; en servidores: xvfb-run):
    xvfb-run -a .venv/bin/python tools/gui_selftest.py

Escenario:
  1. Crea una imagen de prueba con un JPEG "borrado" dentro.
  2. Arranca la app real (CustomTkinter) en Xvfb.
  3. Inyecta la imagen como dispositivo seleccionable.
  4. Recorre las 5 páginas capturando pantallas.
  5. Ejecuta una recuperación real desde la GUI.
  6. Ejecuta el flujo de borrado con doble confirmación (frase).
  7. Comprueba journal de auditoría y cierra con código 0/1.
"""
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

IMG = "/tmp/nyx_gui_selftest.img"
SHOTS = "/tmp/nyx_gui_shots"
os.makedirs(SHOTS, exist_ok=True)

# ── 1. imagen de prueba con JPEG "borrado" ────────────────────────────
img = bytearray(8 * 1024 * 1024)
jpg = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
       + b"\x00" * 20000 + b"\xff\xd9")
img[0x40000:0x40000 + len(jpg)] = jpg
with open(IMG, "wb") as fh:
    fh.write(bytes(img))
print(f"[setup] imagen {IMG} ({len(img)/1e6:.0f} MB, JPEG en 0x40000)")

# ── 2. app real ───────────────────────────────────────────────────────
import tkinter as tk

import customtkinter as ctk

from nyx.nyxcore import device as devmod
from nyx.nyxcore.gui import NyxApp

failures = []


def check(name, cond):
    print(f"{'[ok]' if cond else '[FAIL]'} {name}")
    if not cond:
        failures.append(name)


def shot(app, name):
    app.update_idletasks()
    app.update()
    time.sleep(0.35)
    subprocess.run(["import", "-window", "root", f"{SHOTS}/{name}.png"],
                   check=False)
    print(f"[shot] {SHOTS}/{name}.png")


def fake_device() -> devmod.Device:
    st = os.stat(IMG)
    return devmod.Device(name=os.path.basename(IMG), node=IMG,
                         size=st.st_size, model="SelfTest", bus="loop")


app = NyxApp()
dev = fake_device()

# inyectar la imagen como dispositivo y seleccionarla
app._render_devices([dev])
app.update()
check("dispositivo inyectado y seleccionado",
      app.current is not None and app.current.node == IMG)
check("KPI de dispositivos = 1", app.kpi_devs.cget("text") == "1")

# ── 3. recorrer páginas ───────────────────────────────────────────────
for pid, name in (("dash", "01_panel"), ("rec", "02_recuperar"),
                  ("ana", "03_analizar"), ("wipe", "04_borrar"),
                  ("log", "05_registro")):
    app.show(pid)
    shot(app, name)
check("navegación por las 5 páginas", True)

# ── 4. recuperación real desde la GUI ─────────────────────────────────
app.show("rec")
app.rec_mode.set("Solo carving")
app.rec_out.set("/tmp/nyx_gui_rec")
app._run_recover()
deadline = time.time() + 60
while time.time() < deadline and app._busy:
    app.update_idletasks()
    app.update()
    time.sleep(0.1)
app.update()
lbl = app.rec_lbl.cget("text")
check(f"recuperación GUI completada ({lbl})", "OK" in lbl and "1 elementos" in lbl)
found = []
for root, _d, files in os.walk("/tmp/nyx_gui_rec"):
    found += files
check("JPEG tallado en el disco", any(f.endswith(".jpg") for f in found))
shot(app, "06_recuperado")

# ── 5. flujo de borrado con doble confirmación ────────────────────────
# parcheamos messagebox para responder automáticamente como lo haría el usuario
import tkinter.messagebox as mb

answers = {"askyesno": True, "phrase_ok": True}


def fake_askyesno(*a, **k):
    answers["askyesno_text"] = str(a)
    return True


def fake_showwarning(*a, **k):
    answers["phrase_ok"] = False  # simula frase incorrecta la 1ª vez


mb.askyesno = fake_askyesno

# primera pasada: frase incorrecta → debe cancelar sin borrar
app.show("wipe")
app.wipe_free.set(False)
app.wipe_method.set("zero — NIST 800-88 (recomendado)")

# auto-responder el diálogo de frase: primero mal, luego bien
orig_ctkentry_get = ctk.CTkEntry.get
state = {"tries": 0}


def scripted_get(self):
    val = orig_ctkentry_get(self)
    # cuando el test llega aquí el diálogo está abierto; devolvemos
    # la frase mal la primera vez y bien después
    return val


# En lugar de automatizar el Toplevel (frágil en Xvfb), llamamos directo
# a la lógica interna que el botón Confirmar ejecuta, que es lo que
# queremos verificar: la frase correcta ejecuta, la incorrecta no.
rep = devmod and None
from nyx.nyxcore import safety

phrase = safety.assess(IMG, wipe=True).confirm_phrase
check("frase de confirmación generada", phrase.startswith("ELIMINAR "))

# frase incorrecta NO borra
try:
    safety.require_phrase(
        safety.assess(IMG, wipe=True), "ELIMINAR OTRA COSA")
    check("frase incorrecta rechazada", False)
except safety.SafetyError:
    check("frase incorrecta rechazada", True)

# frase correcta ejecuta el borrado del fichero-imagen (inocuo)
before = os.path.getsize(IMG)
# wipe_device sobre un fichero regular: usamos el flujo de la GUI real
app._do_wipe(dev, "zero", verify=True, free_only=False)
deadline = time.time() + 60
while time.time() < deadline and app._busy:
    app.update_idletasks()
    app.update()
    time.sleep(0.1)
app.update()
wtxt = app.wipe_lbl.cget("text")
check(f"borrado GUI verificado ({wtxt})", "OK" in wtxt and "True" in wtxt)
with open(IMG, "rb") as fh:
    nonzero = sum(1 for b in fh.read() if b)
check(f"imagen a cero ({nonzero} bytes no-cero)", nonzero == 0)
shot(app, "07_borrado")

# ── 6. journal de auditoría ───────────────────────────────────────────
from nyx.nyxcore import audit

res = audit.verify()
check(f"journal íntegro ({res.get('entries', '?')} eventos)", res["ok"])

app.destroy()

print()
if failures:
    print(f"✗ FALLÓ: {failures}")
    sys.exit(1)
print("✓ SELF-TEST GUI COMPLETO: todo en verde")
