"""Run the published meeting viewer against valid, invalid and aging snapshots."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from ai_meeting_runtime import run_meeting
from test_ai_meeting_runtime import Fixture
from test_v240_provider_transport_preflight import request, NOW


class MeetingRoomTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for meeting viewer lifecycle')
    def test_actual_viewer_validation_labels_and_expiry(self):
        html = (Path(__file__).resolve().parent.parent/'web'/'office_3d.html').read_text(encoding='utf-8')
        script = html.split('id="ai-meeting-panel"', 1)[1].split('<script>', 1)[1].split('</script>', 1)[0]
        report = run_meeting(request(), Fixture(), clock=lambda: NOW)
        harness = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{
 for(const mode of ['fixture','live','missing','orders','stale','partial','invalid-final','malformed','timer','foreground','rollback','text-only']){
  let now=Date.parse(input.report.generated_at_utc),requests=0;
  const data=structuredClone(input.report),events={},timers=[],elements={};
  data.version='AI_MEETING_TRANSCRIPT_VIEW_1';
  for(const id of ['ai-meeting-status','ai-meeting-rows','ai-meeting-refresh'])elements[id]={children:[],disabled:false,addEventListener(){},replaceChildren(...x){this.children=x}};
  if(mode==='live'){data.execution_mode='LIVE_PROVIDER';data.model_inference_performed=true;data.model='test-model'}
  if(mode==='orders')data.orders_enabled=true;
  if(mode==='stale')now+=9*3600000;
  if(mode==='partial')data.transcript.pop();
  if(mode==='invalid-final')data.final_verdict='INSUFFICIENT_DATA';
  if(mode==='malformed')data.transcript[0].summary=null;
  if(mode==='text-only')data.transcript[0].summary='<img src=x onerror=alert(1)>';
  const document={hidden:false,getElementById:id=>elements[id],addEventListener:(name,fn)=>{events[name]=fn},createElement:()=>({style:{},set innerHTML(_){throw Error('unsafe HTML sink')}})};
  vm.runInNewContext(input.script,{document,Date:class extends Date{static now(){return now}},setInterval:fn=>timers.push(fn),fetch:async()=>{requests++;return {ok:mode!=='missing',text:async()=>JSON.stringify(data)}}});
  await new Promise(setImmediate);
  if(['missing','orders','stale','partial','invalid-final','malformed'].includes(mode)){
   assert.equal(elements['ai-meeting-rows'].children.length,0,mode);
   assert.match(elements['ai-meeting-status'].textContent,/미연결/);continue;
  }
  assert.equal(elements['ai-meeting-rows'].children.length,7,mode);
  assert.match(elements['ai-meeting-status'].textContent,mode==='live'?/모델 API 실행 완료 기록/:/실제 AI 실행 아님/);
  if(mode==='text-only')assert.ok(elements['ai-meeting-rows'].children[0].textContent.includes('<img'));
  if(['timer','foreground','rollback'].includes(mode)){
   now=Date.parse(data.source_generated_at_utc)+8*3600000;
   timers[0]();assert.equal(elements['ai-meeting-rows'].children.length,7,'inclusive expiry');
   now=mode==='rollback'?Date.parse(data.source_generated_at_utc)-1:now+1;
   if(mode==='timer')timers[0]();else events.visibilitychange();
   assert.equal(elements['ai-meeting-rows'].children.length,0,mode);
   if(mode==='timer')assert.match(elements['ai-meeting-status'].textContent,/만료/);
   else{
    await new Promise(setImmediate);
    assert.equal(elements['ai-meeting-rows'].children.length,0,mode);
    assert.match(elements['ai-meeting-status'].textContent,/미연결/);
    assert.equal(elements['ai-meeting-refresh'].disabled,false);
   }
  }
  assert.equal(requests,['foreground','rollback'].includes(mode)?2:1,'Foreground must retry once; invalid snapshots stay cleared');
 }
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result = subprocess.run([shutil.which('node'), '-e', harness],
                                input=json.dumps({'script': script, 'report': report}),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
