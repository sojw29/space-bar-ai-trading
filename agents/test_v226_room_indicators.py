import unittest
import json
import shutil
import subprocess
from pathlib import Path

ROOM=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")

class RoomIndicatorTests(unittest.TestCase):
    def test_room_fetches_optional_public_indicators(self):
        self.assertIn('fetch("./ohlcv_indicators.json"',ROOM)
        self.assertIn('id="v226-indicator-panel"',ROOM)
        self.assertIn('refresh.addEventListener("click",load)',ROOM)
    def test_rejects_unsafe_or_stale_data(self):
        for marker in ('data.orders_enabled!==false','data.realtime!==false',
                       'data.ai_agents_running!==false','data.trade_signals_available!==false',
                       'age>8*3600000','matches.length!==1','rows.replaceChildren()'):
            self.assertIn(marker,ROOM)
    def test_not_real_ai(self):
        self.assertIn("실시간/AI 판단/매매 신호 아님",ROOM)
        self.assertNotIn("eval(",ROOM)
    @unittest.skipUnless(shutil.which("node"), "Node.js required for browser-script lifecycle test")
    def test_displayed_indicators_expire_without_network_refetch(self):
        script=ROOM.split("/* V226: independent read-only 3D room indicator panel. */",1)[1].split("</script>",1)[0]
        harness=r"""
const assert=require('node:assert/strict');
const vm=require('node:vm');
const script=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{
 for(const candleAge of [3600000,8.5*3600000]){
  const start=Date.UTC(2026,10,2,0);let now=start,requests=0;
  const timers=[],events={};
  const elements={};
  for(const id of ['v226-status','v226-rows','v226-refresh'])elements[id]={children:[],replaceChildren(...x){this.children=x},addEventListener(name,fn){this[name]=fn}};
  const data={version:'V225.0',research_only:true,orders_enabled:false,realtime:false,trade_signals_available:false,ai_agents_running:false,generated_at_utc:new Date(start-3600000).toISOString(),markets:['BTCUSDT','ETHUSDT','SOLUSDT'].map(symbol=>({symbol,close:100,sma50:100,sma200:90,volume20:10,volume_latest:10,trend_label:'SMA50_ABOVE_SMA200',last_completed_candle_utc:new Date(start-candleAge).toISOString()}))};
  const context={Date:class extends Date{static now(){return now}},document:{hidden:false,getElementById:id=>elements[id],createElement:()=>({}),addEventListener:(name,fn)=>{events[name]=fn}},fetch:async()=>{requests++;return {ok:true,text:async()=>JSON.stringify(data)}},setInterval:fn=>timers.push(fn)};
  vm.runInNewContext(script,context);await new Promise(setImmediate);
  assert.equal(elements['v226-rows'].children.length,3);
  assert.ok(timers.length,'Missing expiry timer');
  const limit=Math.min(start+7*3600000,start-candleAge+9*3600000);
  now=limit;timers.forEach(fn=>fn());
  assert.equal(elements['v226-rows'].children.length,3);
  now=limit+1;timers.forEach(fn=>fn());
  assert.equal(elements['v226-rows'].children.length,0);
  assert.match(elements['v226-status'].textContent,/만료/);
  assert.equal(requests,1,'Expiry must not silently fetch');
  now=start;await elements['v226-refresh'].click();
  assert.equal(elements['v226-rows'].children.length,3);
  now=start-2*3600000;
  assert.ok(events.visibilitychange,'Missing foreground expiry check');
  events.visibilitychange();
  assert.equal(elements['v226-rows'].children.length,0);
 }
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result=subprocess.run([shutil.which("node"),"-e",harness],input=json.dumps(script),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=="__main__":unittest.main()
