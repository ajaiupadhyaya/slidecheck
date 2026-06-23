import os
import webbrowser

from pptx_a11y.pipeline import process_file
from pptx_a11y.settings import get_describer, load_settings, save_api_key


def handle_drop(paths, describer, opener=webbrowser.open):
    results = []
    for path in paths:
        if not (os.path.isfile(path) and path.lower().endswith(".pptx")):
            continue
        if path.lower().endswith("_accessible.pptx"):
            continue
        result = process_file(path, describer)
        results.append(result)
        report = os.path.splitext(path)[0] + "_a11y_report.html"
        if os.path.exists(report):
            opener("file://" + os.path.abspath(report))
    return results


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
        ok = sum(1 for r in results if not r.error)
        status.config(text=f"Done: {ok} file(s) processed. Reports opened in your browser.")

    info.drop_target_register(DND_FILES)
    info.dnd_bind("<<Drop>>", on_drop)

    def set_key():
        key = simpledialog.askstring("API key", "Enter your Anthropic API key (leave blank to skip AI alt text):", show="*")
        if key is not None:
            save_api_key(key.strip())
            messagebox.showinfo("SlideCheck", "API key saved.")

    tk.Button(root, text="Set API key…", command=set_key).pack(pady=10)
    root.mainloop()
