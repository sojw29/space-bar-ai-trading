"""Execute the published interpretation/COMMANDER scripts against an advancing clock."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOM = (Path(__file__).resolve().parent.parent / 'web' / 'office_3d.html').read_text(encoding='utf-8')

class SummaryExpiryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for browser-script lifecycle test')
    def test_summary_panels_expire_on_timer_foreground_and_clock_rollback(self):
        panels = {}
        for version, section in (('V228.0', 'v228-interpretation-panel'), ('V229.0', 'v229-commander-panel')):
            panels[version] = ROOM.split('id="' + section + '"', 1)[1].split('<script>', 1)[1].split('</script>', 1)[0]
        harness = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const scripts=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{
 for(const [version,script] of Object.entries(scripts))for(const mode of ['timer','foreground','rollback']){
  const prefix=version==='V228.0'?'v228':'v229';
  const start=Date.UTC(2026,10,2);let now=start,requests=0;
  const timers=[],events={},elements={};
  for(const suffix of ['status','rows'])elements[prefix+'-'+suffix]={children:[],replaceChildren(...x){this.children=x}};
  const data={version,analysis_type:'DETERMINISTIC_INDICATOR_DESCRIPTION',report_type:'DETERMINISTIC_COMMANDER_RESEARCH_BRIEF',research_only:true,orders_enabled:false,realtime:false,ai_agents_running:false,trade_signals_available:false,backtest_verified:false,commander:{status:'COMPILED_NOT_AI'},source_generated_at_utc:new Date(start-3600000).toISOString(),markets:['BTCUSDT','ETHUSDT','SOLUSDT'].map(symbol=>({symbol,ATLAS:{sma_relationship:'SMA50_ABOVE_SMA200'},QUANT:{status:'DESCRIPTIVE_ONLY_NO_BACKTEST',volume_ratio_20:1.5},GUARDIAN:{status:'NO_TRADE_AUTHORIZATION',orders_enabled:false},trend_observation:'SMA50_ABOVE_SMA200',risk_status:'NO_TRADE_AUTHORIZATION',research_conclusion:'DESCRIPTIVE_ONLY',volume_ratio_20:1.5}))};
  const document={hidden:false,getElementById:id=>elements[id],createElement:()=>({}),addEventListener:(name,fn)=>{events[name]=fn}};
  vm.runInNewContext(script,{Date:class extends Date{static now(){return now}},document,fetch:async()=>{requests++;return {ok:true,text:async()=>JSON.stringify(data)}},setInterval:fn=>timers.push(fn)});
  await new Promise(setImmediate);
  assert.equal(elements[prefix+'-rows'].children.length,3,version+' initial render');
  assert.ok(timers.length,version+' missing expiry timer');
  assert.ok(events.visibilitychange,version+' missing foreground check');
  now=start+7*3600000;timers.forEach(fn=>fn());
  assert.equal(elements[prefix+'-rows'].children.length,3,version+' inclusive boundary');
  if(mode==='rollback')now=start-2*3600000;
  else now++;
  if(mode==='timer')timers.forEach(fn=>fn());
  else events.visibilitychange();
  assert.equal(elements[prefix+'-rows'].children.length,0,version+' '+mode);
  assert.match(elements[prefix+'-status'].textContent,/만료/);
  assert.equal(requests,1,'No hidden network refresh');
 }
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result = subprocess.run([shutil.which('node'), '-e', harness], input=json.dumps(panels), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == '__main__':
    unittest.main()
