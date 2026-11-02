"""Exercise local-history deletion against the actual asynchronous browser script."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path


class HistoryClearRaceTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for browser lifecycle regression')
    def test_clear_during_fetch_never_restores_deleted_history(self):
        room = (Path(__file__).resolve().parent.parent / 'web' / 'office_3d.html').read_text(encoding='utf-8')
        script = room.split('id="v230-history-panel"', 1)[1].split('<script>', 1)[1].split('</script>', 1)[0]
        harness = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const script=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{
 for(const mode of ['success','fetch-pending','body-pending','reject-after-clear']){
  const markets=['BTCUSDT','ETHUSDT','SOLUSDT'].map(symbol=>({symbol,trend:'SMA_EQUAL',ratio:1}));
  const old={timestamp:new Date(Date.now()-7200000).toISOString(),markets};
  let stored=JSON.stringify([old]),writes=0,resolveFetch,resolveBody,rejectFetch;
  const elements={};
  for(const suffix of ['status','rows','clear'])elements['v230-'+suffix]={children:[],textContent:'',replaceChildren(...x){this.children=x},append(x){this.children.push(x)},addEventListener(name,fn){this[name]=fn}};
  const data={version:'V229.0',report_type:'DETERMINISTIC_COMMANDER_RESEARCH_BRIEF',research_only:true,orders_enabled:false,realtime:false,ai_agents_running:false,trade_signals_available:false,backtest_verified:false,commander:{status:'COMPILED_NOT_AI'},source_generated_at_utc:new Date(Date.now()-3600000).toISOString(),markets:markets.map(m=>({symbol:m.symbol,trend_observation:m.trend,volume_ratio_20:m.ratio,risk_status:'NO_TRADE_AUTHORIZATION',research_conclusion:'DESCRIPTIVE_ONLY'}))};
  const response={ok:true,text:()=>new Promise(resolve=>{resolveBody=resolve})};
  const pending=new Promise((resolve,reject)=>{resolveFetch=resolve;rejectFetch=reject});
  const document={getElementById:id=>elements[id],createElement:()=>({})};
  const localStorage={getItem:()=>stored,setItem:(key,value)=>{writes++;stored=value},removeItem:()=>{stored=null}};
  vm.runInNewContext(script,{document,localStorage,Date,fetch:()=>pending});
  assert.equal(elements['v230-rows'].children.length,1,'existing history renders');
  if(mode==='body-pending'||mode==='success'){resolveFetch(response);await new Promise(setImmediate)}
  if(mode==='success'){
   resolveBody(JSON.stringify(data));await new Promise(setImmediate);
   assert.equal(writes,1);assert.equal(JSON.parse(stored).length,2);
   assert.equal(elements['v230-rows'].children.length,2);continue;
  }
  elements['v230-clear'].click();
  assert.equal(stored,null);assert.equal(elements['v230-rows'].children.length,0);
  if(mode==='reject-after-clear')rejectFetch(Error('late failure'));
  else {
   if(mode==='fetch-pending'){resolveFetch(response);await new Promise(setImmediate)}
   if(resolveBody)resolveBody(JSON.stringify(data));
  }
  await new Promise(setImmediate);
  assert.equal(writes,0,mode+': pending response must not write after deletion');
  assert.equal(stored,null,mode+': storage remains deleted');
  assert.equal(elements['v230-rows'].children.length,0,mode+': deleted rows remain empty');
  assert.equal(elements['v230-status'].textContent,'로컬 기록 삭제됨',mode+': late completion must not overwrite deletion status');
 }
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result = subprocess.run([shutil.which('node'), '-e', harness], input=json.dumps(script), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
