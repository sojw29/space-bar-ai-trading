"""Actual summary script correlates validated metadata without new requests."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest


class SessionSummaryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_summary_requires_matching_completed_records_and_clears_invalid_metadata(self):
        html = (Path(__file__).resolve().parent.parent/'web'/'office_3d.html').read_text()
        script = html.split('/* Recorded progress and transcript correlation summary. */', 1)[1].split('</script>', 1)[0]
        harness = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const script=JSON.parse(require('node:fs').readFileSync(0,'utf8')),listeners={};
const node={textContent:'',attrs:{},setAttribute(k,v){this.attrs[k]=v},set innerHTML(_){throw Error('unsafe HTML')}};
const document={getElementById:()=>node,addEventListener:(name,fn)=>listeners[name]=fn};
vm.runInNewContext(script,{document,fetch:()=>{throw Error('no new requests')}});
const progress=(state,id='a'.repeat(32))=>listeners['spacebar:workflow-view']({detail:{state,execution_id:id}});
const record=(state,id=null,provenance=null)=>listeners['spacebar:transcript-view']({detail:{state,execution_id:id,provenance}});
assert.equal(node.attrs['data-state'],'UNAVAILABLE');
record('validated','a'.repeat(32),'OFFLINE_FIXTURE');
assert.equal(node.attrs['data-state'],'UNAVAILABLE','a transcript alone cannot establish current session linkage');
progress('READY_NO_MODEL_CALLS');assert.equal(node.attrs['data-state'],'READY_ONLY');assert.match(node.textContent,/모델 호출 없음/);
progress('RUNNING');assert.equal(node.attrs['data-state'],'IN_PROGRESS');
progress('COMPLETED');assert.equal(node.attrs['data-state'],'LINKED_FIXTURE');assert.match(node.textContent,/실제 AI 실행 아님/);
record('loading');assert.equal(node.attrs['data-state'],'RECORD_LOADING');
record('disconnected');assert.equal(node.attrs['data-state'],'RECORD_PENDING');
record('validated',null,'OFFLINE_FIXTURE');assert.equal(node.attrs['data-state'],'RECORD_ID_MISSING');
record('validated','b'.repeat(32),'OFFLINE_FIXTURE');assert.equal(node.attrs['data-state'],'MISMATCH');
record('validated','a'.repeat(32),'LIVE_PROVIDER');assert.equal(node.attrs['data-state'],'LINKED_PROVIDER');
progress('BLOCKED');assert.equal(node.attrs['data-state'],'BLOCKED');
progress('UNAVAILABLE',null);assert.equal(node.attrs['data-state'],'UNAVAILABLE');
progress('COMPLETED');assert.equal(node.attrs['data-state'],'LINKED_PROVIDER');
listeners['spacebar:transcript-view']({detail:{state:'validated',execution_id:'a'.repeat(32),provenance:'LIVE_PROVIDER',secret:'private'}});
assert.equal(node.attrs['data-state'],'RECORD_PENDING');assert.ok(!node.textContent.includes('private'));
listeners['spacebar:workflow-view']({detail:{state:'COMPLETED',execution_id:'invalid'}});
assert.equal(node.attrs['data-state'],'UNAVAILABLE');
progress('COMPLETED');record('validated','a'.repeat(32),'OFFLINE_FIXTURE');assert.equal(node.attrs['data-state'],'LINKED_FIXTURE');
"""
        result = subprocess.run([shutil.which('node'), '-e', harness], input=json.dumps(script),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
