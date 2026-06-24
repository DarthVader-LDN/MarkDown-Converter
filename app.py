"""
MarkItDown Converter — a standalone desktop GUI for converting documents to Markdown.

Wraps Microsoft's `markitdown` library in a responsive Tkinter interface:
batch queue, per-file status, threaded conversion (UI never freezes), and
configurable output location. Designed to be frozen into a single Windows .exe
with PyInstaller (see MarkItDown-GUI.spec).

No third-party GUI dependencies — Tkinter ships with CPython, which keeps the
frozen binary smaller and the build reproducible.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
from pathlib import Path
from typing import Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "MarkItDown — Document to Markdown"
APP_VERSION = "1.0.0"
CREDIT = "Courtesy of the admirable Jishnu Kumaran"

# Extensions MarkItDown handles in a fully offline build (no cloud/keys/ffmpeg).
# Used purely to populate the file-picker filter; MarkItDown auto-detects content
# at conversion time, so unlisted types still work if dragged in via "All files".
SUPPORTED_EXTS: List[str] = [
    ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv", ".tsv",
    ".html", ".htm", ".xml", ".json", ".ipynb", ".epub", ".msg",
    ".txt", ".md", ".rss", ".atom", ".zip",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
]

# Status labels (kept short for the table column).
ST_QUEUED = "Queued"
ST_WORKING = "Converting…"
ST_DONE = "Done"
ST_SKIPPED = "Skipped"
ST_ERROR = "Error"


# --------------------------------------------------------------------------- #
# Worker-thread plumbing
# --------------------------------------------------------------------------- #
class ConversionWorker(threading.Thread):
    """Runs conversions off the UI thread and reports progress via a Queue.

    Messages pushed to ``out_q`` are tuples:
        ("init",)                       -> MarkItDown is being constructed
        ("status", item_id, label)      -> update a row's status
        ("detail", item_id, text)       -> attach an error/detail string to a row
        ("output", item_id, path)       -> record the produced .md path for a row
        ("done", converted, skipped, failed)
        ("fatal", message)              -> unrecoverable error before/while looping
    """

    def __init__(self, jobs: List[tuple], out_q: "queue.Queue"):
        super().__init__(daemon=True)
        self._jobs = jobs  # list of (item_id, src_path, out_path)
        self._q = out_q

    def run(self) -> None:  # noqa: C901 - linear and readable
        try:
            self._q.put(("init",))
            # Imported here (not at module load) so the window appears instantly;
            # importing markitdown also loads the magika ONNX model, which is slow.
            from markitdown import MarkItDown

            md = MarkItDown(enable_plugins=False)
        except Exception:  # pragma: no cover - defensive
            self._q.put(("fatal", "Failed to initialise the conversion engine:\n\n"
                                   + traceback.format_exc()))
            return

        converted = skipped = failed = 0
        for item_id, src, out_path in self._jobs:
            self._q.put(("status", item_id, ST_WORKING))
            try:
                result = md.convert(src)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(result.markdown, encoding="utf-8")
                self._q.put(("output", item_id, str(out_path)))
                self._q.put(("status", item_id, ST_DONE))
                converted += 1
            except Exception as exc:  # surface per-file, keep the batch going
                msg = _friendly_error(exc)
                self._q.put(("detail", item_id, msg))
                # A missing optional dependency is a "skip", not a hard failure.
                label = ST_SKIPPED if "MissingDependency" in type(exc).__name__ else ST_ERROR
                if label == ST_SKIPPED:
                    skipped += 1
                else:
                    failed += 1
                self._q.put(("status", item_id, label))

        self._q.put(("done", converted, skipped, failed))


def _friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    base = str(exc).strip() or name
    if name == "MissingDependencyException":
        return ("This file type needs an optional dependency that wasn't bundled.\n\n"
                + base)
    if name == "UnsupportedFormatException":
        return "MarkItDown does not support this file type.\n\n" + base
    return f"{name}: {base}"


# --------------------------------------------------------------------------- #
# Main application
# --------------------------------------------------------------------------- #
class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.minsize(720, 520)
        self._center(860, 600)

        # item_id -> {"src": Path, "out": Optional[str], "detail": Optional[str]}
        self._rows: Dict[str, dict] = {}
        self._q: "queue.Queue" = queue.Queue()
        self._worker: Optional[ConversionWorker] = None
        self._last_out_dir: Optional[Path] = None

        self._init_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- window helpers ---------------------------------------------------- #
    def _center(self, w: int, h: int) -> None:
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _init_style(self) -> None:
        style = ttk.Style(self)
        # Prefer a clean native-ish theme; fall back gracefully across platforms.
        for theme in ("vista", "clam", "default"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break

        base = ("Segoe UI", 10)
        self.option_add("*Font", base)
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 17))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#5f6368")
        style.configure("Hint.TLabel", font=("Segoe UI", 9), foreground="#5f6368")
        style.configure("Credit.TLabel", font=("Segoe UI Semibold", 10), foreground="#1a73e8")
        style.configure("CreditFoot.TLabel", font=("Segoe UI", 9), foreground="#5f6368")
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(16, 8))
        style.configure("Treeview", rowheight=26)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))

    # ---- layout ------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        # Header
        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="MarkItDown Converter", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Convert PDFs, Office files, HTML, e-books and more into clean Markdown — fully offline.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(header, text=CREDIT, style="Credit.TLabel").pack(anchor="w", pady=(8, 0))

        # Action row
        actions = ttk.Frame(root)
        actions.grid(row=1, column=0, sticky="ew", pady=(16, 8))
        ttk.Button(actions, text="Add files…", command=self._add_files).pack(side="left")
        ttk.Button(actions, text="Add folder…", command=self._add_folder).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Remove selected", command=self._remove_selected).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Clear", command=self._clear).pack(side="left", padx=(8, 0))

        # File table
        table_wrap = ttk.Frame(root)
        table_wrap.grid(row=2, column=0, sticky="nsew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_wrap, columns=("file", "status"), show="headings", selectmode="extended"
        )
        self.tree.heading("file", text="File")
        self.tree.heading("status", text="Status")
        self.tree.column("file", anchor="w", width=560, stretch=True)
        self.tree.column("status", anchor="w", width=140, stretch=False)
        self.tree.tag_configure("done", foreground="#188038")
        self.tree.tag_configure("error", foreground="#c5221f")
        self.tree.tag_configure("skipped", foreground="#b06000")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", self._on_row_activate)

        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")

        ttk.Label(
            root,
            text="Tip: double-click a row to open its Markdown (or view the error if it failed).",
            style="Hint.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(6, 0))

        # Output options
        out = ttk.LabelFrame(root, text="Output", padding=12)
        out.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        out.columnconfigure(1, weight=1)

        self._out_mode = tk.StringVar(value="same")
        ttk.Radiobutton(
            out, text="Save next to each source file", value="same",
            variable=self._out_mode, command=self._sync_out_state,
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Radiobutton(
            out, text="Save all to one folder:", value="custom",
            variable=self._out_mode, command=self._sync_out_state,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        self._out_dir = tk.StringVar(value="")
        self._out_entry = ttk.Entry(out, textvariable=self._out_dir)
        self._out_entry.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(6, 0))
        self._out_browse = ttk.Button(out, text="Browse…", command=self._choose_out_dir)
        self._out_browse.grid(row=1, column=2, sticky="e", pady=(6, 0))
        self._sync_out_state()

        # Footer: progress + primary action
        footer = ttk.Frame(root)
        footer.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        footer.columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(footer, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.status = tk.StringVar(value="Add files to begin.")
        ttk.Label(footer, textvariable=self.status, style="Hint.TLabel").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )

        self.open_btn = ttk.Button(footer, text="Open output folder", command=self._open_output)
        self.open_btn.grid(row=0, column=1, padx=(0, 8))
        self.open_btn.state(["disabled"])
        self.convert_btn = ttk.Button(
            footer, text="Convert", style="Accent.TButton", command=self._start
        )
        self.convert_btn.grid(row=0, column=2)

        # Persistent attribution (always visible, regardless of state).
        credit = ttk.Frame(root)
        credit.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        ttk.Separator(credit, orient="horizontal").pack(fill="x", pady=(0, 6))
        ttk.Label(credit, text=CREDIT, style="CreditFoot.TLabel").pack(anchor="center")

    # ---- file queue management -------------------------------------------- #
    def _add_paths(self, paths: List[str]) -> None:
        existing = {r["src"] for r in self._rows.values()}
        added = 0
        for p in paths:
            path = Path(p)
            if not path.is_file() or path in existing:
                continue
            item_id = self.tree.insert("", "end", values=(str(path), ST_QUEUED))
            self._rows[item_id] = {"src": path, "out": None, "detail": None}
            existing.add(path)
            added += 1
        if added:
            self.status.set(f"{len(self._rows)} file(s) queued.")
            self.open_btn.state(["disabled"])

    def _add_files(self) -> None:
        patterns = " ".join(f"*{e}" for e in SUPPORTED_EXTS)
        files = filedialog.askopenfilenames(
            title="Choose documents to convert",
            filetypes=[("Supported documents", patterns), ("All files", "*.*")],
        )
        if files:
            self._add_paths(list(files))

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose a folder (scanned recursively)")
        if not folder:
            return
        exts = set(SUPPORTED_EXTS)
        found = [str(p) for p in Path(folder).rglob("*") if p.is_file() and p.suffix.lower() in exts]
        if not found:
            messagebox.showinfo(APP_TITLE, "No supported documents found in that folder.")
            return
        self._add_paths(found)

    def _remove_selected(self) -> None:
        for item_id in self.tree.selection():
            self.tree.delete(item_id)
            self._rows.pop(item_id, None)
        self.status.set(f"{len(self._rows)} file(s) queued." if self._rows else "Add files to begin.")

    def _clear(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        self.progress["value"] = 0
        self.open_btn.state(["disabled"])
        self.status.set("Add files to begin.")

    # ---- output controls --------------------------------------------------- #
    def _sync_out_state(self) -> None:
        custom = self._out_mode.get() == "custom"
        state = "normal" if custom else "disabled"
        self._out_entry.configure(state=state)
        self._out_browse.configure(state=state)

    def _choose_out_dir(self) -> None:
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self._out_dir.set(folder)

    def _resolve_output(self, src: Path) -> Path:
        if self._out_mode.get() == "custom":
            target_dir = Path(self._out_dir.get())
        else:
            target_dir = src.parent
        candidate = target_dir / (src.stem + ".md")
        # Avoid clobbering: report.md -> report (1).md, report (2).md, ...
        n = 1
        while candidate.exists():
            candidate = target_dir / f"{src.stem} ({n}).md"
            n += 1
        return candidate

    # ---- run --------------------------------------------------------------- #
    def _start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        if not self._rows:
            messagebox.showinfo(APP_TITLE, "Add some files first.")
            return
        if self._out_mode.get() == "custom":
            d = self._out_dir.get().strip()
            if not d or not Path(d).is_dir():
                messagebox.showwarning(APP_TITLE, "Choose a valid output folder, or use the 'next to source' option.")
                return

        # Build the job list and reset row states.
        jobs = []
        for item_id, row in self._rows.items():
            src = row["src"]
            out_path = self._resolve_output(src)
            row["out"], row["detail"] = None, None
            self.tree.item(item_id, values=(str(src), ST_QUEUED), tags=())
            jobs.append((item_id, src, out_path))
            self._last_out_dir = out_path.parent

        self._set_running(True)
        self.progress.configure(maximum=len(jobs), value=0)
        self.status.set("Initialising conversion engine…")
        self._worker = ConversionWorker(jobs, self._q)
        self._worker.start()
        self.after(80, self._drain_queue)

    def _drain_queue(self) -> None:  # noqa: C901 - simple message switch
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]
                if kind == "init":
                    self.status.set("Loading models… (first run can take a few seconds)")
                elif kind == "status":
                    _, item_id, label = msg
                    tag = {ST_DONE: "done", ST_ERROR: "error", ST_SKIPPED: "skipped"}.get(label, "")
                    src = str(self._rows[item_id]["src"])
                    self.tree.item(item_id, values=(src, label), tags=(tag,) if tag else ())
                    if label in (ST_DONE, ST_ERROR, ST_SKIPPED):
                        self.progress["value"] += 1
                        done = int(self.progress["value"])
                        self.status.set(f"Processed {done} of {int(self.progress['maximum'])}…")
                elif kind == "output":
                    _, item_id, path = msg
                    self._rows[item_id]["out"] = path
                elif kind == "detail":
                    _, item_id, text = msg
                    self._rows[item_id]["detail"] = text
                elif kind == "done":
                    _, conv, skip, fail = msg
                    self._finish(conv, skip, fail)
                    return
                elif kind == "fatal":
                    self._set_running(False)
                    self.status.set("Conversion engine failed to start.")
                    messagebox.showerror(APP_TITLE, msg[1])
                    return
        except queue.Empty:
            pass
        self.after(80, self._drain_queue)

    def _finish(self, converted: int, skipped: int, failed: int) -> None:
        self._set_running(False)
        parts = [f"{converted} converted"]
        if skipped:
            parts.append(f"{skipped} skipped")
        if failed:
            parts.append(f"{failed} failed")
        self.status.set("Finished — " + ", ".join(parts) + ".  Double-click a row to open it.")
        if converted and self._last_out_dir and self._last_out_dir.is_dir():
            self.open_btn.state(["!disabled"])

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.convert_btn.configure(state=state)
        self.convert_btn.configure(text="Converting…" if running else "Convert")

    # ---- row / folder actions --------------------------------------------- #
    def _on_row_activate(self, _event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        row = self._rows.get(sel[0])
        if not row:
            return
        if row.get("detail"):
            messagebox.showerror(f"{row['src'].name} — could not convert", row["detail"])
        elif row.get("out"):
            self._open_path(row["out"])

    def _open_output(self) -> None:
        if self._last_out_dir and self._last_out_dir.is_dir():
            self._open_path(str(self._last_out_dir))

    @staticmethod
    def _open_path(path: str) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception as exc:  # pragma: no cover
            messagebox.showwarning(APP_TITLE, f"Couldn't open:\n{path}\n\n{exc}")

    def _on_close(self) -> None:
        if self._worker and self._worker.is_alive():
            if not messagebox.askyesno(APP_TITLE, "A conversion is running. Quit anyway?"):
                return
        self.destroy()


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
