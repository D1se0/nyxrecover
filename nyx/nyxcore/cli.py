"""NyxRecover CLI — every feature reachable from the terminal too."""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nyx.nyxcore.version import APP_NAME, VERSION, TAGLINE
from nyx.nyxcore import device as devmod, safety, audit, report
from nyx.nyxcore.scan import scan_raw
from nyx.nyxcore.recovery import RecoveryEngine
from nyx.nyxcore.timeline import build_timeline, to_csv
from nyx.nyxcore.keywords import search as kw_search
from nyx.nyxcore.slack import collect as slack_collect
from nyx.nyxcore.cipher import detect as cipher_detect, entropy_map
from nyx.nyxcore.device import human_size
from nyx.nyxwipe.engine import wipe_device, wipe_freespace

console = Console()


def _die(msg: str, code: int = 2):
    console.print(f"[bold red]✗ {msg}[/]")
    sys.exit(code)


def _resolve_partition(node: str) -> str:
    d = devmod.get_device(node)
    return d.partitions[0].node if d.partitions else d.node


def _progress_bar():
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    return Progress(TextColumn("[progress.description]{task.description}"),
                    BarColumn(), TextColumn("{task.percentage:>5.1f}%"),
                    TimeElapsedColumn(), console=console, transient=True)


# ── commands ─────────────────────────────────────────────────────────────
def cmd_devices(_a):
    devs = devmod.list_devices()
    t = Table(title=f"{APP_NAME} — dispositivos", header_style="bold cyan")
    for col in ("Nodo", "Tipo", "Tamaño", "Modelo", "Bus", "Serie", "Particiones"):
        t.add_column(col)
    for d in devs:
        icon = {"system": "🖥", "removable": "🔌", "disk": "💾"}[d.kind]
        parts = ", ".join(p.node for p in d.partitions) or "—"
        t.add_row(f"{icon} {d.node}", d.kind, d.size_human,
                  d.model or "?", d.bus, d.serial or "?", parts)
    console.print(t)


def cmd_info(a):
    d = devmod.get_device(a.node)
    rep = safety.assess(a.node)
    info = devmod.hwinfo(d.node)
    body = (f"[b]{d.node}[/b] — {d.kind} · {d.size_human}\n"
            f"modelo: {d.model or '?'} · serie: {d.serial or '?'} · bus: {d.bus}\n"
            f"riesgo: {rep.label}\n"
            + "\n".join(rep.warnings)
            + ("\n[red]Bloqueos: " + "; ".join(rep.blockers) + "[/]" if rep.blockers else ""))
    console.print(Panel(body, title="Dispositivo"))
    if info.get("geometry"):
        g = info["geometry"]
        console.print(Panel(
            f"sectores: {g['sectors']} · lógico: {g['logical_block']}B · "
            f"físico: {g['physical_block']}B · rotacional: {g['rotational']}\n"
            f"scheduler: {g['scheduler']} · max_sectors_kb: {g['max_sectors_kb']}\n"
            + "\n".join(f"{k}: {v}" for k, v in info["smart"].items()),
            title="Hardware"))
    target = _resolve_partition(d.node)
    try:
        from nyx.nyxfs import fs_summary, UnknownFilesystem
        with open(target, "rb", buffering=0) as fh:
            s = fs_summary(fh)
        console.print(Panel(json.dumps(s, indent=2, ensure_ascii=False),
                            title=f"Filesystem {target}"))
    except (UnknownFilesystem, PermissionError, OSError) as e:
        console.print(f"[yellow]filesystem: sin datos ({e})[/]")


