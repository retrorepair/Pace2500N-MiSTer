#!/usr/bin/env python3
"""Pace 2500N Channel Builder -- the Windows app (packaged as PaceChannelBuilder.exe).

Tabs
  Playout                 start/stop the playout server the MiSTer talks to; what is on now
  Channels                build the line-up: channels, style, programmes (files or Plex)
  Adverts & continuity    rip period adverts / continuity from YouTube; find the spots
  Schedule                the guide each channel will show today
  Settings                Plex sign-in, folders, tools

Everything is metadata: nothing is transcoded until the box tunes a channel.
"""
import json, os, queue, socket, subprocess, sys, threading, time, urllib.parse, urllib.request, uuid, webbrowser
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pace_channels as pc  # noqa: E402
import pace_playout  # noqa: E402

APP = 'Pace Channel Builder'
STYLES = {'bbc': 'BBC style - continuity, no adverts', 'itv': 'ITV style - terrestrial advert breaks',
          'sky': 'Sky style - satellite advert breaks'}
VIDEO_EXT = '*.mpg *.mpeg *.ts *.mkv *.mp4 *.avi *.m4v *.mov *.webm'
NO_WINDOW = pc.NO_WINDOW


def lan_addresses():
    out = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('192.168.1.1', 9))           # no packet is sent; picks the LAN interface
        out.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(out)


# ---------------------------------------------------------------------- Plex
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

    def library_programmes(self, section, kind):
        """Every film (movie library) or every episode (TV library) as programmes, in
        Plex's order, with Plex's durations (no probing needed)."""
        path = f'/library/sections/{section}/all' + ('?type=4' if kind == 'show' else '')
        out = []
        for m in self.get(path).get('Metadata', []):
            if not m.get('duration'):
                continue
            title = (m.get('grandparentTitle') or m['title']) if kind == 'show' else m['title']
            out.append({'title': title, 'source': f"plex:{m['ratingKey']}", 'duration': m['duration'] / 1000.0})
        return out

    def episodes(self, key):
        return [(m['ratingKey'], f"S{m.get('parentIndex', 0):02d}E{m.get('index', 0):02d}  {m['title']}",
                 m.get('grandparentTitle') or m['title']) for m in self.get(f'/library/metadata/{key}/allLeaves').get('Metadata', [])]


def plex_headers(client_id):
    return {'Accept': 'application/json', 'X-Plex-Product': APP, 'X-Plex-Client-Identifier': client_id}


def plex_sign_in(client_id, log, cancelled):
    """Plex's PIN sign-in: the user approves this app on plex.tv in their browser;
    the token comes back here. Returns (token, server_url or None)."""
    req = urllib.request.Request('https://plex.tv/api/v2/pins?strong=true', data=b'', method='POST',
                                 headers=plex_headers(client_id))
    pin = json.load(urllib.request.urlopen(req, timeout=15))
    q = urllib.parse.urlencode({'clientID': client_id, 'code': pin['code'], 'context[device][product]': APP})
    webbrowser.open(f'https://app.plex.tv/auth#?{q}')
    log('Plex: approve "Pace Channel Builder" in the browser window that just opened...')
    token = None
    for _ in range(150):                          # five minutes
        if cancelled():
            return None, None
        time.sleep(2)
        r = urllib.request.Request(f"https://plex.tv/api/v2/pins/{pin['id']}", headers=plex_headers(client_id))
        token = json.load(urllib.request.urlopen(r, timeout=15)).get('authToken')
        if token:
            break
    if not token:
        return None, None
    # find the user's server and its address on the local network
    r = urllib.request.Request('https://plex.tv/api/v2/resources?includeHttps=0',
                               headers=dict(plex_headers(client_id), **{'X-Plex-Token': token}))
    url = None
    for res in json.load(urllib.request.urlopen(r, timeout=15)):
        if 'server' not in res.get('provides', ''):
            continue
        for c in res.get('connections', []):
            if c.get('local') and not c.get('relay'):
                url = f"http://{c['address']}:{c['port']}"
                break
        if url:
            break
    return token, url


