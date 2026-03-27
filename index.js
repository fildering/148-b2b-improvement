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
const SCROLL_PAUSE_MS = Number(process.env.SCROLL_PAUSE_MS || 1500);

function log(...args) { console.log(...args); }

// -------------------- Google Sheets --------------------
async function getSheetsClient() {
  const raw = process.env.GOOGLE_SERVICE_ACCOUNT_JSON || process.env.GOOGLE_CREDENTIALS;
  if (!raw) throw new Error("GOOGLE_CREDENTIALS not set");
  const key = JSON.parse(raw);
  const auth = new google.auth.GoogleAuth({
    credentials: key,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
  return google.sheets({ version: "v4", auth });
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
  
  // 1. ขยายหน้าจอเป็น 9:16 แบบมือถือ
  await page.setViewport({
    width: 450,
    height: 800,
    isMobile: true,
    hasTouch: true
  });

  await page.setUserAgent(
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
  );

  if (COOKIES_JSON) {
    try {
      const cookies = JSON.parse(COOKIES_JSON);
      await page.setCookie(...cookies.map(c => ({ ...c, domain: c.domain || ".facebook.com", path: c.path || "/" })));
    } catch (e) { log("Cookie Error:", e.message); }
  }
  return page;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 2. ฟังก์ชันกด "ดูเพิ่มเติม" และ "ดูความคิดเห็นเพิ่มเติม"
async function autoExpand(page) {
  const targetLabels = [
    "ดูเพิ่มเติม", "See more", 
    "ดูความคิดเห็นเพิ่มเติม", "View more comments", 
    "ความคิดเห็นเพิ่มเติม", "More comments",
    "แสดงความคิดเห็น..."
  ];

  try {
    // หาปุ่มที่มีข้อความตามที่กำหนด
    const buttons = await page.$$("div[role='button'], span[role='button']");
    for (const btn of buttons) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (targetLabels.some(label => text && text.includes(label))) {
        await btn.click();
        await sleep(1000); 
      }
    }
  } catch (e) { /* ignore */ }
}

async function scrapeGroup(page, groupUrl) {
  log("Scraping:", groupUrl);
  await page.goto(groupUrl, { waitUntil: "networkidle2", timeout: 60000 });
  
  // เลื่อนหน้าจอและกดขยายเนื้อหา
  for (let i = 0; i < SCROLL_LOOPS; i++) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await sleep(SCROLL_PAUSE_MS);
    await autoExpand(page); 
  }

  const posts = await page.$$eval("div[role='article']", (articles) => {
    return articles.map(a => {
      const anchors = Array.from(a.querySelectorAll("a")).map(x => x.href);
      const permalink = anchors.find(h => h.includes("/posts/") || h.includes("/permalink/")) || "";
      
      // ดึง Text และทำความสะอาดเบื้องต้น
      let rawText = (a.innerText || "").trim();
      
      // 3. ตัดข้อความส่วนเกินออก
      const junk = [
        "ถูกใจ", "แสดงความคิดเห็น", "ส่ง", "แชร์", "ตอบกลับ", 
        "Like", "Comment", "Share", "Reply", "เขียนความคิดเห็น..."
      ];
      let cleaned = rawText;
      junk.forEach(word => {
        const regex = new RegExp(`\\n?${word}\\b`, 'g');
        cleaned = cleaned.replace(regex, "");
      });

      return {
        permalink,
        text: cleaned.trim(),
        author: a.querySelector("h3 a, strong a")?.innerText || "Unknown"
      };
    });
  });

  const unique = posts.filter(p => p.permalink && p.text).slice(0, MAX_POSTS_PER_GROUP);
  return { status: unique.length ? "ok" : "no_posts", rows: unique };
}

// -------------------- Job & Server --------------------
async function runJob() {
  log("Job start:", new Date().toLocaleString("th-TH", { timeZone: TZ }));
  let browser;
  try {
    browser = await launchBrowser();
    const page = await newAuthedPage(browser);
    
    // เช็ค Login
    await page.goto("https://www.facebook.com/", { waitUntil: "domcontentloaded" });
    if (page.url().includes("/login")) throw new Error("Session Expired");

    const allRows = [];
    const now = new Date().toISOString();

    for (const url of GROUP_URLS) {
      const res = await scrapeGroup(page, url);
      if (res.status === "ok") {
        res.rows.forEach(p => allRows.push([now, url, p.permalink, p.author, "", p.text]));
      }
    }
    await appendRowsToSheet(allRows);
  } catch (e) { log("❌ Job Error:", e.message); }
  finally { if (browser) await browser.close(); }
}

const app = express();
app.get("/", (req, res) => res.send("Bot is Running"));
app.listen(process.env.PORT || 8080, () => {
  log("Server started");
  cron.schedule(CRON_SCHEDULE, runJob, { timezone: TZ });
  if (RUN_ON_START) runJob();
});
