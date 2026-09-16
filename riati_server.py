#!/usr/bin/env python3
"""Account-scoped Riati pilot. Python stdlib; no cloud service required."""
import argparse
import base64
import hashlib
import hmac
import ipaddress
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import ssl
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

ROOT = Path(__file__).resolve().parent
SESSION_AGE = 12 * 3600
METRICS = {'hr': (20, 250, 'bpm', 15*60), 'spo2': (40, 100, '%', 120*60), 'steps': (0, 100000, 'steps', 24*3600)}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,care_code TEXT UNIQUE,consent_at REAL NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT REFERENCES users ON DELETE CASCADE,csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS links(patient_id TEXT REFERENCES users ON DELETE CASCADE,clinician_id TEXT REFERENCES users ON DELETE CASCADE,created REAL NOT NULL,PRIMARY KEY(patient_id,clinician_id));
CREATE TABLE IF NOT EXISTS invitations(hash TEXT PRIMARY KEY,used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users ON DELETE CASCADE,label TEXT NOT NULL,hash TEXT UNIQUE NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,last_received REAL);
CREATE TABLE IF NOT EXISTS readings(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users ON DELETE CASCADE,device_id TEXT REFERENCES devices ON DELETE CASCADE,metric TEXT NOT NULL,value REAL NOT NULL,measured_at REAL NOT NULL,received_at REAL NOT NULL,source TEXT NOT NULL,UNIQUE(user_id,metric,measured_at,value,source));
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,patient_id TEXT REFERENCES users ON DELETE CASCADE,kind TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,created REAL NOT NULL,explanation TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,patient_id TEXT REFERENCES users ON DELETE CASCADE,clinician_id TEXT REFERENCES users ON DELETE CASCADE,version INTEGER NOT NULL,keywords TEXT NOT NULL,created REAL NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS readings_patient_time ON readings(user_id,measured_at);
CREATE INDEX IF NOT EXISTS events_patient_time ON events(patient_id,created);
'''

class APIError(Exception):
    def __init__(self, status, message): self.status, self.message = status, message

def digest(v): return hashlib.sha256(v.encode()).hexdigest()
def ident(): return secrets.token_hex(16)
def norm(v):
    v = re.sub('[ً-ْـ]', '', v.lower())
    return re.sub(r'\s+', ' ', v.translate(str.maketrans('أإآةى', 'اااهي'))).strip()

def password_hash(password, salt=None, algorithm=None):
    salt = salt or secrets.token_bytes(16)
    algorithm = algorithm or ('scrypt' if hasattr(hashlib, 'scrypt') else 'pbkdf2-sha256')
    if algorithm == 'scrypt':
        key = hashlib.scrypt(password.encode(), salt=salt, n=2**17, r=8, p=1, maxmem=256*1024*1024, dklen=32)
    elif algorithm == 'pbkdf2-sha256':
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000, dklen=32)
    else:
        raise ValueError('Unknown password algorithm')
    return algorithm + ':' + base64.b64encode(salt).decode() + ':' + base64.b64encode(key).decode()

def verify_password(password, stored):
    if not isinstance(password, str) or len(password) > 128: return False
    try:
        algorithm, salt, _ = stored.split(':')
        return hmac.compare_digest(password_hash(password, base64.b64decode(salt), algorithm), stored)
    except (ValueError, TypeError, AttributeError): return False

def text_value(data, key, limit=200, required=True):
    val = data.get(key, '')
    if not isinstance(val, str) or len(val) > limit: raise APIError(400, 'Invalid ' + key)
    val = val.strip()
    if required and not val: raise APIError(400, key + ' is required')
    return val

def lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('8.8.8.8', 80)); return sock.getsockname()[0]
    except OSError: return '127.0.0.1'
    finally: sock.close()

class Store:
    def __init__(self, directory):
        self.directory = Path(directory); self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.path = self.directory / 'riati.sqlite3'
        with self.db() as c: c.executescript(SCHEMA)
        os.chmod(self.path, 0o600)
        with self.db() as c:
            if not c.execute('SELECT 1 FROM users WHERE role="clinician"').fetchone() and not c.execute('SELECT 1 FROM invitations WHERE used=0').fetchone():
                token = secrets.token_urlsafe(24)
                c.execute('INSERT INTO invitations(hash) VALUES(?)', (digest(token),))
                p = self.directory / 'care-team-invitation.txt'; p.write_text(token+'\n'); os.chmod(p, 0o600)
        self.dummy_password = password_hash(secrets.token_urlsafe(24))
    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=15); c.row_factory = sqlite3.Row; c.execute('PRAGMA foreign_keys=ON')
        try:
            with c: yield c
        finally: c.close()
    def event(self, c, patient, kind, title, body, explanation):
        eid = ident()
        c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)', (eid, patient, kind, title, body, time.time(), json.dumps(explanation, ensure_ascii=False)))
        return eid

class RiatiServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, store, origin=None):
        super().__init__(address, Handler)
        self.store = store; self.tls = False
        self.origin = origin or 'http://127.0.0.1:' + str(self.server_port)
        self.allowed_hosts = {'localhost', '127.0.0.1', lan_ip()}
        self.limits = {}; self.limit_lock = threading.Lock()
    def throttle(self, key, maximum, window=60):
        now = time.time()
        with self.limit_lock:
            stamps = [x for x in self.limits.get(key, []) if now-x < window]
            if len(stamps) >= maximum: raise APIError(429, 'Too many attempts. Try again later.')
            self.limits[key] = stamps + [now]
            if len(self.limits)>10000: self.limits = {k:v for k,v in self.limits.items() if v and now-v[-1]<3600}

class Handler(BaseHTTPRequestHandler):
    server_version = 'Riati'
    def log_message(self, *args): pass  # Never log health payloads, keys, email addresses or URLs.
    def json(self, status, data, cookie=None):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body)))
        if cookie: self.send_header('Set-Cookie', cookie)
        self.end_headers(); self.wfile.write(body)
    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Permissions-Policy', 'camera=(), geolocation=()')
        if getattr(self, 'path', '').startswith(('/portal', '/api')):
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        super().end_headers()
    def cookie(self, token='', clear=False):
        return 'riati_session='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age='+('0' if clear else str(SESSION_AGE))+('; Secure' if self.server.tls else '')
    def read_body(self):
        if self.headers.get('Transfer-Encoding'): raise APIError(400, 'Unsupported transfer encoding')
        try: size = int(self.headers.get('Content-Length', '0'))
        except ValueError: raise APIError(400, 'Invalid request size')
        if not 0 < size <= 32768: raise APIError(413, 'Request must contain at most 32 KB')
        if self.headers.get_content_type() != 'application/json': raise APIError(415, 'Use JSON')
        try: body = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeDecodeError): raise APIError(400, 'Invalid JSON')
        if not isinstance(body, dict): raise APIError(400, 'Expected a JSON object')
        return body
    def check_host(self):
        host = urlparse('http://' + self.headers.get('Host','')).hostname
        if host not in self.server.allowed_hosts: raise APIError(400, 'Unknown host')
    def check_origin(self):
        origin = self.headers.get('Origin')
        expected = ('https' if self.server.tls else 'http')+'://'+self.headers.get('Host','')
        if origin and origin != expected: raise APIError(403, 'This request must come from Riati')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site': raise APIError(403, 'Cross-site request rejected')
        if self.headers.get('X-Riati-Request') != '1': raise APIError(403, 'Missing request header')
    def user(self, c, write=False):
        cookie = SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: raise APIError(401, 'Sign in to continue')
        token = cookie.get('riati_session')
        row = c.execute('SELECT u.*,s.csrf,s.hash AS session_hash FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.hash=? AND s.expires>?', (digest(token.value if token else ''),time.time())).fetchone()
        if not row: raise APIError(401, 'Sign in to continue')
        if write and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''), row['csrf']): raise APIError(403, 'Session check failed. Refresh and try again.')
        return row
    def public_user(self, u): return {k:u[k] for k in ('id','name','email','role','care_code')}
    def session(self, c, user):
        raw = secrets.token_urlsafe(32); csrf = secrets.token_urlsafe(24)
        c.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
        c.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(raw),user['id'],csrf,time.time()+SESSION_AGE))
        return {'user':self.public_user(user),'csrf':csrf}, self.cookie(raw)
    def patient(self, c, u, pid=None):
        if u['role']=='patient':
            if pid and pid!=u['id']: raise APIError(403, 'You can only access your own record')
            return u
        if not pid: raise APIError(400, 'Choose a patient')
        row = c.execute('SELECT u.* FROM users u JOIN links l ON u.id=l.patient_id WHERE u.id=? AND l.clinician_id=?', (pid,u['id'])).fetchone()
        if not row: raise APIError(403, 'This patient has not shared their record with you')
        return row
    def do_GET(self): self.dispatch('GET')
    def do_POST(self): self.dispatch('POST')
    def do_DELETE(self): self.dispatch('DELETE')
    def dispatch(self, method):
        try:
            self.check_host()
            path = urlparse(self.path).path
            if path.startswith('/api/'):
                result = self.api(method,path)
                if result is not None: self.json(200,result)
            elif path in ('/live','/ingest'):
                raise APIError(410, 'The shared bridge has been replaced. Sign in at /portal/ and create a private device connection.')
            elif method=='GET': self.static(path)
            else: raise APIError(404,'Not found')
        except APIError as e: self.json(e.status, {'error':e.message})
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception:
            self.json(500, {'error':'Could not complete the request. Please try again.'})
    def api(self, method, path):
        store = self.server.store
        if method=='POST' and path=='/api/readings': return self.ingest()
        if method in ('POST','DELETE'): self.check_origin()
        with store.db() as c:
            if path=='/api/signup' and method=='POST':
                self.server.throttle(('signup',self.client_address[0]),8,3600)
                d=self.read_body(); name=text_value(d,'name',80); email=text_value(d,'email',254).lower()
                password=d.get('password'); invitation=text_value(d,'invitation',100,False)
                if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise APIError(400,'Enter a valid email address')
                if not isinstance(password,str) or not 12<=len(password)<=128: raise APIError(400,'Use a password with 12–128 characters')
                if d.get('consent') is not True: raise APIError(400,'Consent is required for the local pilot')
                role='patient'
                if invitation:
                    invite=c.execute('SELECT * FROM invitations WHERE hash=? AND used=0',(digest(invitation),)).fetchone()
                    if not invite: raise APIError(400,'This care-team invitation is invalid or already used')
                    role='clinician'
                if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(): raise APIError(409,'Unable to create this account. Try signing in.')
                uid=ident(); hashed=password_hash(password)
                if invitation:
                    changed=c.execute('UPDATE invitations SET used=1 WHERE hash=? AND used=0',(digest(invitation),)).rowcount
                    if changed != 1: raise APIError(400,'This invitation has already been used')
                c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?,?)',(uid,name,email,hashed,role,secrets.token_hex(5).upper() if role=='clinician' else None,time.time(),time.time()))
                user=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
                body,cookie=self.session(c,user); c.commit(); self.json(201,body,cookie); return None
            if path=='/api/login' and method=='POST':
                self.server.throttle(('login',self.client_address[0]),12,300)
                d=self.read_body(); email=text_value(d,'email',254).lower(); password=d.get('password','')
                if not isinstance(password,str) or len(password)>128: raise APIError(400,'Invalid password')
                self.server.throttle(('account-login',digest(email)),15,900)
                user=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                valid=verify_password(password,user['password'] if user else store.dummy_password)
                if not user or not valid: raise APIError(401,'Email or password is incorrect')
                body,cookie=self.session(c,user); c.commit(); self.json(200,body,cookie); return None
            u=self.user(c,method!='GET')
            if method!='GET': self.server.throttle(('write',u['id']),90)
            if path=='/api/session' and method=='GET':
                return {'user':self.public_user(u),'csrf':u['csrf'],'origin':self.server.origin,'mode':'local-pilot'}
            if path=='/api/logout' and method=='POST':
                c.execute('DELETE FROM sessions WHERE hash=?',(u['session_hash'],)); c.commit(); self.json(200,{'ok':True},self.cookie(clear=True)); return None
            if path=='/api/patients' and method=='GET':
                if u['role']!='clinician': raise APIError(403,'Care-team account required')
                rows=c.execute('SELECT u.id,u.name,l.created FROM users u JOIN links l ON u.id=l.patient_id WHERE l.clinician_id=? ORDER BY u.name',(u['id'],)).fetchall()
                return {'patients':[dict(x) for x in rows]}
            if path=='/api/record' and method=='GET':
                pid=parse_qs(urlparse(self.path).query).get('patient_id',[None])[0]; p=self.patient(c,u,pid)
                readings=c.execute('SELECT metric,value,measured_at,received_at,source FROM readings WHERE user_id=? ORDER BY measured_at DESC,received_at DESC LIMIT 200',(p['id'],)).fetchall()
                latest={}
                for metric in METRICS:
                    r=c.execute('SELECT metric,value,measured_at,received_at,source FROM readings WHERE user_id=? AND metric=? ORDER BY measured_at DESC,received_at DESC LIMIT 1',(p['id'],metric)).fetchone()
                    if r: latest[metric]={**dict(r),'stale':time.time()-r['measured_at']>METRICS[metric][3]}
                events=[]
                for e in c.execute('SELECT * FROM events WHERE patient_id=? ORDER BY created DESC LIMIT 100',(p['id'],)):
                    events.append({**dict(e),'explanation':json.loads(e['explanation'])})
                plans=[{**dict(r),'keywords':json.loads(r['keywords'])} for r in c.execute('SELECT p.*,u.name AS author FROM plans p JOIN users u ON p.clinician_id=u.id JOIN links l ON l.patient_id=p.patient_id AND l.clinician_id=p.clinician_id WHERE p.patient_id=? AND p.active=1 ORDER BY p.created DESC',(p['id'],))]
                sharing=[dict(x) for x in c.execute('SELECT u.id,u.name,l.created FROM users u JOIN links l ON u.id=l.clinician_id WHERE l.patient_id=?',(p['id'],))]
                devices=[dict(x) for x in c.execute('SELECT id,label,created,expires,revoked,last_received FROM devices WHERE user_id=? ORDER BY created DESC',(p['id'],))] if u['role']=='patient' else []
                return {'patient':{'id':p['id'],'name':p['name']},'latest':latest,'history':[dict(x) for x in readings[:200]],'events':events,'plans':plans,'sharing':sharing,'devices':devices,'server_time':time.time()}
            if path=='/api/share-preview' and method=='POST':
                if u['role']!='patient': raise APIError(403,'Patient account required')
                d=self.read_body(); code=text_value(d,'code',30).replace(' ','').upper()
                row=c.execute('SELECT id,name FROM users WHERE care_code=? AND role="clinician"',(code,)).fetchone()
                if not row: raise APIError(404,'Care-team code not found')
                return {'clinician':dict(row)}
            if path=='/api/sharing' and method=='POST':
                if u['role']!='patient': raise APIError(403,'Patient account required')
                d=self.read_body(); code=text_value(d,'code',30).replace(' ','').upper()
                if d.get('consent') is not True: raise APIError(400,'Confirm permission to share your record')
                row=c.execute('SELECT id,name FROM users WHERE care_code=? AND role="clinician"',(code,)).fetchone()
                if not row: raise APIError(404,'Care-team code not found')
                if d.get('clinician_id')!=row['id']: raise APIError(400,'Preview the recipient before sharing')
                c.execute('INSERT OR IGNORE INTO links VALUES(?,?,?)',(u['id'],row['id'],time.time()))
                return {'ok':True}
            if path.startswith('/api/sharing/') and method=='DELETE':
                if u['role']!='patient': raise APIError(403,'Patient account required')
                cid=path.rsplit('/',1)[-1]
                c.execute('DELETE FROM links WHERE patient_id=? AND clinician_id=?',(u['id'],cid))
                c.execute('UPDATE plans SET active=0 WHERE patient_id=? AND clinician_id=?',(u['id'],cid))
                return {'ok':True}
            if path=='/api/checkins' and method=='POST':
                if u['role']!='patient': raise APIError(403,'Patient account required')
                d=self.read_body(); feeling=text_value(d,'feeling',40); note=text_value(d,'note',1000,False)
                if feeling not in ('well','breathless','wheezing','better'): raise APIError(400,'Choose how you feel')
                names={'well':'Feeling well','breathless':'More breathless','wheezing':'Wheezing','better':'Breathing feels easier'}
                body=names[feeling]+(' — '+note if note else '')
                store.event(c,u['id'],'checkin','Patient check-in',body,{'trigger':body,'rule':'Patient-submitted observation','checks':['Submitted from this patient’s signed-in account','Saved without clinical classification'],'outcome':'Available in the shared care record. No emergency service or external notification was contacted.'})
                plans=c.execute('SELECT p.*,u.name AS author FROM plans p JOIN users u ON p.clinician_id=u.id JOIN links l ON p.patient_id=l.patient_id AND p.clinician_id=l.clinician_id WHERE p.patient_id=? AND p.active=1',(u['id'],)).fetchall()
                equivalents={'well':'well بخير','breathless':'breathless ضيق نفس','wheezing':'wheezing صفير','better':'better تحسنت'}
                for plan in plans:
                    words=json.loads(plan['keywords']); hit=next((w for w in words if norm(w) in norm(equivalents[feeling]+' '+note)),None)
                    if hit:
                        store.event(c,u['id'],'review','Care-team review requested','Matched “'+hit+'”. Available for review in Riati.',{'trigger':body,'rule':'Observation plan v'+str(plan['version'])+' · keyword “'+hit+'”','author':plan['author'],'approved_at':plan['created'],'checks':['Plan was active at the time','Patient sharing permission was active','Action limited to an in-app review request'],'outcome':'Added to the care record. No treatment instruction was generated.','plan_id':plan['id']})
                return {'ok':True}
            if path=='/api/plans' and method=='POST':
                if u['role']!='clinician': raise APIError(403,'Care-team account required')
                d=self.read_body(); p=self.patient(c,u,text_value(d,'patient_id',64)); words=d.get('keywords')
                if not isinstance(words,list) or not 1<=len(words)<=20 or any(not isinstance(w,str) or not 2<=len(w.strip())<=50 for w in words): raise APIError(400,'Add 1–20 symptom words (2–50 characters each)')
                if d.get('confirmed') is not True: raise APIError(400,'Confirm the observation plan')
                version=c.execute('SELECT COALESCE(MAX(version),0)+1 FROM plans WHERE patient_id=? AND clinician_id=?',(p['id'],u['id'])).fetchone()[0]
                c.execute('UPDATE plans SET active=0 WHERE patient_id=? AND clinician_id=?',(p['id'],u['id']))
                planid=ident(); words=list(dict.fromkeys(w.strip() for w in words))
                c.execute('INSERT INTO plans VALUES(?,?,?,?,?,?,1)',(planid,p['id'],u['id'],version,json.dumps(words,ensure_ascii=False),time.time()))
                store.event(c,p['id'],'plan','Observation plan approved','Version '+str(version)+' · '+u['name'],{'trigger':'Care-team member approved an observation plan','rule':'Matching symptom words create an in-app review request','author':u['name'],'checks':['Care-team account','Active patient sharing permission','No medication or treatment automation'],'outcome':'Plan is active for future check-ins.','plan_id':planid})
                return {'ok':True,'version':version}
            if path=='/api/responses' and method=='POST':
                if u['role']!='clinician': raise APIError(403,'Care-team account required')
                d=self.read_body(); p=self.patient(c,u,text_value(d,'patient_id',64)); note=text_value(d,'note',1500)
                store.event(c,p['id'],'message','Care-team message',note,{'trigger':'Message written by '+u['name'],'rule':'Manual care-team response','author':u['name'],'checks':['Care-team account','Active patient sharing permission'],'outcome':'Visible in the patient’s Riati account. No SMS or email was sent.'})
                return {'ok':True}
            if path=='/api/device-tokens' and method=='POST':
                if u['role']!='patient': raise APIError(403,'Patient account required')
                d=self.read_body(); label=text_value(d,'label',60)
                if c.execute('SELECT COUNT(*) FROM devices WHERE user_id=? AND revoked=0 AND expires>?',(u['id'],time.time())).fetchone()[0]>=5: raise APIError(400,'Revoke an existing connection before adding another')
                raw=secrets.token_urlsafe(32); device=ident(); expiry=time.time()+30*86400
                c.execute('INSERT INTO devices VALUES(?,?,?,?,?,?,0,NULL)',(device,u['id'],label,digest(raw),time.time(),expiry))
                return {'id':device,'token':raw,'expires':expiry,'endpoint':self.server.origin+'/api/readings'}
            if path.startswith('/api/device-tokens/') and method=='DELETE':
                if u['role']!='patient': raise APIError(403,'Patient account required')
                c.execute('UPDATE devices SET revoked=1 WHERE id=? AND user_id=?',(path.rsplit('/',1)[-1],u['id']))
                return {'ok':True}
            if path=='/api/account' and method=='DELETE':
                d=self.read_body()
                if not verify_password(d.get('password',''),u['password']): raise APIError(403,'Password is incorrect')
                c.execute('DELETE FROM users WHERE id=?',(u['id'],)); c.commit(); self.json(200,{'ok':True},self.cookie(clear=True)); return None
            raise APIError(404,'Not found')
    def ingest(self):
        auth=self.headers.get('Authorization','')
        if not auth.startswith('Bearer ') or len(auth)>200: raise APIError(401,'A private device key is required')
        tokenhash=digest(auth[7:]); self.server.throttle(('ingest-ip',self.client_address[0]),180)
        with self.server.store.db() as c:
            device=c.execute('SELECT * FROM devices WHERE hash=? AND revoked=0 AND expires>?',(tokenhash,time.time())).fetchone()
            if not device: raise APIError(401,'Device key is invalid, revoked or expired')
            self.server.throttle(('device',device['id']),60)
            d=self.read_body()
            if 'patient_id' in d or 'user_id' in d: raise APIError(400,'Device keys already identify the account')
            entries=d.get('readings',[d])
            if not isinstance(entries,list) or not 1<=len(entries)<=50: raise APIError(400,'Send 1–50 readings')
            validated=[]; now=time.time()
            for item in entries:
                if not isinstance(item,dict): raise APIError(400,'Invalid reading')
                metric=item.get('metric'); val=item.get('value'); source=text_value(item,'source',80)
                if not isinstance(metric,str) or metric not in METRICS or isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val): raise APIError(400,'Invalid metric or numeric value')
                if metric=='spo2' and 0<val<=1: val*=100
                low,high,unit,_=METRICS[metric]
                if not low<=val<=high: raise APIError(400,'Value outside accepted device range')
                measured=text_value(item,'measured_at',50)
                try:
                    stamp=datetime.fromisoformat(measured.replace('Z','+00:00'))
                    if stamp.tzinfo is None: raise ValueError()
                    stamp=stamp.timestamp()
                except (ValueError,OverflowError): raise APIError(400,'measured_at must be an ISO date with a timezone')
                if not now-7*86400<=stamp<=now+120: raise APIError(400,'Measurement time must be within the last 7 days and not in the future')
                validated.append((metric,round(float(val),2),stamp,source))
            stored=0
            for metric,val,stamp,source in validated:
                stored+=c.execute('INSERT OR IGNORE INTO readings VALUES(?,?,?,?,?,?,?,?)',(ident(),device['user_id'],device['id'],metric,val,stamp,now,source)).rowcount
            c.execute('UPDATE devices SET last_received=? WHERE id=?',(now,device['id']))
            if stored:
                self.server.store.event(c,device['user_id'],'reading','Device readings received',str(stored)+' new reading(s)',{'trigger':'Upload from connection “'+device['label']+'”','rule':'Record permitted heart rate, oxygen saturation or step samples','checks':['Private device key valid','Key scoped to this patient','Original measurement timestamp retained','Duplicate readings ignored'],'outcome':'Stored as device-submitted observations. Source names are supplied by the sending device; no clinical interpretation was performed.'})
            return {'ok':True,'stored':stored,'duplicates':len(validated)-stored}
    def static(self,path):
        path=unquote(path)
        public={'/':'Riati.dc.html','/Riati.dc.html':'Riati.dc.html','/demo.html':'demo.html','/watch-sim.html':'watch-sim.html','/demo-previous.html':'demo-previous.html','/demo-previous.js':'demo-previous.js','/demo-previous.css':'demo-previous.css','/support.js':'support.js','/assets/vendor/react.production.min.js':'assets/vendor/react.production.min.js','/assets/vendor/react-dom.production.min.js':'assets/vendor/react-dom.production.min.js','/assets/logo.png':'assets/logo.png','/portal':'portal/index.html','/portal/':'portal/index.html','/portal/index.html':'portal/index.html','/portal/app.js':'portal/app.js','/portal/style.css':'portal/style.css','/demo-enhancements.js':'demo-enhancements.js','/demo-enhancements.css':'demo-enhancements.css'}
        if path not in public: raise APIError(404,'Not found')
        p=ROOT/public[path]
        if not p.is_file(): raise APIError(404,'Not found')
        body=p.read_bytes(); self.send_response(200); self.send_header('Content-Type',(mimetypes.guess_type(str(p))[0] or 'application/octet-stream')+('; charset=utf-8' if p.suffix in ('.html','.js','.css') else ''))
        self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('port',nargs='?',type=int,default=8734); parser.add_argument('--lan',action='store_true'); parser.add_argument('--data-dir',default=str(ROOT/'.riati')); args=parser.parse_args()
    store=Store(args.data_dir); host='0.0.0.0' if args.lan else '127.0.0.1'
    srv=RiatiServer((host,args.port),store)
    if args.lan:
        from riati_tls import configure_tls
        configure_tls(srv,store.directory)
    print('Riati pilot: '+srv.origin+'/portal/',flush=True)
    print('First care-team invitation is saved in '+str(store.directory/'care-team-invitation.txt'),flush=True)
    print('Keep this Mac awake while testing. Ctrl+C stops the server.',flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: srv.server_close()

if __name__=='__main__': main()
