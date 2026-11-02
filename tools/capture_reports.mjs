// Optional documentation helper. Requires Playwright + an installed Edge browser.
// Example: node tools/capture_reports.mjs <HTML> <PNG> [node_modules_directory]
import { createRequire } from 'node:module';
import { resolve, join } from 'node:path';
import { mkdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const [input, output, modules] = process.argv.slice(2);
if (!input || !output) throw new Error('Usage: node capture_reports.mjs <HTML> <PNG> [node_modules_directory]');
const require = createRequire(import.meta.url);
const { chromium } = require(modules ? join(modules, 'playwright') : 'playwright');
const temporary = process.env.EXPORTLENS_TEMP || (process.platform === 'win32' ? 'F:/CodexTemp/ExportLens/browser' : '/tmp/exportlens-browser');
await mkdir(temporary, { recursive: true });
process.env.TEMP = temporary;
process.env.TMP = temporary;
process.env.TMPDIR = temporary;
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.EXPORTLENS_BROWSER || (process.platform === 'win32' ? 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' : undefined),
  args: ['--disable-gpu', '--disable-extensions', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows', '--disable-features=CalculateNativeWinOcclusion'],
});
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 960 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const failures = [];
  page.on('pageerror', error => failures.push(error.message));
  await page.goto(pathToFileURL(resolve(input)).href, { waitUntil: 'load' });
  await page.screenshot({ path: resolve(output), fullPage: true, timeout: 15000, animations: 'disabled' });
  if (failures.length) throw new Error(failures.join('\n'));
  console.log(JSON.stringify({ title: await page.title(), screenshot: resolve(output), pageErrors: failures.length }));
} finally {
  await browser.close();
}
