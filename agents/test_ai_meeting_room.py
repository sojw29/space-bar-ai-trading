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
        script = '/* Completed'+html.split('/* Completed model meeting snapshots only.', 1)[1].split('</script>', 1)[0]
        report = run_meeting(request(), Fixture(), clock=lambda: NOW)
        harness = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{
 for(const mode of ['fixture','live','missing','orders','stale','partial','invalid-final','guardian-review','missing-priority','citations','peer-citation','malformed','timer','foreground','rollback','text-only']){
  let now=Date.parse(input.report.generated_at_utc),requests=0;
  const data=structuredClone(input.report),events={},timers=[],elements={};
  data.version='AI_MEETING_TRANSCRIPT_VIEW_1';
  for(const id of ['ai-meeting-status','ai-meeting-rows','ai-meeting-refresh','ai-meeting-decision','ai-meeting-agent-filter','ai-meeting-linked','ai-meeting-search','ai-meeting-agent-count','ai-meeting-search-original','ai-meeting-phase-filter'])elements[id]={children:[],disabled:false,addEventListener(name,fn){this[name]=fn},append(...x){this.children.push(...x)},replaceChildren(...x){this.children=x}};
  if(mode==='live'){data.execution_mode='LIVE_PROVIDER';data.model_inference_performed=true;data.model='test-model'}
  if(mode==='orders')data.orders_enabled=true;
  if(mode==='stale')now+=9*3600000;
  if(mode==='partial')data.transcript.pop();
  if(mode==='invalid-final')data.final_verdict='INSUFFICIENT_DATA';
  if(['guardian-review','missing-priority'].includes(mode)){
   data.transcript[5].verdict='REVIEW_NEEDED';
   data.final_verdict='REVIEW_NEEDED';
   if(mode==='missing-priority')data.transcript[6].verdict=data.final_verdict='INSUFFICIENT_DATA';
  }
  if(mode==='citations'){
   data.transcript[6].summary='분석 [M02], 검토 [M05]';
   data.transcript[6].concerns=['중복 인용 [M02]'];
  }
  if(mode==='peer-citation')data.transcript[3].summary='QUANT 분석 [M02] 인용';
  if(mode==='malformed')data.transcript[0].summary=null;
  if(mode==='text-only')data.transcript[0].summary='<img src=x onerror=alert(1)>';
  const document={hidden:false,getElementById:id=>elements[id],addEventListener:(name,fn)=>{events[name]=fn},createElement:()=>({style:{},children:[],addEventListener(name,fn){this[name]=fn},append(...x){this.children.push(...x)},focus(){this.focused=true},scrollIntoView(){this.scrolled=true},set innerHTML(_){throw Error('unsafe HTML sink')}})};
  vm.runInNewContext(input.script,{document,Date:class extends Date{static now(){return now}},setInterval:fn=>timers.push(fn),fetch:async()=>{requests++;return {ok:mode!=='missing',text:async()=>JSON.stringify(data)}}});
  await new Promise(setImmediate);
  if(['missing','orders','stale','partial','invalid-final','malformed'].includes(mode)){
   assert.equal(elements['ai-meeting-rows'].children.length,0,mode);
   assert.match(elements['ai-meeting-status'].textContent,/미연결/);continue;
  }
  assert.equal(elements['ai-meeting-rows'].children.length,7,mode);
  assert.match(elements['ai-meeting-status'].textContent,mode==='live'?/모델 API 실행 완료 기록/:/실제 AI 실행 아님/);
  if(mode==='guardian-review')assert.match(elements['ai-meeting-decision'].textContent,/판정 규칙 근거 위치: \[M06\] GUARDIAN/);
  if(mode==='missing-priority'){
   const decision=elements['ai-meeting-decision'].textContent;
   assert.match(decision,/판정 규칙 근거 위치: \[M07\] COMMANDER · 자료 부족/);
   assert.doesNotMatch(decision,/\[M06\] GUARDIAN · 추가 검토/);
   const filter=elements['ai-meeting-agent-filter'];
   filter.value='ATLAS';filter.change();
   const target=elements['ai-meeting-rows'].children[6];
   assert.equal(target.hidden,true);
   const button=elements['ai-meeting-decision'].children[0].children[0];
   assert.equal(button.textContent,'[M07] 발언 보기');
   button.onclick();
   assert.equal(target.hidden,false);
   assert.equal(target.focused,true);
   assert.equal(target.scrolled,true);
   const restore=elements['ai-meeting-decision'].children[0].children[1];
   assert.equal(restore.hidden,false);
   restore.onclick();
   assert.equal(filter.value,'ATLAS');
   assert.equal(target.hidden,true);
   assert.equal(restore.hidden,true);
   assert.equal(button.focused,true);
  }
  if(mode==='citations'){
   const buttons=elements['ai-meeting-decision'].children[0].children;
   assert.deepEqual(buttons.map(button=>button.textContent),['[M02] 발언 보기','[M05] 발언 보기','이전 발언 보기 복원']);
   buttons[1].onclick();
   assert.equal(elements['ai-meeting-rows'].children[4].focused,true);
  }
  if(mode==='peer-citation'){
   const rows=elements['ai-meeting-rows'].children;
   const search=elements['ai-meeting-search'];
   for(const query of ['[M02]','m02']){
    search.value=query;search.input();
    assert.deepEqual(rows.flatMap((row,index)=>row.hidden?[]:[index]),[1,3]);
    assert.match(elements['ai-meeting-agent-count'].textContent,/원문 1개 · 인용 발언 1개/);
    assert.match(rows[1].textContent,/^원문 · \[M02\]/);
    assert.match(rows[3].textContent,/^인용 발언 · \[M04\]/);
   }
   const original=elements['ai-meeting-search-original'];
   assert.equal(original.hidden,false);
   const filter=elements['ai-meeting-agent-filter'];
   filter.value='ATLAS';filter.change();
   const phase=elements['ai-meeting-phase-filter'];
   phase.value='ANALYSIS';phase.change();
   assert.equal(rows[1].hidden,true);
   original.click();
   assert.equal(filter.value,'ALL');
   assert.equal(phase.value,'ANALYSIS');
   assert.equal(rows[1].hidden,false);
   assert.equal(rows[1].focused,true);
   assert.equal(search.value,'m02');
   search.value='';search.input();
   assert.equal(original.hidden,true);
   phase.value='ALL';phase.change();
   assert.match(rows[1].textContent,/^\[M02\]/);
   assert.match(rows[3].textContent,/^\[M04\]/);
   const review=rows[3];
   assert.match(review.textContent,/인용한 초기 분석: \[M02\] QUANT/);
   assert.doesNotMatch(review.textContent,/인용한 초기 분석:.*\[M01\]/);
   review.click();
   const linked=elements['ai-meeting-linked'];
   assert.equal(linked.hidden,false);
   assert.match(linked.textContent,/상호 검토에서 인용한 초기 분석 \(1건\)\n\[M02\] QUANT/);
   assert.match(linked.textContent,/그 외 검토에 제공된 발언 \(2건\)\n\[M01\] ATLAS/);
  }
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
