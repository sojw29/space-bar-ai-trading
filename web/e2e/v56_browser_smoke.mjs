/* V56: real Chromium + software WebGL browser smoke against LOCAL Python API.
 * No Binance network access, private API keys or trading actions.
 */
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {mkdtemp, writeFile, readFile, mkdir, rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {chromium} from "playwright";
import {build} from "esbuild";

const here=path.dirname(fileURLToPath(import.meta.url));
const repo=path.resolve(here,"../..");
const output=process.env.SPACEBAR_BROWSER_ARTIFACTS?
 path.resolve(repo,process.env.SPACEBAR_BROWSER_ARTIFACTS):
 path.join(repo,"reports/v56/browser-artifacts");
const port=Number(process.env.SPACEBAR_TEST_PORT||18956);
const base="http://127.0.0.1:"+port;
const moduleURL="https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js";
const runDir=await mkdtemp(path.join(tmpdir(),"spacebar-v56-"));
let server=null,browser=null;
const errors=[];
async function waitForApi(){
 const deadline=Date.now()+12000;
 while(Date.now()<deadline){
  if(server.exitCode!==null)throw Error("local Python server exited: "+server.exitCode);
  try{
   const r=await fetch(base+"/health",{signal:AbortSignal.timeout(900)});
   if(r.ok)return;
  }catch(_){}
  await new Promise(r=>setTimeout(r,200));
 }
 throw Error("localhost Python API did not start");
}
async function smoke(){
 await mkdir(output,{recursive:true});
 const last=Math.floor((Date.now()/1000-900)/300)*300;
 const start=last-79*300;
 let csv="timestamp,open,high,low,close,volume\n";
 for(let i=0;i<80;i++){
  const price=50000+i*4;
  csv+=[start+i*300,price-1,price+8,price-8,price,100+i].join(",")+"\n";
 }
 const csvPath=path.join(runDir,"BTC_5m.csv");
 await writeFile(csvPath,csv,"utf8");
 server=spawn(process.env.PYTHON||"python3",
  ["-u","agents/dashboard_api_v28.py","--port",String(port),"--history",csvPath],
  {cwd:repo,stdio:["ignore","pipe","pipe"]});
 let stderr="";
 server.stderr.on("data",data=>{stderr+=String(data);});
 await waitForApi();
 const market=await (await fetch(base+"/api/v1/market")).json();
 assert.equal(market.paper_only,true);
 assert.equal(market.orders_enabled,false);
 assert.equal(market.realtime,false);
 assert.equal(market.candles.length,60);
 const bundling=await build({
  entryPoints:[path.join(here,"node_modules/three/build/three.module.js")],
  format:"esm",bundle:true,platform:"browser",write:false,
  logLevel:"silent",target:"es2022"
 });
 const bundledThree=bundling.outputFiles[0].text;
 browser=await chromium.launch({
  headless:true,
  args:["--enable-webgl","--use-gl=angle","--use-angle=swiftshader",
        "--disable-gpu-sandbox","--no-sandbox"]
 });
 const context=await browser.newContext({viewport:{width:1360,height:900},deviceScaleFactor:1});
 async function serveThree(page){
  await page.route(moduleURL,route=>route.fulfill({
   status:200,contentType:"text/javascript; charset=utf-8",body:bundledThree
  }));
 }
 const page=await context.newPage();
 page.on("pageerror",e=>errors.push(String(e)));
 await serveThree(page);
 await page.goto(base+"/office3d",{waitUntil:"domcontentloaded"});
 await page.locator('#stage[data-render-ready="true"]').waitFor({timeout:35000});
 const canvas=page.locator("#stage canvas");
 await canvas.waitFor();
 assert.ok(await canvas.evaluate(el=>el.width>0&&el.height>0));
 await page.locator('#market-board-status[data-status="READY"]').waitFor({timeout:12000});
 await page.locator('#ops-research[data-level="ok"]').waitFor();
 await page.locator('#commander-votes .vote-card').first().waitFor();
 assert.equal(await page.locator("#commander-votes .vote-card").count(),6);
 await page.locator('button[data-view="commander"]').click();
 assert.equal(await page.locator('button[data-view="commander"]').getAttribute("aria-pressed"),"true");
 await page.getByRole("button",{name:"ATLAS",exact:true}).click();
 assert.equal(await page.locator("#selected-name").textContent(),"ATLAS");
 await page.screenshot({path:path.join(output,"v56-working-3d.png"),fullPage:true});

 // Block a research request: the next navigation must not preserve old votes
 // or a fabricated market chart.
 const disconnected=await context.newPage();
 await serveThree(disconnected);
 await disconnected.route("**/api/v1/agents",route=>route.fulfill({
  status:503,contentType:"application/json",
  body:JSON.stringify({error:"feed_not_ready",orders_enabled:false})
 }));
 await disconnected.goto(base+"/office3d",{waitUntil:"domcontentloaded"});
 await disconnected.locator('#stage[data-render-ready="true"]').waitFor({timeout:35000});
 await disconnected.locator('#ops-research[data-level="error"]').waitFor({timeout:12000});
 assert.equal(await disconnected.locator("#commander-decision").textContent(),
              "WAIT · 주문 승인 아님");
 assert.equal(await disconnected.locator('#market-board-status').getAttribute("data-status"),"BLOCKED");
 await disconnected.screenshot({path:path.join(output,"v56-disconnected-3d.png"),fullPage:true});

 // CDN module failure exercises the independent classic-script watchdog and
 // explicit link to the still-working CSS 2.5D dashboard.
 const fallback=await context.newPage();
 await fallback.route(moduleURL,route=>route.abort());
 await fallback.goto(base+"/office3d",{waitUntil:"domcontentloaded"});
 await fallback.locator('#webgl-fallback[data-visible="true"]').waitFor({timeout:20000});
 assert.equal(await fallback.locator("#webgl-fallback a").getAttribute("href"),"/dashboard");
 await fallback.screenshot({path:path.join(output,"v56-webgl-fallback.png"),fullPage:true});
 const homepage=await (await fetch(base+"/dashboard")).text();
 assert.ok(homepage.includes('id="trading-room"'));
 const res=await fetch(base+"/office3d",{method:"POST",body:'{"BUY":true}'});
 assert.equal(res.status,405);
 assert.equal(errors.length,0,"Unexpected JS page errors: "+errors.join(" | "));
 console.log("V56 Chromium 3D, controls, fail-closed feed, 2.5D fallback: PASS");
}
try{
 await smoke();
}catch(error){
 console.error("V56 browser smoke failed",error);
 if(server)console.error("API stderr (truncated):",String(server.stderr||"").slice(-2000));
 process.exitCode=1;
}finally{
 if(browser)await browser.close();
 if(server&&!server.killed)server.kill("SIGTERM");
 await rm(runDir,{recursive:true,force:true});
}
