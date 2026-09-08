# notion-widgets

Custom embeds for a Notion dashboard. Static HTML on GitHub Pages, with
live Notion data refreshed hourly by a GitHub Action.

## Why it is built this way

Notion has no plugin API. Every third-party "widget" is a hosted HTML
page in an iframe, so this repo is that — just self-owned and styled to
match the workspace.

**The Notion token never reaches the browser.** A scheduled Action runs
`scripts/build_data.py` with the token from a repo secret and commits a
plain JSON file. The widget pages fetch that JSON with no credentials.
Putting an integration token in client-side JS would expose full
read/write access to the workspace to anyone who views source.

```
Notion API --(Action, hourly, token in secret)--> docs/data/*.json
                                                        |
                                    docs/widgets/*.html (no auth)
                                                        |
                                          Notion /embed block
```

## Widgets

| Widget | Data | What it shows |
|---|---|---|
| `today.html` | live | Today's items, open/overdue counts, links back to each task |
| `countdown.html` | none | Days until fixed dates — edit the `EVENTS` array in the file |

## Setup

1. **Add the secret.** Repo → Settings → Secrets and variables → Actions
   → New repository secret, named `NOTION_API_KEY`.
2. **Enable Pages.** Settings → Pages → Source: *Deploy from a branch*,
   branch `main`, folder `/docs`.
3. **Run it once.** Actions → build-widget-data → Run workflow.
4. **Embed.** In Notion type `/embed`, paste the widget URL, resize.

URLs follow `https://elim1840.github.io/notion-widgets/widgets/<name>.html`

## Local test

```bash
export NOTION_API_KEY=$(grep '^NOTION_API_KEY' ~/.hermes/.env | cut -d= -f2- | tr -d '"')
python3 scripts/build_data.py
python3 -m http.server 8000 --directory docs
# open http://localhost:8000/widgets/today.html
```

## Adding a widget

Drop an HTML file in `docs/widgets/`. If it needs Notion data, add the
query to `scripts/build_data.py` and write another file under
`docs/data/`. Keep credentials out of anything under `docs/`.

## Notes

- Both widgets follow the viewer's light/dark preference.
- Embeds do render in the Notion mobile apps, but page **columns** do
  not — a widget in a right-hand column stacks below on a phone.
- The Action pushes a commit only when the JSON actually changes.
