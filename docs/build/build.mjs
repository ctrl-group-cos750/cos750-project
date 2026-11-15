// Builds the group's documents into branded PDFs in docs/build/out/.
//
//   npm run pdf            every document
//   npm run pdf -- se id   only these
//
// A document is one Markdown file, docs/<name>/<name>-document.md, that starts with a front
// matter block giving its title, short name and version. Each top-level section is a `#`
// heading. Headings are numbered here, so the Markdown never carries numbers. See
// docs/README.md for the conventions.
import { execFileSync } from 'node:child_process'
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import MarkdownIt from 'markdown-it'
import { chromium } from 'playwright'

const here = dirname(fileURLToPath(import.meta.url))
const docsDir = resolve(here, '..')
const repoDir = resolve(docsDir, '..')
const outDir = join(here, 'out')
const require = createRequire(import.meta.url)

const escape = (s) =>
  String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
// CSS string literal, for the running header and footer.
const cssString = (s) => `"${String(s).replace(/["\\]/g, '\\$&')}"`

function git(args) {
  try {
    return execFileSync('git', args, { cwd: repoDir, encoding: 'utf8' }).trim()
  } catch {
    return ''
  }
}

// --- Markdown -------------------------------------------------------------------------------

function markdown() {
  const md = new MarkdownIt({ html: true, typographer: true })

  // Mermaid fences become diagrams; Mermaid draws them in the browser before printing.
  const fence = md.renderer.rules.fence
  md.renderer.rules.fence = (tokens, i, options, env, self) => {
    const token = tokens[i]
    if (token.info.trim() === 'mermaid') {
      return `<figure class="diagram"><pre class="mermaid">${escape(token.content)}</pre></figure>\n`
    }
    return fence(tokens, i, options, env, self)
  }

  // Headings get their section number and an id; captions and TODOs get a class.
  md.core.ruler.push('ctrl_group', (state) => {
    const { env } = state
    const tokens = state.tokens
    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i]
      if (token.type === 'heading_open') {
        const level = Number(token.tag.slice(1))
        if (level > 3) continue
        env.counters[level - 1] += 1
        env.counters.fill(0, level)
        const num = env.counters.slice(0, level).join('.')
        const inline = tokens[i + 1]
        token.attrSet('id', `s-${num.replaceAll('.', '-')}`)
        token.attrSet('data-num', num)
        env.toc.push({ level, num, text: inline.content, id: `s-${num.replaceAll('.', '-')}` })
      }
      if (token.type === 'paragraph_open') {
        const inline = tokens[i + 1]
        const first = inline.children?.[0]
        if (!first || first.type !== 'text') continue
        const caption = /^(Table|Figure):\s*/.exec(first.content)
        if (caption) {
          token.attrJoin('class', `caption ${caption[1].toLowerCase()}`)
          first.content = first.content.slice(caption[0].length)
        } else if (first.content.startsWith('TODO:')) {
          token.attrJoin('class', 'todo')
          env.todos.push(inline.content)
        }
      }
    }
  })
  return md
}

// --- HTML -----------------------------------------------------------------------------------

function fontLinks() {
  return [
    '@fontsource/source-serif-4/400.css',
    '@fontsource/source-serif-4/400-italic.css',
    '@fontsource/source-serif-4/600.css',
    '@fontsource/space-grotesk/500.css',
    '@fontsource/space-grotesk/700.css',
    '@fontsource/jetbrains-mono/400.css',
    '@fontsource/jetbrains-mono/700.css',
  ]
    .map((f) => `<link rel="stylesheet" href="${pathToFileURL(require.resolve(f))}">`)
    .join('\n')
}

// Alphabetical by surname (the last word of the name), whatever order team.json lists them in.
const surname = (name) => name.trim().split(/\s+/).at(-1)

function cover(doc, team, logo, built) {
  const members = [...team.members]
    .sort((a, b) => surname(a.name).localeCompare(surname(b.name), 'en-ZA'))
    .map(
      (m) =>
        `<li><span class="name">${escape(m.name)}</span><span class="number">${escape(m.studentNumber ?? '')}</span></li>`,
    )
    .join('')
  return `
<section class="cover">
  <div class="cover-logo">${logo}</div>
  <div class="cover-title">
    <p class="product">${escape(team.product)}</p>
    <p class="title">${escape(doc.title)}</p>
    <p class="tagline">${escape(team.tagline)}</p>
  </div>
  <div class="cover-meta">
    <p class="version">${escape(doc.version)} · ${escape(built.date)}</p>
    <p class="group">${escape(team.group)}</p>
    <ul class="members">${members}</ul>
    <p class="module">${escape(team.module)}<br>${escape(team.institution)}</p>
  </div>
</section>`
}