def cmd_scan(a):
    src = a.source
    prog = _progress_bar()
    with prog:
        task = prog.add_task("escaneando", total=None)
        res = scan_raw(src, entropy=a.entropy,
                       progress=lambda d, t: prog.update(task, completed=d, total=t))
    t = Table(title=f"Firmas en {src}", header_style="bold cyan")
    for col in ("Firma", "Tipo", "Categoría", "Offset"):
        t.add_column(col)
    cats = {}
    for h in res["hits"]:
        t.add_row(h["name"], h["ext"], h["cat"], f"0x{h['offset']:x}")
        cats[h["cat"]] = cats.get(h["cat"], 0) + 1
    console.print(t)
    console.print(f"total: {len(res['hits'])} · velocidad: "
                  f"{res['speed']/1e6:.0f} MB/s · {res['elapsed']:.1f}s")
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(res, indent=2, default=str))
        console.print(f"JSON → {a.json_out}")
    audit.log("scan", {"source": src, "hits": len(res["hits"])})


def cmd_recover(a):
    eng = RecoveryEngine(a.source, a.out)
    cancel = threading.Event()
    prog = _progress_bar()
    with prog:
        task = prog.add_task("recuperando", total=None)

        def cb(done, total):
            prog.update(task, completed=done, total=total)

        if a.mode == "carve":
            res = eng.carve(progress=cb, min_size=a.min_size)
        elif a.mode == "fs":
            res = eng.recover_fs(progress=cb,
                                 include_alive=not a.only_deleted,
                                 only_paths=a.paths)
        else:
            r1 = eng.recover_fs(progress=cb, include_alive=not a.only_deleted)
            r2 = eng.carve(progress=cb)
            res = {"session": str(eng.session), "count": r1["count"] + r2["count"],
                   "results": r1["results"] + r2["results"]}
    eng.write_manifest()
    console.print(Panel(
        f"✔ [b]{res['count']}[/b] elementos · {human_size(eng.stats['bytes'])}\n"
        f"sala: [u]{res.get('session', '')}[/u]\n"
        f"manifiesto: {eng.session / 'manifest.json' if eng.session else '—'}",
        title="Recuperación completada"))
    audit.log("recover", {"source": a.source, "mode": a.mode,
                          "count": res["count"]})


def cmd_timeline(a):
    evs = build_timeline(a.source)
    out = Path(a.out) if a.out else \
        Path("nyx_informes") / f"timeline-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    to_csv(evs, str(out))
    t = Table(title=f"Timeline ({len(evs)} eventos)", header_style="bold cyan")
    for col in ("Fecha", "T", "Acción", "Ruta", "Bytes", "Estado"):
        t.add_column(col)
    for e in evs[: a.limit]:
        t.add_row(e["iso"], e["type"], e["label"], e["path"], str(e["size"]),
                  "[red]borrado[/]" if e["deleted"] else "-")
    console.print(t)
    console.print(f"CSV → {out}")


def cmd_keywords(a):
    kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
    if not kws:
        _die("indica palabras clave: --keywords texto,dni,cv")
    prog = _progress_bar()
    with prog:
        task = prog.add_task("buscando", total=None)
        res = kw_search(a.source, kws,
                        progress=lambda d, t: prog.update(task, completed=d, total=t))
    t = Table(title=f"{res['total']} coincidencias", header_style="bold cyan")
    for col in ("Clave", "Offset", "Contexto"):
        t.add_column(col, overflow="fold")
    for h in res["hits"][: a.limit]:
        t.add_row(h["keyword"], f"0x{h['offset']:x}",
                  h["context"].replace("\n", " ")[:120])
    console.print(t)
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=2, ensure_ascii=False))
        console.print(f"JSON → {a.out}")


def cmd_slack(a):
    out = a.out or f"nyx_recuperados/slack-{time.strftime('%Y%m%d-%H%M%S')}"
    res = slack_collect(a.source, out)
    console.print(Panel(f"🕳 {res['files']} zonas extraídas → {out}\n"
                        f"({res['duration_s']}s)", title="Slack space"))
    for r in res["results"][:20]:
        console.print(f"  {r['path']} · {r['slack_bytes']}B · no-cero: {r['nonzero']}")


