#!/usr/bin/env python3
"""Riati watch bridge — serves the project folder and receives live readings.

  GET  /live                      latest readings + this Mac's LAN address (the demo polls this)
  GET  /ingest?hr=72&spo2=96      store readings (easy to call from an iPhone Shortcut or a browser)
  POST /ingest  {"hr":72,...}     same, JSON body (what an aggregator or native HealthKit app would send)

Run:  python3 watch_bridge.py [port]      (default port 8734)
"""
import json, os, socket, sys, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8734
ROOT = os.path.dirname(os.path.abspath(__file__))
FIELDS = {'hr', 'spo2', 'rr', 'sbp', 'dbp', 'temp', 'wt', 'steps', 'borg'}
DRY_WEIGHT_KG = 78
latest = {}


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return '127.0.0.1'


class Bridge(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ingest(self, params):
        now = int(time.time() * 1000)
        src = params.get('source', 'watch')
        if isinstance(src, list):
            src = src[0]
        got = {}
        for k, raw in params.items():
            if k not in FIELDS:
                continue
            try:
                v = float(raw[0] if isinstance(raw, list) else raw)
            except (TypeError, ValueError):
                continue
            if k == 'spo2' and v <= 1.0:
                v *= 100                      # Shortcuts may send 0.97 instead of 97
            if k == 'wt' and v > 30:
                v -= DRY_WEIGHT_KG            # absolute kg -> change vs dry weight
            latest[k] = {'v': round(v, 1), 'ts': now, 'src': str(src)[:40]}
            got[k] = latest[k]['v']
        print(time.strftime('%H:%M:%S'), 'ingest', got or '(no recognised field)', flush=True)
        self._json(200 if got else 400, {'ok': bool(got), 'stored': got})

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/live':
            return self._json(200, {'ok': True, 'ip': lan_ip(), 'port': PORT, 'now': int(time.time() * 1000), 'data': latest})
        if u.path == '/ingest':
            return self._ingest(parse_qs(u.query))
        if u.path == '/':
            self.path = '/demo.html'
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != '/ingest':
            return self._json(404, {'ok': False})
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n).decode('utf-8', 'replace') if n else ''
        params = {}
        if raw.lstrip().startswith('{'):
            try:
                params = json.loads(raw)
            except ValueError:
                params = {}
        else:
            params = parse_qs(raw)
        if not isinstance(params, dict):
            params = {}
        return self._ingest(params)

    def end_headers(self):
        # the page must never be cached while you iterate on it
        # (self.path is unset when the server answers a malformed request, e.g. an https:// probe)
        if getattr(self, 'path', '').endswith(('.html', '.js', '.css', '.md')):
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    ip = lan_ip()
    print('Riati watch bridge')
    print(f'  demo page : http://{ip}:{PORT}/demo.html   (open this on the Mac or on the iPhone)')
    print(f'  ingest    : http://{ip}:{PORT}/ingest?hr=72&spo2=96')
    print('  Ctrl+C to stop', flush=True)
    ThreadingHTTPServer(('0.0.0.0', PORT), Bridge).serve_forever()
