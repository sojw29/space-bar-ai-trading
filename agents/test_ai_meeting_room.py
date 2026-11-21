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
 for(const mode of ['fixture','live','missing','orders','stale','partial','invalid-final','guardian-review','missing-priority','citations','peer-citation','meeting-comparison','malformed','timer','foreground','rollback','text-only']){
  let now=Date.parse(input.report.generated_at_utc),requests=0,noServer=false;
  const data=structuredClone(input.report),events={},timers=[],elements={};
  data.version='AI_MEETING_TRANSCRIPT_VIEW_1';
  for(const id of ['ai-meeting-status','ai-meeting-rows','ai-meeting-refresh','ai-meeting-decision','ai-meeting-agent-filter','ai-meeting-linked','ai-meeting-close-linked','ai-meeting-prev-linked','ai-meeting-next-linked','ai-meeting-search','ai-meeting-agent-count','ai-meeting-search-original','ai-meeting-phase-filter','ai-meeting-opinions','ai-meeting-opinion-cards','ai-meeting-opinion-agreement','ai-meeting-issues','ai-meeting-issue-rows','ai-meeting-comparison','ai-meeting-comparison-result','ai-meeting-comparison-summary','ai-meeting-comparison-baseline','ai-meeting-comparison-import','ai-meeting-import-pair','ai-meeting-pair-slot-1','ai-meeting-pair-slot-2','ai-meeting-pair-info-1','ai-meeting-pair-info-2','ai-meeting-pair-remove-1','ai-meeting-pair-remove-2','ai-meeting-exit-file-pair','ai-meeting-comparison-import-status','ai-meeting-comparison-reset-filters','ai-meeting-return-comparison','ai-meeting-comparison-evidence','ai-meeting-comparison-filters','ai-meeting-comparison-agent','ai-meeting-comparison-search','ai-meeting-comparison-verdict','ai-meeting-comparison-summary-changes','ai-meeting-comparison-concern-changes','ai-meeting-comparison-phase','ai-meeting-comparison-toggle-changes','ai-meeting-comparison-change-count','ai-meeting-pin-comparison','ai-meeting-clear-comparison','ai-meeting-save-comparison','ai-meeting-save-comparison-json','ai-meeting-comparison-save-status'])elements[id]={children:[],disabled:false,addEventListener(name,fn){this[name]=fn},append(...x){this.children.push(...x)},replaceChildren(...x){this.children=x}};
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
  if(mode==='meeting-comparison'){
   data.transcript[3].concerns=['표본 부족'];
   data.transcript[4].concerns=['표본 부족'];
   data.transcript[6].concerns=['표본 부족','수수료 확인'];
  }
  if(mode==='malformed')data.transcript[0].summary=null;
  if(mode==='text-only')data.transcript[0].summary='<img src=x onerror=alert(1)>';
  const downloads=[];
  let savedBlob;
  const document={activeElement:null,body:{appendChild(){}},hidden:false,getElementById:id=>elements[id],addEventListener:(name,fn)=>{events[name]=fn},createElement:tag=>tag==='a'?{click(){downloads.push(this.download)},remove(){}}:({style:{},children:[],attrs:{},setAttribute(name,value){this.attrs[name]=value},addEventListener(name,fn){this[name]=fn},append(...x){this.children.push(...x)},focus(){this.focused=true},scrollIntoView(){this.scrolled=true},set innerHTML(_){throw Error('unsafe HTML sink')}})};
  vm.runInNewContext(input.script,{document,Blob,URL:{createObjectURL(blob){savedBlob=blob;return "blob:test"},revokeObjectURL(){}},setTimeout:()=>0,Date:class extends Date{static now(){return now}},setInterval:fn=>timers.push(fn),fetch:async()=>{requests++;return {ok:mode!=='missing'&&!noServer,text:async()=>JSON.stringify(data)}}});
  await new Promise(setImmediate);
  if(['missing','orders','stale','partial','invalid-final','malformed'].includes(mode)){
   assert.equal(elements['ai-meeting-rows'].children.length,0,mode);
   assert.match(elements['ai-meeting-status'].textContent,/미연결/);continue;
  }
  assert.equal(elements['ai-meeting-rows'].children.length,7,mode);
  assert.match(elements['ai-meeting-status'].textContent,mode==='live'?/모델 API 실행 완료 기록/:/실제 AI 실행 아님/);
  if(mode==='guardian-review')assert.match(elements['ai-meeting-decision'].textContent,/판정 규칙 근거 위치: \[M06\] GUARDIAN/);
  if(mode==='missing-priority'){
   const missing=elements['ai-meeting-issue-rows'].children.at(-1);
   assert.equal(missing.textContent,'자료 부족으로 표시된 발언');
   assert.equal(missing.children[0].textContent,'[M07] COMMANDER · 최종 결론');
   const decision=elements['ai-meeting-decision'].textContent;
   assert.match(decision,/판정 규칙 근거 위치: \[M07\] COMMANDER · 자료 부족/);
   assert.doesNotMatch(decision,/\[M06\] GUARDIAN · 추가 검토/);
   const filter=elements['ai-meeting-agent-filter'];
   filter.value='ATLAS';filter.change();
   const phase=elements['ai-meeting-phase-filter'];
   phase.value='CONCLUSION';phase.change();
   const search=elements['ai-meeting-search'];
   search.value='m07';search.input();
   const target=elements['ai-meeting-rows'].children[6];
   assert.equal(target.hidden,true);
   const button=elements['ai-meeting-decision'].children[0].children[0];
   assert.equal(button.textContent,'[M07] 발언 보기');
   button.onclick();
   assert.equal(target.hidden,false);
   assert.equal(target.focused,true);
   assert.equal(phase.value,'CONCLUSION');
   assert.equal(search.value,'m07');
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
   const initialJump=linked.children.at(-1).children[0];
   assert.equal(initialJump.textContent,'[M02] 초기 분석으로 이동');
   phase.value='PEER_REVIEW';phase.change();
   assert.equal(rows[1].hidden,true);
   initialJump.onclick();
   assert.match(linked.textContent,/^선택 발언 \[M02\] QUANT/);
   assert.equal(rows[1].hidden,false);
   assert.equal(rows[1].focused,true);
   rows[1].click();
   assert.match(linked.textContent,/이 분석을 인용한 상호 검토 \(1건\)\n\[M04\] ATLAS/);
   const reviewJump=linked.children.at(-1).children[0];
   assert.equal(reviewJump.textContent,'[M04] 상호 검토로 이동');
   phase.value='ANALYSIS';phase.change();
   assert.equal(review.hidden,true);
   reviewJump.onclick();
   assert.match(linked.textContent,/^선택 발언 \[M04\] ATLAS/);
   assert.equal(review.attrs['aria-current'],'true');
   assert.ok(review.style.outline);
   assert.equal(rows[1].attrs['aria-current'],'false');
   assert.equal(rows[1].style.outline,'');
   assert.equal(review.hidden,false);
   assert.equal(review.focused,true);
   assert.equal(review.scrolled,true);
   const prev=elements['ai-meeting-prev-linked'],next=elements['ai-meeting-next-linked'];
   assert.equal(prev.hidden,false);
   phase.value='PEER_REVIEW';phase.change();
   assert.equal(prev.disabled,true);
   next.click();
   assert.match(linked.textContent,/^선택 발언 \[M05\] QUANT/);
   prev.click();
   assert.match(linked.textContent,/^선택 발언 \[M04\] ATLAS/);
   phase.value='ALL';phase.change();
   const close=elements['ai-meeting-close-linked'];
   assert.equal(close.hidden,false);
   review.focused=false;
   close.click();
   assert.equal(linked.hidden,true);
   assert.equal(close.hidden,true);
   assert.equal(review.attrs['aria-current'],'false');
   assert.equal(review.focused,true);
   review.click();
   let escapeHandled=false;
   const escape={key:'Escape',target:search,preventDefault(){escapeHandled=true}};
   events.keydown(escape);
   assert.equal(linked.hidden,false);
   assert.equal(escapeHandled,false);
   review.focused=false;
   events.keydown({...escape,target:review});
   assert.equal(linked.hidden,true);
   assert.equal(close.hidden,true);
   assert.equal(escapeHandled,true);
   assert.equal(review.focused,true);
   rows[0].click();
   assert.doesNotMatch(linked.textContent,/이 분석을 인용한 상호 검토/);
   phase.value='ANALYSIS';phase.change();
   assert.equal(linked.hidden,false);
   phase.value='PEER_REVIEW';phase.change();
   assert.equal(rows[0].hidden,true);
   assert.equal(linked.hidden,true);
   assert.equal(linked.textContent,'');
   assert.equal(rows[0].attrs['aria-current'],'false');
  }
  if(mode==='meeting-comparison'){
   const cards=elements['ai-meeting-opinion-cards'].children;
   assert.equal(cards.length,3);
   assert.match(cards[0].textContent,/ATLAS.*\n\[M01\].*\n\[M04\]/);
   cards[0].children[0].click();
   assert.match(elements['ai-meeting-linked'].textContent,/^선택 발언 \[M01\]/);
   assert.match(elements['ai-meeting-opinion-agreement'].textContent,/표본 부족 · ATLAS, QUANT/);
   const issue=elements['ai-meeting-issue-rows'].children[0];
   assert.deepEqual(Array.from(issue.children,button=>button.textContent),['[M04] ATLAS · 상호 검토','[M05] QUANT · 상호 검토','[M07] COMMANDER · 최종 결론']);
   issue.children[0].click();
   assert.match(elements['ai-meeting-linked'].textContent,/^선택 발언 \[M04\]/);
   const result=elements['ai-meeting-comparison-result'];
   const overview=elements['ai-meeting-comparison-summary'];
   const evidence=elements['ai-meeting-comparison-evidence'];
   assert.equal(overview.hidden,true);
   assert.equal(evidence.hidden,true);
   const earlier=structuredClone(data);
   const save=elements['ai-meeting-save-comparison'];
   const saveJson=elements['ai-meeting-save-comparison-json'];
   assert.equal(save.disabled,true);
   assert.equal(saveJson.disabled,true);
   elements['ai-meeting-pin-comparison'].click();
   assert.match(result.textContent,/비교 기준 지정됨/);
   const baselineLabel=elements['ai-meeting-comparison-baseline'];
   assert.match(baselineLabel.textContent,/고정한 비교 기준/);
   now+=60000;
   data.generated_at_utc=new Date(now).toISOString();
   data.source_generated_at_utc=new Date(now-60000).toISOString();
   data.started_at_utc=new Date(now).toISOString();
   data.transcript[1].verdict='REVIEW_NEEDED';
   data.transcript[1].summary='거래량 자료 추가 확인';
   data.transcript[3].verdict='REVIEW_NEEDED';
   data.transcript[6].verdict=data.final_verdict='REVIEW_NEEDED';
   data.transcript[6].concerns=['거래량 확인 필요','수수료 확인'];
   await elements['ai-meeting-refresh'].click();
   assert.match(result.textContent,/최종 판정: 관측 요약 → 추가 검토 필요/);
   assert.equal(overview.hidden,false);
   assert.match(overview.textContent,/초기 분석 변경 1건 · 상호 검토 변경 1건 · 새 최종 우려 1건/);
   assert.equal(evidence.hidden,false);
   const [analysisChange,peerChange,finalChange,concernSources]=evidence.children;
   const filterAgent=elements['ai-meeting-comparison-agent'];
   const filterPhase=elements['ai-meeting-comparison-phase'];
   const toggle=elements['ai-meeting-comparison-toggle-changes'];
   const count=elements['ai-meeting-comparison-change-count'];
   assert.match(count.textContent,/3 \/ 3건/);
   filterAgent.value='QUANT';filterAgent.change();
   assert.equal(analysisChange.hidden,false);
   assert.equal(peerChange.hidden,true);
   assert.equal(finalChange.hidden,true);
   assert.match(count.textContent,/1 \/ 3건/);
   filterPhase.value='PEER_REVIEW';filterPhase.change();
   assert.equal(toggle.disabled,true);
   assert.equal(concernSources.hidden,undefined);
   assert.match(count.textContent,/조건에 맞는 판정 변경 없음/);
   filterPhase.value='ANALYSIS';filterPhase.change();
   toggle.click();
   assert.equal(analysisChange.open,true);
   assert.equal(peerChange.open,false);
   toggle.click();
   assert.equal(analysisChange.open,false);
   const resetComparison=elements['ai-meeting-comparison-reset-filters'];
   assert.equal(resetComparison.disabled,false);
   resetComparison.click();
   assert.equal(filterAgent.value,'ALL');
   assert.equal(filterPhase.value,'ALL');
   assert.equal(resetComparison.disabled,true);
   assert.match(analysisChange.children[0].textContent,/QUANT · 초기 분석/);
   const [olderCard,newerCard]=analysisChange.children[1].children;
   assert.match(olderCard.children[0].textContent,/이전 \[M02\]/);
   assert.match(newerCard.children[0].textContent,/이후 \[M02\].*\n거래량 자료 추가 확인/);
   assert.equal(olderCard.children.length,1);
   assert.equal(newerCard.children[1].textContent,'[M02] 현재 회의에서 열기');
   newerCard.children[1].click();
   assert.match(elements['ai-meeting-linked'].textContent,/^선택 발언 \[M02\] QUANT/);
   const back=elements['ai-meeting-return-comparison'];
   assert.equal(back.hidden,false);
   const previousRequests=requests;
   document.activeElement=back;
   timers[0]();
   assert.equal(requests,previousRequests);
   back.click();
   document.activeElement=null;
   assert.equal(back.hidden,true);
   assert.equal(newerCard.children[1].focused,true);
   assert.equal(newerCard.children[1].scrolled,true);
   assert.equal(elements['ai-meeting-linked'].hidden,true);
   assert.equal(concernSources.children[0].textContent,'우려 사항이 기록된 원문');
   const [addedIssue,continuedIssue,oldIssue]=concernSources.children.slice(1);
   assert.match(addedIssue.children[0].textContent,/새로 기록된 우려 · 거래량 확인 필요/);
   assert.match(continuedIssue.children[0].textContent,/이어진 우려 · 수수료 확인/);
   assert.match(oldIssue.children[0].textContent,/이후 결론에 재언급되지 않은 우려 · 표본 부족/);
   assert.match(addedIssue.children[1].children[0].textContent,/이후 \[M07\]/);
   assert.match(continuedIssue.children[1].children[0].textContent,/이전 \[M07\]/);
   assert.match(result.textContent,/초기 분석 판정 변경: QUANT 관측 요약 → 추가 검토 필요/);
   assert.match(result.textContent,/상호 검토 판정 변경: ATLAS 관측 요약 → 추가 검토 필요/);
   assert.match(result.textContent,/전체 발언 판정 분포: 관측 요약 7 → 4 · 추가 검토 필요 0 → 3/);
   assert.match(result.textContent,/모델 fixture · 원본 데이터 UTC/);
   assert.match(result.textContent,/새로 기록된 최종 우려: 거래량 확인 필요 \(이전 없음 · 이후 M07\)/);
   assert.match(result.textContent,/새로 기록된 최종 우려: 거래량 확인 필요/);
   assert.match(result.textContent,/재언급되지 않은 우려: 표본 부족/);
   assert.match(result.textContent,/두 결론에 모두 기록된 우려: 수수료 확인/);
   assert.equal(save.disabled,false);
   save.click();
   assert.deepEqual(downloads,['spacebar-meeting-comparison.txt']);
   assert.equal(await savedBlob.text(),result.textContent+'\n');
   assert.equal(saveJson.disabled,false);
   saveJson.click();
   assert.equal(downloads.at(-1),'spacebar-meeting-comparison.json');
   const report=JSON.parse(await savedBlob.text());
   assert.equal(report.version,'SPACEBAR_MEETING_COMPARISON_1');
   assert.equal(report.orders_enabled,false);
   assert.equal(report.earlier.verdict_counts.OBSERVATION_ONLY,7);
   assert.equal(report.later.source_generated_at_utc,data.source_generated_at_utc);
   assert.deepEqual(report.analysis_changes,[{agent:'QUANT',earlier:'OBSERVATION_ONLY',later:'REVIEW_NEEDED'}]);
   assert.deepEqual(report.final_concerns.not_repeated[0].earlier_statement_ids,['M04','M05','M07']);
   assert.deepEqual(report.final_concerns.not_repeated[0].later_statement_ids,['M04','M05']);
   analysisChange.open=true;
   concernSources.open=true;
   addedIssue.open=true;
   await elements['ai-meeting-refresh'].click();
   assert.equal(evidence.children[0].open,true);
   assert.equal(evidence.children[1].open,false);
   assert.equal(evidence.children[3].open,true);
   assert.equal(evidence.children[3].children[1].open,true);
   const chronological=result.textContent;
   const importer=elements['ai-meeting-comparison-import'];
   const importStatus=elements['ai-meeting-comparison-import-status'];
   const archive={version:'SPACEBAR_MEETING_ARCHIVE_1',archived_at_utc:earlier.generated_at_utc,
    research_only:true,orders_enabled:false,trade_authorization:'DENIED',process_liveness_verified:false,
    record:{...earlier,workflow_execution_id:earlier.workflow_execution_id??null,market_source:earlier.market_source??null,
     verdict_counts:{OBSERVATION_ONLY:7,REVIEW_NEEDED:0,INSUFFICIENT_DATA:0},
     transcript:earlier.transcript.map((statement,index)=>({id:'M0'+(index+1),...statement}))}};
   async function importFile(value,size=12000){
    importer.files=[{size,text:async()=>JSON.stringify(value)}];
    await importer.change();
   }
   await importFile(archive);
   assert.match(importStatus.textContent,/비교 기준으로 불러왔어요/);
   assert.match(baselineLabel.textContent,/저장한 회의록/);
   assert.match(result.textContent,/비교 기준 출처: 저장한 회의록 JSON/);
   saveJson.click();
   assert.equal(JSON.parse(await savedBlob.text()).baseline_origin,'ARCHIVE_FILE');
   const fromFile=result.textContent;
   for(const invalid of [
    {...archive,orders_enabled:true},
    {...archive,record:{...archive.record,market_source:'OKX_USDT_PERPETUAL_5M'}},
    {...archive,record:{...archive.record,final_verdict:'REVIEW_NEEDED'}},
    {...archive,record:{...archive.record,verdict_counts:{OBSERVATION_ONLY:8,REVIEW_NEEDED:0,INSUFFICIENT_DATA:0}}},
   ]){
    await importFile(invalid);
    assert.match(importStatus.textContent,/기존 비교 기준은 유지했어요/);
    assert.equal(result.textContent,fromFile);
   }
   await importFile(archive,262145);
   assert.match(importStatus.textContent,/256 KiB/);
   assert.equal(result.textContent,fromFile);
   const second={...archive,archived_at_utc:data.generated_at_utc,record:{
    ...archive.record,source_generated_at_utc:data.source_generated_at_utc,started_at_utc:data.started_at_utc,
    generated_at_utc:data.generated_at_utc,final_verdict:data.final_verdict,
    verdict_counts:{OBSERVATION_ONLY:4,REVIEW_NEEDED:3,INSUFFICIENT_DATA:0},
    transcript:data.transcript.map((statement,index)=>({id:'M0'+(index+1),...statement})),
   }};
   const pairInput=elements['ai-meeting-import-pair'];
   const exitPair=elements['ai-meeting-exit-file-pair'];
   const fileFor=(value,name='meeting.json')=>({name,size:12000,text:async()=>JSON.stringify(value)});
   const slot1=elements['ai-meeting-pair-slot-1'],slot2=elements['ai-meeting-pair-slot-2'];
   const info1=elements['ai-meeting-pair-info-1'],info2=elements['ai-meeting-pair-info-2'];
   slot1.files=[fileFor(second,'later.json')];
   await slot1.change();
   assert.match(info1.textContent,/later.json/);
   assert.equal(exitPair.hidden,true);
   slot2.files=[fileFor(archive,'earlier.json')];
   await slot2.change();
   assert.match(info2.textContent,/^이전 회의 · earlier[.]json/);
   assert.match(info1.textContent,/^이후 회의 · later[.]json/);
   assert.equal(exitPair.hidden,false);
   const chosenPair=result.textContent;
   slot2.files=[fileFor(second,'duplicate.json')];
   await slot2.change();
   assert.match(importStatus.textContent,/서로 다른 회의록/);
   assert.match(info2.textContent,/^이전 회의 · earlier[.]json/);
   assert.match(info1.textContent,/^이후 회의 · later[.]json/);
   assert.equal(result.textContent,chosenPair);
   slot2.files=[fileFor({...archive,record:{...archive.record,workflow_execution_id:'b'.repeat(32)}},'replacement.json')];
   await slot2.change();
   assert.match(info2.textContent,/replacement.json/);
   assert.notEqual(result.textContent,chosenPair);
   elements['ai-meeting-pair-remove-2'].click();
   assert.match(info1.textContent,/later.json/);
   assert.equal(info2.textContent,'선택한 파일 없음');
   assert.equal(result.textContent,fromFile);
   pairInput.files=[fileFor(second,'quick-later.json'),fileFor(archive,'quick-earlier.json')];
   await pairInput.change();
   assert.match(info1.textContent,/quick-later.json/);
   assert.match(info2.textContent,/quick-earlier.json/);
   assert.equal(exitPair.hidden,false);
   assert.match(result.textContent,/최종 판정: 관측 요약 → 추가 검토 필요/);
   assert.match(result.textContent,/비교 출처: 저장한 회의록 JSON 두 개/);
   assert.equal(evidence.children[0].children[1].children[1].children.length,1);
   saveJson.click();
   assert.equal(JSON.parse(await savedBlob.text()).baseline_origin,'ARCHIVE_PAIR');
   const fromPair=result.textContent;
   pairInput.files=[fileFor(second),fileFor(second)];
   await pairInput.change();
   assert.match(importStatus.textContent,/서로 다른 회의록/);
   assert.equal(result.textContent,fromPair);
   noServer=true;
   await elements['ai-meeting-refresh'].click();
   assert.match(elements['ai-meeting-status'].textContent,/미연결/);
   assert.equal(result.textContent,fromPair);
   saveJson.click();
   assert.equal(JSON.parse(await savedBlob.text()).baseline_origin,'ARCHIVE_PAIR');
   noServer=false;
   await elements['ai-meeting-refresh'].click();
   assert.equal(result.textContent,fromPair);
   exitPair.click();
   assert.equal(exitPair.hidden,true);
   assert.equal(result.textContent,fromFile);
   elements['ai-meeting-pin-comparison'].click();
   Object.assign(data,earlier);
   await elements['ai-meeting-refresh'].click();
   assert.equal(result.textContent,chronological);
   assert.equal(evidence.children[0].open,false);
   const [activeEarlier,baselineLater]=evidence.children[0].children[1].children;
   assert.equal(activeEarlier.children[1].textContent,'[M02] 현재 회의에서 열기');
   assert.equal(baselineLater.children.length,1);
   elements['ai-meeting-clear-comparison'].click();
   assert.equal(save.disabled,true);
   assert.equal(saveJson.disabled,true);
   assert.match(result.textContent,/비교 기준을 지정/);
   assert.equal(overview.hidden,true);
   assert.equal(evidence.hidden,true);
   assert.equal(evidence.children.length,0);
   second.record.transcript[0].summary='New summary only';
   second.record.transcript[2].concerns=['새 우려만'];
   pairInput.files=[fileFor(second),fileFor(archive)];
   await pairInput.change();
   const [summaryOnly]=evidence.children;
   const concernCard=evidence.children.find(node=>node.children[0].textContent.startsWith('GUARDIAN · 초기 분석'));
   const searchChange=elements['ai-meeting-comparison-search'];
   const verdictChange=elements['ai-meeting-comparison-verdict'];
   const summaryChanges=elements['ai-meeting-comparison-summary-changes'];
   const concernChanges=elements['ai-meeting-comparison-concern-changes'];
   assert.equal(summaryOnly.hidden,true);
   assert.equal(concernCard.hidden,true);
   summaryChanges.checked=true;summaryChanges.change();
   searchChange.value='new SUMMARY';searchChange.input();
   assert.equal(summaryOnly.hidden,false);
   assert.match(count.textContent,/발언 변경 1 \/ 4건/);
   verdictChange.value='REVIEW_NEEDED';verdictChange.change();
   assert.equal(summaryOnly.hidden,true);
   resetComparison.click();
   assert.equal(searchChange.value,'');
   assert.equal(verdictChange.value,'ALL');
   assert.equal(summaryChanges.checked,false);
   concernChanges.checked=true;concernChanges.change();
   assert.equal(concernCard.hidden,false);
   assert.equal(summaryOnly.hidden,true);
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
  assert.equal(requests,mode==='meeting-comparison'?6:['foreground','rollback'].includes(mode)?2:1,'Foreground must retry once; invalid snapshots stay cleared');
 }
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result = subprocess.run([shutil.which('node'), '-e', harness],
                                input=json.dumps({'script': script, 'report': report}),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
