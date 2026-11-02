import unittest
import json
import shutil
import subprocess
from pathlib import Path

ROOM=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")
class AgentPanelTests(unittest.TestCase):
    def test_panel_fetches_published_diagnostics(self):
        self.assertIn('id="v227-agent-panel"',ROOM)
        self.assertIn('fetch("./market_diagnostics.json"',ROOM)
        self.assertIn('refresh.addEventListener("click",load)',ROOM)
    def test_fail_closed_on_stale_unsafe_or_unexpected_agent_status(self):
        for marker in ('d.orders_enabled!==false','d.ai_agents_running!==false',
                       'd.trade_signals_available!==false','age>8*3600000',
                       '"INSUFFICIENT_HISTORY"','"NO_TRADE_AUTHORIZATION"',
                       'record.status!==expectedStatus'):
            self.assertIn(marker,ROOM)
    def test_honest_non_ai_disclaimer(self):
        self.assertIn("실제 AI 실행/거래 신호 아님",ROOM)
    @unittest.skipUnless(shutil.which("node"), "Node.js required for browser-script lifecycle test")
    def test_agent_status_expires_and_refreshes_without_background_requests(self):
        script=ROOM.split("/* V227: transparent read-only diagnostic statuses, never AI execution. */",1)[1].split("</script>",1)[0]
        harness=r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const script=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{
 const start=Date.UTC(2026,10,2);let now=start,requests=0,fail=false;
 const timers=[],events={},elements={};
 for(const id of ['v227-status','v227-rows','v227-refresh'])elements[id]={children:[],replaceChildren(...x){this.children=x},addEventListener(name,fn){this[name]=fn}};
 const data={version:'V224.0',research_only:true,orders_enabled:false,realtime:false,ai_agents_running:false,trade_signals_available:false,captured_at_utc:new Date(start-3600000).toISOString(),ATLAS:{status:'DATA_PRESENT',note:'data'},QUANT:{status:'INSUFFICIENT_HISTORY',note:'history'},GUARDIAN:{status:'NO_TRADE_AUTHORIZATION',note:'denied'}};
 const context={Date:class extends Date{static now(){return now}},document:{hidden:false,getElementById:id=>elements[id],createElement:()=>({}),addEventListener:(name,fn)=>{events[name]=fn}},fetch:async()=>{requests++;return {ok:!fail,text:async()=>JSON.stringify(data)}},setInterval:fn=>timers.push(fn)};
 vm.runInNewContext(script,context);await new Promise(setImmediate);
 assert.equal(elements['v227-rows'].children.length,3);
 assert.ok(timers.length,'Missing agent-status expiry timer');
 now=start+7*3600000;timers.forEach(fn=>fn());
 assert.equal(elements['v227-rows'].children.length,3);
 now++;timers.forEach(fn=>fn());
 assert.equal(elements['v227-rows'].children.length,0);
 assert.match(elements['v227-status'].textContent,/만료/);
 assert.equal(requests,1);
 now=start;await elements['v227-refresh'].click();
 assert.equal(elements['v227-rows'].children.length,3);
 now=start-2*3600000;assert.ok(events.visibilitychange);events.visibilitychange();
 assert.equal(elements['v227-rows'].children.length,0);
 now=start;await elements['v227-refresh'].click();
 fail=true;await elements['v227-refresh'].click();
 assert.equal(elements['v227-rows'].children.length,0);
 assert.match(elements['v227-status'].textContent,/미연결/);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result=subprocess.run([shutil.which("node"),"-e",harness],input=json.dumps(script),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=="__main__":unittest.main()
