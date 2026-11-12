// Prints slides.html to slides.pdf (16:9, one slide per page) with the Chromium that the
// end-to-end tests use. From the repository root: node docs/presentation/build.mjs
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const require = createRequire(join(here, '../../e2e/package.json'))
const { chromium } = require('playwright')

const browser = await chromium.launch(
  process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {},
)
const page = await browser.newPage()
await page.goto(pathToFileURL(join(here, 'slides.html')).href)
await page.pdf({ path: join(here, 'slides.pdf'), width: '1280px', height: '720px', printBackground: true })
if (process.argv.includes('--png')) {
  await page.setViewportSize({ width: 1280, height: 720 })
  const slides = await page.locator('section').all()
  for (const [i, s] of slides.entries()) await s.screenshot({ path: join(here, `slide-${i + 1}.png`) })
}
await browser.close()
console.log('docs/presentation/slides.pdf')
