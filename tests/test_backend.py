import io, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import app as service

def test_end_to_end():
    client=service.app.test_client()
    response=client.post('/api/evidence/register',data={'file':(io.BytesIO(b'original forensic evidence'),'sample.txt')},content_type='multipart/form-data')
    assert response.status_code==201
    eid=response.json['evidence_id']
    assert client.post('/api/evidence/verify/'+eid).json['verified'] is True
    assert client.get('/api/ledger/validate').json['valid'] is True
    assert client.get('/api/merkle/root').json['merkle_root']
    response=client.post('/api/custody/transfer',json={'evidence_id':eid,'new_custodian':'investigator_b','reason':'Lab analysis'})
    assert response.status_code==200
    with service.db() as c: stored=c.execute('SELECT stored_name FROM evidence WHERE id=?',(eid,)).fetchone()['stored_name']
    path=service.UPLOADS/stored
    try:
        path.write_bytes(b'modified forensic evidence')
        assert client.post('/api/evidence/verify/'+eid).json['verified'] is False
    finally: path.unlink(missing_ok=True)
    assert client.get('/api/ledger/validate').json['valid'] is True

def test_merkle():
    h1=service.digest(b'one');h2=service.digest(b'two')
    assert service.merkle_root([h1,h2])!=service.merkle_root([h1,service.digest(b'changed')])
    assert service.merkle_root([]) is None
