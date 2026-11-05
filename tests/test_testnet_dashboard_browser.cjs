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
      const html = fs.readFileSync(path.join(root, "web", filename), "utf8");
      await page.route("**/*", async route => {
        const url = new URL(route.request().url());
        if (url.origin !== "http://local.test") {
          await route.abort("blockedbyclient");
          return;
        }
        if (url.pathname === "/api/v1/testnet/staging/status") {
          if (response === null) {
            await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
          } else {
            await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(response) });
          }
        } else if (url.pathname === "/" + filename) {
          await route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: html });
        } else {
          await route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
        }
      });
      await page.goto("http://local.test/" + filename, { waitUntil: "domcontentloaded" });
      const label = page.locator("#testnet-staging-state");
      await label.waitFor({ state: "visible" });
      assert.equal(await label.getAttribute("role"), "status");
      assert.equal(await label.getAttribute("aria-live"), "polite");
      await page.waitForFunction(() => document.querySelector("#testnet-staging-state")?.textContent.includes("NOT CONNECTED"), null, { timeout: 5000 });
      response = { ...safe, orders_enabled: true };
      await page.evaluate(() => refreshTestnetSafety());
      assert.match(await label.textContent(), /상태 확인 불가/);
      response = { ...safe, network_enabled: true };
      await page.evaluate(() => refreshTestnetSafety());
      assert.match(await label.textContent(), /상태 확인 불가/);
      response = { ...safe, research_only: false };
      await page.evaluate(() => refreshTestnetSafety());
      assert.match(await label.textContent(), /상태 확인 불가/);
      response = {};
      await page.evaluate(() => refreshTestnetSafety());
      assert.match(await label.textContent(), /상태 확인 불가/);
      response = null;
      await page.evaluate(() => refreshTestnetSafety());
      assert.match(await label.textContent(), /상태 확인 불가/);
      response = safe;
      await page.evaluate(() => refreshTestnetSafety());
      assert.match(await label.textContent(), /NOT CONNECTED/);
      if (filename.includes("mobile")) {
        // CSS regressions: escaped newline text must not swallow mobile focus and layout rules.
        await page.evaluate(() => {
          const styles = Array.from(document.styleSheets).flatMap(sheet => Array.from(sheet.cssRules));
          if (!styles.some(rule => rule.selectorText === "button:focus-visible")) {
            throw new Error("mobile keyboard focus rule missing");
          }
          if (!styles.some(rule => rule.conditionText === "(max-width: 480px)")) {
            throw new Error("mobile responsive rule missing");
          }
        });
        // AI meeting transcript is display-only and must reject unsafe or malformed data.
        await page.evaluate(async () => {
          const originalFetch = window.fetch;
          const expected = [
            ["ATLAS","ANALYSIS"],["QUANT","ANALYSIS"],["GUARDIAN","ANALYSIS"],
            ["ATLAS","PEER_REVIEW"],["QUANT","PEER_REVIEW"],
            ["GUARDIAN","PEER_REVIEW"],["COMMANDER","CONCLUSION"]
          ];
          const valid = {
            version:"AI_MEETING_TRANSCRIPT_VIEW_1",status:"COMPLETED",call_count:7,
            ai_agents_running:false,trade_authorization:"DENIED",research_only:true,orders_enabled:false,
            execution_mode:"OFFLINE_FIXTURE",model_inference_performed:false,
            final_verdict:"INSUFFICIENT_DATA",generated_at_utc:"2026-11-04T00:00:00Z",
            transcript:expected.map(([agent,phase])=>({agent,phase,summary:"Offline review",verdict:"INSUFFICIENT_DATA"}))
          };
          let payload=valid;
          window.fetch=(url,options)=>url==="/api/v1/meeting/transcript"
            ? Promise.resolve({ok:true,json:async()=>payload})
            : originalFetch(url,options);
          const state=document.getElementById("meeting-state");
          const detail=document.getElementById("meeting-detail");
          try {
            await refreshMeeting();
            if (!state.textContent.includes("확인 완료") ||
                !detail.textContent.includes("INSUFFICIENT_DATA") ||
                !detail.textContent.includes("OFFLINE_FIXTURE") ||
                !state.textContent.includes("오프라인 예시 데이터") ||
                !detail.textContent.includes("주문 권한: DENIED") ||
                document.querySelectorAll("#meeting-steps li").length!==7)
              throw new Error("valid offline meeting not displayed");
            for (const unsafe of [
              {...valid,trade_authorization:"APPROVED"},
              {...valid,orders_enabled:true},
              {...valid,ai_agents_running:true},
              {...valid,execution_mode:"LIVE_PROVIDER",model_inference_performed:false},
              {...valid,transcript:[]},
              {...valid,transcript:valid.transcript.map((entry,i)=>i===3?{...entry,agent:"COMMANDER"}:entry)},
              {...valid,generated_at_utc:"not-a-timestamp"},
              {...valid,generated_at_utc:"2026-11-04T09:00:00+09:00"}
            ]) {
              payload=unsafe;
              await refreshMeeting();
              if (!state.textContent.includes("미연결") || detail.textContent!=="" ||
                  document.querySelectorAll("#meeting-steps li").length!==0)
                throw new Error("unsafe meeting was displayed");
            }
          } finally { window.fetch=originalFetch; }
        });
        // A stale successful audit response cannot revive data after a newer failure.
        await page.evaluate(async () => {
          const originalFetch = window.fetch;
          const pending = [];
          window.fetch = (url, options) => {
            if (url === "/api/v1/replay/audit") {
              return new Promise(resolve => pending.push(resolve));
            }
            return originalFetch(url, options);
          };
          try {
            const older = refresh();
            const newer = refresh();
            pending[1]({ ok: false, status: 503 });
            await newer;
            pending[0]({
              ok: true,
              json: async () => ({
                mode: "historical_offline_audit",
                realtime: false,
                orders_enabled: false,
                signals_enabled: false,
                audit: {
                  symbol: "BTC", timeframe_minutes: 5, candle_count: 300,
                  first_timestamp: 1000, last_timestamp: 2000,
                  closed_trades: 0, realized_pnl: 0, ending_realized_equity: 10000,
                  open_quantity: 0, win_rate_pct: 0, max_drawdown_pct: 0,
                  data_sha256: "a".repeat(64)
                }
              })
            });
            await older;
            if (!document.querySelector("#status").textContent.includes("데이터 미연결")) {
              throw new Error("stale audit success overwrote newer failure");
            }
            if (document.querySelector("#cards").children.length !== 0) {
              throw new Error("stale audit response revived cards");
            }
          } finally {
            window.fetch = originalFetch;
          }
        });
        // A later valid audit response must restore verified cards after an outage.
        response = safe;
        await page.evaluate(async () => {
          const originalFetch = window.fetch;
          window.fetch = (url, options) => {
            if (url === "/api/v1/replay/audit") {
              return Promise.resolve({
                ok: true,
                json: async () => ({
                  mode: "historical_offline_audit", realtime: false,
                  orders_enabled: false, signals_enabled: false,
                  audit: {
                    symbol: "BTC", timeframe_minutes: 5, candle_count: 300,
                    first_timestamp: 1000, last_timestamp: 2000,
                    closed_trades: 0, realized_pnl: 0, ending_realized_equity: 10000,
                    open_quantity: 0, win_rate_pct: 0, max_drawdown_pct: 0,
                    data_sha256: "b".repeat(64)
                  }
                })
              });
            }
            return originalFetch(url, options);
          };
          try {
            await refresh();
            if (!document.querySelector("#status").textContent.includes("HISTORICAL")) {
              throw new Error("audit did not recover after outage");
            }
            if (document.querySelector("#cards").children.length !== 8) {
              throw new Error("verified audit cards were not restored");
            }
          } finally {
            window.fetch = originalFetch;
          }
        });
        // Audit data must fail closed on a stalled request, without showing stale cards.
        await page.evaluate(async () => {
          const originalFetch = window.fetch;
          let aborted = false;
          window.fetch = (url, options) => {
            if (url !== "/api/v1/replay/audit") return originalFetch(url, options);
            return new Promise((resolve, reject) => {
              const onAbort = () => {
                aborted = true;
                reject(new DOMException("Aborted", "AbortError"));
              };
              if (options.signal.aborted) onAbort();
              else options.signal.addEventListener("abort", onAbort, { once: true });
            });
          };
          try {
            await refresh();
            if (!aborted) throw new Error("audit request did not time out");
            if (!document.querySelector("#status").textContent.includes("데이터 미연결")) {
              throw new Error("audit timeout did not fail closed");
            }
            if (document.querySelector("#cards").children.length !== 0) {
              throw new Error("stale audit cards remained after timeout");
            }
          } finally {
            window.fetch = originalFetch;
          }
        });

        response = null;
        await page.getByRole("button", { name: /새로고침/ }).click();
        await page.waitForFunction(() => document.querySelector("#testnet-staging-state")?.textContent.includes("상태 확인 불가"), null, { timeout: 5000 });
        response = safe;
        await page.getByRole("button", { name: /새로고침/ }).click();
        await page.waitForFunction(() => document.querySelector("#testnet-staging-state")?.textContent.includes("NOT CONNECTED"), null, { timeout: 5000 });
      }
      // An older response must never overwrite a newer safety decision.
      await page.evaluate(async () => {
        const originalFetch = window.fetch;
        const pending = [];
        window.fetch = (url, options) => {
          if (url === "/api/v1/testnet/staging/status") {
            return new Promise(resolve => pending.push(resolve));
          }
          return originalFetch(url, options);
        };
        try {
          const older = refreshTestnetSafety();
          const newer = refreshTestnetSafety();
          const payload = value => ({ ok: true, json: async () => value });
          pending[1](payload({ version: "TESTNET_STAGING_STATUS_1", status: "NOT_CONNECTED", staging_enabled: false, orders_enabled: false, network_enabled: false, live_trading_approved: false, research_only: true }));
          await newer;
          pending[0](payload({ orders_enabled: true }));
          await older;
          if (!document.querySelector("#testnet-staging-state").textContent.includes("NOT CONNECTED")) {
            throw new Error("stale unsafe response overwrote newer safe result");
          }
          const oldSafe = refreshTestnetSafety();
          const newUnsafe = refreshTestnetSafety();
          pending[3](payload({ orders_enabled: true }));
          await newUnsafe;
          pending[2](payload({ version: "TESTNET_STAGING_STATUS_1", status: "NOT_CONNECTED", staging_enabled: false, orders_enabled: false, network_enabled: false, live_trading_approved: false, research_only: true }));
          await oldSafe;
          if (!document.querySelector("#testnet-staging-state").textContent.includes("상태 확인 불가")) {
            throw new Error("stale safe response overwrote newer unsafe result");
          }
        } finally {
          window.fetch = originalFetch;
        }
      });
      // A stalled request must abort and fail closed rather than spin forever.
      await page.evaluate(async () => {
        const originalFetch = window.fetch;
        let observedAbort = false;
        window.fetch = (url, options) => {
          if (url !== "/api/v1/testnet/staging/status") return originalFetch(url, options);
          return new Promise((resolve, reject) => {
            const onAbort = () => {
              observedAbort = true;
              reject(new DOMException("The operation was aborted.", "AbortError"));
            };
            if (options.signal.aborted) onAbort();
            else options.signal.addEventListener("abort", onAbort, { once: true });
          });
        };
        try {
          await refreshTestnetSafety();
          if (!observedAbort) throw new Error("stalled safety request was not aborted");
          if (!document.querySelector("#testnet-staging-state").textContent.includes("상태 확인 불가")) {
            throw new Error("timeout did not fail closed");
          }
        } finally {
          window.fetch = originalFetch;
        }
      });
      response = safe;
      await page.evaluate(() => refreshTestnetSafety());
      assert.match(await label.textContent(), /NOT CONNECTED/);
      assert.deepEqual(errors, [], filename + ": " + errors.join("; "));
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(err => { console.error(err); process.exitCode = 1; });
