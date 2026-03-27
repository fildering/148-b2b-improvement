import cron from "node-cron";
import express from "express";
import puppeteer from "puppeteer";
import { google } from "googleapis";

// -------------------- ENV --------------------
const CRON_SCHEDULE = process.env.CRON_SCHEDULE || "*/15 * * * *";
const RUN_ON_START = (process.env.RUN_ON_START || "true").toLowerCase() === "true";
const TZ = process.env.TZ || "Asia/Bangkok";
const SHEET_ID = process.env.SHEET_ID || process.env.GOOGLE_SHEET_ID || "";
const SHEET_NAME = process.env.SHEET_NAME || "Raw";
const RAW_GROUP_URLS = process.env.GROUP_URLS || "";
const GROUP_URLS = RAW_GROUP_URLS.split(",").map((s) => s.trim()).filter(Boolean);
const COOKIES_JSON = process.env.COOKIES_JSON || process.env.FB_COOKIE_JSON || "";
const MAX_POSTS_PER_GROUP = Number(process.env.MAX_POSTS_PER_GROUP || 10);
const SCROLL_LOOPS = Number(process.env.SCROLL_LOOPS || 2); 
const SCROLL_PAUSE_MS = Number(process.env.SCROLL_PAUSE_MS || 3000); // เพิ่มเวลาให้โหลดคอมเมนต์ทัน

function log(...args) { console.log(`[${new Date().toLocaleTimeString()}]`, ...args); }

// -------------------- Google Sheets --------------------
async function getSheetsClient() {
  const raw = process.env.GOOGLE_SERVICE_ACCOUNT_JSON || process.env.GOOGLE_CREDENTIALS;
  if (!raw) throw new Error("GOOGLE_CREDENTIALS not set");
  const key = JSON.parse(raw);
  return google.sheets({ version: "v4", auth: new google.auth.GoogleAuth({
    credentials: key,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  })});
}

async function appendRowsToSheet(rows) {
  if (!SHEET_ID || !rows.length) return;
  try {
    const sheets = await getSheetsClient();
    await sheets.spreadsheets.values.append({
      spreadsheetId: SHEET_ID,
      range: `${SHEET_NAME}!A:Z`,
      valueInputOption: "RAW",
      insertDataOption: "INSERT_ROWS",
      requestBody: { values: rows },
    });
    log(`✅ Appended ${rows.length} row(s) to Sheets`);
  } catch (e) { log("❌ Sheets Error:", e.message); }
}

// -------------------- Puppeteer --------------------
async function launchBrowser() {
  return puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-notifications"],
  });
}

async function newAuthedPage(browser) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });
  await page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36");

  if (COOKIES_JSON) {
    try {
      const cookies = JSON.parse(COOKIES_JSON);
      await page.setCookie(...cookies.map(c => ({ ...c, domain: c.domain || ".facebook.com", path: c.path || "/" })));
    } catch (e) { log("Cookie Error:", e.message); }
  }
  return page;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// *** ฟังก์ชันกดขยาย "รายการตอบกลับ" และ "ความคิดเห็นเพิ่มเติม" ***
async function autoExpand(page) {
  try {
    await page.evaluate(() => {
      // ใช้ Regex หาคำว่า "รายการ" หรือ "ความคิดเห็น" เพื่อรองรับตัวเลขที่ไม่แน่นอน
      const btnRegex = /รายการ|ความคิดเห็น|ดูเพิ่มเติม|See more|comments/i;
      const buttons = Array.from(document.querySelectorAll("div[role='button'], span[role='button'], div[style*='cursor: pointer'], a"));
      
      let count = 0;
      for (const btn of buttons) {
        if (count >= 10) break; // เพิ่มจำนวนการกดต่อรอบ
        const txt = btn.innerText || "";
        if (btnRegex.test(txt)) {
          btn.click();
          count++;
        }
      }
    });
    await sleep(2000); 
  } catch (e) { /* ignore */ }
}

async function scrapeGroup(page, groupUrl) {
  log("Scraping:", groupUrl);
  try {
    await page.goto(groupUrl, { waitUntil: "networkidle2", timeout: 60000 });
    
    for (let i = 0; i < SCROLL_LOOPS; i++) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await sleep(SCROLL_PAUSE_MS);
      await autoExpand(page); 
    }

    const posts = await page.$$eval("div[role='article']", (articles) => {
      return articles.map(a => {
        const anchors = Array.from(a.querySelectorAll("a")).map(x => x.href);
        const permalink = anchors.find(h => h.includes("/posts/") || h.includes("/permalink/")) || "";
        
        let text = (a.innerText || "").trim();
        
        // --- รายการคำขยะที่ต้องการตัดทิ้ง (ทำความสะอาด Sheets) ---
        const junk = [
          "ถูกใจ", "แสดงความคิดเห็น", "ส่ง", "แชร์", "ตอบกลับ", "เขียนความคิดเห็น...",
          "ดูความคิดเห็นเพิ่มเติม", "ดูการตอบกลับ", "รายการ", "ชั่วโมง", "นาที", "เมื่อสักครู่",
          "ผู้ดูแล", "ผู้มีส่วนร่วมดาวเด่น", "Like", "Reply", "Comment", "Share"
        ];

        junk.forEach(word => {
          // ลบทั้งบรรทัดที่มีคำขยะเหล่านี้อยู่
          const reg = new RegExp(`.*${word}.*\\n?`, 'g');
          text = text.replace(reg, "");
        });

        // ลบช่องว่างส่วนเกินให้เหลือบรรทัดเดียว
        text = text.replace(/\n\s*\n/g, '\n').trim();

        return { 
          permalink, 
          text, 
          author: a.querySelector("h3, strong, a[role='link']")?.innerText || "Unknown" 
        };
      });
    });

    const unique = posts.filter(p => p.permalink && p.text.length > 10).slice(0, MAX_POSTS_PER_GROUP);
    return { status: unique.length ? "ok" : "no_posts", rows: unique };
  } catch (e) {
    log(`❌ Scrape Error:`, e.message);
    return { status: "error", rows: [] };
  }
}

// -------------------- Job --------------------
async function runJob() {
  log(">>> Job Start");
  let browser;
  try {
    browser = await launchBrowser();
    const page = await newAuthedPage(browser);
    
    await page.goto("https://www.facebook.com/", { waitUntil: "domcontentloaded" });
    if (page.url().includes("/login")) {
      log("❌ Session Expired!");
      return;
    }

    const allRows = [];
    const now = new Date().toISOString();

    for (const url of GROUP_URLS) {
      const res = await scrapeGroup(page, url);
      if (res.status === "ok") {
        log(`Found ${res.rows.length} posts in ${url}`);
        res.rows.forEach(p => allRows.push([now, url, p.permalink, p.author, "", p.text]));
      }
    }

    if (allRows.length > 0) await appendRowsToSheet(allRows);
    log(">>> Job Done");
  } catch (e) { log("❌ Global Error:", e.message); }
  finally { if (browser) await browser.close(); }
}

// -------------------- Server --------------------
const app = express();
app.get("/", (req, res) => res.send("Bot Active"));
app.listen(process.env.PORT || 8080, () => {
  log("Server Start");
  cron.schedule(CRON_SCHEDULE, runJob, { timezone: TZ });
  if (RUN_ON_START) runJob();
});
