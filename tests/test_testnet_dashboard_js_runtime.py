"""Execute dashboard safety-panel JavaScript in an isolated Node VM.

No browser, exchange network, or real HTTP server is used.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "web" / "command_center.html", ROOT / "web" / "audit_room_mobile_v153.html"]

NODE_HARNESS = r"""
const vm = require('node:vm');
const fs = require('node:fs');
const html = fs.readFileSync(process.argv[1], 'utf8');
const start = html.indexOf('async function refreshTestnetSafety(){');
const end = html.indexOf('refreshTestnetSafety();', start);
if (start < 0 || end < 0) throw new Error('safety function missing');
const declaration = 'let testnetSafetyRequestId=0;';
if (!html.includes(declaration)) throw new Error('safety request guard missing');
const fn = declaration + '\n' + html.slice(start, end);
async function scenario(reply, expected, httpOk = true) {
  let calls = 0;
  const element = {textContent: ''};
  const context = {
    AbortController,
    setTimeout,
    clearTimeout,
    document: {getElementById: id => {
      if (id !== 'testnet-staging-state') throw new Error('unexpected DOM access');
      return element;
    }},
    fetch: async (url, opts) => {
      calls++;
      if (url !== '/api/v1/testnet/staging/status' || opts.cache !== 'no-store')
        throw new Error('unexpected fetch');
      if (reply === null) throw new Error('network unavailable');
      return {ok: httpOk, json: async () => reply};
    },
  };
  vm.createContext(context);
  vm.runInContext(fn + '; this.testSafety = refreshTestnetSafety;', context, {timeout: 1000});
  await context.testSafety();
  if (calls !== 1) throw new Error('unexpected fetch count: ' + calls);
  if (!element.textContent.includes(expected)) throw new Error('unexpected status: ' + element.textContent);
}
const safe = {
  version:'TESTNET_STAGING_STATUS_1',status:'NOT_CONNECTED',
  staging_enabled:false,orders_enabled:false,network_enabled:false,
  live_trading_approved:false,research_only:true
};
(async () => {
  await scenario(safe, 'NOT CONNECTED');
  await scenario(null, '상태 확인 불가');
  await scenario({...safe, orders_enabled:true}, '상태 확인 불가');
  await scenario({...safe, status:'STAGED_NOT_SENT'}, '상태 확인 불가');
  await scenario(safe, '상태 확인 불가', false);
  await scenario({...safe, network_enabled:true}, '상태 확인 불가');
  await scenario({...safe, staging_enabled:true}, '상태 확인 불가');
  await scenario({...safe, live_trading_approved:true}, '상태 확인 불가');
  await scenario({...safe, research_only:false}, '상태 확인 불가');
  await scenario({...safe, version:'UNKNOWN'}, '상태 확인 불가');
  await scenario({...safe, orders_enabled:undefined}, '상태 확인 불가');
  await scenario({}, '상태 확인 불가');
})().catch(e => {console.error(e); process.exitCode = 1});
"""


class TestDashboardSafetyRuntime(unittest.TestCase):
    def test_fail_closed_status_for_both_pages(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for safety runtime checks")
        for page in PAGES:
            with self.subTest(page=page.name):
                result = subprocess.run(
                    [node, "-e", NODE_HARNESS, str(page)],
                    capture_output=True, text=True, timeout=15, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
