// Builds the group's documents into branded PDFs in docs/build/out/.
//
//   npm run pdf            every document
//   npm run pdf -- se id   only these
//
// A document is a folder under docs/ with a document.json and numbered Markdown sections
// (01-overview.md, 02-...). Each section file starts with a level-1 heading. Headings are
// numbered here, so the Markdown never carries numbers. See docs/README.md for the conventions.
import { execFileSync } from 'node:child_process'
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { basename, dirname, join, resolve } from 'node:path'
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

function cover(doc, team, logo, built) {
  const members = team.members
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
  const footer = `Built from ${built.ref}`
  return `<!doctype html>
<html lang="en-ZA">
<head>
<meta charset="utf-8">
<title>${escape(`${team.group} – ${doc.title}`)}</title>
${fontLinks()}
<link rel="stylesheet" href="style.css">
<style>
  @page { @top-left { content: ${cssString(header)} } @bottom-left { content: ${cssString(footer)} } }
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

async function documents(only) {
  const found = []
  for (const entry of await readdir(docsDir, { withFileTypes: true })) {
    const config = join(docsDir, entry.name, 'document.json')
    if (entry.isDirectory() && existsSync(config)) {
      if (only.length && !only.includes(entry.name)) continue
      found.push({ dir: join(docsDir, entry.name), ...JSON.parse(await readFile(config, 'utf8')) })
    }
  }
  const missing = only.filter((name) => !found.some((d) => basename(d.dir) === name))
  if (missing.length) throw new Error(`No document folder with a document.json: ${missing.join(', ')}`)
  return found
}

function builtInfo(dir) {
  const [hash, date] = git(['log', '-1', '--format=%h %cs', '--', dir]).split(' ')
  const dirty = git(['status', '--porcelain', '--', dir]) !== ''
  const today = new Date().toISOString().slice(0, 10)
  return {
    date: dirty || !date ? today : date,
    ref: hash ? `${hash}${dirty ? ' with local edits' : ''}` : 'an uncommitted copy',
  }
}

async function build(browser, doc, team, logo) {
  const md = markdown()
  const env = { counters: [0, 0, 0], toc: [], todos: [] }
  const files = (await readdir(doc.dir)).filter((f) => /^\d+.*\.md$/.test(f)).sort()
  if (!files.length) throw new Error(`${doc.dir} has no numbered .md sections`)
  let body = ''
  for (const file of files) {
    const source = await readFile(join(doc.dir, file), 'utf8')
    body += `<section class="part" data-file="${escape(file)}">\n${md.render(source, env)}</section>\n`
  }

  const built = builtInfo(doc.dir)
  const html = page(doc, team, body, env.toc, logo, built, md)
  const htmlPath = join(outDir, `${doc.file}.html`)
  await writeFile(htmlPath, html)

  const tab = await browser.newPage()
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
