"""Build live.html: the Practice Pulse design, reading BigQuery live through the viewer's connector."""
import pathlib, re, sys
here = pathlib.Path(__file__).parent
project = sys.argv[1] if len(sys.argv) > 1 else "your-gcp-project"
t = (here.parent / "dashboard" / "template.html").read_text()

def sub(old, new, count=1):
    global t
    assert t.count(old) >= 1, old[:60]
    t = t.replace(old, new, count)

sub('<span class="sample">Demo with sample data</span>', '<span class="sample">Live from BigQuery, sample data</span>')
sub("</style>", """.live { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-left: auto; font-size: .84rem; color: var(--ink-3) }\n#app:not([hidden]) { display: grid; gap: 16px }
.live .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--good); margin-right: 8px; vertical-align: 1px }
.live .dot.busy { background: var(--watch-mark); animation: blink 1.2s infinite } .live .dot.warn { background: var(--act-mark) }
@keyframes blink { 50% { opacity: .3 } }
.btn { border: 0; background: var(--teal-bright); border-radius: 4px; padding: 8px 16px; font-weight: 600; font-size: .8rem; letter-spacing: .06em; text-transform: uppercase; cursor: pointer; color: #ffffff }
.btn:hover { background: #2296a3 }
#gate { max-width: 560px; margin: 48px auto; text-align: center; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); padding: 32px 28px; display: grid; gap: 12px; justify-items: center }
#gate h2 { font-size: 1.4rem; font-weight: 600 } #gate p { color: var(--ink-2); max-width: 46ch }
.pulse { width: 42px; height: 42px; border-radius: 50%; border: 4px solid var(--teal-soft); border-top-color: var(--teal-bright); animation: spin 1s linear infinite }
@keyframes spin { to { transform: rotate(360deg) } }
@media (prefers-reduced-motion: reduce) { .pulse, .live .dot.busy { animation: none } }
.steps { list-style: none; padding: 0; margin: 6px 0 0; text-align: left; font-size: .9rem; display: grid; gap: 4px }
.steps li::before { content: "○"; display: inline-block; width: 1.4em; color: var(--ink-3) }
.steps li.ok::before { content: "✓"; color: var(--good) } .steps li.error::before { content: "!"; color: var(--act) }
.sec-note { font-size: .86rem; border-radius: 8px; padding: 8px 12px; margin-bottom: 12px }
.sec-note.wait { background: var(--sunk); color: var(--ink-2) } .sec-note.bad { background: var(--act-bg); color: var(--act) }
</style>""")
sub('<div class="wrap">\n', '<div class="wrap">\n  <div id="gate" role="status" aria-live="polite"></div>\n  <div id="app" hidden>\n')
i = t.index('<nav class="tabs"'); j = t.rindex('  </div>', 0, i)
t = t[:j] + '    <div class="live"><span id="live-txt"></span><button class="btn" id="refresh" title="Re-run the BigQuery queries">Refresh data</button></div>\n' + t[j:]
sub('<div class="card-head"><h2>Where the money goes</h2><p id="opex-sub"></p></div>',
    '<div class="card-head"><h2>Where the money goes</h2><p id="opex-sub"></p></div>\n      <p class="sec-note note-opex" hidden></p>')
sub('  <section class="view" id="v-marketing" role="tabpanel" hidden>\n', '  <section class="view" id="v-marketing" role="tabpanel" hidden>\n    <p class="sec-note note-detail" hidden></p>\n')
sub('<div class="card-head"><h2>Do the books match?</h2><p>Sage Intacct compared with the system that tracks each number day to day.</p></div>', '<div class="card-head"><h2>Do the books match?</h2><p>Sage Intacct compared with the system that tracks each number day to day.</p></div>\n      <p class="sec-note note-detail" hidden></p>')
# close #app before the footer
t = re.sub(r'(\n\s*<footer>)', r'\n  </div>\1', t, count=1)

# script surgery
sub("const DATA = /*__DATA__*/;", "const DATA = { locations: [], monthly: [], channels: [], mix: [], recon: [], opex: [], opex_accounts: [], sources: [], unmapped: 0 };")
sub("const LOC = Object.fromEntries(DATA.locations.map(l => [l.location_key, l]));", "let LOC = {};")
sub("const MONTHS = [...new Set(DATA.monthly.map(r => r.month))].sort();", "let MONTHS = [];")
sub('$("#f-region").innerHTML', 'function setupFilters() {\n$("#f-region").innerHTML')
sub('.join("");\nfunction fillLocs() {', '.join("");\n  fillLocs();\n}\nfunction fillLocs() {')
sub("}\nfillLocs();\n", "}\n")
sub("function hbars(el, items, { fmt, max, ticks = 4, W = 620 }) {\n", "function hbars(el, items, { fmt, max, ticks = 4, W = 620 }) {\n  if (!items.length) { el.innerHTML = '<p class=\"muted\" style=\"font-size:.9rem\">Nothing to show for this selection yet.</p>'; return }\n")
sub("if (location.hash && document.getElementById(\"v-\" + location.hash.slice(1))) showTab(location.hash.slice(1));\n", "")
sub('$("#sources").innerHTML = DATA.sources.map', 'function drawSources() {\n$("#sources").innerHTML = DATA.sources.map')
sub('sample rows</span></div>`).join("");', 'rows in BigQuery</span></div>`).join("");\n}')
sub("\nrender();\n</script>", "\n__LOADER__\n</script>")
sub("function render() {\n", "function render() {\n  drawSources();\n")

loader = (here / "loader.js").read_text().replace("__PROJECT__", project)
t = t.replace("__LOADER__", loader)
qs = "".join(f'<script type="text/plain" id="q-{n}">\n{(here / (n + ".sql")).read_text()}</script>\n' for n in ("core", "detail", "opex", "weekly"))
t = t.replace("<script>", qs + "<script>", 1)
t = t.replace("All figures are sample data generated to demonstrate the platform; none are real Northwind numbers.",
              "Every number is read live from the Northwind BigQuery warehouse through your own Google Cloud BigQuery connector. The warehouse holds sample data generated to demonstrate the platform; none are real Northwind numbers.")
(here / "live.html").write_text(t)
print("wrote live.html", len(t))