function contents(toc, md) {
  const items = toc
    .filter((h) => h.level <= 2)
    .map(
      (h) =>
        `<li class="l${h.level}"><a href="#${h.id}"><span class="num">${h.num}</span>${md.renderInline(h.text)}</a></li>`,
    )
    .join('\n')
  return `<nav class="toc"><p class="toc-title">Contents</p><ol>${items}</ol></nav>`
}

function page(doc, team, body, toc, logo, built, md) {
  const header = `${team.group} · ${doc.short} · ${doc.version}`
  return `<!doctype html>
<html lang="en-ZA">
<head>
<meta charset="utf-8">
<title>${escape(`${team.group} – ${doc.title}`)}</title>
${fontLinks()}
<link rel="stylesheet" href="style.css">
<style>
  @page { @top-left { content: ${cssString(header)} } }
  @page :first { @top-left { content: none } @bottom-left { content: none } @bottom-right { content: none } }
</style>
</head>
<body>
${cover(doc, team, logo, built)}
${contents(toc, md)}
<main>
${body}
</main>
</body>
</html>`
}

// --- Build ----------------------------------------------------------------------------------

// The block between the opening `---` lines: one `key: value` per line.
function frontMatter(source, path) {
  const match = /^---\n([\s\S]*?)\n---\n/.exec(source)
  if (!match) throw new Error(`${path} must start with a --- front matter block (title, short, version)`)
  const meta = Object.fromEntries(
    match[1]
      .split('\n')
      .filter((line) => line.trim())
      .map((line) => {
        const at = line.indexOf(':')
        return [line.slice(0, at).trim(), line.slice(at + 1).trim()]
      }),
  )
  for (const key of ['title', 'short', 'version']) {
    if (!meta[key]) throw new Error(`${path}: front matter has no ${key}`)
  }
  return { meta, body: source.slice(match[0].length) }
}

async function documents(only) {
  const found = []
  for (const entry of await readdir(docsDir, { withFileTypes: true })) {
    const path = join(docsDir, entry.name, `${entry.name}-document.md`)
    if (!entry.isDirectory() || !existsSync(path)) continue
    if (only.length && !only.includes(entry.name)) continue
    const { meta, body } = frontMatter(await readFile(path, 'utf8'), path)
    found.push({ name: entry.name, path, file: `ctrl-group-${entry.name}-document`, body, ...meta })
  }
  const missing = only.filter((name) => !found.some((d) => d.name === name))
  if (missing.length) throw new Error(`No docs/<name>/<name>-document.md for: ${missing.join(', ')}`)
  return found
}

function builtInfo(path) {
  const [hash, date] = git(['log', '-1', '--format=%h %cs', '--', path]).split(' ')
  const dirty = git(['status', '--porcelain', '--', path]) !== ''
  const today = new Date().toISOString().slice(0, 10)
  return {
    date: dirty || !date ? today : date,
    ref: hash ? `${hash}${dirty ? ' with local edits' : ''}` : 'an uncommitted copy',
  }
}

/** Runs in the page before printing. Chromium honours "keep with next" between a heading and the
 * block after it, but not along a chain (heading, a one-line lead-in, then a table or wireframe that
 * can't split), so a heading could end a page alone. Each heading is wrapped with what follows it
 * up to and including its first substantial block, and the wrapper is never split: a heading moves
 * to the next page with that content rather than ending a page by itself. Short paragraphs (a
 * lead-in such as "Tool: …" or a sentence ending in a colon) and a subheading straight after it
 * are pulled in along the way, and a caption stays with its table or figure. Only a block taller
 * than most of a page, or a table, list or paragraph taller than a third of one, is left out of
 * the wrapper; the wrapper then keeps to its first lines. */
