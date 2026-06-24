import os
import webbrowser

from pptx_a11y.pipeline import process_file
from pptx_a11y.report import batch_index
from pptx_a11y.settings import get_describer, load_settings, save_api_key


def handle_drop(paths, describer, opener=webbrowser.open):
    results = []
    for path in paths:
        if not (os.path.isfile(path) and path.lower().endswith(".pptx")):
            continue
        if path.lower().endswith("_accessible.pptx"):
            continue
        results.append(process_file(path, describer))
    _open_reports(results, opener)
    return results


def _open_reports(results, opener):
    """Open one batch index when several decks in the same folder succeed,
    otherwise open each per-file report (and nothing for a failed file)."""
    ok = [r for r in results if not r.error and r.output_path]
    dirs = {os.path.dirname(os.path.abspath(r.source_path)) for r in ok}
    if len(ok) >= 2 and len(dirs) == 1:
        index = batch_index.write_index(results, dirs.pop())
        opener("file://" + os.path.abspath(index))
        return
    for r in ok:
        report = os.path.splitext(r.source_path)[0] + "_a11y_report.html"
        if os.path.exists(report):
            opener("file://" + os.path.abspath(report))


def drop_summary(dropped, results) -> dict:
    """Pure helper so the GUI can give honest, testable feedback after a drop."""
    pptx = [
        p
        for p in dropped
        if p.lower().endswith(".pptx") and not p.lower().endswith("_accessible.pptx")
    ]
    ok = [r for r in results if not r.error]
    errors = [(os.path.basename(r.source_path), r.error) for r in results if r.error]
    if not pptx:
        status = "No PowerPoint (.pptx) files found in what you dropped."
    else:
        status = f"Done: {len(ok)} of {len(pptx)} file(s) processed."
        if errors:
            status += f" {len(errors)} could not be opened — see the error popup."
    return {"status": status, "errors": errors, "ok": len(ok), "pptx": len(pptx)}


def _parse_drop(data: str) -> list[str]:
    """tkinterdnd2 delivers space-separated paths, brace-wrapped if they contain spaces."""
    import re
    return [p.strip("{}") for p in re.findall(r"\{[^}]*\}|\S+", data)]


def main():  # pragma: no cover - UI wiring
    from tkinterdnd2 import DND_FILES, TkinterDnD
    import tkinter as tk
    from tkinter import simpledialog, messagebox

    root = TkinterDnD.Tk()
    root.title("SlideCheck")
    root.geometry("460x300")

    info = tk.Label(root, text="Drop .pptx files here", width=50, height=8, relief="ridge", bg="#f5f5f5")
    info.pack(padx=20, pady=20, fill="both", expand=True)

    status = tk.Label(root, text="", fg="#137333")
    status.pack()

    def on_drop(event):
        paths = _parse_drop(event.data)
        describer = get_describer(load_settings())
        status.config(text="Processing…")
        root.update_idletasks()
        results = handle_drop(paths, describer)
        summary = drop_summary(paths, results)
        status.config(text=summary["status"])
        if summary["errors"]:
            detail = "\n".join(f"• {name}: {err}" for name, err in summary["errors"])
            messagebox.showerror("SlideCheck — some files could not be processed", detail)
        elif summary["pptx"] == 0:
            messagebox.showinfo("SlideCheck", "No PowerPoint (.pptx) files were found in what you dropped.")

    info.drop_target_register(DND_FILES)
    info.dnd_bind("<<Drop>>", on_drop)

    def set_key():
        key = simpledialog.askstring("API key", "Enter your Anthropic API key (leave blank to skip AI alt text):", show="*")
        if key is not None:
            save_api_key(key.strip())
            messagebox.showinfo("SlideCheck", "API key saved.")

    tk.Button(root, text="Set API key…", command=set_key).pack(pady=10)
    root.mainloop()
