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
import json, os, queue, re, socket, subprocess, sys, threading, time, urllib.parse, urllib.request, uuid, webbrowser
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pace_channels as pc  # noqa: E402
import pace_playout  # noqa: E402

APP = 'Pace Channel Builder 0.8.0B'
STYLES = {'bbc': 'BBC style - continuity, no adverts', 'itv': 'ITV style - terrestrial advert breaks',
          'sky': 'Sky style - satellite advert breaks'}
# Guide genre pages (TV Guide 2-8). Automatic: Plex films make a movie channel, otherwise the
# commonest Plex genre of the channel's programmes; Entertainment when Plex cannot say.
GENRES = {'auto': 'Automatic (from Plex)', 'entertainment': 'Entertainment', 'movies': 'Movies',
          'sports': 'Sports', 'news': 'News & Documentaries', 'kids': 'Kids', 'music': 'Music & Radio',
          'specialist': 'Specialist'}
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
        req = urllib.request.Request(f'{self.url}{path}',
                                     headers={'Accept': 'application/json', 'X-Plex-Token': self.token})
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)['MediaContainer']

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
            out.append({'title': title, 'source': f"plex:{m['ratingKey']}", 'duration': m['duration'] / 1000.0,
                        'summary': m.get('summary', '')})
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
        self.log_q = queue.Queue(maxsize=300)
        self.ui_q = queue.SimpleQueue()
        self.server = None
        self.start_diagnostics()
        self.settings = pc.load_settings(self.log)
        self.settings.setdefault('plex_client_id', str(uuid.uuid4()))
        if not self.settings.get('data_root'):
            self.settings['data_root'] = str(pc.ROOT)
        self.lineup_path = None
        self.lineup = {'channels': []}
        self.server_thread = None
        self.server_stop = None
        self.restart_playout = False
        self.closing = False
        self.status_pending = False
        self.signing_in = False
        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True, padx=6, pady=6)
        self.tab_playout(nb)
        self.tab_channels(nb)
        self.radio = RadioPanel(nb, self)
        nb.add(self.radio, text='  Music & Radio  ')
        self.tab_interstitials(nb)
        self.tab_schedule(nb)
        self.tab_settings(nb)
        self.protocol('WM_DELETE_WINDOW', self.quit_app)
        last = self.settings.get('last_lineup')
        if last and Path(last).exists():
            self.load(last, startup=True)
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
        self.diagnostics_stop = threading.Event()
        faulthandler.enable(file=self.log_file, all_threads=True)
        self.file_log(f'==== {APP} started (pid {os.getpid()})')

        def hook(kind, exc_type, exc, tb):
            self.file_log(f'uncaught exception in {kind}:' + chr(10) + ''.join(traceback.format_exception(exc_type, exc, tb)))
        sys.excepthook = lambda t, e, tb: hook('main thread', t, e, tb)
        threading.excepthook = lambda a: hook(f'thread {a.thread.name if a.thread else "?"}', a.exc_type, a.exc_value, a.exc_traceback)
        self.report_callback_exception = lambda t, e, tb: hook('Tk callback', t, e, tb)

        def watchdog():
            missed = 0
            while not self.diagnostics_stop.wait(5):
                srv = self.server
                if not srv:
                    missed = 0
                    continue
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/service", timeout=5) as response:
                        response.read()
                    missed = 0
                except Exception as e:
                    if self.server is not srv or (self.server_stop and self.server_stop.is_set()):
                        continue
                    missed += 1
                    self.log(f'WATCHDOG: playout did not answer ({e}); thread stacks written to app.log')
                    if missed <= 3:
                        with self.log_lock:
                            if not self.log_file.closed:
                                self.log_file.write(f'---- thread stacks {time.strftime("%H:%M:%S")}' + chr(10))
                                faulthandler.dump_traceback(file=self.log_file, all_threads=True)
                                self.log_file.flush()
        threading.Thread(target=watchdog, name='watchdog', daemon=True).start()

    def file_log(self, line):
        with self.log_lock:
            if not self.log_file.closed:
                self.log_file.write(pc.redact(line) + chr(10))

    def close_window(self):
        import faulthandler
        self.diagnostics_stop.set()
        with self.log_lock:
            faulthandler.disable()
            self.log_file.close()
        self.destroy()

    # ------------------------------------------------------------ plumbing
    def log(self, msg):
        msg = pc.redact(msg)
        if not msg[:2].isdigit():
            msg = time.strftime('%H:%M:%S ') + msg
        self.file_log(msg)
        try:
            self.log_q.put_nowait(msg)
        except queue.Full:
            pass

    def ui(self, fn):
        """Run fn on the Tk thread (background work must not touch widgets)."""
        self.ui_q.put(fn)

    def pump(self):
        self.after(150, self.pump)
        for _ in range(30):
            try:
                callback = self.ui_q.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception:
                self.report_callback_exception(*sys.exc_info())
            if self.closing and not self.server_thread:
                return
        lines = []
        for _ in range(80):
            try:
                lines.append(self.log_q.get_nowait())
            except queue.Empty:
                break
        if lines:
            self.logbox.insert('end', '\n'.join(lines) + '\n')
            self.logbox.delete('1.0', 'end-1500lines')
            self.logbox.see('end')

    def background(self, fn, *args):
        def run():
            try:
                fn(*args)
            except Exception as e:  # report, keep the app alive
                msg = pc.redact(e)
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
        if self.server_thread:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        if self.server_thread or self.closing:
            return
        if not self.lineup_path:
            messagebox.showinfo(APP, 'Create or open a line-up on the Channels tab first.')
            return
        if not Path(self.settings.get('huffman_ram', '')).is_file():
            messagebox.showerror(APP, 'Select FLASH_U202.bin under Firmware image in Settings to encode guide text.')
            return
        path, settings = self.lineup_path, dict(self.settings)
        stop = self.server_stop = threading.Event()
        self.btn_play.config(state='normal', text='Cancel start')
        self.status_lbl.config(text='Starting...', foreground='#a60')

        def run():
            srv = None
            try:
                srv = pace_playout.Server(settings['port'], path, settings, log=self.log)
                srv.timeout = 0.25
                self.server = srv
                self.log(f"playout running on port {srv.server_address[1]} with {len(srv.chans)} channel(s)")
                self.ui(lambda: self.show_running(stop))
                while not stop.is_set():
                    srv.handle_request()
            except Exception as e:
                self.log(f'playout failed: {e}')
            finally:
                if srv:
                    srv.server_close()
                    self.log('playout stopped')
                self.server = None
                self.ui(self.playout_stopped)
        self.server_thread = threading.Thread(target=run, daemon=True)
        self.server_thread.start()

    def show_running(self, stop):
        if not stop.is_set():
            self.btn_play.config(state='normal', text='Stop playout')
            self.status_lbl.config(text='Running', foreground='#060')

    def stop_server(self):
        self.restart_playout = False
        if getattr(self, '_reload_job', None):
            self.after_cancel(self._reload_job)
            self._reload_job = None
        if self.server_stop:
            self.server_stop.set()
            self.btn_play.config(state='disabled')
            self.status_lbl.config(text='Stopping...', foreground='#a60')

    def playout_stopped(self):
        self.server_thread = self.server_stop = None
        if self.closing:
            self.close_window()
            return
        self.btn_play.config(state='normal', text='Start playout')
        self.status_lbl.config(text='Stopped', foreground='#a00')
        self.streaming_lbl.config(text='')
        if self.restart_playout:
            self.restart_playout = False
            self.start_server()

    def refresh_now(self):
        self.after(2000, self.refresh_now)
        srv = self.server
        if not srv or self.status_pending or self.closing:
            return
        self.status_pending = True

        def read():
            try:
                d = srv.now()
            except Exception as e:
                d = pc.redact(e)
            self.ui(lambda: self.show_status(srv, d))
        threading.Thread(target=read, name='playout status', daemon=True).start()

    def show_status(self, srv, d):
        self.status_pending = False
        if self.server is not srv:
            return
        if isinstance(d, str):
            self.streaming_lbl.config(text=f'Status unavailable: {d}')
            return
        self.now_tv.delete(*self.now_tv.get_children())
        for c in d['channels']:
            self.now_tv.insert('', 'end', values=(c['number'], c['name'], c['now'], f"{c['next_at']}  {c['next']}",
                                                  f"{c['on_air']}: {c['source']}"))
        self.radio.show_tracks(d['radio'])
        streams = d['streaming']
        if streams:
            text = 'Box connected - streaming: ' + ', '.join(f"{s['channel']} ({s['seconds']} s)" for s in streams)
        else:
            text = 'Waiting for the MiSTer relay to tune a service.'
        self.streaming_lbl.config(text=text, foreground='#060' if streams else '#a60')

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
        music = ttk.Frame(f)
        music.pack(fill='x', pady=4)
        self.music_lbl = ttk.Label(music, text='EPG background audio is off')
        self.music_lbl.pack(side='left', padx=6)
        ttk.Button(music, text='Choose audio…', command=self.choose_music).pack(side='left', padx=3)
        ttk.Button(music, text='Clear', command=self.clear_music).pack(side='left')
        ttk.Button(top, text='Music & Radio…', command=lambda: nb.select(self.radio)).pack(side='right', padx=2)
        self.music_path_lbl = ttk.Label(f, foreground='#555', wraplength=1030)
        self.music_path_lbl.pack(fill='x', padx=6)
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
        for text, cmd in (('Add', self.add_channel), ('Add IPTV', self.add_iptv), ('Remove', self.del_channel),
                          ('Up', lambda: self.move_channel(-1)), ('Down', lambda: self.move_channel(1))):
            ttk.Button(row, text=text, command=cmd, width=9 if text == 'Add IPTV' else 8).pack(side='left', padx=1)
        right = ttk.Frame(body, padding=(10, 0))
        body.add(right, weight=3)
        form = ttk.Frame(right)
        form.pack(fill='x')
        self.v_name, self.v_num, self.v_style, self.v_start, self.v_genre = (tk.StringVar() for _ in range(5))
        ttk.Label(form, text='Name').grid(row=0, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.v_name, width=30).grid(row=0, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Channel number').grid(row=1, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.v_num, width=8).grid(row=1, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Style').grid(row=2, column=0, sticky='w')
        ttk.Combobox(form, textvariable=self.v_style, values=list(STYLES.values()), state='readonly', width=40).grid(
            row=2, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Guide genre').grid(row=3, column=0, sticky='w')
        ttk.Combobox(form, textvariable=self.v_genre, values=list(GENRES.values()), state='readonly', width=40).grid(
            row=3, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Broadcast day starts (UTC)').grid(row=4, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.v_start, width=8).grid(row=4, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Adverts / continuity sets').grid(row=5, column=0, sticky='nw')
        self.sets_box = tk.Listbox(form, selectmode='multiple', exportselection=False, height=4, width=40)
        self.sets_box.grid(row=5, column=1, sticky='w', pady=2)
        ttk.Label(form, text='Changes are saved as you make them.', foreground='#555').grid(row=6, column=1, sticky='w', pady=6)
        self._showing = False
        for v in (self.v_name, self.v_num, self.v_style, self.v_start, self.v_genre):
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
            kind = 'live IPTV' if c.get('iptv') else f"{len(c.get('programmes') or [])} programmes"
            self.chan_list.insert('end', f"{c.get('number', '')}   {c['name']}   ({kind})")
        if select is not None and self.lineup['channels']:
            self.chan_list.selection_set(select)
            self.show_channel()

    def show_channel(self):
        self.cancel_channel_edit()
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
        self.v_genre.set(GENRES.get(c.get('genre', 'auto'), GENRES['auto']))
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
        self.cancel_channel_edit()
        self._apply_job = self.after(700, self.apply_channel)

    def cancel_channel_edit(self):
        if getattr(self, '_apply_job', None):
            self.after_cancel(self._apply_job)
            self._apply_job = None

    def apply_channel(self):
        self._apply_job = None
        c = self.current()
        if not c:
            return
        c['name'] = self.v_name.get().strip() or c['name']
        try:
            number = int(self.v_num.get())
        except ValueError:
            number = c['number']
        if number != c['number']:
            # one number, one service: the box shows a second row with that number and never
            # gives it listings, so a number already in use is refused
            owner = next((o.get('name', '?') for o in self.lineup['channels'] + list(self.lineup.get('radio') or [])
                          if o is not c and isinstance(o, dict) and str(o.get('number')) == str(number)), None)
            if owner:
                self.v_num.set(str(c['number']))
                messagebox.showerror(APP, f'Channel number {number} is already used by {owner}.')
            else:
                c['number'] = number
        c['style'] = next((k for k, v in STYLES.items() if v == self.v_style.get()), 'bbc')
        c['start'] = self.v_start.get().strip() or '06:00'
        c['genre'] = next((k for k, v in GENRES.items() if v == self.v_genre.get()), 'auto')
        names = self.set_names()
        c['interstitials'] = [names[i] for i in self.sets_box.curselection()]
        sel = self.chan_list.curselection()
        self.refresh_channels(sel[0] if sel else None)
        self.changed()

    def add_channel(self):
        n = len(self.lineup['channels'])
        used = {str(o.get('number')) for o in self.lineup['channels'] + list(self.lineup.get('radio') or [])
                if isinstance(o, dict)}
        number = next(k for k in range(101, 1000) if str(k) not in used)
        self.lineup['channels'].append({'name': f'Channel {n + 1}', 'number': number, 'style': 'bbc', 'start': '06:00',
                                        'interstitials': [], 'programmes': []})
        self.refresh_channels(n)
        self.changed()

    def add_iptv(self):
        """A live TV channel from an internet stream: chosen from an iptv-org country list, or
        any stream URL typed in. Converted only while the box is tuned to it."""
        IPTVPicker(self, self.add_live_channel)

    def add_live_channel(self, name, url, genre='entertainment', tvg_id=''):
        used = {str(o.get('number')) for o in self.lineup['channels'] + list(self.lineup.get('radio') or [])
                if isinstance(o, dict)}
        first = pc.GENRE_BLOCK.get(genre, 101)
        number = next((k for k in range(first, 1000) if str(k) not in used and not 800 <= k <= 899),
                      next(k for k in range(101, 1000) if str(k) not in used and not 800 <= k <= 899))
        n = len(self.lineup['channels'])
        channel = {'name': name, 'number': number, 'style': 'sky', 'genre': genre,
                   'iptv': url, 'interstitials': [], 'programmes': []}
        if tvg_id:
            channel['tvg_id'] = tvg_id      # playout finds the channel's guide data by it
        self.lineup['channels'].append(channel)
        self.refresh_channels(n)
        self.changed()
        self.log(f'IPTV channel {number} {name} added ({GENRES.get(genre, genre)}) - checking the stream...')

        def check():
            probe = re.sub(r'ffmpeg(\.exe)?$', lambda m: 'ffprobe' + (m.group(1) or ''), self.settings['ffmpeg'])
            args = [probe, '-v', 'error', '-rw_timeout', '10000000']
            if '.m3u8' in url:
                args += ['-extension_picky', '0']
            args += ['-show_entries', 'stream=codec_type,codec_name,width,height', '-of', 'compact', url]
            try:
                out = subprocess.run(args, capture_output=True, text=True, timeout=40,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
            except (OSError, subprocess.SubprocessError) as e:
                out = ''
                self.log(f'{name}: stream check failed: {e}')
            video = re.search(r'codec_name=(\w+)\|codec_type=video\|width=(\d+)\|height=(\d+)', out)
            audio = 'codec_type=audio' in out
            guide = pc.iptv_guide(channel)
            self.log(f'{name}: ' + (f'guide data from {guide[0]}' if guide else
                                    'no guide data found - the Guide will show "Live TV"'))
            if video and audio:
                self.log(f'{name}: stream OK - {video.group(1)} {video.group(2)}x{video.group(3)} with sound')
            else:
                self.log(f'{name}: WARNING - the stream did not answer with picture and sound; it may be '
                         'offline, geo-blocked or not a video stream')
        threading.Thread(target=check, name='IPTV check', daemon=True).start()

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
            path = Path(f)
            source = path.relative_to(pc.ROOT) if pc.portable() and path.is_relative_to(pc.ROOT) else path
            c['programmes'].append({'title': path.stem, 'source': source.as_posix()})
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
        self.cancel_channel_edit()
        self.lineup, self.lineup_path = {'channels': []}, None
        self.path_lbl.config(text='(unsaved)')
        self.refresh_channels()
        self.show_music()
        self.radio.refresh()

    def show_music(self):
        music = self.lineup.get('epg_music')
        path = pc.ROOT / music if music else None
        available = path and path.is_file()
        self.music_lbl.config(text='EPG background audio is off' if not path else
                                   'EPG background audio selected' if available else 'EPG background audio file is missing')
        self.music_path_lbl.config(text=str(path) if path else '')

    def choose_music(self):
        file = filedialog.askopenfilename(title='Choose EPG background audio', initialdir=pc.ROOT / 'roms' / 'music',
                                          filetypes=[('Audio', '*.mp2 *.mp3 *.wav *.flac *.m4a *.ogg'), ('All files', '*')])
        if file:
            path = Path(file)
            self.lineup['epg_music'] = path.relative_to(pc.ROOT).as_posix() if path.is_relative_to(pc.ROOT) else str(path)
            self.show_music()
            self.changed()

    def clear_music(self):
        if self.lineup.pop('epg_music', None):
            self.show_music()
            self.changed()

    def open(self):
        f = filedialog.askopenfilename(title='Open line-up', filetypes=[('Line-up', '*.json')], initialdir=pc.ROOT / 'roms')
        if f:
            self.load(f)

    def load(self, f, startup=False):
        try:
            lineup = pc.read_lineup(f)
        except Exception as e:
            # never refuse to open over a bad file: say which file and why, start with no line-up
            self.log(f'could not open line-up {f}: {e}')
            if not startup:
                messagebox.showerror(APP, f'Could not open the line-up\n{f}\n\n{e}')
            return
        self.cancel_channel_edit()
        self.lineup = lineup
        self.lineup_path = f
        self.path_lbl.config(text=f)
        self.settings['last_lineup'] = f
        if not startup:
            pc.save_settings(self.settings)
        self.refresh_channels(0 if self.lineup['channels'] else None)
        self.show_music()
        self.radio.refresh()
        if self.server_thread:
            self.reload_playout()

    def save(self):
        if not self.lineup_path:
            return self.save_as()
        # write a temp file and swap it in, so the app closing mid-save can't leave a broken line-up
        pc.write_json(self.lineup_path, self.lineup, indent=1)

    def changed(self):
        """Every edit: save the line-up now (a new one goes to roms/lineup.json), and have a
        running playout pick it up shortly (edits in quick succession reload once)."""
        if not self.lineup_path:
            folder = pc.ROOT / 'roms'
            path = folder / 'lineup.json'
            n = 2
            while path.exists():
                path = folder / f'lineup-{n}.json'
                n += 1
            self.lineup_path = str(path)
            self.path_lbl.config(text=self.lineup_path)
            self.settings['last_lineup'] = self.lineup_path
        self.save()
        pc.save_settings(self.settings)
        if self.server_thread and (not self.server_stop.is_set() or self.restart_playout):
            if getattr(self, '_reload_job', None):
                self.after_cancel(self._reload_job)
            self._reload_job = self.after(2000, self.reload_playout)

    def reload_playout(self):
        self._reload_job = None
        if self.server_thread:
            self.log('line-up changed: reloading playout')
            self.stop_server()
            self.restart_playout = True

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
        ttk.Button(row, text='Search', command=lambda: self.background(self.yt_search, self.v_query.get().strip())).pack(side='left')
        ttk.Label(row, text='   Rip into set').pack(side='left')
        ttk.Entry(row, textvariable=self.v_set, width=18).pack(side='left', padx=4)
        ttk.Button(row, text='Rip selected', command=self.yt_rip).pack(side='left')
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

    def yt_search(self, q):
        self.log(f'YouTube search: {q}')
        out = subprocess.run([self.ytdlp(), '--flat-playlist', '--print', '%(id)s|%(duration)s|%(title)s', f'ytsearch20:{q}'],
                             capture_output=True, text=True, creationflags=NO_WINDOW, timeout=90, check=True)
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
        name = self.v_set.get().strip()
        if not name or name in ('.', '..') or Path(name).name != name or ':' in name:
            self._ripping = False
            messagebox.showerror(APP, 'Enter a folder name for the set.')
            return
        target = pc.ROOT / 'roms' / 'interstitials' / name
        ff = str(Path(self.settings['ffmpeg']).parent)
        self.background(self._yt_rip, ids, target, ff)

    def _yt_rip(self, ids, target, ff):
        try:
            self.rip_videos(ids, target, ff)
        finally:
            self.ui(lambda: setattr(self, '_ripping', False))

    def rip_videos(self, ids, target, ff):
        target.mkdir(parents=True, exist_ok=True)
        for vid in ids:
            self.log(f'ripping {vid} into {target.name}')
            subprocess.run([self.ytdlp(), '--ffmpeg-location', ff, '-f', 'bv*[height<=576]+ba/b', '--merge-output-format', 'mkv',
                            '--write-info-json', '--no-playlist', '-o', str(target / '%(id)s.%(ext)s'), str(vid)],
                           capture_output=True, creationflags=NO_WINDOW, timeout=900, check=True)
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
            for s0, ln, title, _ in c.events_utc(d):
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
        ttk.Button(row, text='Test connection', command=self.test_plex).pack(side='left', padx=6)
        ttk.Button(row, text='Sign out', command=self.plex_sign_out).pack(side='left')
        ttk.Label(f, text='Plex server address').grid(row=3, column=0, sticky='w')
        self.v_plex_url = tk.StringVar(value=self.settings.get('plex_url', ''))
        ttk.Entry(f, textvariable=self.v_plex_url, width=50).grid(row=3, column=1, sticky='w')
        ttk.Separator(f).grid(row=4, column=0, columnspan=3, sticky='we', pady=12)
        ttk.Label(f, text='Folders and tools', style='Head.TLabel').grid(row=5, column=0, sticky='w')
        self.v_paths = {}
        fields = (('data_root', 'Data folder (line-ups, roms\\)', 'dir'), ('huffman_ram', 'Firmware image (guide text)', 'file'),
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
        self.v_text_options = {}
        for row, (key, label) in enumerate((
                ('teletext', 'Live Teletext pages (V080B or newer core)'),
                ('teletext_subtitles', 'Page 888 subtitles from English text / Teletext tracks'),
                ('teletext_internet', 'News, weather from public IP, and MiSTer updates'),
                ('auto_pillarbox', 'Fill 4:3 programmes stored inside a 16:9 picture')), 12):
            var = tk.BooleanVar(value=self.settings.get(key, True))
            self.v_text_options[key] = var
            ttk.Checkbutton(f, text=label, variable=var).grid(row=row, column=1, sticky='w', pady=2)
        self.v_subtitle_delay = tk.StringVar(value=str(self.settings.get('subtitle_delay', .7)))
        ttk.Label(f, text='Subtitle delay (seconds)').grid(row=16, column=0, sticky='w')
        ttk.Entry(f, textvariable=self.v_subtitle_delay, width=10).grid(row=16, column=1, sticky='w')
        ttk.Button(f, text='Save settings', command=self.save_settings).grid(row=17, column=1, sticky='w', pady=10)
        ttk.Label(f, text=f'Settings are stored in {pc.settings_path()}.',
                  foreground='#555').grid(row=18, column=0, columnspan=3, sticky='w')
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
        url, token = self.v_plex_url.get().strip(), self.settings.get('plex_token')
        if not url or not token:
            messagebox.showinfo(APP, 'Sign in and enter the Plex server address first.')
            return
        self.background(self.read_plex_status, Plex(url, token))

    def read_plex_status(self, plex):
        secs = plex.sections()
        msg = 'Plex libraries: ' + ', '.join(t for _, t, _ in secs)
        self.log(msg)
        self.ui(lambda: messagebox.showinfo(APP, msg))

    def save_settings(self):
        settings = {**self.settings, **{k: v.get().strip() for k, v in self.v_paths.items()}}
        settings.update(plex_url=self.v_plex_url.get().strip().rstrip('/'), autostart=bool(self.v_autostart.get()))
        settings.update({key: bool(var.get()) for key, var in self.v_text_options.items()})
        try:
            settings['port'], settings['days'] = int(settings['port']), int(settings['days'])
            settings['subtitle_delay'] = float(self.v_subtitle_delay.get())
            if not 1 <= settings['port'] <= 65535 or not 1 <= settings['days'] <= 8:
                raise ValueError
            if not -10 <= settings['subtitle_delay'] <= 10:
                raise ValueError
        except ValueError:
            messagebox.showerror(APP, 'Enter a port from 1 to 65535, 1 to 8 days of listings, and a subtitle delay from -10 to 10 seconds.')
            return
        if not Path(settings['data_root']).is_dir():
            messagebox.showerror(APP, 'Choose an existing data folder.')
            return
        old_root = Path(self.settings['data_root'])
        if Path(settings['library_cache']) == old_root / 'roms' / 'library_cache.json':
            settings['library_cache'] = str(Path(settings['data_root']) / 'roms' / 'library_cache.json')
        pc.save_settings(settings)
        self.settings = pc.load_settings(self.log)
        self.show_plex_state()
        self.show_music()
        self.refresh_sets()
        self.log('settings saved')
        if self.server_thread:
            self.reload_playout()

    def quit_app(self):
        if self.server_thread and '--selftest' not in sys.argv and not messagebox.askyesno(
                APP, 'Playout is running - closing the app stops your channels on the box.' + chr(10) * 2 + 'Close anyway?'):
            return
        self.file_log('==== closed by the user' if '--selftest' not in sys.argv else '==== selftest done')
        self.signing_in = False
        self.closing = True
        self.cancel_channel_edit()
        self.stop_server()
        if not self.server_thread:
            self.close_window()


class RadioPanel(ttk.Frame):
    """Edit the internet radio services stored in the current line-up."""

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.table = ttk.Treeview(self, columns=('number', 'name', 'now'), show='headings', height=10)
        for col, label, width in (('number', 'Channel', 68), ('name', 'Station', 220), ('now', 'Now playing', 540)):
            self.table.heading(col, text=label)
            self.table.column(col, width=width, stretch=(col == 'now'))
        scroll = ttk.Scrollbar(self, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.table.bind('<<TreeviewSelect>>', self.select_station)
        form = ttk.Frame(self)
        form.grid(row=1, column=0, sticky='ew', pady=(8, 4))
        form.columnconfigure(1, weight=1)
        self.number, self.name, self.url = (tk.StringVar(self) for _ in range(3))
        for row, (label, value) in enumerate((('Channel (800–899)', self.number), ('Station name', self.name),
                                               ('Direct stream URL', self.url))):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', padx=(0, 8), pady=3)
            ttk.Entry(form, textvariable=value).grid(row=row, column=1, sticky='ew', pady=3)
        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, sticky='ew', pady=(4, 0))
        for label, command in (('New', self.new_station), ('Save station', self.save_station),
                               ('Remove selected', self.remove_stations), ('Add starter stations', self.add_presets)):
            ttk.Button(actions, text=label, command=command).pack(side='left', padx=(0, 5))
        self.refresh()

    def stations(self):
        return self.app.lineup.get('radio', [])

    def tv_numbers(self):
        return {str(channel.get('number', '')).strip() for channel in self.app.lineup['channels']}

    def refresh(self, select=None):
        self.table.delete(*self.table.get_children())
        for i, station in enumerate(self.stations()):
            if isinstance(station, dict):
                self.table.insert('', 'end', iid=str(i), values=(station.get('number', ''), station.get('name', ''), ''))
        if select is None:
            self.new_station()
        else:
            self.table.selection_set(str(select))

    def new_station(self):
        self.table.selection_remove(self.table.selection())
        used = self.tv_numbers() | {str(s.get('number', '')).strip() for s in self.stations() if isinstance(s, dict)}
        self.number.set(next((str(n) for n in range(800, 900) if str(n) not in used), ''))
        self.name.set('')
        self.url.set('')

    def select_station(self, _event):
        selection = self.table.selection()
        if len(selection) == 1:
            self.number.set(self.table.set(selection[0], 'number'))
            self.name.set(self.table.set(selection[0], 'name'))
            self.url.set(self.stations()[int(selection[0])].get('url', ''))

    def show_tracks(self, stations):
        tracks = {(str(s['number']), s['name']): s['now'] for s in stations}
        for row in self.table.get_children():
            number = self.table.set(row, 'number')
            name = self.table.set(row, 'name')
            self.table.set(row, 'now', tracks.get((number, name), ''))

    def save_station(self):
        selection = self.table.selection()
        if len(selection) > 1:
            messagebox.showinfo(APP, 'Select one station to edit or choose New.', parent=self)
            return
        stations = list(self.stations())
        index = int(selection[0]) if selection else len(stations)
        try:
            station = pc.RadioStation(dict(number=self.number.get(), name=self.name.get(), url=self.url.get()))
            used = self.tv_numbers() | {str(s.get('number', '')).strip() for i, s in enumerate(stations)
                                        if i != index and isinstance(s, dict)}
            if str(station.number) in used:
                raise ValueError('Channel number already in use.')
        except ValueError as exc:
            messagebox.showerror(APP, str(exc), parent=self)
            return
        stations[index:index + 1] = [dict(number=station.number, name=station.name, url=station.url)]
        self.save(stations, select=index)

    def remove_stations(self):
        selected = {int(i) for i in self.table.selection()}
        if selected:
            self.save([station for i, station in enumerate(self.stations()) if i not in selected])

    def add_presets(self):
        stations = list(self.stations())
        numbers = self.tv_numbers() | {str(s.get('number', '')).strip() for s in stations if isinstance(s, dict)}
        urls = {s.get('url') for s in stations if isinstance(s, dict) and isinstance(s.get('url'), str)}
        presets = json.loads((HERE / 'radio.example.json').read_text(encoding='utf-8'))
        for station in presets:
            if str(station['number']) not in numbers and station['url'] not in urls:
                stations.append(station)
        if len(stations) == len(self.stations()):
            messagebox.showinfo(APP, 'No starter stations to add. They are already listed or their channel numbers are in use.',
                                parent=self)
        else:
            self.save(stations)

    def save(self, stations, select=None):
        self.app.lineup['radio'] = stations
        self.app.changed()
        self.refresh(select)


class IPTVPicker(tk.Toplevel):
    """Pick a live channel from an iptv-org country list (official sources by default), or
    paste any stream URL."""
    def __init__(self, app, done):
        super().__init__(app)
        self.title('Add an IPTV channel')
        self.geometry('900x560')
        self.app, self.done, self.rows = app, done, []
        top = ttk.Frame(self, padding=8)
        top.pack(fill='x')
        ttk.Label(top, text='Country list').pack(side='left')
        self.country = ttk.Combobox(top, values=['uk', 'us', 'ie', 'au', 'ca', 'fr', 'de'], width=5)
        self.country.set('uk')
        self.country.pack(side='left', padx=4)
        ttk.Button(top, text='Load', command=self.load).pack(side='left', padx=4)
        ttk.Label(top, text='Search').pack(side='left', padx=(16, 0))
        self.search = tk.StringVar()
        self.search.trace_add('write', lambda *a: self.show())
        ttk.Entry(top, textvariable=self.search, width=24).pack(side='left', padx=4)
        self.official = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text='Official sources only (Pluto TV, Samsung TV Plus, BBC, ...)', variable=self.official,
                        command=self.show).pack(side='left', padx=8)
        cols = ('name', 'genre', 'listings', 'notes', 'source')
        self.tree = ttk.Treeview(self, columns=cols, show='headings', selectmode='extended')
        for c, t, w in (('name', 'Channel', 220), ('genre', 'Guide genre', 100), ('listings', 'Listings', 70),
                        ('notes', 'Notes', 120), ('source', 'Stream', 360)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8)
        row = ttk.Frame(self, padding=8)
        row.pack(fill='x')
        ttk.Button(row, text='Add selected', command=self.add).pack(side='left')
        ttk.Button(row, text='Paste a stream URL instead...', command=self.paste).pack(side='left', padx=8)
        self.status = ttk.Label(row, text='', foreground='#555')
        self.status.pack(side='left', padx=8)
        ttk.Label(self, text='Many unofficial entries in these lists are re-streams of paid channels; the filter keeps '
                             'to broadcasters\' own and free ad-supported services.', foreground='#555',
                  padding=(8, 0, 8, 8)).pack(anchor='w')
        self.load()

    def load(self):
        country = self.country.get().strip().lower() or 'uk'
        self.status.config(text=f'Loading the {country} list...')

        def run():
            try:
                rows = pc.iptv_playlist(country)
                for r in rows:      # programme listings available for the channel (else "Live TV")
                    r['listings'] = bool(pc.iptv_guide({'iptv': r['url'], 'tvg_id': r['tvg_id']}))
            except Exception as e:
                msg = f'Could not load the iptv-org list: {e}'
                self.app.ui(lambda: self.winfo_exists() and self.status.config(text=msg))
                return
            self.app.ui(lambda: self.winfo_exists() and self.loaded(rows))
        threading.Thread(target=run, name='iptv-org list', daemon=True).start()

    def loaded(self, rows):
        self.rows = rows
        self.show()

    def show(self):
        text = self.search.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for i, r in enumerate(self.rows):
            if self.official.get() and not r['official']:
                continue
            if text and text not in (r['name'] + ' ' + r['group']).lower():
                continue
            self.tree.insert('', 'end', iid=str(i), values=(r['name'], GENRES.get(r['genre'], r['genre']),
                                                            'yes' if r.get('listings') else '-',
                                                            r['notes'], r['url']))
            shown += 1
        self.status.config(text=f'{shown} of {len(self.rows)} channels')

    def add(self):
        picked = [self.rows[int(i)] for i in self.tree.selection()]
        for r in picked:
            self.done(r['name'], r['url'], r['genre'], r.get('tvg_id', ''))
        if picked:
            self.destroy()

    def paste(self):
        url = simpledialog.askstring(APP, 'Live stream URL (http/https, e.g. an .m3u8 playlist):', parent=self)
        if not url:
            return
        url = url.strip()
        if not url.lower().startswith(('http://', 'https://')):
            messagebox.showerror(APP, 'The stream needs an http:// or https:// address.', parent=self)
            return
        name = simpledialog.askstring(APP, 'Channel name shown in the guide:', initialvalue='Live TV', parent=self)
        if name and name.strip():
            self.done(name.strip(), url, 'entertainment')
            self.destroy()


class PlexPicker(tk.Toplevel):
    """Browse Plex libraries -> shows/movies -> episodes; add the selection."""
    def __init__(self, app, plex, done):
        super().__init__(app)
        self.title('Add from Plex')
        self.geometry('820x560')
        self.app, self.plex, self.done = app, plex, done
        self.sections, self.item_rows, self.ep_rows = [], [], []
        self.request = 0
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
        self.fetch(plex.sections, self.show_sections)

    def fetch(self, work, show):
        self.request += 1
        request = self.request

        def run():
            try:
                result = work()
            except Exception as e:
                error = pc.redact(e)
                self.app.log(f'Plex: {error}')
                self.app.ui(lambda: finish(lambda: messagebox.showerror(APP, error, parent=self)))
            else:
                self.app.ui(lambda: finish(lambda: show(result)))

        def finish(update):
            if self.winfo_exists() and request == self.request:
                update()

        threading.Thread(target=run, name='Plex library', daemon=True).start()

    def show_sections(self, sections):
        self.sections = sections
        self.lib['values'] = [f'{t}  ({ty})' for _, t, ty in sections]

    def load_items(self):
        selected = self.lib.current()
        if selected < 0:
            return
        key = self.sections[selected][0]
        self.item_rows, self.ep_rows = [], []
        self.items.delete(0, 'end')
        self.eps.delete(0, 'end')
        self.fetch(lambda: self.plex.items(key), self.show_items)

    def show_items(self, items):
        self.item_rows = items
        for _, title, _ in items:
            self.items.insert('end', title)

    def load_eps(self):
        sel = self.items.curselection()
        if not sel:
            return
        key, title, ty = self.item_rows[sel[0]]
        self.ep_rows = []
        self.eps.delete(0, 'end')
        self.fetch(lambda: self.plex.episodes(key) if ty == 'show' else [(key, title, title)], self.show_episodes)

    def show_episodes(self, episodes):
        self.ep_rows = episodes
        self.eps.delete(0, 'end')
        for _, label, _ in self.ep_rows:
            self.eps.insert('end', label)

    def add_library(self):
        if self.lib.current() < 0:
            messagebox.showinfo(APP, 'Choose a library first.', parent=self)
            return
        key, title, kind = self.sections[self.lib.current()]
        what = 'episodes' if kind == 'show' else 'items'

        def add_rows(rows):
            if rows and messagebox.askyesno(APP, f'Add all {len(rows)} {what} from "{title}" to the channel?', parent=self):
                self.done(rows)
                self.destroy()
        self.fetch(lambda: self.plex.library_programmes(key, kind), add_rows)

    def add(self):
        if not self.eps.curselection():
            return
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
    while app.server_thread:
        app.update()
        time.sleep(0.05)
    pc.write_json(out, res, indent=1)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--selftest':
        selftest(sys.argv[2])
    else:
        App().mainloop()
