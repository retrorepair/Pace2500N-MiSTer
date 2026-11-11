#!/usr/bin/env python3
"""Pace 2500N Channel Builder (Windows desktop app, Python 3 + tkinter).

  py -3 tools\\pace_builder.pyw            (or double-click)

  Channels       build a line-up: channels, their style (BBC / ITV / Sky),
                 broadcast-day start, interstitial sets and programmes (files
                 or Plex items). Saved as pure metadata (JSON).
  Interstitials  rip period advert / continuity recordings from YouTube into
                 roms/interstitials/<set> and find the cuts between spots.
  Schedule       today's guide for each channel, exactly as the box will show it.
  Playout        start/stop the on-demand playout server the MiSTer relay talks to.
  Settings       ffmpeg, Plex server address and token, port.
"""
import json, os, queue, subprocess, sys, threading, time, urllib.parse, urllib.request, webbrowser
import tkinter as tk
from datetime import date, datetime, timezone
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import pace_channels as pc  # noqa: E402

YTDLP_GUESS = [Path(os.environ.get('APPDATA', '')) / 'Python' / 'Python312' / 'Scripts' / 'yt-dlp.exe']
STYLES = ['bbc', 'itv', 'sky']
VIDEO_EXT = '*.mpg *.mpeg *.ts *.mkv *.mp4 *.avi *.m4v *.mov *.webm'


