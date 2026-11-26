// Render report/report.html to report.pdf with headless Chromium (Playwright).
// Usage: node report/html2pdf.js report/report.html report.pdf
const { chromium } = require('playwright');
(async () => {
  const [src, out] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + require('path').resolve(src), { waitUntil: 'load' });
  await page.pdf({ path: out, format: 'A4', printBackground: true,
    margin: { top: '13mm', bottom: '14mm', left: '14mm', right: '14mm' },
    displayHeaderFooter: true, headerTemplate: '<span></span>',
    footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#666"><span class="pageNumber"></span> / <span class="totalPages"></span></div>' });
  await browser.close();
})();