# ---------------------------------------------------------------------- app
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP)
        self.geometry('1120x740')
        self.minsize(900, 600)
        try:
            ttk.Style(self).theme_use('vista')
        except tk.TclError:
            pass
        ttk.Style(self).configure('Big.TButton', font=('Segoe UI', 12, 'bold'), padding=10)
        ttk.Style(self).configure('Head.TLabel', font=('Segoe UI', 13, 'bold'))
        self.settings = pc.load_settings()
        self.settings.setdefault('plex_client_id', str(uuid.uuid4()))
        if not self.settings.get('data_root'):
            self.settings['data_root'] = str(pc.ROOT)
        pc.save_settings(self.settings)
        self.lineup_path = None
        self.lineup = {'channels': []}
        self.server = None
        self.server_thread = None
        self.signing_in = False
        self.log_q = queue.Queue()
        self.start_diagnostics()
        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True, padx=6, pady=6)
        self.tab_playout(nb)
        self.tab_channels(nb)
        self.tab_interstitials(nb)
        self.tab_schedule(nb)
        self.tab_settings(nb)
        self.protocol('WM_DELETE_WINDOW', self.quit_app)
        last = self.settings.get('last_lineup')
        if last and Path(last).exists():
            self.load(last)
        self.after(200, self.pump)
        self.after(1000, self.refresh_now)
        if self.settings.get('autostart', True) and self.lineup_path and '--selftest' not in sys.argv:
            self.after(800, self.start_server)

    # ------------------------------------------------------------ diagnostics
    def start_diagnostics(self):
        """A windowed app has no console: everything that matters goes to
        app.log beside settings.json - the log, uncaught exceptions in any
        thread, a fault dump on a hard crash, and the stacks of every thread
        when playout stops answering (hang watchdog)."""
        import faulthandler, traceback
        path = pc.settings_path().with_name('app.log')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 5 << 20:
            path.replace(path.with_suffix('.old.log'))
        self.log_file = open(path, 'a', buffering=1, encoding='utf-8')
        self.log_lock = threading.Lock()
        faulthandler.enable(file=self.log_file, all_threads=True)
        self.file_log(f'==== {APP} started (pid {os.getpid()})')

        def hook(kind, exc_type, exc, tb):
            self.file_log(f'uncaught exception in {kind}:' + chr(10) + ''.join(traceback.format_exception(exc_type, exc, tb)))
        sys.excepthook = lambda t, e, tb: hook('main thread', t, e, tb)
        threading.excepthook = lambda a: hook(f'thread {a.thread.name if a.thread else "?"}', a.exc_type, a.exc_value, a.exc_traceback)
        self.report_callback_exception = lambda t, e, tb: hook('Tk callback', t, e, tb)

        def watchdog():
            missed = 0
            while True:
                time.sleep(5)
                srv = self.server
                if not srv:
                    missed = 0
                    continue
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/service", timeout=15).read()
                    missed = 0
                except Exception as e:
                    missed += 1
                    self.log(f'WATCHDOG: playout did not answer ({e}); thread stacks written to app.log')
                    if missed <= 3:
                        with self.log_lock:
                            self.log_file.write(f'---- thread stacks {time.strftime("%H:%M:%S")}' + chr(10))
                            faulthandler.dump_traceback(file=self.log_file, all_threads=True)
                            self.log_file.flush()
        threading.Thread(target=watchdog, name='watchdog', daemon=True).start()

    def file_log(self, line):
        with self.log_lock:
            self.log_file.write(line + chr(10))

    # ------------------------------------------------------------ plumbing
    def log(self, msg):
        if not msg[:2].isdigit():
            msg = time.strftime('%H:%M:%S ') + msg
        self.file_log(msg)
        self.log_q.put(msg)

    def ui(self, fn):
        """Run fn on the Tk thread (background work must not touch widgets)."""
        self.log_q.put(fn)

    def pump(self):
        while not self.log_q.empty():
            item = self.log_q.get()
            if callable(item):
                item()
                continue
            self.logbox.insert('end', item + '\n')
            self.logbox.see('end')
        self.after(200, self.pump)

    def background(self, fn, *args):
        def run():
            try:
                fn(*args)
            except Exception as e:  # report, keep the app alive
                msg = str(e)
                self.log(f'error: {msg}')
                self.ui(lambda: messagebox.showerror(APP, msg))
        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------ playout
    def tab_playout(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text='  Playout  ')
        top = ttk.Frame(f)
        top.pack(fill='x')
        self.btn_play = ttk.Button(top, text='Start playout', style='Big.TButton', command=self.toggle_server)
        self.btn_play.pack(side='left')
        self.status_lbl = ttk.Label(top, text='Stopped', style='Head.TLabel', foreground='#a00')
        self.status_lbl.pack(side='left', padx=16)
        ttk.Button(top, text='Open status page in browser',
                   command=lambda: webbrowser.open(f"http://localhost:{self.settings['port']}/")).pack(side='right')
        addr = ', '.join(f"{a}:{self.settings['port']}" for a in lan_addresses()) or '(unknown)'
        ttk.Label(f, text=f'The MiSTer relay must point at this PC: {addr}   '
                          '(set in /media/fat/linux/pace/relay.ini on the MiSTer).  Nothing is transcoded until the box tunes a channel.',
                  foreground='#555').pack(anchor='w', pady=(8, 4))
        ttk.Label(f, text='On air now', style='Head.TLabel').pack(anchor='w', pady=(8, 2))
        cols = ('no', 'channel', 'now', 'next', 'onair')
        self.now_tv = ttk.Treeview(f, columns=cols, show='headings', height=6)
        for c, t, w in (('no', 'No.', 50), ('channel', 'Channel', 140), ('now', 'Now', 220), ('next', 'Next', 260), ('onair', 'Playing', 360)):
            self.now_tv.heading(c, text=t)
            self.now_tv.column(c, width=w, anchor='w')
        self.now_tv.pack(fill='x')
        self.streaming_lbl = ttk.Label(f, text='', foreground='#060')
        self.streaming_lbl.pack(anchor='w', pady=6)
        ttk.Label(f, text='Log', style='Head.TLabel').pack(anchor='w')
        self.logbox = tk.Text(f, height=14, font=('Consolas', 9))
        self.logbox.pack(fill='both', expand=True)

    def toggle_server(self):
        if self.server:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        if not self.lineup_path:
            messagebox.showinfo(APP, 'Create or open a line-up on the Channels tab first.')
            return
        if not Path(self.settings.get('huffman_ram', '')).exists():
            messagebox.showerror(APP, 'The firmware RAM image (for guide text) is not set or missing - see Settings.')
            return
        self.save()
        self.btn_play.config(state='disabled')
        self.status_lbl.config(text='Starting...', foreground='#a60')

        def run():
            try:
                srv = pace_playout.Server(int(self.settings['port']), self.lineup_path, self.settings, log=self.log)
            except Exception as e:
                self.log(f'playout could not start: {e}')
                self.ui(lambda: (self.btn_play.config(state='normal'),
                                 self.status_lbl.config(text='Stopped', foreground='#a00')))
                return
            self.server = srv
            self.log(f"playout running on port {srv.server_address[1]} with {len(srv.chans)} channel(s)")
            self.ui(lambda: (self.btn_play.config(state='normal', text='Stop playout'),
                             self.status_lbl.config(text='Running', foreground='#060')))
            srv.serve_forever()
        self.server_thread = threading.Thread(target=run, daemon=True)
        self.server_thread.start()

    def stop_server(self):
        srv, self.server = self.server, None
        if srv:
            threading.Thread(target=lambda: (srv.shutdown(), srv.server_close()), daemon=True).start()
            self.log('playout stopped')
        self.btn_play.config(text='Start playout')
        self.status_lbl.config(text='Stopped', foreground='#a00')

    def refresh_now(self):
        if self.server:
            try:
                d = self.server.now()
                self.now_tv.delete(*self.now_tv.get_children())
                for c in d['channels']:
                    self.now_tv.insert('', 'end', values=(c['number'], c['name'], c['now'], f"{c['next_at']}  {c['next']}",
                                                          f"{c['on_air']}: {c['source']}"))
                st = d['streaming']
                last = getattr(self.server, 'last_box', None)
                if st:
                    text = 'Box connected - streaming: ' + '; '.join(f"{s['channel']} ({s['seconds']} s)" for s in st)
                elif last:
                    text = (f'Box not connected (last connected {time.strftime("%H:%M:%S", time.localtime(last[0]))} '
                            f'from {last[1]}). Is the Pace core running on the MiSTer?')
                else:
                    text = ('The box has not connected yet. Load the Pace core on the MiSTer; if it still does not '
                            'connect, check relay.ini on the MiSTer points at this PC and Windows Firewall allows this app.')
                self.streaming_lbl.config(text=text, foreground='#060' if st else '#a60')
            except Exception as e:
                self.streaming_lbl.config(text=f'status: {e}')
        self.after(2000, self.refresh_now)

    # ------------------------------------------------------------ channels
    def tab_channels(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text='  Channels  ')
        top = ttk.Frame(f)
        top.pack(fill='x')
        for text, cmd in (('New line-up', self.new), ('Open...', self.open), ('Save', self.save), ('Save as...', self.save_as)):
            ttk.Button(top, text=text, command=cmd).pack(side='left', padx=2)
        self.path_lbl = ttk.Label(top, text='(unsaved)', foreground='#555')
        self.path_lbl.pack(side='left', padx=10)
        body = ttk.Panedwindow(f, orient='horizontal')
        body.pack(fill='both', expand=True, pady=6)
        left = ttk.Frame(body)
        body.add(left, weight=1)
        ttk.Label(left, text='Channels', style='Head.TLabel').pack(anchor='w')
        self.chan_list = tk.Listbox(left, exportselection=False, height=14, font=('Segoe UI', 10))
        self.chan_list.pack(fill='both', expand=True)
        self.chan_list.bind('<<ListboxSelect>>', lambda e: self.show_channel())
        row = ttk.Frame(left)
        row.pack(fill='x', pady=2)
        for text, cmd in (('Add', self.add_channel), ('Remove', self.del_channel), ('Up', lambda: self.move_channel(-1)),
                          ('Down', lambda: self.move_channel(1))):
            ttk.Button(row, text=text, command=cmd, width=8).pack(side='left', padx=1)
        right = ttk.Frame(body, padding=(10, 0))
        body.add(right, weight=3)
        form = ttk.Frame(right)
        form.pack(fill='x')
        self.v_name, self.v_num, self.v_style, self.v_start = (tk.StringVar() for _ in range(4))
        ttk.Label(form, text='Name').grid(row=0, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.v_name, width=30).grid(row=0, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Channel number').grid(row=1, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.v_num, width=8).grid(row=1, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Style').grid(row=2, column=0, sticky='w')
        ttk.Combobox(form, textvariable=self.v_style, values=list(STYLES.values()), state='readonly', width=40).grid(
            row=2, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Broadcast day starts (UTC)').grid(row=3, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.v_start, width=8).grid(row=3, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Adverts / continuity sets').grid(row=4, column=0, sticky='nw')
        self.sets_box = tk.Listbox(form, selectmode='multiple', exportselection=False, height=4, width=40)
        self.sets_box.grid(row=4, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Changes are saved as you make them.', foreground='#555').grid(row=5, column=1, sticky='w', pady=6)
        self._showing = False
        for v in (self.v_name, self.v_num, self.v_style, self.v_start):
            v.trace_add('write', lambda *a: self.field_edited())
        self.sets_box.bind('<<ListboxSelect>>', lambda e: self.field_edited())
        ttk.Label(right, text='Programmes (play in this order, repeating through the day)', style='Head.TLabel').pack(anchor='w', pady=(6, 2))
        self.prog = ttk.Treeview(right, columns=('title', 'source'), show='headings', height=12)
        self.prog.heading('title', text='Title in the guide')
        self.prog.heading('source', text='Source')
        self.prog.column('title', width=220)
        self.prog.column('source', width=520)
        self.prog.pack(fill='both', expand=True)
        row = ttk.Frame(right)
        row.pack(fill='x', pady=4)
        for text, cmd in (('Add files...', self.add_files), ('Add from Plex...', self.add_plex), ('Rename', self.rename_prog),
                          ('Remove', self.del_prog), ('Up', lambda: self.move_prog(-1)), ('Down', lambda: self.move_prog(1))):
            ttk.Button(row, text=text, command=cmd).pack(side='left', padx=1)

    def set_names(self):
        base = pc.ROOT / 'roms' / 'interstitials'
        return [f'roms/interstitials/{d.name}' for d in sorted(base.glob('*')) if d.is_dir()] if base.exists() else []

    def current(self):
        sel = self.chan_list.curselection()
        return self.lineup['channels'][sel[0]] if sel else None

    def refresh_channels(self, select=None):
        self.chan_list.delete(0, 'end')
        for c in self.lineup['channels']:
            self.chan_list.insert('end', f"{c.get('number', '')}   {c['name']}   ({len(c['programmes'])} programmes)")
        if select is not None and self.lineup['channels']:
            self.chan_list.selection_set(select)
            self.show_channel()

    def show_channel(self):
        c = self.current()
        if not c:
            return
        self._showing = True
        try:
            self._show_channel(c)
        finally:
            self._showing = False

    def _show_channel(self, c):
        self.v_name.set(c['name'])
        self.v_num.set(c.get('number', ''))
        self.v_style.set(STYLES.get(c.get('style', 'bbc')))
        self.v_start.set(c.get('start', '06:00'))
        self.sets_box.delete(0, 'end')
        names = self.set_names()
        for n in names:
            self.sets_box.insert('end', n.split('/')[-1])
            if n in c.get('interstitials', []):
                self.sets_box.selection_set('end')
        self.prog.delete(*self.prog.get_children())
        for p in c['programmes']:
            self.prog.insert('', 'end', values=(p['title'], p['source']))

    def field_edited(self):
        if self._showing or not self.current():
            return
        if getattr(self, '_apply_job', None):
            self.after_cancel(self._apply_job)
        self._apply_job = self.after(700, self.apply_channel)

    def apply_channel(self):
        self._apply_job = None
        c = self.current()
        if not c:
            return
        c['name'] = self.v_name.get().strip() or c['name']
        try:
            c['number'] = int(self.v_num.get())
        except ValueError:
            pass
        c['style'] = next((k for k, v in STYLES.items() if v == self.v_style.get()), 'bbc')
        c['start'] = self.v_start.get().strip() or '06:00'
        names = self.set_names()
        c['interstitials'] = [names[i] for i in self.sets_box.curselection()]
        sel = self.chan_list.curselection()
        self.refresh_channels(sel[0] if sel else None)
        self.changed()

    def add_channel(self):
        n = len(self.lineup['channels'])
        self.lineup['channels'].append({'name': f'Channel {n + 1}', 'number': 101 + n, 'style': 'bbc', 'start': '06:00',
                                        'interstitials': [], 'programmes': []})
        self.refresh_channels(n)
        self.changed()

    def del_channel(self):
        sel = self.chan_list.curselection()
        if sel and messagebox.askyesno(APP, 'Remove this channel from the line-up?'):
            del self.lineup['channels'][sel[0]]
            self.refresh_channels(0 if self.lineup['channels'] else None)
            self.changed()

    def move_channel(self, d):
        sel = self.chan_list.curselection()
        if sel and 0 <= sel[0] + d < len(self.lineup['channels']):
            ch = self.lineup['channels']
            ch[sel[0]], ch[sel[0] + d] = ch[sel[0] + d], ch[sel[0]]
            self.refresh_channels(sel[0] + d)
            self.changed()

    def add_files(self):
        c = self.current()
        if not c:
            return
        for f in filedialog.askopenfilenames(title='Programmes', filetypes=[('Video', VIDEO_EXT), ('All files', '*.*')]):
            c['programmes'].append({'title': Path(f).stem, 'source': Path(f).as_posix()})
        self.show_channel()
        self.changed()

    def add_plex(self):
        c = self.current()
        if not c:
            return
        if not self.settings.get('plex_url') or not self.settings.get('plex_token'):
            messagebox.showinfo(APP, 'Sign in with Plex on the Settings tab first.')
            return
        try:
            PlexPicker(self, Plex(self.settings['plex_url'], self.settings['plex_token']),
                       lambda items: (c['programmes'].extend(items),
                                      self.refresh_channels(self.chan_list.curselection()[0]), self.changed()))
        except Exception as e:
            messagebox.showerror(APP, f'Plex: {e}')

    def selected_prog(self):
        sel = self.prog.selection()
        return self.prog.index(sel[0]) if sel else None

    def rename_prog(self):
        c, i = self.current(), self.selected_prog()
        if c and i is not None:
            t = simpledialog.askstring(APP, 'Title shown in the guide:', initialvalue=c['programmes'][i]['title'])
            if t:
                c['programmes'][i]['title'] = t
                self.show_channel()
                self.changed()

    def del_prog(self):
        c, i = self.current(), self.selected_prog()
        if c and i is not None:
            del c['programmes'][i]
            self.show_channel()
            self.changed()

    def move_prog(self, d):
        c, i = self.current(), self.selected_prog()
        if c and i is not None and 0 <= i + d < len(c['programmes']):
            p = c['programmes']
            p[i], p[i + d] = p[i + d], p[i]
            self.show_channel()
            self.changed()
            self.prog.selection_set(self.prog.get_children()[i + d])

    def new(self):
        self.lineup, self.lineup_path = {'channels': []}, None
        self.path_lbl.config(text='(unsaved)')
        self.refresh_channels()

    def open(self):
        f = filedialog.askopenfilename(title='Open line-up', filetypes=[('Line-up', '*.json')], initialdir=pc.ROOT / 'roms')
        if f:
            self.load(f)

    def load(self, f):
        try:
            lineup = json.loads(Path(f).read_text())
            if not isinstance(lineup, dict) or not isinstance(lineup.get('channels'), list):
                raise ValueError('it has no "channels" list, so it is not a channel line-up')
        except Exception as e:
            # never refuse to open over a bad file: say which file and why, start with no line-up
            self.log(f'could not open line-up {f}: {e}')
            messagebox.showerror(APP, f'Could not open the line-up\n{f}\n\n{e}\n\nUse Open... on the Channels tab to pick another.')
            return
        self.lineup = lineup
        self.lineup_path = f
        self.path_lbl.config(text=f)
        self.settings['last_lineup'] = f
        pc.save_settings(self.settings)
        self.refresh_channels(0 if self.lineup['channels'] else None)

    def save(self):
        if not self.lineup_path:
            return self.save_as()
        # write a temp file and swap it in, so the app closing mid-save can't leave a broken line-up
        p = Path(self.lineup_path)
        tmp = p.with_name(p.name + '.saving')
        tmp.write_text(json.dumps(self.lineup, indent=1))
        os.replace(tmp, p)

    def changed(self):
        """Every edit: save the line-up now (a new one goes to roms/lineup.json), and have a
        running playout pick it up shortly (edits in quick succession reload once)."""
        if not self.lineup_path:
            self.lineup_path = str(pc.ROOT / 'roms' / 'lineup.json')
            self.path_lbl.config(text=self.lineup_path)
            self.settings['last_lineup'] = self.lineup_path
            pc.save_settings(self.settings)
        self.save()
        if self.server:
            if getattr(self, '_reload_job', None):
                self.after_cancel(self._reload_job)
            self._reload_job = self.after(2000, self.reload_playout)

    def reload_playout(self):
        self._reload_job = None
        if self.server:
            self.log('line-up changed: reloading playout')
            self.stop_server()
            self.after(500, self.start_server)

    def save_as(self):
        f = filedialog.asksaveasfilename(title='Save line-up', defaultextension='.json', initialdir=pc.ROOT / 'roms',
                                         filetypes=[('Line-up', '*.json')])
        if f:
            self.lineup_path = f
            self.path_lbl.config(text=f)
            self.settings['last_lineup'] = f
            pc.save_settings(self.settings)
            self.save()

    # ------------------------------------------------------------ interstitials
    def tab_interstitials(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text='  Adverts & continuity  ')
        ttk.Label(f, text='Period adverts and continuity are ripped from YouTube into sets named by station and years '
                          '(e.g. itv_1987_89, bbc1_1988_89, sky1_1993_94). Each set is split into the original spots '
                          'automatically; breaks reuse them exactly as they aired.', wraplength=1000).pack(anchor='w')
        row = ttk.Frame(f)
        row.pack(fill='x', pady=6)
        self.v_query, self.v_set = tk.StringVar(value='TVS adverts 1987'), tk.StringVar(value='itv_1987_89')
        ttk.Label(row, text='Search YouTube for').pack(side='left')
        ttk.Entry(row, textvariable=self.v_query, width=36).pack(side='left', padx=4)
        ttk.Button(row, text='Search', command=lambda: self.background(self.yt_search)).pack(side='left')
        ttk.Label(row, text='   Rip into set').pack(side='left')
        ttk.Entry(row, textvariable=self.v_set, width=18).pack(side='left', padx=4)
        ttk.Button(row, text='Rip selected', command=lambda: self.background(self.yt_rip)).pack(side='left')
        self.yt = ttk.Treeview(f, columns=('len', 'title', 'id'), show='headings', height=9, selectmode='extended')
        for col, t, w in (('len', 'Length', 70), ('title', 'Title', 760), ('id', 'Video', 120)):
            self.yt.heading(col, text=t)
            self.yt.column(col, width=w)
        self.yt.pack(fill='x')
        row = ttk.Frame(f)
        row.pack(fill='x', pady=(10, 2))
        ttk.Label(row, text='Your sets', style='Head.TLabel').pack(side='left')
        ttk.Button(row, text='Import videos into set...', command=self.import_videos).pack(side='left', padx=12)
        ttk.Button(row, text='Refresh', command=self.refresh_sets).pack(side='left')
        ttk.Label(f, text='Long compilations are split automatically at the cuts between items (black frames with '
                          'silence; announcer pauses in continuity). Select a set to see its spots; Play to check one, '
                          'Exclude anything that is not an advert/ident/continuity (a break never runs across it).',
                  wraplength=1000, foreground='#555').pack(anchor='w')
        pane = ttk.Panedwindow(f, orient='horizontal')
        pane.pack(fill='both', expand=True, pady=4)
        left = ttk.Frame(pane)
        pane.add(left, weight=1)
        self.sets = ttk.Treeview(left, columns=('set', 'files', 'size'), show='headings', height=8, selectmode='browse')
        for col, t, w in (('set', 'Set', 170), ('files', 'Recordings', 80), ('size', 'Size', 70)):
            self.sets.heading(col, text=t)
            self.sets.column(col, width=w)
        self.sets.pack(fill='both', expand=True)
        self.sets.bind('<<TreeviewSelect>>', lambda e: self.refresh_spots())
        right = ttk.Frame(pane)
        pane.add(right, weight=3)
        self.spots = ttk.Treeview(right, columns=('rec', 'start', 'len', 'state'), show='headings', height=8)
        for col, t, w in (('rec', 'Recording', 300), ('start', 'Starts at', 90), ('len', 'Length', 70), ('state', 'Used?', 220)):
            self.spots.heading(col, text=t)
            self.spots.column(col, width=w)
        self.spots.pack(fill='both', expand=True)
        self.spots.bind('<Double-1>', lambda e: self.play_spot())
        row = ttk.Frame(right)
        row.pack(fill='x', pady=2)
        ttk.Button(row, text='Play', command=self.play_spot).pack(side='left')
        ttk.Button(row, text='Exclude / include', command=self.toggle_spot).pack(side='left', padx=4)
        self.spot_lbl = ttk.Label(row, text='', foreground='#555')
        self.spot_lbl.pack(side='left', padx=8)
        self.spot_rows = {}
        self.refresh_sets()

    def ytdlp(self):
        for p in (self.settings.get('ytdlp'), pc.bundled('yt-dlp.exe'),
                  str(Path(os.environ.get('APPDATA', '')) / 'Python' / 'Python312' / 'Scripts' / 'yt-dlp.exe')):
            if p and Path(p).exists():
                return p
        return 'yt-dlp'

    def yt_search(self):
        q = self.v_query.get().strip()
        self.log(f'YouTube search: {q}')
        out = subprocess.run([self.ytdlp(), '--flat-playlist', '--print', '%(id)s|%(duration)s|%(title)s', f'ytsearch20:{q}'],
                             capture_output=True, text=True, creationflags=NO_WINDOW)
        rows = [line.split('|', 2) for line in out.stdout.splitlines() if line.count('|') >= 2]

        def fill():
            self.yt.delete(*self.yt.get_children())
            for vid, ln, title in rows:
                try:
                    ln = f'{int(float(ln)) // 60}:{int(float(ln)) % 60:02d}'
                except ValueError:
                    pass
                self.yt.insert('', 'end', values=(ln, title, vid))
        self.ui(fill)

    def yt_rip(self):
        ids = [self.yt.item(i)['values'][2] for i in self.yt.selection()]
        if not ids:
            return
        if getattr(self, '_ripping', False):
            self.log('a rip is already running - wait for it to finish')
            return
        self._ripping = True
        try:
            self._yt_rip(ids)
        finally:
            self._ripping = False

    def _yt_rip(self, ids):
        target = pc.ROOT / 'roms' / 'interstitials' / self.v_set.get().strip()
        target.mkdir(parents=True, exist_ok=True)
        ff = str(Path(self.settings['ffmpeg']).parent)
        for vid in ids:
            self.log(f'ripping {vid} into {target.name}')
            subprocess.run([self.ytdlp(), '--ffmpeg-location', ff, '-f', 'bv*[height<=576]+ba/b', '--merge-output-format', 'mkv',
                            '--write-info-json', '--no-playlist', '-o', str(target / '%(id)s.%(ext)s'), str(vid)],
                           capture_output=True, creationflags=NO_WINDOW)
        self.log('rip finished; finding spots...')
        self.ui(self.refresh_sets)
        self.analyse(target)

    def refresh_sets(self):
        self.sets.delete(*self.sets.get_children())
        base = pc.ROOT / 'roms' / 'interstitials'
        for d in sorted(base.glob('*')) if base.exists() else []:
            files = [x for x in d.glob('*') if x.suffix.lower() in pc.VIDEO_SUFFIXES]
            self.sets.insert('', 'end', values=(d.name, len(files), f'{sum(x.stat().st_size for x in files) >> 20} MB'))

    def selected_set(self):
        sel = self.sets.selection()
        return pc.ROOT / 'roms' / 'interstitials' / str(self.sets.item(sel[0])['values'][0]) if sel else None

    def import_videos(self):
        """Bring videos downloaded anywhere into a set (copied), then find their spots."""
        files = filedialog.askopenfilenames(title='Videos to add to a set', filetypes=[('Video', VIDEO_EXT), ('All files', '*.*')])
        if not files:
            return
        default = self.selected_set().name if self.selected_set() else self.v_set.get().strip()
        name = simpledialog.askstring(APP, 'Set name (station and years, e.g. c4_1994):', initialvalue=default)
        if not name:
            return
        target = pc.ROOT / 'roms' / 'interstitials' / name.strip()

        def run():
            import shutil
            target.mkdir(parents=True, exist_ok=True)
            for src in files:
                dst = target / Path(src).name
                if not dst.exists():
                    self.log(f'importing {Path(src).name} into {target.name}')
                    shutil.copy2(src, dst)
            self.ui(self.refresh_sets)
            self.analyse(target)
            self.ui(lambda: self.select_set(target.name))
        self.background(run)

    def select_set(self, name):
        for i in self.sets.get_children():
            if str(self.sets.item(i)['values'][0]) == name:
                self.sets.selection_set(i)
                self.sets.see(i)

    def refresh_spots(self):
        folder = self.selected_set()            # read on the Tk thread
        if folder:
            self.spot_lbl.config(text='finding spots...')
            self.background(self.show_spots, folder)

    def show_spots(self, folder):
        media = pc.Media(self.settings)
        excluded = pc.excluded_spots(folder)
        rows, used, total = [], 0, 0.0
        for f in sorted(folder.glob('*')):
            if f.suffix.lower() not in pc.VIDEO_SUFFIXES:
                continue
            title = f.name
            info = f.with_suffix('.info.json')
            if info.exists():
                try:
                    title = json.loads(info.read_text(encoding='utf-8')).get('title', f.name)
                except ValueError:
                    pass
            for a, ln in pc.recording_spots(media, f, self.log):
                sid = pc.spot_id(f, a)
                if sid in excluded:
                    state = 'excluded'
                elif not pc.usable(ln):
                    state = 'not used (too short)' if ln < 2 else 'not used (too long - a programme?)'
                else:
                    state = 'used'
                    used += 1
                    total += ln
                rows.append((str(f), a, ln, title, state, sid))

        def fill():
            self.spots.delete(*self.spots.get_children())
            self.spot_rows = {}
            for src, a, ln, title, state, sid in rows:
                i = self.spots.insert('', 'end', values=(title[:60], f'{int(a) // 60}:{a % 60:04.1f}', f'{ln:.1f} s', state))
                self.spot_rows[i] = (src, a, ln, sid)
            self.spot_lbl.config(text=f'{used} usable spots, {total / 60:.0f} minutes')
        self.ui(fill)

    def play_spot(self):
        sel = self.spots.selection()
        if not sel:
            return
        src, a, ln, _ = self.spot_rows[sel[0]]
        ffplay = str(Path(self.settings['ffmpeg']).with_name('ffplay.exe'))
        subprocess.Popen([ffplay, '-hide_banner', '-loglevel', 'error', '-autoexit', '-ss', f'{a:.2f}', '-t', f'{ln:.2f}',
                          '-window_title', f'{Path(src).name} @ {a:.1f}s', src], creationflags=NO_WINDOW)

    def toggle_spot(self):
        folder = self.selected_set()
        if not folder:
            return
        ids = pc.excluded_spots(folder)
        for i in self.spots.selection():
            sid = self.spot_rows[i][3]
            ids.symmetric_difference_update({sid})
        pc.set_excluded(folder, ids)
        self.refresh_spots()

    def analyse_set(self):
        folder = self.selected_set()
        if folder:
            self.analyse(folder)

    def analyse(self, folder):
        runs = pc.interstitial_runs(pc.Media(self.settings), [str(folder)], self.log)
        self.log(f'{Path(folder).name}: {sum(len(r) for r in runs)} spots in {len(runs)} recordings, '
                 f'{sum(s[2] for r in runs for s in r) / 60:.0f} minutes')

    # ------------------------------------------------------------ schedule
    def tab_schedule(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text='  Schedule  ')
        row = ttk.Frame(f)
        row.pack(fill='x')
        ttk.Button(row, text="Show today's guide", command=lambda: self.save() or self.background(self.build_schedule)).pack(side='left')
        ttk.Button(row, text='Find natural breaks in programmes (slow, once)',
                   command=lambda: self.save() or self.background(self.prepare)).pack(side='left', padx=6)
        self.sched = tk.Text(f, font=('Consolas', 10))
        self.sched.pack(fill='both', expand=True, pady=6)

    def build_schedule(self):
        chans, _ = pc.load_lineup(self.lineup_path, self.settings, self.log)
        d = datetime.now(timezone.utc).date()
        lines = []
        for c in chans:
            lines.append(f'{c.number}  {c.name}   ({c.style}, {sum(len(r) for r in c.runs)} advert/continuity spots)')
            for s0, ln, title in c.events_utc(d):
                lines.append(f'      {s0 // 3600:02d}:{s0 // 60 % 60:02d}  {ln // 60:4d} min  {title}')
            lines.append('')

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
        self.log('natural breaks found for all programmes')

    # ------------------------------------------------------------ settings
    def tab_settings(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text='  Settings  ')
        ttk.Label(f, text='Plex', style='Head.TLabel').grid(row=0, column=0, sticky='w')
        self.plex_lbl = ttk.Label(f, text='')
        self.plex_lbl.grid(row=1, column=0, columnspan=3, sticky='w')
        row = ttk.Frame(f)
        row.grid(row=2, column=0, columnspan=3, sticky='w', pady=4)
        self.btn_plex = ttk.Button(row, text='Sign in with Plex...', style='Big.TButton', command=self.plex_sign_in)
        self.btn_plex.pack(side='left')
        ttk.Button(row, text='Test connection', command=lambda: self.background(self.test_plex)).pack(side='left', padx=6)
        ttk.Button(row, text='Sign out', command=self.plex_sign_out).pack(side='left')
        ttk.Label(f, text='Plex server address').grid(row=3, column=0, sticky='w')
        self.v_plex_url = tk.StringVar(value=self.settings.get('plex_url', ''))
        ttk.Entry(f, textvariable=self.v_plex_url, width=50).grid(row=3, column=1, sticky='w')
        ttk.Separator(f).grid(row=4, column=0, columnspan=3, sticky='we', pady=12)
        ttk.Label(f, text='Folders and tools', style='Head.TLabel').grid(row=5, column=0, sticky='w')
        self.v_paths = {}
        fields = (('data_root', 'Data folder (line-ups, roms\\)', 'dir'), ('huffman_ram', 'Firmware RAM image (guide text)', 'file'),
                  ('ffmpeg', 'ffmpeg.exe', 'file'), ('port', 'Playout port', None), ('days', 'Days of listings', None))
        for i, (key, label, kind) in enumerate(fields):
            ttk.Label(f, text=label).grid(row=6 + i, column=0, sticky='w', pady=2)
            v = tk.StringVar(value=str(self.settings.get(key, '')))
            ttk.Entry(f, textvariable=v, width=80 if kind else 10).grid(row=6 + i, column=1, sticky='w')
            if kind:
                ttk.Button(f, text='Browse...', command=lambda v=v, kind=kind: self.browse(v, kind)).grid(row=6 + i, column=2, padx=4)
            self.v_paths[key] = v
        self.v_autostart = tk.BooleanVar(value=self.settings.get('autostart', True))
        ttk.Checkbutton(f, text='Start playout when the app opens', variable=self.v_autostart).grid(row=11, column=1, sticky='w', pady=4)
        ttk.Button(f, text='Save settings', command=self.save_settings).grid(row=12, column=1, sticky='w', pady=10)
        ttk.Label(f, text=f'Settings are stored in {pc.settings_path()} (never in the project or on GitHub).',
                  foreground='#555').grid(row=13, column=0, columnspan=3, sticky='w')
        self.show_plex_state()

    def browse(self, var, kind):
        p = filedialog.askdirectory() if kind == 'dir' else filedialog.askopenfilename()
        if p:
            var.set(p)

    def show_plex_state(self):
        if self.settings.get('plex_token'):
            self.plex_lbl.config(text=f"Signed in. Server: {self.settings.get('plex_url') or '(not found - enter the address below)'}",
                                 foreground='#060')
        else:
            self.plex_lbl.config(text='Not signed in. Click "Sign in with Plex" - your browser opens Plex\'s own sign-in page; '
                                      'approve "Pace Channel Builder" and you are done.', foreground='#a60')

    def plex_sign_in(self):
        if self.signing_in:
            return
        self.signing_in = True
        self.btn_plex.config(state='disabled', text='Waiting for Plex...')

        def run():
            try:
                token, url = plex_sign_in(self.settings['plex_client_id'], self.log, lambda: not self.signing_in)
                if token:
                    self.settings['plex_token'] = token
                    if url:
                        self.settings['plex_url'] = url
                    pc.save_settings(self.settings)
                    self.log(f'Plex: signed in; server {url or "(not found)"}')
                else:
                    self.log('Plex: sign-in not completed')
            finally:
                self.signing_in = False
                self.ui(lambda: (self.btn_plex.config(state='normal', text='Sign in with Plex...'),
                                 self.v_plex_url.set(self.settings.get('plex_url', '')), self.show_plex_state()))
        self.background(run)

    def plex_sign_out(self):
        self.settings.pop('plex_token', None)
        pc.save_settings(self.settings)
        self.show_plex_state()

    def test_plex(self):
        self.ui(self.save_settings)
        time.sleep(0.3)
        secs = Plex(self.settings['plex_url'], self.settings['plex_token']).sections()
        msg = 'Plex libraries: ' + ', '.join(t for _, t, _ in secs)
        self.log(msg)
        self.ui(lambda: messagebox.showinfo(APP, msg))

    def save_settings(self):
        self.settings['plex_url'] = self.v_plex_url.get().strip().rstrip('/')
        self.settings['autostart'] = bool(self.v_autostart.get())
        for k, v in self.v_paths.items():
            val = v.get().strip()
            self.settings[k] = int(val) if k in ('port', 'days') and val.isdigit() else val
        pc.save_settings(self.settings)
        pc.load_settings()                 # applies the data folder
        self.show_plex_state()
        self.refresh_sets()
        self.log('settings saved')

    def quit_app(self):
        if self.server and '--selftest' not in sys.argv and not messagebox.askyesno(
                APP, 'Playout is running - closing the app stops your channels on the box.' + chr(10) * 2 + 'Close anyway?'):
            return
        self.file_log('==== closed by the user' if '--selftest' not in sys.argv else '==== selftest done')
        self.signing_in = False
        self.stop_server()
        self.destroy()


class PlexPicker(tk.Toplevel):
    """Browse Plex libraries -> shows/movies -> episodes; add the selection."""
    def __init__(self, app, plex, done):
        super().__init__(app)
        self.title('Add from Plex')
        self.geometry('820x560')
        self.plex, self.done = plex, done
        ttk.Label(self, text='Library').pack(anchor='w', padx=8, pady=(8, 0))
        self.lib = ttk.Combobox(self, state='readonly', width=50)
        self.lib.pack(anchor='w', padx=8, pady=4)
        self.lib.bind('<<ComboboxSelected>>', lambda e: self.load_items())
        pane = ttk.Panedwindow(self, orient='horizontal')
        pane.pack(fill='both', expand=True, padx=8)
        self.items = tk.Listbox(pane, exportselection=False)
        pane.add(self.items, weight=1)
        self.items.bind('<<ListboxSelect>>', lambda e: self.load_eps())
        self.eps = tk.Listbox(pane, selectmode='extended', exportselection=False)
        pane.add(self.eps, weight=2)
        row = ttk.Frame(self)
        row.pack(pady=6)
        ttk.Button(row, text='Add selected to the channel', command=self.add).pack(side='left', padx=4)
        ttk.Button(row, text='Add the whole library', command=self.add_library).pack(side='left', padx=4)
        self.sections = plex.sections()
        self.lib['values'] = [f'{t}  ({ty})' for _, t, ty in self.sections]

    def load_items(self):
        self.item_rows = self.plex.items(self.sections[self.lib.current()][0])
        self.items.delete(0, 'end')
        for _, t, _ in self.item_rows:
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

    def add_library(self):
        if self.lib.current() < 0:
            messagebox.showinfo(APP, 'Choose a library first.', parent=self)
            return
        key, title, kind = self.sections[self.lib.current()]
        rows = self.plex.library_programmes(key, kind)
        what = 'episodes' if kind == 'show' else 'items'
        if rows and messagebox.askyesno(APP, f'Add all {len(rows)} {what} from "{title}" to the channel?', parent=self):
            self.done(rows)
            self.destroy()

    def add(self):
        self.done([{'title': show, 'source': f'plex:{key}'} for i in self.eps.curselection()
                   for key, _, show in [self.ep_rows[i]]])
        self.destroy()


def selftest(out):
    """Packaged-app check: load the line-up, run playout in-process, report."""
    app = App()
    res = {'lineup': app.lineup_path, 'channels': [c['name'] for c in app.lineup['channels']],
           'ffmpeg': app.settings['ffmpeg'], 'ffmpeg_exists': Path(app.settings['ffmpeg']).exists(),
           'ytdlp': app.ytdlp(), 'data_root': str(pc.ROOT), 'sets': len(app.sets.get_children())}
    app.start_server()
    for _ in range(300):
        app.update()
        time.sleep(0.05)
        if app.server:
            break
    for _ in range(40):
        app.update()
        time.sleep(0.05)
    try:
        res['service_itv'] = urllib.request.urlopen(f"http://127.0.0.1:{app.settings['port']}/service?video=0x4210&audio=0x4112",
                                                    timeout=5).read().decode()
        res['now'] = json.load(urllib.request.urlopen(f"http://127.0.0.1:{app.settings['port']}/now.json", timeout=10))['channels']
    except Exception as e:
        res['error'] = str(e)
    res['log'] = app.logbox.get('1.0', 'end').splitlines()[-8:]
    app.quit_app()
    Path(out).write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--selftest':
        selftest(sys.argv[2])
    else:
        App().mainloop()
