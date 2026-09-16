import json
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from riati_server import RiatiServer, Store, digest

class Client:
    def __init__(self, base): self.base=base;self.csrf='';self.opener=build_opener(HTTPCookieProcessor(CookieJar()))
    def call(self,path,method='GET',body=None,headers=None):
        head={'Content-Type':'application/json','X-Riati-Request':'1','X-CSRF-Token':self.csrf}
        head.update(headers or {})
        req=Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=head,method=method)
        try:
            r=self.opener.open(req);raw=r.read();code=r.status
        except HTTPError as e:raw=e.read();code=e.code
        try:data=json.loads(raw)
        except ValueError:data=raw.decode(errors='replace')
        if isinstance(data,dict) and data.get('csrf'):self.csrf=data['csrf']
        return code,data

class Accounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=Path(__file__).resolve().parents[1]/'work'/'account-build';parent.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(dir=parent);cls.store=Store(cls.temp.name)
        cls.server=RiatiServer(('127.0.0.1',0),cls.store)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
        cls.patient=Client(cls.base);cls.other=Client(cls.base);cls.clinician=Client(cls.base);cls.outsider=Client(cls.base)
        invite=(Path(cls.temp.name)/'care-team-invitation.txt').read_text().strip()
        cls.p=cls.signup(cls.patient,'Patient One','patient@example.test')
        cls.p2=cls.signup(cls.other,'Patient Two','other@example.test')
        cls.c=cls.signup(cls.clinician,'Care Reviewer','reviewer@example.test',invite)
        with cls.store.db() as db:db.execute('INSERT INTO invitations(hash) VALUES(?)',(digest('second-invite'),))
        cls.c2=cls.signup(cls.outsider,'Unlinked Reviewer','unlinked@example.test','second-invite')
    @classmethod
    def signup(cls,client,name,email,invitation=''):
        status,data=client.call('/api/signup','POST',{'name':name,'email':email,'password':'test-only-long-password','consent':True,'invitation':invitation})
        if status!=201:raise AssertionError((status,data))
        return data['user']
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
    def pair(self):
        code,preview=self.patient.call('/api/share-preview','POST',{'code':self.c['care_code']});self.assertEqual(code,200)
        status,_=self.patient.call('/api/sharing','POST',{'code':self.c['care_code'],'clinician_id':preview['clinician']['id'],'consent':True});self.assertEqual(status,200)
    def test_01_authentication_and_boundaries(self):
        anonymous=Client(self.base)
        self.assertEqual(anonymous.call('/api/record')[0],401)
        self.assertEqual(self.patient.call('/api/patients')[0],403)
        self.assertEqual(self.patient.call('/api/record?patient_id='+self.p2['id'])[0],403)
        self.assertEqual(self.outsider.call('/api/record?patient_id='+self.p['id'])[0],403)
        self.assertEqual(self.patient.call('/api/device-tokens','POST',{'label':'x'}, {'X-CSRF-Token':'bad'})[0],403)
        self.assertEqual(self.patient.call('/api/checkins','POST',{'feeling':'well'},{'Origin':'https://untrusted.example'})[0],403)
        self.assertEqual(self.patient.call('/api/checkins','POST',{'feeling':'well'},{'X-Riati-Request':''})[0],403)
        for path in ['/.git/config','/.riati/riati.sqlite3','/README.md','/uploads/brief_ar.pdf','/portal/../riati_server.py']:
            self.assertEqual(anonymous.call(path)[0],404,path)
        self.assertEqual(anonymous.call('/ingest?hr=70')[0],410)
        self.assertEqual(anonymous.call('/live')[0],410)
        self.assertEqual(anonymous.call('/api/session',headers={'Host':'attacker.example'})[0],400)
    def test_02_share_and_immutable_explanations(self):
        self.pair()
        self.assertEqual(self.clinician.call('/api/record?patient_id='+self.p['id'])[0],200)
        self.assertEqual(self.clinician.call('/api/plans','POST',{'patient_id':self.p['id'],'keywords':['wheezing'],'confirmed':True})[0],200)
        self.assertEqual(self.patient.call('/api/checkins','POST',{'feeling':'wheezing','note':'test symptom'})[0],200)
        _,record=self.patient.call('/api/record');review=next(e for e in record['events'] if e['kind']=='review');snapshot=review['explanation']
        self.assertIn('v1',snapshot['rule']);self.assertIn('No treatment',snapshot['outcome'])
        self.assertEqual(self.clinician.call('/api/plans','POST',{'patient_id':self.p['id'],'keywords':['breathless'],'confirmed':True})[0],200)
        _,record=self.patient.call('/api/record');self.assertEqual(next(e for e in record['events'] if e['id']==review['id'])['explanation'],snapshot)
        self.assertEqual(self.clinician.call('/api/responses','POST',{'patient_id':self.p['id'],'note':'Your check-in has been reviewed.'})[0],200)
        _,record=self.patient.call('/api/record');self.assertTrue(any(e['kind']=='message' for e in record['events']))
        self.assertEqual(self.outsider.call('/api/responses','POST',{'patient_id':self.p['id'],'note':'not allowed'})[0],403)
        self.assertEqual(self.patient.call('/api/plans','POST',{'patient_id':self.p['id'],'keywords':['well'],'confirmed':True})[0],403)
    def test_03_device_scoping_timestamps_and_validation(self):
        status,key=self.patient.call('/api/device-tokens','POST',{'label':'Test iPhone'});self.assertEqual(status,200)
        anon=Client(self.base);headers={'Authorization':'Bearer '+key['token']}
        old=time.time()-3600
        payload={'metric':'hr','value':73,'measured_at':datetime.fromtimestamp(old,timezone.utc).isoformat(),'source':'Apple Health test'}
        self.assertEqual(anon.call('/api/readings','POST',payload)[0],401)
        status,result=anon.call('/api/readings','POST',payload,headers);self.assertEqual(status,200);self.assertEqual(result['stored'],1)
        self.assertEqual(anon.call('/api/readings','POST',payload,headers)[1]['duplicates'],1)
        _,record=self.patient.call('/api/record');self.assertEqual(record['latest']['hr']['value'],73);self.assertTrue(record['latest']['hr']['stale']);self.assertAlmostEqual(record['latest']['hr']['measured_at'],old,places=3)
        self.assertNotIn('spo2',record['latest']);self.assertNotIn('hr',self.other.call('/api/record')[1]['latest'])
        for bad in [{'value':float('nan')},{'value':True},{'value':999},{'metric':'sbp'},{'measured_at':'bad'},{'measured_at':'2026-01-01T00:00:00'}, {'patient_id':self.p2['id']},{'measured_at':datetime.fromtimestamp(time.time()+3600,timezone.utc).isoformat()}]:
            self.assertEqual(anon.call('/api/readings','POST',{**payload,**bad},headers)[0],400,bad)
        self.assertEqual(self.patient.call('/api/device-tokens/'+key['id'],'DELETE')[0],200)
        self.assertEqual(anon.call('/api/readings','POST',payload,headers)[0],401)
        with self.store.db() as db:
            self.assertNotEqual(db.execute('SELECT hash FROM devices WHERE id=?',(key['id'],)).fetchone()[0],key['token'])
            password=db.execute('SELECT password FROM users WHERE id=?',(self.p['id'],)).fetchone()[0];self.assertNotIn('test-only-long-password',password)
    def test_04_revocation_and_logout(self):
        self.pair();self.assertEqual(self.patient.call('/api/sharing/'+self.c['id'],'DELETE')[0],200)
        self.assertEqual(self.clinician.call('/api/record?patient_id='+self.p['id'])[0],403)
        self.assertEqual(self.clinician.call('/api/responses','POST',{'patient_id':self.p['id'],'note':'no longer permitted'})[0],403)
        self.assertEqual(self.clinician.call('/api/patients')[1]['patients'],[])
        self.assertEqual(self.patient.call('/api/record')[1]['plans'],[])
        fresh=Client(self.base);self.assertEqual(fresh.call('/api/login','POST',{'email':'patient@example.test','password':'wrong'})[0],401)
        self.assertEqual(fresh.call('/api/login','POST',{'email':'patient@example.test','password':'test-only-long-password'})[0],200)
        self.assertEqual(fresh.call('/api/logout','POST',{})[0],200);self.assertEqual(fresh.call('/api/session')[0],401)
    def test_05_delete_account_cascades(self):
        client=Client(self.base);user=self.signup(client,'Disposable','delete@example.test')
        _,key=client.call('/api/device-tokens','POST',{'label':'Delete me'})
        client.call('/api/checkins','POST',{'feeling':'well'})
        self.assertEqual(client.call('/api/account','DELETE',{'password':'wrong'})[0],403)
        self.assertEqual(client.call('/api/account','DELETE',{'password':'test-only-long-password'})[0],200)
        self.assertEqual(client.call('/api/session')[0],401)
        with self.store.db() as db:
            for table,column in [('users','id'),('sessions','user_id'),('devices','user_id'),('events','patient_id')]:self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table+' WHERE '+column+'=?',(user['id'],)).fetchone()[0],0)

if __name__=='__main__':unittest.main(verbosity=2)