function keepHeadingsWithContent() {
  const SHORT = 260 // characters: a lead-in, not a paragraph worth reading on its own
  const PAGE = 255 * (96 / 25.4) // the height of an A4 page's text area (style.css @page), in CSS px
  const isHeading = (el) => /^H[1-4]$/.test(el?.tagName ?? '')
  const isCaption = (el) => el?.tagName === 'P' && el.classList.contains('caption')
  const isShort = (el) => el.tagName === 'P' && el.textContent.trim().length < SHORT
  for (const heading of [...document.querySelectorAll('main h1, main h2, main h3, main h4')]) {
    if (heading.parentElement?.classList.contains('keep')) continue
    const group = []
    let next = heading
    let tooTall = false
    while (next) {
      const height = isHeading(next) ? 0 : next.getBoundingClientRect().height
      // Tables (whose header row repeats), lists and paragraphs split cleanly, so a tall one is not
      // held whole; a diagram, wireframe or figure can't split, so it is, up to most of a page.
      const limit = { TABLE: 0.3, UL: 0.3, OL: 0.3, P: 0.3, DIV: 0.3 }[next.tagName] ?? 0.8
      if (height > limit * PAGE) {
        tooTall = true
        break
      }
      group.push(next)
      if (isCaption(next.nextElementSibling)) group.push((next = next.nextElementSibling))
      const done = !isHeading(next) && !isShort(next)
      next = next.nextElementSibling
      if (done) break
    }
    const wrap = document.createElement('div')
    wrap.className = tooTall ? 'keep keep-with-next' : 'keep'
    heading.before(wrap)
    for (const el of group) wrap.append(el)
  }
}

async function build(browser, doc, team, logo) {
  const md = markdown()
  const env = { counters: [0, 0, 0], toc: [], todos: [] }
  // The HTML is written to out/, so an image path relative to the Markdown file (images/x.png)
  // would point into out/. Point it at the document's own folder instead.
  const body = md
    .render(doc.body, env)
    .replace(
      /<img src="(?![a-z]+:|\/)([^"]+)"/g,
      (_, src) => `<img src="${pathToFileURL(join(dirname(doc.path), src)).href}"`,
    )

  const built = builtInfo(doc.path)
  const html = page(doc, team, body, env.toc, logo, built, md)
  const htmlPath = join(outDir, `${doc.file}.html`)
  await writeFile(htmlPath, html)

  // Lay the page out at the printed text width (A4 less the 20 mm side margins in style.css), so
  // the heights keepHeadingsWithContent measures are the heights that print.
  const tab = await browser.newPage({ viewport: { width: Math.round(170 * (96 / 25.4)), height: 1000 } })
  try {
    await tab.goto(pathToFileURL(htmlPath).href)
    if (await tab.locator('pre.mermaid').count()) {
      await tab.addScriptTag({ path: require.resolve('mermaid/dist/mermaid.min.js') })
      await tab.evaluate(async () => {
        const mermaid = globalThis.mermaid
        mermaid.initialize({
          startOnLoad: false,
          theme: 'base',
          themeVariables: {
            fontFamily: 'Space Grotesk, sans-serif',
            primaryColor: '#e9f1fb',
            primaryBorderColor: '#2470c9',
            primaryTextColor: '#141413',
            lineColor: '#184a85',
          },
        })
        await mermaid.run({ querySelector: 'pre.mermaid' })
      })
    }
    await tab.evaluate(() => document.fonts.ready)
    await tab.evaluate(keepHeadingsWithContent)
    await tab.pdf({
      path: join(outDir, `${doc.file}.pdf`),
      preferCSSPageSize: true,
      printBackground: true,
      outline: true,
      tagged: true,
    })
  } finally {
    await tab.close()
  }
  return env.todos
}

const only = process.argv.slice(2)
const team = JSON.parse(await readFile(join(here, 'team.json'), 'utf8'))
const logo = await readFile(join(repoDir, 'assets/svg/logo-stacked.svg'), 'utf8')
await mkdir(outDir, { recursive: true })
await writeFile(join(outDir, 'style.css'), await readFile(join(here, 'style.css')))

const browser = await chromium.launch()
try {
  for (const doc of await documents(only)) {
    const todos = await build(browser, doc, team, logo)
    const name = `${doc.file}.pdf`
    console.log(`${name}${todos.length ? `  (${todos.length} TODO${todos.length > 1 ? 's' : ''})` : ''}`)
    for (const todo of todos) console.log(`    ${todo.slice(0, 100)}`)
  }
} finally {
  await browser.close()
}
if (team.members.length < team.groupSize) {
  console.log(`team.json lists ${team.members.length} of ${team.groupSize} members.`)
}
