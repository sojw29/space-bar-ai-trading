"""Source selection, base-volume normalization and provenance through the actual chain."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlparse, parse_qs

from ohlcv_indicators_v225 import build, fetch_public, publish, SYMBOLS
from agent_indicator_interpretation_v228 import interpret
from commander_research_brief_v229 import summarize
from agent_research_runtime_v233 import build_research
from agent_handoff_audit_v234 import compile_handoff
from research_consistency_review_v235 import review
from model_adapter_contract_v236 import build_adapter_requests
from provider_transport_preflight_v240 import preflight
from ai_meeting_runtime import run_meeting
from ai_meeting_publication import validate_public_report
from ai_meeting_readiness import assess_readiness, render_summary
from market_source_provenance import with_market_source
from test_ai_meeting_runtime import Fixture


def okx_response(symbol):
    end = int(datetime.now(timezone.utc).timestamp()//300)*300000
    rows = []
    for i in range(220):
        price = 100+i/10
        rows.append([str(end-(220-i)*300000), str(price), str(price+1), str(price-1),
                     str(price), '9000', '50', '5000', '1'])
    rows.append([str(end), '100', '101', '99', '100', '999999', '999999', '999999', '0'])
    return {'code': '0', 'data': list(reversed(rows))}


def pipeline(snapshot):
    now = datetime.now(timezone.utc)
    brief = summarize(interpret(snapshot, now), now)
    bundle = build_adapter_requests(review(compile_handoff(build_research(brief, now), now), now), now)
    return brief, bundle


class MarketSourceTests(unittest.TestCase):
    def test_okx_uses_completed_swap_base_volume(self):
        result = build(okx_response, provider='okx')
        self.assertEqual(result['market_source'], 'OKX_USDT_PERPETUAL_5M')
        for market in result['markets']:
            self.assertEqual(market['volume_latest'], 50)
            self.assertEqual(market['volume20'], 50)
            self.assertLess(market['close'], 130)

    def test_fixed_official_url_has_explicit_swap_and_timeframe_without_auth(self):
        with patch('ohlcv_indicators_v225.urlopen') as opener:
            opener.return_value.__enter__.return_value.read.return_value = json.dumps(okx_response('BTCUSDT')).encode()
            fetch_public('BTCUSDT', 'okx')
            request = opener.call_args.args[0]
            parsed = urlparse(request.full_url)
            self.assertEqual(parsed.netloc, 'www.okx.com')
            self.assertEqual(parsed.path, '/api/v5/market/candles')
            self.assertEqual(parse_qs(parsed.query), {'instId':['BTC-USDT-SWAP'], 'bar':['5m'], 'limit':['220']})
            self.assertNotIn('Authorization', request.headers)
            self.assertEqual(opener.call_args.kwargs['timeout'], 15)

    def test_no_automatic_provider_fallback_on_403(self):
        with patch('ohlcv_indicators_v225.urlopen') as opener, tempfile.TemporaryDirectory() as directory:
            opener.side_effect = HTTPError('https://api.bybit.com', 403, 'Forbidden', {}, None)
            target = Path(directory)/'indicators.json'
            target.write_text('old snapshot')
            with self.assertRaises(HTTPError): publish(target, provider='bybit')
            self.assertEqual(opener.call_count, 1)
            self.assertEqual(urlparse(opener.call_args.args[0].full_url).netloc, 'api.bybit.com')
            self.assertFalse(target.exists())

    def test_rejects_invalid_source_rows_gaps_duplicates_and_insufficient_complete_data(self):
        mutations = [lambda d: d.update(code='error'),
                     lambda d: d['data'][1].__setitem__(8, 'unknown'),
                     lambda d: d['data'].pop(10),
                     lambda d: d['data'].append(deepcopy(d['data'][1])),
                     lambda d: d['data'][1].__setitem__(6, 'nan'),
                     lambda d: [row.__setitem__(8, '0') for row in d['data']]]
        for mutation in mutations:
            data = okx_response('BTCUSDT'); mutation(data)
            with self.assertRaises(ValueError): build(lambda s: data, provider='okx')
        with patch('ohlcv_indicators_v225.urlopen') as opener:
            opener.return_value.__enter__.return_value.read.return_value = b'x'*262145
            with self.assertRaises(ValueError): fetch_public('BTCUSDT', 'okx')

    def test_selected_source_survives_readiness_requests_model_context_and_publication(self):
        snapshot = build(okx_response, provider='okx')
        brief, bundle = pipeline(snapshot)
        expected = snapshot['market_source']
        self.assertEqual(brief['market_source'], expected)
        self.assertEqual(preflight(bundle, dry_run=True)['market_source'], expected)
        self.assertTrue(all(r['facts']['market_source']==expected for r in bundle['requests']))
        fixture = Fixture()
        report = run_meeting(bundle, fixture)
        self.assertEqual(report['market_source'], expected)
        self.assertTrue(all(context['facts']['market_source']==expected for _,_,context in fixture.calls))
        readiness = assess_readiness(brief)
        self.assertIn('OKX USDT 무기한', render_summary(readiness))
        # Only a synthetic unit-test record: no real inference and never published.
        report.update(execution_mode='LIVE_PROVIDER', model_inference_performed=True, model='test-model')
        validate_public_report(report, bundle=bundle)
        report['market_source'] = 'BYBIT_USDT_PERPETUAL_5M'
        with self.assertRaises(ValueError): validate_public_report(report, bundle=bundle)

    def test_source_mismatch_or_unknown_provider_fails_before_model_call(self):
        _, bundle = pipeline(build(okx_response, provider='okx'))
        for source in ('BYBIT_USDT_PERPETUAL_5M', 'unknown'):
            changed = deepcopy(bundle)
            changed['requests'][0]['facts']['market_source'] = source
            fixture = Fixture()
            with self.assertRaises(ValueError): run_meeting(changed, fixture)
            self.assertEqual(fixture.calls, [])
        with self.assertRaises(ValueError): with_market_source({'market_source':'unknown'}, {})
        with self.assertRaises(ValueError): build(provider='unknown')

    @unittest.skipUnless(shutil.which('node'), 'Node.js required for market-source viewer check')
    def test_actual_meeting_viewer_labels_okx_and_rejects_unknown_source(self):
        _, bundle = pipeline(build(okx_response, provider='okx'))
        report = run_meeting(bundle, Fixture())
        room = (Path(__file__).resolve().parent.parent/'web/office_3d.html').read_text()
        script = room.split('id="ai-meeting-panel"',1)[1].split('<script>',1)[1].split('</script>',1)[0]
        harness = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{for(const mode of ['okx','unknown']){
 const data=structuredClone(input.report);data.version='AI_MEETING_TRANSCRIPT_VIEW_1';if(mode==='unknown')data.market_source='untrusted';
 const elements={};for(const id of ['ai-meeting-status','ai-meeting-rows','ai-meeting-refresh'])elements[id]={children:[],disabled:false,addEventListener(){},replaceChildren(...x){this.children=x}};
 const document={getElementById:id=>elements[id],createElement:()=>({style:{}}),addEventListener:()=>{}};
 vm.runInNewContext(input.script,{document,Date,setInterval:()=>{},fetch:async()=>({ok:true,text:async()=>JSON.stringify(data)})});
 await new Promise(setImmediate);
 assert.equal(elements['ai-meeting-rows'].children.length,mode==='okx'?7:0);
 assert.match(elements['ai-meeting-status'].textContent,mode==='okx'?/OKX USDT 무기한/:/출처 검증 실패/);
}})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result = subprocess.run([shutil.which('node'),'-e',harness],input=json.dumps({'script':script,'report':report}),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required for local-history venue checks')
    def test_actual_local_history_preserves_source_and_blocks_mixed_venue_comparisons(self):
        brief, _ = pipeline(build(okx_response, provider='okx'))
        room = (Path(__file__).resolve().parent.parent/'web/office_3d.html').read_text()
        scripts = {name:room.split('id="'+section+'"',1)[1].split('<script>',1)[1].split('</script>',1)[0]
                   for name,section in [('history','v230-history-panel'),('compare','v231-change-panel'),('chart','v232-chart-panel')]}
        harness = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
(async()=>{
 function element(){return {children:[],listeners:{},replaceChildren(...x){this.children=x},append(x){this.children.push(x)},addEventListener(n,fn){this.listeners[n]=fn},setAttribute(){}}}
 const markets=['BTCUSDT','ETHUSDT','SOLUSDT'].map(symbol=>({symbol,trend:'SMA_EQUAL',ratio:1}));
 let stored=JSON.stringify([{timestamp:new Date(Date.now()-7200000).toISOString(),markets,market_source:'BYBIT_USDT_PERPETUAL_5M'}]);
 const elements={};const document={getElementById:id=>elements[id]||(elements[id]=element()),createElement:element,createElementNS:element};
 vm.runInNewContext(input.scripts.history,{document,Date,localStorage:{getItem:()=>stored,setItem:(k,v)=>stored=v,removeItem:()=>stored=null},fetch:async()=>({ok:true,text:async()=>JSON.stringify(input.brief)})});
 await new Promise(setImmediate);
 assert.equal(JSON.parse(stored).at(-1).market_source,'OKX_USDT_PERPETUAL_5M','history must retain venue');
 for(const mode of ['same','mixed','legacy']){
  const records=[0,1].map(i=>({timestamp:new Date(Date.now()-(2-i)*3600000).toISOString(),markets,market_source:'OKX_USDT_PERPETUAL_5M'}));
  if(mode==='mixed')records[0].market_source='BYBIT_USDT_PERPETUAL_5M';
  if(mode==='legacy')delete records[0].market_source;
  for(const name of ['compare','chart']){
   const els={};const doc={getElementById:id=>els[id]||(els[id]=element()),createElement:element,createElementNS:element};
   vm.runInNewContext(input.scripts[name],{document:doc,Date,localStorage:{getItem:()=>JSON.stringify(records)}});
   if(name==='chart')els['v232-chart-panel'].listeners.toggle({target:{open:true}});
   const rows=els[name==='compare'?'v231-rows':'v232-chart'];
   const status=els[name==='compare'?'v231-status':'v232-chart-status'];
   if(mode==='same')assert.ok(rows.children.length>0,name+' same venue');
   else {assert.equal(rows.children.length,0,name+' '+mode);assert.match(status.textContent,/서로 다른 거래소/)}
  }
 }
})().catch(e=>{console.error(e);process.exitCode=1});
"""
        result = subprocess.run([shutil.which('node'),'-e',harness],input=json.dumps({'scripts':scripts,'brief':brief}),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__': unittest.main()
