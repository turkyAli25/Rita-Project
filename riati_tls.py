"""Short-lived local TLS for same-Wi-Fi testing; trust remains an explicit device action."""
import html
import ipaddress
import plistlib
import ssl
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from riati_server import lan_ip, digest

def configure_tls(server, directory):
    folder=Path(directory)/'tls';folder.mkdir(exist_ok=True,mode=0o700)
    ip=lan_ip();ipaddress.ip_address(ip)
    def run(*args): subprocess.run(['openssl',*map(str,args)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    ca=folder/'riati-test-root.pem';key=folder/'riati-test-root.key'
    if not ca.exists():
        conf=folder/'root.cnf';conf.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ca\nprompt=no\n[dn]\nCN=Riati local pilot (30 days)\n[ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\n')
        run('req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','30','-keyout',key,'-out',ca,'-config',conf)
        key.chmod(0o600)
    cert=folder/'server.pem';skey=folder/'server.key';csr=folder/'server.csr';ext=folder/'server.cnf'
    ext.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:'+ip+',IP:127.0.0.1,DNS:localhost\n')
    run('req','-newkey','rsa:2048','-nodes','-sha256','-keyout',skey,'-out',csr,'-subj','/CN=Riati local pilot')
    run('x509','-req','-in',csr,'-CA',ca,'-CAkey',key,'-CAcreateserial','-out',cert,'-days','14','-sha256','-extfile',ext)
    skey.chmod(0o600)
    der=folder/'riati-test-root.cer';run('x509','-in',ca,'-outform','DER','-out',der)
    fingerprint=subprocess.check_output(['openssl','x509','-in',str(ca),'-noout','-fingerprint','-sha256'],text=True).strip()
    profile=plistlib.dumps({'PayloadContent':[{'PayloadCertificateFileName':'riati-test-root.cer','PayloadContent':der.read_bytes(),'PayloadDescription':'Trust the Riati server on your own Wi-Fi for this test. Remove the profile after testing.','PayloadDisplayName':'Riati local pilot certificate','PayloadIdentifier':'local.riati.pilot.certificate','PayloadType':'com.apple.security.root','PayloadUUID':str(uuid.uuid4()),'PayloadVersion':1}],'PayloadDescription':'One local test certificate. No device management, VPN, or other settings. Remove after the test.','PayloadDisplayName':'Riati local pilot','PayloadIdentifier':'local.riati.pilot','PayloadOrganization':'Riati local test','PayloadRemovalDisallowed':False,'PayloadType':'Configuration','PayloadUUID':str(uuid.uuid4()),'PayloadVersion':1})
    server.tls=True;server.origin='https://'+ip+':'+str(server.server_port)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(cert,skey)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    origin=server.origin
    class Setup(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/owner':
                if self.client_address[0]!='127.0.0.1' or self.headers.get('Host')!='127.0.0.1:'+str(server.server_port+1) or self.headers.get('Sec-Fetch-Site')=='cross-site':
                    self.send_error(403);return
                invitation_file=Path(directory)/'care-team-invitation.txt'
                invitation=invitation_file.read_text().strip() if invitation_file.exists() else ''
                with server.store.db() as db:
                    unused=bool(db.execute('SELECT 1 FROM invitations WHERE hash=? AND used=0',(digest(invitation),)).fetchone())
                invitation_html=('<p>Your one-use care-team invitation:</p><p style="font:18px monospace;overflow-wrap:anywhere;user-select:all;padding:16px;background:white;border:1px solid #E6DDE9">'+html.escape(invitation)+'</p>') if unused else '<p>Your care-team invitation has already been used. Sign in to your account.</p>'
                data=('<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Riati owner setup</title><body style="font:17px/1.6 system-ui;max-width:700px;margin:40px auto;padding:24px;background:#FAF7F3;color:#2E1834"><h1>Set up your Riati account</h1><p>This page is available only on this Mac.</p><ol><li><a href="/">Set up the local certificate</a> and verify its fingerprint.</li><li>Open Riati below and choose Create account.</li><li>Enter your own name, email and password.</li><li>Open “Have a care-team invitation?” and paste the invitation below.</li><li>After signing in, give your care-team sharing code to your friend. They create a patient account and approve sharing with your name.</li></ol>'+invitation_html+'<p><a href="'+html.escape(origin)+'/portal/">Open Riati</a></p><p>For your friend on this Wi-Fi: <a href="http://'+ip+':'+str(server.server_port+1)+'/">iPhone setup page</a>.</p><p>The pilot only records observations. Your professional credentials are not verified by this local app.</p></body></html>').encode();mime='text/html; charset=utf-8'
            elif self.path=='/riati.mobileconfig': data=profile;mime='application/x-apple-aspen-config'
            elif self.path=='/riati-test-root.cer':data=der.read_bytes();mime='application/pkix-cert'
            elif self.path=='/':
                data=('''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Riati Wi-Fi setup</title><body style="font:18px system-ui;max-width:680px;margin:50px auto;padding:24px;background:#FAF7F3;color:#2E1834"><h1>Connect to Riati on this Wi-Fi</h1><p>This page only supplies a local test certificate. Do not enter account details here.</p><ol><li>Check that the fingerprint below matches the one on the Mac.</li><li><a href="/riati.mobileconfig">Download the Riati test certificate profile</a>.</li><li>On iPhone: Settings → General → VPN &amp; Device Management → Riati local pilot → Install.</li><li>Settings → General → About → Certificate Trust Settings → enable trust for Riati local pilot.</li><li>Open the secure site below, then create your account.</li></ol><p><a href="'''+html.escape(origin)+'''/portal/">Open Riati securely</a></p><p>On Mac, import <a href="/riati-test-root.cer">the certificate</a> into Keychain Access and trust it for SSL only if its fingerprint matches. This is a test certificate, not a publicly trusted website certificate.</p><small style="overflow-wrap:anywhere">'''+html.escape(fingerprint)+'''</small><p>Remove the Riati profile and disable its trust after the pilot. The root certificate expires after 30 days.</p></body></html>''').encode();mime='text/html; charset=utf-8'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'");self.end_headers();self.wfile.write(data)
    setup=ThreadingHTTPServer(('0.0.0.0',server.server_port+1),Setup)
    threading.Thread(target=setup.serve_forever,daemon=True).start()
    print('Owner setup (this Mac only): http://127.0.0.1:'+str(server.server_port+1)+'/owner',flush=True)
    print('iPhone certificate setup: http://'+ip+':'+str(server.server_port+1)+'/',flush=True)
    print('Verify this certificate fingerprint on the iPhone: '+fingerprint,flush=True)

