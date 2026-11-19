/* Render actual CLI HTML at desktop/mobile widths without remote assets. */
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const generated=spawnSync(process.env.PYTHON||'python3',['-c',`
from ai_meeting_archive import render_report
from test_ai_meeting_archive import archive
a,b=archive(),archive()
a['record']['market_source']='BYBIT_USDT_PERPETUAL_5M'
b['record'].update(market_source='OKX_USDT_PERPETUAL_5M',model='<img src=https://archive.invalid/test>',execution_mode='LIVE_PROVIDER',model_inference_performed=True)
b['record']['transcript'][0]['summary']='different private statement'
print(render_report(a,b))
`],{cwd:repo,env:{...process.env,PYTHONPATH:path.join(repo,'agents')},encoding:'utf8',timeout:10000});
assert.equal(generated.status,0,generated.stderr);
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try{
 for(const viewport of [{width:1280,height:800},{width:390,height:844}]){
  const context=await browser.newContext({viewport,javaScriptEnabled:false});
  const page=await context.newPage(),requests=[];
  page.on('request',request=>requests.push(request.url()));
  await page.setContent(generated.stdout,{waitUntil:'domcontentloaded'});
  await page.getByRole('heading',{name:'비교 조건 요약',exact:true}).waitFor();
  assert.equal(await page.locator('section[aria-label="비교 조건 요약"]').isVisible(),true);
  assert.ok((await page.locator('section[aria-label="비교 조건 요약"]').textContent()).includes('시장 출처가 다름'));
  assert.ok((await page.locator('section[aria-label="비교 조건 요약"]').textContent()).includes('실행 모드가 다름'));
  assert.equal(await page.getByText('<img src=https://archive.invalid/test>',{exact:true}).count(),1);
  assert.equal(await page.locator('img,script,iframe').count(),0);
  assert.equal(await page.getByRole('heading',{name:'판단 전환표',exact:true}).count(),1);
  assert.equal(await page.getByRole('heading',{name:'발언별 변경 여부',exact:true}).count(),1);
  assert.equal(await page.getByText('M07',{exact:true}).count(),1);
  assert.ok(await page.getByRole('cell',{name:'초기 분석',exact:true}).count()>0);
  assert.ok(await page.getByRole('cell',{name:'최종 결론',exact:true}).count()>0);
  assert.equal(await page.locator('body').evaluate(node=>node.scrollWidth<=window.innerWidth),true);
  assert.deepEqual(requests,[],'standalone report must not request network assets');
  await page.emulateMedia({media:'print'});
  await page.setViewportSize({width:1122,height:794});
  assert.equal(await page.locator('.table').first().evaluate(node=>getComputedStyle(node).overflowX),'visible');
  assert.equal(await page.locator('thead').first().evaluate(node=>getComputedStyle(node).display),'table-header-group');
  assert.equal(await page.locator('tr').first().evaluate(node=>getComputedStyle(node).breakInside),'avoid');
  assert.equal(await page.locator('body').evaluate(node=>node.scrollWidth<=window.innerWidth),true);
  const pdf=await page.pdf({preferCSSPageSize:true,printBackground:true});
  assert.equal(pdf.subarray(0,5).toString(),'%PDF-');assert.ok(pdf.length>1000);
  assert.deepEqual(requests,[],'print/PDF rendering must not fetch remote assets');
  await context.close();
 }
 console.log('Archive CLI HTML: desktop/mobile, localized labels, print/PDF, no script/network: PASS');
}finally{await browser.close();}
