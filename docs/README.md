# Docs

| Folder | What goes in it |
|---|---|
| `se/` | The SE document: `se-document.md` |
| `id/` | The ID document: `id-document.md` |
| `build/` | The script that turns `se/` and `id/` into branded PDFs |
| `spec/` | The examination specification, as issued |
| `references/` | Works cited by the spec or by our SE and ID documents |
| `course-material/` | The COS750 lectures and readings from ClickUP, one folder per lecture, with an index of what each gives the project |
| `deploy/` | How the app is hosted (Coolify, DNS) |
| `brand/` | The brand and UI guide: logo, colour, type, the UI kit and how the app writes. The live kit is `/ui-kit` on staging |

## Naming

- Lowercase, words separated by hyphens, no spaces: `cos750-exam-spec-v1.pdf`.
- A new version of the spec gets a new suffix (`-v2`); the old one stays.
- A reference is named `<first-author-surname>-<year>-<short-title>`: `kumar-2024-cs2023.pdf`.
  List it in `references/README.md` with its full citation.

## The SE and ID documents

Both documents are written in Markdown here, reviewed through PRs like code, and built into PDFs
in one standard format: the Ctrl Group cover, a contents page, numbered sections, and a running
header and footer with page numbers.

```
cd docs/build
npm install                 # once
npm run pdf                 # both documents, into docs/build/out/
npm run pdf -- se           # only one
```

You don't need to build locally:

- **Latest from `staging`:** every change to `docs/` that lands on `staging` replaces the
  [`docs-latest` release](https://github.com/ctrl-group-cos750/cos750-project/releases/tag/docs-latest).
  These links always give the newest PDFs:
  - <https://github.com/ctrl-group-cos750/cos750-project/releases/download/docs-latest/ctrl-group-se-document.pdf>
  - <https://github.com/ctrl-group-cos750/cos750-project/releases/download/docs-latest/ctrl-group-id-document.pdf>
- **From a PR:** every PR that changes `docs/` builds both PDFs in CI (the `docs` workflow). Open
  the run and download the `documents` artifact.

### Writing conventions

- **One Markdown file per document:** `docs/<name>/<name>-document.md`. It starts with a front
  matter block, then each top-level section is a `#` heading, with `##` and `###` inside it:

  ```
  ---
  title: Software Engineering Document
  short: SE document
  version: Draft 2
  ---

  # Overview
  ```

  `title` goes on the cover, `short` and `version` in the running header. A new document is a
  new folder with its own `<name>-document.md`.
- **Don't number headings.** The build numbers them (1, 1.1, 1.1.1) and builds the contents page,
  so adding or moving a section renumbers everything. Cross-references written by hand (§4.2)
  have to be checked when sections move.
- **Captions:** a paragraph straight after a table or diagram that starts with `Table:` or
  `Figure:` becomes a numbered caption ("Table 3: …").
- **Diagrams:** a ```` ```mermaid ```` code block is drawn as a diagram (flowcharts, sequence,
  class, ER, state and Gantt diagrams). See <https://mermaid.js.org/intro/>.
- **Unfinished parts:** a paragraph starting with `TODO:` is highlighted in the PDF, and the build
  lists every one, so nothing unfinished is submitted by accident.
- **References:** the ID document numbers its references (`[12]`) and lists them in its last
  section.
- **Cover details:** title and version come from the front matter; the group name and members
  are in `build/team.json`. Every document is the whole group's, so covers name the group
  and its members, never individual authors or roles.
- Keep `[PROVISIONAL]` and other markers out of headings where possible; they also show in the
  contents.
