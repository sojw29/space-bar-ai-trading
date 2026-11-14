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
const element=()=>({attrs:{},events:{},textContent:'',setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this.events[k]=v}});
const status=element(),detail=element(),button=element(),timers=[],events={};
const elements={'meeting-progress-status':status,'meeting-progress-detail':detail,'meeting-progress-refresh':button};
const document={hidden:false,getElementById:id=>elements[id],addEventListener:(k,v)=>events[k]=v};
let now=Date.now(),code=200,count=0,hold=null;
const snapshot={version:'MEETING_WORKFLOW_STATUS_1',event:'STAGE_STARTED',workflow_stage:'PREPARATION',status:'RUNNING',execution_id:'a'.repeat(32),updated_at_utc:new Date(now).toISOString()};
const view={version:'MEETING_WORKFLOW_STATUS_VIEW_1',snapshot,read_only:true,orders_enabled:false,process_liveness_verified:false};
class Clock extends Date{static now(){return now}}
const context={document,Date:Clock,AbortController,setTimeout,clearTimeout,setInterval:fn=>timers.push(fn),
 fetch:async(url,options)=>{assert.equal(url,'/api/v1/meeting/workflow-status');assert.equal(options.credentials,'omit');count++;if(hold)return await new Promise(resolve=>hold=resolve);return {ok:code===200,status:code,text:async()=>JSON.stringify(view)}}};
vm.runInNewContext(script,context);
const flush=()=>new Promise(setImmediate);
(async()=>{
 await flush();
 assert.equal(status.attrs['data-state'],'RUNNING');assert.match(status.textContent,/회의 입력 준비/);
 assert.match(detail.textContent,/실행 ID/);assert.equal(button.disabled,false);
 snapshot.status='READY_NO_MODEL_CALLS';snapshot.workflow_stage='SETUP';snapshot.event='WORKFLOW_FINISHED';
 await button.events.click();assert.match(status.textContent,/모델 호출 없음/);
 now+=300001;timers[0]();assert.equal(detail.textContent,'');assert.equal(status.attrs['data-state'],'unavailable');
 now=Date.now();snapshot.updated_at_utc=new Date(now).toISOString();
 code=404;await button.events.click();assert.match(status.textContent,/서버의 상태 파일 설정/);assert.equal(detail.textContent,'');
 code=200;view.orders_enabled=true;await button.events.click();assert.equal(status.attrs['data-state'],'unavailable');
 view.orders_enabled=false;await button.events.click();assert.equal(status.attrs['data-state'],'READY_NO_MODEL_CALLS');
 snapshot.status='COMPLETED';snapshot.workflow_stage='SETUP';await button.events.click();assert.equal(status.attrs['data-state'],'unavailable');
 snapshot.workflow_stage='COMPLETED';await button.events.click();assert.match(status.textContent,/회의 실행 완료 기록/);
 // Extended runtime progress shows only validated role/phase/count metadata.
 snapshot.version='MEETING_WORKFLOW_STATUS_2';snapshot.event='MODEL_PROGRESS';snapshot.status='RUNNING';snapshot.workflow_stage='INFERENCE';
 Object.assign(snapshot,{agent:'QUANT',phase:'PEER_REVIEW',attempted_calls:5,validated_responses:4});
 await button.events.click();assert.match(detail.textContent,/QUANT · 상호 검토/);assert.match(detail.textContent,/검증된 응답: 4\/7/);
 snapshot.validated_responses=1;await button.events.click();assert.equal(status.attrs['data-state'],'unavailable');assert.equal(detail.textContent,'');
 snapshot.validated_responses=4;snapshot.agent='COMMANDER';await button.events.click();assert.equal(status.attrs['data-state'],'unavailable');
 snapshot.agent='QUANT';await button.events.click();assert.equal(status.attrs['data-state'],'RUNNING');
 snapshot.version='MEETING_WORKFLOW_STATUS_1';snapshot.event='WORKFLOW_FINISHED';snapshot.status='COMPLETED';snapshot.workflow_stage='COMPLETED';
 for(const field of ['agent','phase','attempted_calls','validated_responses'])delete snapshot[field];
 document.hidden=true;const before=count;timers[1]();assert.equal(count,before);
 document.hidden=false;hold=true;const first=button.events.click();assert.equal(detail.textContent,'');
 await button.events.click();timers[1]();assert.equal(count,before+1);assert.equal(button.disabled,true);
 const release=hold;hold=null;release({ok:true,text:async()=>JSON.stringify(view)});await first;
 assert.equal(status.attrs['data-state'],'COMPLETED');assert.equal(button.disabled,false);
})().catch(error=>{console.error(error);process.exitCode=1});
"""
        result = subprocess.run([shutil.which('node'), '-e', harness], input=json.dumps(script),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
