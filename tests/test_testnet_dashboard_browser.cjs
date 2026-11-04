"use strict";
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

const root = path.resolve(__dirname, "..");
const pages = ["command_center.html", "audit_room_mobile_v153.html"];
const safe = {
  version: "TESTNET_STAGING_STATUS_1",
  status: "NOT_CONNECTED",
  staging_enabled: false,
  orders_enabled: false,
  network_enabled: false,
  live_trading_approved: false,
  research_only: true,
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const filename of pages) {
      const page = await browser.newPage({
        viewport: filename.includes("mobile") ? { width: 390, height: 844 } : { width: 1280, height: 800 },
      });
      const errors = [];
      page.on("pageerror", e => errors.push(e.message));
      let response = safe;
      await page.route("http://local.test/**", async route => {
        const url = new URL(route.request().url());
        if (url.pathname === "/api/v1/testnet/staging/status") {
          if (response === null) {
            await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
          } else {
            await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(response) });
          }
        } else {
          await route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
        }
      });
      const html = fs.readFileSync(path.join(root, "web", filename), "utf8");
      await page.goto("http://local.test/" + filename, { waitUntil: "domcontentloaded" }).catch(() => {});
      await page.setContent(html, { waitUntil: "domcontentloaded" });
      const label = page.locator("#testnet-staging-state");
      await label.waitFor({ state: "visible" });
      await assert.doesNotReject(() => label.getAttribute("role"));
      await page.waitForFunction(() => document.querySelector("#testnet-staging-state")?.textContent.includes("NOT CONNECTED"), { timeout: 5000 });
      response = { ...safe, orders_enabled: true };
      await page.evaluate(() => refreshTestnetSafety());
      assert.match(await label.textContent(), /상태 확인 불가/);
      response = null;
      await page.evaluate(() => refreshTestnetSafety());
      assert.match(await label.textContent(), /상태 확인 불가/);
      assert.deepEqual(errors, [], filename + ": " + errors.join("; "));
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(err => { console.error(err); process.exitCode = 1; });
