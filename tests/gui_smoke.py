"""Exercise actual Tk controls and background callbacks without input automation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

gui = app.App()
gui.source.set(str(Path('validation/integration/library').resolve()))
out = Path('validation/gui-1.1.0').resolve(); out.mkdir(exist_ok=True)
gui.output.set(str(out))
gui._all(True)
gui.toggle_theme(); assert gui.dark
gui.toggle_theme(); assert not gui.dark
app.messagebox.showinfo = lambda *a, **kw: None
app.messagebox.showerror = lambda *a, **kw: None
gui.after(100, gui.start_scan)
def verify():
    if gui.worker and not gui.worker.is_alive():
        assert gui.last_report and gui.last_report.exists(), gui.status.get()
        assert 'Scan concluído' in gui.log_text.get('1.0', 'end')
        print('GUI_PASS', gui.last_report, flush=True)
        gui.destroy()
    else:
        gui.after(100, verify)
gui.after(500, verify)
gui.after(60000, gui.destroy)
gui.mainloop()