def cmd_wipe(a):
    rep = safety.assess(a.node, wipe=True)
    console.print(Panel(
        f"[b red]⚠ OPERACIÓN IRREVERSIBLE[/]\n{rep.label}\n"
        + "\n".join(rep.warnings)
        + ("\n[red]Bloqueos: " + "; ".join(rep.blockers) + "[/]" if rep.blockers else ""),
        title="Borrado seguro"))
    if rep.blocked:
        _die("operación bloqueada: " + "; ".join(rep.blockers))
    expected = rep.confirm_phrase
    typed = input(f"Escribe {expected} para confirmar: ")
    try:
        safety.require_phrase(rep, typed)
    except safety.SafetyError as e:
        _die(str(e))
    with safety.DeviceLock(a.node):
        um = safety.umount_all(a.node)
        if um["failed"]:
            _die(f"no se pudo desmontar: {um['failed']}")
        prog = _progress_bar()
        with prog:
            task = prog.add_task("borrando", total=None)
            cert = wipe_device(a.node, method=a.method, verify=not a.no_verify,
                               progress=lambda p, n, pos, size:
                               prog.update(task, completed=pos, total=size))
    out = Path(a.cert) if a.cert else \
        Path("nyx_informes") / f"certificado-borrado-{time.strftime('%Y%m%d-%H%M%S')}.html"
    report.generate({
        "title": "Certificado de borrado seguro",
        "subtitle": f"{a.node} · {cert['method']} · {cert['standard']}",
        "sections": [{"title": "Resumen", "kpis": [
            ("Dispositivo", a.node), ("Tamaño", human_size(cert["size"])),
            ("Método", cert["method"]), ("Pasadas", cert["passes"]),
            ("Duración", f"{cert['duration_s']} s"),
            ("Verificación", "OK" if cert["verify"].get("ok") else "REVISAR"),
            ("Errores", cert["write_errors_total"]),
        ]}]}, str(out))
    console.print(Panel(f"✔ Borrado completado · verificado: "
                        f"{cert['verify'].get('ok')}\nCertificado → {out}",
                        title="Éxito"))
    audit.log("wipe", {"node": a.node, "method": a.method, "cert": str(out)})


def cmd_wipe_free(a):
    mps = devmod.mounted_mountpoints(a.mountpoint)
    if not mps and not Path(a.mountpoint).is_mount():
        _die(f"{a.mountpoint} no está montado")
    mp = a.mountpoint
    console.print(Panel(f"🧽 Se sobrescribirá el espacio libre de [b]{mp}[/b].\n"
                        "Los ficheros borrados dejarán de ser recuperables.",
                        title="Confirmación"))
    if input("¿Continuar? (si/NO): ").strip().lower() != "si":
        _die("cancelado")
    prog = _progress_bar()
    with prog:
        task = prog.add_task("sobrescribiendo", total=None)
        res = wipe_freespace(mp, progress=lambda w, _t: prog.update(task, completed=w % (100 << 20), total=100 << 20))
    console.print(f"✔ {res['bytes_overwritten']/1e9:.2f} GB sobrescritos")
    audit.log("wipe-free", {"mountpoint": mp})


def cmd_audit(_a):
    res = audit.verify()
    if res["ok"]:
        console.print(f"[green]✔ Cadena íntegra[/] · {res['entries']} eventos · {res.get('path','')}")
    else:
        console.print(f"[red]✗ Cadena ALTERADA en línea {res['first_bad']}[/]")
        sys.exit(1)


def cmd_cipher(a):
    c = cipher_detect(a.source)
    console.print(Panel(json.dumps(c, indent=2, ensure_ascii=False),
                        title="Detección de cifrado"))
    pts = entropy_map(a.source, sample=32768, max_points=100)
    bars = "".join("▁▂▃▄▅▆▇█"[min(7, int(p["entropy"] * 2.5))] for p in pts)
    console.print(f"entropía: {bars}")


