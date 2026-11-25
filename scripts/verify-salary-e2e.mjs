// 薪资匹配打分 - 浏览器端到端验证
// 场景1: 期望 22-34K vs 岗位 22-38K -> 薪资匹配满分 15
// 场景2: 期望改为 30K+(只填下限) -> 同一岗位 7.5
// 通过 API 改求职意向，UI 上只读验证分数与文案
import { chromium } from "playwright";
import fs from "fs";

const BASE = "http://127.0.0.1:5180";
const API = "http://127.0.0.1:8000/api";
const SHOT = "D:/AIProjects/JobCopilot/.screenshots";

async function apiLogin() {
  const r = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "zhangsan", password: "123456" }),
  });
  const j = await r.json();
  return j.data.access_token;
}

async function setSalary(token, min, max) {
  const r = await fetch(`${API}/resumes/intent`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ salary_min: min, salary_max: max }),
  });
  return r.json();
}

async function getMatchScore(token, jobId) {
  const r = await fetch(`${API}/match/job/${jobId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const j = await r.json();
  return j.data?.breakdown?.salary?.score;
}

const failures = [];
const log = (msg) => console.log(msg);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("pageerror", (e) => consoleErrors.push(String(e)));

try {
  const token = await apiLogin();

  // 场景1: 22-34K 期望
  await setSalary(token, 22, 34);
  const score1 = await getMatchScore(token, 217);
  log(`场景1 API score (22-34 vs 22-38): ${score1}`);
  if (score1 !== 15) failures.push(`场景1 API 期望 15 实际 ${score1}`);

  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.screenshot({ path: `${SHOT}/01-login.png` });

  // 登录表单（用户名/密码默认已填 zhangsan/123456，直接提交）
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.waitForURL(/\/seeker\/jobs/, { timeout: 20000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOT}/02-after-login.png` });

  // 岗位详情页（路由是 /seeker/jobs/:id）
  await page.goto(`${BASE}/seeker/jobs/217`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=薪资匹配", { timeout: 20000 });
  await page.waitForTimeout(800);
  const row1 = (await page.locator("text=薪资匹配").first().locator("..").textContent()) || "";
  const hint1 = await page.locator("div", { has: page.locator("text=薪资匹配") }).first().textContent();
  log(`场景1 详情页薪资行: ${row1} | block: ${hint1}`);
  if (!/15\s*\/\s*15/.test(row1)) failures.push(`场景1 薪资分数非满分: ${row1}`);
  if (!hint1 || !hint1.includes("22-34") || !hint1.includes("22-38")) {
    failures.push(`场景1 期望文案异常: ${hint1}`);
  }
  await page.screenshot({ path: `${SHOT}/03-job217-salary-22-34.png`, fullPage: true });

  // 场景2: 改成 30K 以上
  await setSalary(token, 30, null);
  const score2 = await getMatchScore(token, 217);
  log(`场景2 API score (30K+ vs 22-38): ${score2}`);
  if (score2 !== 7.5) failures.push(`场景2 API 期望 7.5 实际 ${score2}`);

  await page.goto(`${BASE}/seeker/jobs/217`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=薪资匹配", { timeout: 20000 });
  await page.waitForTimeout(800);
  const row2 = (await page.locator("text=薪资匹配").first().locator("..").textContent()) || "";
  const hint2 = await page.locator("div", { has: page.locator("text=薪资匹配") }).first().textContent();
  log(`场景2 详情页薪资行: ${row2} | block: ${hint2}`);
  if (!/7\.5\s*\/\s*15/.test(row2)) failures.push(`场景2 薪资分数非 7.5: ${row2}`);
  if (!hint2 || !hint2.includes("30")) failures.push(`场景2 期望文案异常: ${hint2}`);
  await page.screenshot({ path: `${SHOT}/04-job217-salary-30plus.png`, fullPage: true });

  // 恢复原始期望 22-34
  await setSalary(token, 22, 34);
  const restored = await getMatchScore(token, 217);
  log(`恢复后 score: ${restored}`);
  if (restored !== 15) failures.push(`恢复后期望 15 实际 ${restored}`);

  if (consoleErrors.length) failures.push(`console errors: ${consoleErrors.slice(0, 3).join(" | ")}`);
} catch (e) {
  failures.push(`EXCEPTION: ${e}`);
  await page.screenshot({ path: `${SHOT}/99-error.png`, fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}

fs.writeFileSync(`${SHOT}/verify-result.json`, JSON.stringify({ failures, consoleErrors }, null, 2));
if (failures.length) {
  console.log("FAILED:\n" + failures.join("\n"));
  process.exit(1);
} else {
  console.log("ALL PASSED");
}