class Plex:
    def __init__(self, url, token):
        self.url, self.token = url.rstrip('/'), token

    def get(self, path):
        sep = '&' if '?' in path else '?'
        req = urllib.request.Request(f'{self.url}{path}{sep}X-Plex-Token={self.token}',
                                     headers={'Accept': 'application/json'})
        return json.load(urllib.request.urlopen(req, timeout=15))['MediaContainer']

    def sections(self):
        return [(d['key'], d['title'], d['type']) for d in self.get('/library/sections').get('Directory', [])]

    def items(self, section):
        return [(m['ratingKey'], m['title'], m['type']) for m in self.get(f'/library/sections/{section}/all').get('Metadata', [])]

    def episodes(self, key):
        return [(m['ratingKey'], f"{m.get('grandparentTitle', '')} S{m.get('parentIndex', 0):02d}E{m.get('index', 0):02d} {m['title']}",
                 m.get('grandparentTitle') or m['title']) for m in self.get(f'/library/metadata/{key}/allLeaves').get('Metadata', [])]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Pace 2500N Channel Builder')
        self.geometry('1100x720')
        self.settings = pc.load_settings()
        self.lineup_path = None
        self.lineup = {'channels': []}
        self.server = None
        self.log_q = queue.Queue()
        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True)
        self.tab_channels(nb)
        self.tab_interstitials(nb)
        self.tab_schedule(nb)
        self.tab_playout(nb)
        self.tab_settings(nb)
        self.protocol('WM_DELETE_WINDOW', self.quit_app)
        last = self.settings.get('last_lineup')
        if last and Path(last).exists():
            self.load(last)
        self.after(200, self.pump_log)

    # ------------------------------------------------------------ helpers
    def log(self, msg):
        self.log_q.put(time.strftime('%H:%M:%S ') + msg)

    def ui(self, fn):
        """Run fn on the Tk thread (background work must not touch widgets)."""
        self.log_q.put(fn)

    def pump_log(self):
        while not self.log_q.empty():
            item = self.log_q.get()
            if callable(item):
                item()
                continue
            self.logbox.insert('end', item + '\n')
            self.logbox.see('end')
        self.after(200, self.pump_log)

    def background(self, fn, *args):
        def run():
            try:
                fn(*args)
            except Exception as e:  # report, keep the app alive
                self.log(f'error: {e}')
        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------ channels
    def tab_channels(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text='Channels')
        top = ttk.Frame(f)
        top.pack(fill='x')
        for text, cmd in (('New line-up', self.new), ('Open...', self.open), ('Save', self.save), ('Save as...', self.save_as)):
            ttk.Button(top, text=text, command=cmd).pack(side='left', padx=2)
        self.path_lbl = ttk.Label(top, text='(unsaved)')
        self.path_lbl.pack(side='left', padx=10)
        body = ttk.Panedwindow(f, orient='horizontal')
        body.pack(fill='both', expand=True, pady=6)
        left = ttk.Frame(body)
        body.add(left, weight=1)
        self.chan_list = tk.Listbox(left, exportselection=False, height=12)
        self.chan_list.pack(fill='both', expand=True)
        self.chan_list.bind('<<ListboxSelect>>', lambda e: self.show_channel())
        row = ttk.Frame(left)
        row.pack(fill='x')
        for text, cmd in (('Add', self.add_channel), ('Remove', self.del_channel), ('Up', lambda: self.move_channel(-1)),
                          ('Down', lambda: self.move_channel(1))):
            ttk.Button(row, text=text, command=cmd).pack(side='left', padx=1)
        right = ttk.Frame(body)
        body.add(right, weight=3)
        form = ttk.Frame(right)
        form.pack(fill='x')
        self.v_name, self.v_num, self.v_style, self.v_start, self.v_sets = (tk.StringVar() for _ in range(5))
        for i, (label, var) in enumerate((('Name', self.v_name), ('Number', self.v_num), ('Day starts (UTC)', self.v_start),
                                          ('Interstitial sets (;)', self.v_sets))):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky='w')
            ttk.Entry(form, textvariable=var, width=60).grid(row=i, column=1, sticky='we', pady=1)
        ttk.Label(form, text='Style').grid(row=4, column=0, sticky='w')
        ttk.Combobox(form, textvariable=self.v_style, values=STYLES, state='readonly', width=8).grid(row=4, column=1, sticky='w')
        ttk.Button(form, text='Apply', command=self.apply_channel).grid(row=5, column=1, sticky='w', pady=4)
        ttk.Label(form, text='bbc = continuity only, no adverts; itv = terrestrial adverts with centre breaks; sky = satellite breaks',
                  foreground='#666').grid(row=6, column=0, columnspan=2, sticky='w')
        cols = ('title', 'source')
        self.prog = ttk.Treeview(right, columns=cols, show='headings', height=14)
        self.prog.heading('title', text='Programme title')
        self.prog.heading('source', text='Source')
        self.prog.column('title', width=220)
        self.prog.column('source', width=520)
        self.prog.pack(fill='both', expand=True, pady=4)
        row = ttk.Frame(right)
        row.pack(fill='x')
        for text, cmd in (('Add files...', self.add_files), ('Add from Plex...', self.add_plex), ('Rename', self.rename_prog),
                          ('Remove', self.del_prog), ('Up', lambda: self.move_prog(-1)), ('Down', lambda: self.move_prog(1))):
            ttk.Button(row, text=text, command=cmd).pack(side='left', padx=1)

    def current(self):
        sel = self.chan_list.curselection()
        return self.lineup['channels'][sel[0]] if sel else None

    def refresh_channels(self, select=None):
        self.chan_list.delete(0, 'end')
        for c in self.lineup['channels']:
            self.chan_list.insert('end', f"{c.get('number', '')}  {c['name']}  ({c.get('style', 'bbc')}, {len(c['programmes'])} progs)")
        if select is not None and self.lineup['channels']:
            self.chan_list.selection_set(select)
            self.show_channel()

    def show_channel(self):
        c = self.current()
        if not c:
            return
        self.v_name.set(c['name']); self.v_num.set(c.get('number', '')); self.v_style.set(c.get('style', 'bbc'))
        self.v_start.set(c.get('start', '06:00')); self.v_sets.set(';'.join(c.get('interstitials', [])))
        self.prog.delete(*self.prog.get_children())
        for p in c['programmes']:
            self.prog.insert('', 'end', values=(p['title'], p['source']))

    def apply_channel(self):
        c = self.current()
        if not c:
            return
        c['name'] = self.v_name.get().strip() or c['name']
        try:
            c['number'] = int(self.v_num.get())
        except ValueError:
            pass
        c['style'] = self.v_style.get() or 'bbc'
        c['start'] = self.v_start.get().strip() or '06:00'
        c['interstitials'] = [s.strip() for s in self.v_sets.get().split(';') if s.strip()]
        self.refresh_channels(self.chan_list.curselection()[0])

    def add_channel(self):
        n = len(self.lineup['channels'])
        self.lineup['channels'].append({'name': f'Channel {n + 1}', 'number': 101 + n, 'style': 'bbc', 'start': '06:00',
                                        'interstitials': [], 'programmes': []})
        self.refresh_channels(n)

    def del_channel(self):
        sel = self.chan_list.curselection()
        if sel and messagebox.askyesno('Remove channel', 'Remove this channel from the line-up?'):
            del self.lineup['channels'][sel[0]]
            self.refresh_channels(0 if self.lineup['channels'] else None)

    def move_channel(self, d):
        sel = self.chan_list.curselection()
        if not sel:
            return
        i, chans = sel[0], self.lineup['channels']
        j = i + d
        if 0 <= j < len(chans):
            chans[i], chans[j] = chans[j], chans[i]
            self.refresh_channels(j)

    def add_files(self):
        c = self.current()
        if not c:
            return
        files = filedialog.askopenfilenames(title='Programmes', filetypes=[('Video', VIDEO_EXT), ('All', '*.*')])
        for f in files:
            c['programmes'].append({'title': Path(f).stem, 'source': Path(f).as_posix()})
        self.show_channel()

    def add_plex(self):
        c = self.current()
        if not c:
            return
        if not self.settings.get('plex_url') or not self.settings.get('plex_token'):
            messagebox.showinfo('Plex', 'Set the Plex server address and token on the Settings tab first.')
            return
        PlexPicker(self, Plex(self.settings['plex_url'], self.settings['plex_token']),
                   lambda items: (c['programmes'].extend(items), self.show_channel()))

    def selected_prog(self):
        sel = self.prog.selection()
        return self.prog.index(sel[0]) if sel else None

    def rename_prog(self):
        c, i = self.current(), self.selected_prog()
        if c and i is not None:
            t = simpledialog.askstring('Title', 'Programme title (as shown in the guide):', initialvalue=c['programmes'][i]['title'])
            if t:
                c['programmes'][i]['title'] = t
                self.show_channel()

    def del_prog(self):
        c, i = self.current(), self.selected_prog()
        if c and i is not None:
            del c['programmes'][i]
            self.show_channel()

    def move_prog(self, d):
        c, i = self.current(), self.selected_prog()
        if c and i is not None and 0 <= i + d < len(c['programmes']):
            p = c['programmes']
            p[i], p[i + d] = p[i + d], p[i]
            self.show_channel()
            self.prog.selection_set(self.prog.get_children()[i + d])

    def new(self):
        self.lineup, self.lineup_path = {'channels': []}, None
        self.path_lbl.config(text='(unsaved)')
        self.refresh_channels()

    def open(self):
        f = filedialog.askopenfilename(title='Open line-up', filetypes=[('Line-up', '*.json')], initialdir=ROOT / 'roms')
        if f:
            self.load(f)

    def load(self, f):
        self.lineup = json.loads(Path(f).read_text())
        self.lineup_path = f
        self.path_lbl.config(text=f)
        self.settings['last_lineup'] = f
        pc.save_settings(self.settings)
        self.refresh_channels(0 if self.lineup['channels'] else None)

    def save(self):
        if not self.lineup_path:
            return self.save_as()
        Path(self.lineup_path).write_text(json.dumps(self.lineup, indent=1))
        self.log(f'saved {self.lineup_path}')

    def save_as(self):
        f = filedialog.asksaveasfilename(title='Save line-up', defaultextension='.json', initialdir=ROOT / 'roms',
                                         filetypes=[('Line-up', '*.json')])
        if f:
            self.lineup_path = f
            self.path_lbl.config(text=f)
            self.settings['last_lineup'] = f
            pc.save_settings(self.settings)
            self.save()

    # ------------------------------------------------------------ interstitials
    def tab_interstitials(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text='Interstitials')
        ttk.Label(f, text='Period adverts and continuity, ripped from YouTube into roms/interstitials/<set>. '
                          'Name sets by station and years, e.g. itv_1987_89, bbc1_1988_89, sky1_1993_94.').pack(anchor='w')
        row = ttk.Frame(f)
        row.pack(fill='x', pady=4)
        self.v_query, self.v_set = tk.StringVar(value='TVS adverts 1987'), tk.StringVar(value='itv_1987_89')
        ttk.Label(row, text='Search').pack(side='left')
        ttk.Entry(row, textvariable=self.v_query, width=40).pack(side='left', padx=4)
        ttk.Button(row, text='Search YouTube', command=lambda: self.background(self.yt_search)).pack(side='left')
        ttk.Label(row, text='  into set').pack(side='left')
        ttk.Entry(row, textvariable=self.v_set, width=18).pack(side='left', padx=4)
        ttk.Button(row, text='Rip selected', command=lambda: self.background(self.yt_rip)).pack(side='left')
        self.yt = ttk.Treeview(f, columns=('id', 'len', 'title'), show='headings', height=8, selectmode='extended')
        for col, w in (('id', 110), ('len', 60), ('title', 700)):
            self.yt.heading(col, text=col)
            self.yt.column(col, width=w)
        self.yt.pack(fill='x')
        row = ttk.Frame(f)
        row.pack(fill='x', pady=6)
        ttk.Button(row, text='Refresh sets', command=self.refresh_sets).pack(side='left')
        ttk.Button(row, text='Analyse selected set', command=lambda: self.background(self.analyse_set)).pack(side='left', padx=4)
        self.sets = ttk.Treeview(f, columns=('set', 'files', 'size'), show='headings', height=8)
        for col, w in (('set', 260), ('files', 80), ('size', 100)):
            self.sets.heading(col, text=col)
            self.sets.column(col, width=w)
        self.sets.pack(fill='x')
        self.refresh_sets()

    def ytdlp(self):
        for p in [self.settings.get('ytdlp')] + YTDLP_GUESS:
            if p and Path(p).exists():
                return str(p)
        return 'yt-dlp'

    def yt_search(self):
        q = self.v_query.get().strip()
        self.log(f'YouTube search: {q}')
        out = subprocess.run([self.ytdlp(), '--flat-playlist', '--print', '%(id)s|%(duration)s|%(title)s', f'ytsearch15:{q}'],
                             capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        rows = [l.split('|', 2) for l in out.stdout.splitlines() if l.count('|') >= 2]
        def fill():
            self.yt.delete(*self.yt.get_children())
            for vid, ln, title in rows:
                self.yt.insert('', 'end', values=(vid, ln, title))
        self.ui(fill)

    def yt_rip(self):
        ids = [self.yt.item(i)['values'][0] for i in self.yt.selection()]
        target = ROOT / 'roms' / 'interstitials' / self.v_set.get().strip()
        target.mkdir(parents=True, exist_ok=True)
        ff = str(Path(self.settings['ffmpeg']).parent)
        for vid in ids:
            self.log(f'ripping {vid} into {target.name}')
            subprocess.run([self.ytdlp(), '--ffmpeg-location', ff, '-f', 'bv*[height<=576]+ba/b', '--merge-output-format', 'mkv',
                            '--write-info-json', '--no-playlist', '-o', str(target / '%(id)s.%(ext)s'), str(vid)],
                           capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.log('rip finished')
        self.ui(self.refresh_sets)
        self.analyse(target)

    def refresh_sets(self):
        self.sets.delete(*self.sets.get_children())
        base = ROOT / 'roms' / 'interstitials'
        for d in sorted(base.glob('*')) if base.exists() else []:
            files = [f for f in d.glob('*') if f.suffix.lower() in ('.mkv', '.mp4', '.webm', '.mpg', '.ts', '.avi')]
            self.sets.insert('', 'end', values=(d.relative_to(ROOT).as_posix(), len(files),
                                               f'{sum(f.stat().st_size for f in files) >> 20} MB'))

    def analyse_set(self):
        sel = self.sets.selection()
        if sel:
            self.analyse(ROOT / self.sets.item(sel[0])['values'][0])

    def analyse(self, folder):
        media = pc.Media(self.settings)
        runs = pc.interstitial_runs(media, [str(folder)], self.log)
        self.log(f'{Path(folder).name}: {sum(len(r) for r in runs)} spots in {len(runs)} recordings, '
                 f'{sum(s[2] for r in runs for s in r) / 60:.0f} min')

    # ------------------------------------------------------------ schedule
    def tab_schedule(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text='Schedule')
        row = ttk.Frame(f)
        row.pack(fill='x')
        ttk.Button(row, text='Save and build today\'s guide',
                   command=lambda: self.save() or self.background(self.build_schedule)).pack(side='left')
        ttk.Button(row, text='Prepare (find natural breaks)',
                   command=lambda: self.save() or self.background(self.prepare)).pack(side='left', padx=4)
        self.sched = tk.Text(f, font=('Consolas', 10))
        self.sched.pack(fill='both', expand=True, pady=4)

    def build_schedule(self):
        chans, _ = pc.load_lineup(self.lineup_path, self.settings, self.log)
        d = datetime.now(timezone.utc).date()
        lines = []
        for c in chans:
            lines.append(f'== {c.number} {c.name}  ({c.style}, {sum(len(r) for r in c.runs)} interstitial spots)')
            for s0, ln, title in c.events_utc(d):
                lines.append(f'   {s0 // 3600:02d}:{s0 // 60 % 60:02d}  {ln // 60:4d} min  {title}')
        def show():
            self.sched.delete('1.0', 'end')
            self.sched.insert('end', '\n'.join(lines))
        self.ui(show)

    def prepare(self):
        chans, media = pc.load_lineup(self.lineup_path, self.settings, self.log)
        for c in chans:
            if c.style != 'bbc':
                for p in c.programmes:
                    if not p['source'].startswith('plex:'):
                        media.cuts(p['source'], self.log)
        self.log('prepare finished')

    # ------------------------------------------------------------ playout
    def tab_playout(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text='Playout')
        row = ttk.Frame(f)
        row.pack(fill='x')
        self.btn_start = ttk.Button(row, text='Start playout server', command=self.start_server)
        self.btn_start.pack(side='left')
        ttk.Button(row, text='Stop', command=self.stop_server).pack(side='left', padx=4)
        ttk.Button(row, text='Open status page', command=lambda: webbrowser.open(f"http://localhost:{self.settings['port']}/")).pack(side='left')
        ttk.Label(f, text='The MiSTer relay (/media/fat/linux/pace/relay.ini) must point at this PC\'s address and port. '
                          'Nothing is transcoded until the box tunes a channel.').pack(anchor='w', pady=4)
        self.logbox = tk.Text(f, height=30, font=('Consolas', 9))
        self.logbox.pack(fill='both', expand=True)

    def start_server(self):
        if self.server and self.server.poll() is None:
            return
        self.save()
        self.server = subprocess.Popen([sys.executable.replace('pythonw', 'python'), str(HERE / 'pace_playout.py'), self.lineup_path], cwd=str(ROOT),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        def read():
            for line in self.server.stdout:
                self.log_q.put(line.rstrip())
        threading.Thread(target=read, daemon=True).start()

    def stop_server(self):
        if self.server and self.server.poll() is None:
            self.server.terminate()
            self.log('playout server stopped')

    # ------------------------------------------------------------ settings
    def tab_settings(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text='Settings')
        self.v_set_vars = {}
        fields = (('ffmpeg', 'ffmpeg.exe'), ('plex_url', 'Plex server (e.g. http://192.168.1.53:32400)'),
                  ('plex_token', 'Plex token'), ('port', 'Playout port'), ('days', 'Guide days'), ('ytdlp', 'yt-dlp.exe'))
        for i, (key, label) in enumerate(fields):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky='w', pady=2)
            v = tk.StringVar(value=str(self.settings.get(key, '')))
            ttk.Entry(f, textvariable=v, width=80, show='*' if key == 'plex_token' else '').grid(row=i, column=1, sticky='we')
            self.v_set_vars[key] = v
        ttk.Button(f, text='Save settings', command=self.save_settings).grid(row=len(fields), column=1, sticky='w', pady=6)
        ttk.Button(f, text='Test Plex', command=lambda: self.background(self.test_plex)).grid(row=len(fields) + 1, column=1, sticky='w')
        ttk.Label(f, text=f'Stored in {pc.settings_path()} (not in the project or git).', foreground='#666').grid(
            row=len(fields) + 2, column=0, columnspan=2, sticky='w', pady=8)

    def save_settings(self):
        for k, v in self.v_set_vars.items():
            val = v.get().strip()
            self.settings[k] = int(val) if k in ('port', 'days') and val.isdigit() else val
        pc.save_settings(self.settings)
        self.log('settings saved')

    def test_plex(self):
        self.save_settings()
        secs = Plex(self.settings['plex_url'], self.settings['plex_token']).sections()
        self.log('Plex libraries: ' + ', '.join(f'{t} ({k}, {ty})' for k, t, ty in secs))

    def quit_app(self):
        self.stop_server()
        self.destroy()


class PlexPicker(tk.Toplevel):
    """Browse Plex libraries -> shows/movies -> episodes; add the selection."""
    def __init__(self, app, plex, done):
        super().__init__(app)
        self.title('Add from Plex')
        self.geometry('760x520')
        self.plex, self.done, self.app = plex, done, app
        self.lib = ttk.Combobox(self, state='readonly', width=40)
        self.lib.pack(anchor='w', padx=6, pady=4)
        self.lib.bind('<<ComboboxSelected>>', lambda e: self.load_items())
        pane = ttk.Panedwindow(self, orient='horizontal')
        pane.pack(fill='both', expand=True, padx=6)
        self.items = tk.Listbox(pane, exportselection=False)
        pane.add(self.items, weight=1)
        self.items.bind('<<ListboxSelect>>', lambda e: self.load_eps())
        self.eps = tk.Listbox(pane, selectmode='extended', exportselection=False)
        pane.add(self.eps, weight=2)
        ttk.Button(self, text='Add selected', command=self.add).pack(pady=4)
        self.sections = plex.sections()
        self.lib['values'] = [f'{t} ({ty})' for _, t, ty in self.sections]

    def load_items(self):
        key = self.sections[self.lib.current()][0]
        self.item_rows = self.plex.items(key)
        self.items.delete(0, 'end')
        for _, t, ty in self.item_rows:
            self.items.insert('end', t)
        self.ep_rows = []
        self.eps.delete(0, 'end')

    def load_eps(self):
        sel = self.items.curselection()
        if not sel:
            return
        key, title, ty = self.item_rows[sel[0]]
        self.ep_rows = self.plex.episodes(key) if ty == 'show' else [(key, title, title)]
        self.eps.delete(0, 'end')
        for _, label, _ in self.ep_rows:
            self.eps.insert('end', label)

    def add(self):
        picked = [{'title': show, 'source': f'plex:{key}'} for i in self.eps.curselection()
                  for key, _, show in [self.ep_rows[i]]]
        self.done(picked)
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