def cmd_report(a):
    out = Path(a.out) if a.out else \
        Path("nyx_informes") / f"informe-{time.strftime('%Y%m%d-%H%M%S')}.html"
    sections = []
    d = devmod.get_device(a.node)
    rep = safety.assess(a.node)
    sections.append({"title": "Dispositivo", "kpis": [
        ("Nodo", d.node), ("Tipo", d.kind), ("Tamaño", d.size_human),
        ("Modelo", d.model or "?"), ("Riesgo", rep.label)]})
    sections.append({"title": "Sesiones de auditoría", "table": {
        "headers": ["Sesión", "Eventos"],
        "rows": [[s["file"], s["entries"]] for s in audit.sessions()]}})
    report.generate({"title": "Informe NyxRecover",
                     "subtitle": f"{d.node} · {time.strftime('%Y-%m-%d %H:%M')}",
                     "sections": sections}, str(out))
    console.print(f"✔ Informe → {out}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nyx", description=f"{APP_NAME} v{VERSION} — {TAGLINE}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("devices", help="listar dispositivos")
    s.set_defaults(fn=cmd_devices)

    s = sub.add_parser("info", help="detalle + hardware + filesystem")
    s.add_argument("node")
    s.set_defaults(fn=cmd_info)

    s = sub.add_parser("scan", help="escaneo de firmas")
    s.add_argument("source")
    s.add_argument("--entropy", action="store_true")
    s.add_argument("--json", dest="json_out")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("recover", help="recuperar datos borrados")
    s.add_argument("source")
    s.add_argument("-m", "--mode", choices=["smart", "fs", "carve"], default="smart")
    s.add_argument("-o", "--out", default="nyx_recuperados")
    s.add_argument("--only-deleted", action="store_true")
    s.add_argument("--min-size", type=int, default=128)
    s.add_argument("--paths", nargs="*", help="recuperar solo estas rutas")
    s.set_defaults(fn=cmd_recover)

    s = sub.add_parser("timeline", help="línea temporal forense")
    s.add_argument("source")
    s.add_argument("-o", "--out")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(fn=cmd_timeline)

    s = sub.add_parser("keywords", help="buscar texto en crudo")
    s.add_argument("source")
    s.add_argument("-k", "--keywords", required=True)
    s.add_argument("-o", "--out")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(fn=cmd_keywords)

    s = sub.add_parser("slack", help="extraer espacio slack")
    s.add_argument("source")
    s.add_argument("-o", "--out")
    s.set_defaults(fn=cmd_slack)

    s = sub.add_parser("wipe", help="borrado seguro IRREVERSIBLE")
    s.add_argument("node")
    s.add_argument("--method", choices=["zero", "dod5220", "random", "gutmann"],
                   default="zero")
    s.add_argument("--no-verify", action="store_true")
    s.add_argument("--cert")
    s.set_defaults(fn=cmd_wipe)

    s = sub.add_parser("wipe-free", help="sobrescribir espacio libre montado")
    s.add_argument("mountpoint")
    s.set_defaults(fn=cmd_wipe_free)

    s = sub.add_parser("audit", help="verificar cadena de auditoría")
    s.set_defaults(fn=cmd_audit)

    s = sub.add_parser("cipher", help="detectar cifrado + entropía")
    s.add_argument("source")
    s.set_defaults(fn=cmd_cipher)

    s = sub.add_parser("report", help="informe HTML del dispositivo")
    s.add_argument("node")
    s.add_argument("-o", "--out")
    s.set_defaults(fn=cmd_report)
    return p


def main():
    args = build_parser().parse_args()
    console.print(Panel(f"[b]🜲 {APP_NAME}[/] v{VERSION} — {TAGLINE}",
                        style="cyan on #0d1321"))
    try:
        args.fn(args)
    except FileNotFoundError as e:
        _die(str(e))
    except PermissionError:
        _die("permisos insuficientes — ejecuta con sudo")
    except KeyboardInterrupt:
        _die("interrumpido", 130)


if __name__ == "__main__":
    main()
