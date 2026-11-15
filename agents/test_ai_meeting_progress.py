"""Run the actual progress panel script with persisted workflow status snapshots."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest


class ProgressPanelTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_render_expire_failure_and_recovery(self):
        html = (Path(__file__).resolve().parent.parent/'web'/'office_3d.html').read_text()
        script = '/* Read-only persisted workflow progress. */' + html.split('/* Read-only persisted workflow progress. */', 1)[1].split('</script>', 1)[0]
        harness = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const script=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const panelEvents=[];class ViewEvent{constructor(type,options){this.type=type;this.detail=options.detail}}
const element=()=>({attrs:{},events:{},style:{},dataset:{},children:[],hidden:false,value:0,textContent:'',replaceChildren(...children){this.children=children},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v,capture){this.events[k]=v;this.capture=capture}});
const status=element(),detail=element(),button=element(),steps=element(),countBar=element(),openRecord=element(),timers=[],events={},windowEvents={};
const elements={'meeting-progress-status':status,'meeting-progress-detail':detail,'meeting-progress-refresh':button,'meeting-progress-stages':steps,'meeting-progress-count':countBar,'meeting-progress-open-record':openRecord};
const document={dispatchEvent:event=>{panelEvents.push(event);return true},createElement:element,hidden:false,getElementById:id=>elements[id],addEventListener:(k,v)=>events[k]=v};
let now=Date.now(),code=200,count=0,hold=null,networkError=null,errorBodies=0;
const snapshot={version:'MEETING_WORKFLOW_STATUS_1',event:'STAGE_STARTED',workflow_stage:'PREPARATION',status:'RUNNING',execution_id:'a'.repeat(32),updated_at_utc:new Date(now).toISOString()};
const view={version:'MEETING_WORKFLOW_STATUS_VIEW_1',snapshot,read_only:true,orders_enabled:false,process_liveness_verified:false};
class Clock extends Date{static now(){return now}}
const context={document,window:{addEventListener:(name,fn)=>windowEvents[name]=fn},Date:Clock,AbortController,CustomEvent:ViewEvent,setTimeout,clearTimeout,setInterval:fn=>timers.push(fn),
 fetch:async(url,options)=>{assert.equal(url,'/api/v1/meeting/workflow-status');assert.equal(options.credentials,'omit');count++;if(networkError)throw networkError;if(hold)return await new Promise(resolve=>hold=resolve);return {ok:code===200,status:code,text:async()=>{if(code!==200){errorBodies++;return "private-server-detail";}return JSON.stringify(view)}}}};
vm.runInNewContext(script,context);
const flush=()=>new Promise(setImmediate);
(async()=>{
 await flush();
 assert.equal(status.attrs['data-state'],'RUNNING');assert.match(status.textContent,/회의 입력 준비/);
 assert.match(detail.textContent,/실행 ID/);assert.equal(button.disabled,false);
 assert.equal(steps.children.length,7);assert.equal(steps.children.filter(node=>node.attrs['aria-current']==='step').length,1);
 assert.equal(steps.children.find(node=>node.attrs['aria-current']==='step').attrs['data-stage'],'PREPARATION');assert.equal(countBar.hidden,true);assert.equal(openRecord.disabled,true);
 snapshot.status='READY_NO_MODEL_CALLS';snapshot.workflow_stage='SETUP';snapshot.event='WORKFLOW_FINISHED';
 await button.events.click();assert.match(status.textContent,/모델 호출 없음/);assert.equal(countBar.hidden,true);
 assert.equal(steps.children.find(node=>node.attrs['aria-current']==='step').attrs['data-stage'],'SETUP');
 now+=300001;timers[0]();assert.equal(detail.textContent,'');assert.equal(steps.hidden,true);assert.equal(openRecord.disabled,true);assert.equal(openRecord.dataset.executionId,undefined);assert.equal(steps.children.length,0);assert.equal(countBar.hidden,true);assert.equal(status.attrs['data-state'],'unavailable');
 now=Date.now();snapshot.updated_at_utc=new Date(now).toISOString();
 code=404;await button.events.click();assert.match(status.textContent,/서버의 상태 파일 설정/);assert.equal(detail.textContent,'');
 code=409;await button.events.click();assert.match(status.textContent,/선택한 실행과 다른 진행 기록/);assert.equal(detail.textContent,'');
 code=200;view.orders_enabled=true;await button.events.click();assert.equal(status.attrs['data-state'],'unavailable');
 view.orders_enabled=false;await button.events.click();assert.equal(status.attrs['data-state'],'READY_NO_MODEL_CALLS');
 snapshot.status='COMPLETED';snapshot.workflow_stage='SETUP';await button.events.click();assert.equal(status.attrs['data-state'],'unavailable');
 snapshot.workflow_stage='COMPLETED';await button.events.click();assert.match(status.textContent,/회의 실행 완료 기록/);
 assert.equal(openRecord.disabled,false);assert.equal(openRecord.dataset.executionId,snapshot.execution_id);
 // Failed reads clear completion metadata and never display an HTTP error body.
 for(const [http,message] of [[401,/접근 설정/],[403,/접근 설정/],[429,/조회 요청이 많습니다/],[502,/응답 지연/],[504,/응답 지연/],[503,/상태 파일/],[500,/서버 오류/]]){
  code=http;await button.events.click();assert.match(status.textContent,message);
  assert.equal(status.attrs['data-state'],'unavailable');assert.equal(openRecord.disabled,true);
  assert.equal(openRecord.dataset.executionId,undefined);assert.equal(detail.textContent,'');assert.equal(errorBodies,0);
  code=200;await button.events.click();assert.equal(openRecord.disabled,false);
 }
 networkError=new TypeError('private-network-detail');await button.events.click();assert.match(status.textContent,/네트워크 연결/);assert.ok(!status.textContent.includes('private'));
 networkError={name:'AbortError',message:'private-timeout-detail'};await button.events.click();assert.match(status.textContent,/시간 초과/);assert.ok(!status.textContent.includes('private'));
 networkError=null;await button.events.click();assert.equal(openRecord.disabled,false);
 // A suspended timer must not leave an expired completion action enabled.
 assert.equal(openRecord.capture,true,'expiry guard runs before the viewer click handler');
 const completedAt=now;
 now=completedAt+300000;openRecord.events.click();assert.equal(openRecord.disabled,false);
 now++;openRecord.events.click();assert.equal(openRecord.disabled,true);assert.equal(openRecord.dataset.executionId,undefined);
 assert.equal(status.attrs['data-state'],'unavailable');assert.equal(panelEvents.at(-1).detail.state,'UNAVAILABLE');
 now=completedAt;snapshot.updated_at_utc=new Date(now).toISOString();await button.events.click();
 now--;openRecord.events.click();assert.equal(openRecord.disabled,true,'clock rollback also clears completion action');
 now=completedAt;await button.events.click();assert.equal(openRecord.disabled,false,'fresh reload restores action');
 // Extended runtime progress shows only validated role/phase/count metadata.
 snapshot.version='MEETING_WORKFLOW_STATUS_2';snapshot.event='MODEL_PROGRESS';snapshot.status='RUNNING';snapshot.workflow_stage='INFERENCE';
 Object.assign(snapshot,{agent:'QUANT',phase:'PEER_REVIEW',attempted_calls:5,validated_responses:4});
 await button.events.click();assert.match(detail.textContent,/QUANT · 상호 검토/);assert.match(detail.textContent,/검증된 응답: 4\/7/);
 assert.equal(openRecord.disabled,true);assert.equal(openRecord.dataset.executionId,undefined);
 assert.equal(countBar.hidden,false);assert.equal(countBar.value,4);assert.match(countBar.attrs['aria-valuetext'],/4\/7/);
 assert.equal(steps.children.find(node=>node.attrs['aria-current']==='step').attrs['data-stage'],'INFERENCE');
 snapshot.validated_responses=1;await button.events.click();assert.equal(countBar.hidden,true);assert.equal(countBar.value,0);assert.equal(steps.hidden,true);assert.equal(status.attrs['data-state'],'unavailable');assert.equal(detail.textContent,'');
 snapshot.validated_responses=4;snapshot.agent='COMMANDER';await button.events.click();assert.equal(status.attrs['data-state'],'unavailable');
 snapshot.agent='QUANT';await button.events.click();assert.equal(status.attrs['data-state'],'RUNNING');
 snapshot.version='MEETING_WORKFLOW_STATUS_1';snapshot.event='WORKFLOW_FINISHED';snapshot.status='COMPLETED';snapshot.workflow_stage='COMPLETED';
 for(const field of ['agent','phase','attempted_calls','validated_responses'])delete snapshot[field];
 document.hidden=true;const before=count;timers[1]();assert.equal(count,before);
 document.hidden=false;hold=true;const first=button.events.click();assert.equal(detail.textContent,'');
 await button.events.click();timers[1]();assert.equal(count,before+1);assert.equal(button.disabled,true);
 const release=hold;hold=null;release({ok:true,text:async()=>JSON.stringify(view)});await first;
 assert.equal(status.attrs['data-state'],'COMPLETED');assert.equal(button.disabled,false);
 assert.equal(countBar.hidden,true);assert.equal(countBar.value,0);
 assert.equal(steps.children.find(node=>node.attrs['aria-current']==='step').attrs['data-stage'],'COMPLETED');
 // Safari restoration and reconnect refresh progress without waiting for polling.
 let prior=count;windowEvents.pageshow({persisted:false});assert.equal(count,prior);
 document.hidden=true;windowEvents.online();windowEvents.pageshow({persisted:true});assert.equal(count,prior);
 document.hidden=false;now+=300001;hold=true;
 windowEvents.pageshow({persisted:true});assert.equal(count,prior+1);assert.equal(openRecord.disabled,true);
 assert.equal(openRecord.dataset.executionId,undefined);assert.equal(status.attrs['data-state'],'loading');
 windowEvents.online();windowEvents.pageshow({persisted:true});assert.equal(count,prior+1,'resume events share the existing in-flight guard');
 snapshot.updated_at_utc=new Date(now).toISOString();
 const restore=hold;hold=null;restore({ok:true,text:async()=>JSON.stringify(view)});await flush();
 assert.equal(count,prior+2,'coalesced restore events trigger one follow-up request');
 assert.equal(status.attrs['data-state'],'COMPLETED');assert.equal(openRecord.disabled,false);
 code=503;windowEvents.online();await flush();assert.equal(status.attrs['data-state'],'unavailable');assert.equal(openRecord.disabled,true);
 code=200;prior=count;windowEvents.online();await flush();assert.equal(count,prior+1);assert.equal(status.attrs['data-state'],'COMPLETED');
 // Discard the obsolete response and its error when a reconnect is queued.
 prior=count;hold=true;const pending=button.events.click();windowEvents.online();windowEvents.online();
 const failure=hold;hold=null;failure({ok:false,status:503});await pending;await flush();
 assert.equal(count,prior+2);assert.equal(status.attrs['data-state'],'COMPLETED');
 // Do not replay a queued reconnect after the tab becomes hidden.
 prior=count;hold=true;const background=button.events.click();windowEvents.online();document.hidden=true;
 const stale=hold;hold=null;stale({ok:true,text:async()=>{throw Error('obsolete body must not publish')}});await background;
 assert.equal(count,prior+1);assert.equal(openRecord.disabled,true);assert.notEqual(status.attrs['data-state'],'COMPLETED');
 document.hidden=false;windowEvents.online();await flush();assert.equal(count,prior+2);assert.equal(status.attrs['data-state'],'COMPLETED');
 const emitted=panelEvents.filter(event=>event.type==='spacebar:workflow-view');assert.equal(emitted.at(-1).detail.state,'COMPLETED');assert.equal(emitted.at(-1).detail.execution_id,snapshot.execution_id);
 assert.ok(emitted.every(event=>Object.keys(event.detail).sort().join(',')==='execution_id,state'));
})().catch(error=>{console.error(error);process.exitCode=1});
"""
        result = subprocess.run([shutil.which('node'), '-e', harness], input=json.dumps(script),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
