# -*- coding: utf-8 -*-
"""Render a system folder's docs into ONE self-contained index.html.

    python build_site.py video-player

The three existing systems shipped a page like this and the builder that made them was
lost with a cleaned scratchpad, so this is a rebuild against the observed output: a single
offline-ready file, fonts embedded as base64, mermaid pre-rendered to INLINE SVG (never a
runtime script — the page has to work with no network and no JS), on the same warm-dark
"digital blackboard" the videos use.

Deliberately no markdown dependency. None of `markdown` / `marko` / `mistune` /
`commonmark` is installed in this project's interpreter, and adding one to render seven
documents that use eight constructs is the wrong trade. The subset below is exactly what
the doc standard produces: headings, tables, fenced code, mermaid, blockquotes, lists,
inline code / bold / italic / links, and `---`.
"""
import base64, html, io, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONTDIR = os.path.join(HERE, "..", "Youtube scale journey", "system-design-series",
                       "whatif-videoplayer-v2-2026-08-08", "q1", "fonts")

MMD_CFG = """{
 "theme": "base",
 "themeVariables": {
  "fontFamily": "JetBrains Mono, monospace", "fontSize": "17px",
  "lineColor": "#8a8372", "primaryTextColor": "#ece9e0",
  "clusterBkg": "#1b1914", "clusterBorder": "#5a544a",
  "edgeLabelBackground": "#14130f", "titleColor": "#d8c4a8",
  "nodeTextColor": "#ece9e0", "edgeLabelColor": "#cfc7b6",
  "actorBkg": "#2b211b", "actorBorder": "#dfa88f", "actorTextColor": "#f0dac0",
  "signalColor": "#c8c8d0", "signalTextColor": "#c8c8d0",
  "noteBkgColor": "#2b2513", "noteBorderColor": "#c08532", "noteTextColor": "#f0dac0",
  "labelBoxBkgColor": "#2e1a10", "labelBoxBorderColor": "#f54e00",
  "sequenceNumberColor": "#141210"
 },
 "flowchart": { "curve": "basis", "htmlLabels": false, "nodeSpacing": 46, "rankSpacing": 70 }
}"""


def font_face(name, weight, filename):
    p = os.path.join(FONTDIR, filename)
    b64 = base64.b64encode(io.open(p, "rb").read()).decode("ascii")
    return ("@font-face{font-family:'%s';font-weight:%s;font-display:swap;"
            "src:url(data:font/woff2;base64,%s) format('woff2');}" % (name, weight, b64))


# ── the markdown subset the doc standard actually uses ──────────────────────────────
def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render(md, svgs):
    out, i, lines = [], 0, md.split("\n")
    while i < len(lines):
        ln = lines[i]

        if ln.startswith("```"):
            lang = ln[3:].strip()
            j = i + 1
            body = []
            while j < len(lines) and not lines[j].startswith("```"):
                body.append(lines[j]); j += 1
            if lang == "mermaid":
                out.append('<figure class="d">%s</figure>' % (svgs.pop(0) if svgs else ""))
            else:
                out.append("<pre><code>%s</code></pre>"
                           % html.escape("\n".join(body), quote=False))
            i = j + 1; continue

        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lv = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lv, inline(m.group(2)), lv))
            i += 1; continue

        if ln.strip() == "---":
            out.append("<hr>"); i += 1; continue

        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            head = cells(ln); i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i])); i += 1
            out.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (
                "".join("<th>%s</th>" % inline(c) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r)
                        for r in rows)))
            continue

        if ln.startswith(">"):
            body = []
            while i < len(lines) and lines[i].startswith(">"):
                body.append(lines[i].lstrip(">").strip()); i += 1
            out.append("<blockquote>%s</blockquote>" % inline(" ".join(body)))
            continue

        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", ln)
        if m:
            ordered = bool(re.match(r"\d", m.group(2)))
            items, tag = [], "ol" if ordered else "ul"
            while i < len(lines):
                mm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if not mm:
                    # a wrapped continuation line belongs to the item above it
                    if items and lines[i].startswith("  ") and lines[i].strip():
                        items[-1] += " " + lines[i].strip(); i += 1; continue
                    break
                items.append(mm.group(3)); i += 1
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(x)
                                                     for x in items), tag))
            continue

        if ln.strip():
            para = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", ">", "|", "```", "-", "*")):
                para.append(lines[i].strip()); i += 1
            if para:
                out.append("<p>%s</p>" % inline(" ".join(para)))
                continue
        i += 1
    return "\n".join(out)


def mermaid_svgs(md, workdir, tag):
    """Pre-render every mermaid fence to inline SVG. No runtime script on the page."""
    blocks = re.findall(r"```mermaid\n([\s\S]*?)```", md)
    cfg = os.path.join(workdir, "mmd.json")
    io.open(cfg, "w", encoding="utf-8").write(MMD_CFG)
    svgs = []
    for n, b in enumerate(blocks):
        src = os.path.join(workdir, "%s-%d.mmd" % (tag, n))
        dst = os.path.join(workdir, "%s-%d.svg" % (tag, n))
        io.open(src, "w", encoding="utf-8").write(b)
        r = subprocess.run(["bunx", "@mermaid-js/mermaid-cli@11", "-i", src, "-o", dst,
                            "-c", cfg, "-b", "transparent"],
                           capture_output=True, shell=(os.name == "nt"))
        if r.returncode != 0 or not os.path.exists(dst):
            raise SystemExit("mermaid failed on %s block %d — parse it before building"
                             % (tag, n))
        s = io.open(dst, encoding="utf-8").read()
        s = re.sub(r"^<\?xml[^>]*\?>\s*", "", s)
        s = re.sub(r"<!DOCTYPE[^>]*>\s*", "", s)
        s = re.sub(r'(<svg[^>]*?)\s(?:width|height)="[^"]*"', r"\1", s)
        svgs.append(s)
    return svgs


CSS = """
*{box-sizing:border-box}
body{margin:0;background:#14130f;color:#d8d3c6;
  font:400 17px/1.72 Inter,system-ui,-apple-system,sans-serif;
  background-image:radial-gradient(circle,rgba(240,218,192,.05) 1px,transparent 1px);
  background-size:34px 34px;}
.wrap{max-width:940px;margin:0 auto;padding:72px 26px 120px}
h1,h2,h3,h4{color:#f0dac0;line-height:1.22;font-weight:800;letter-spacing:-.01em}
h1{font-size:2.5rem;margin:0 0 .4em}
h2{font-size:1.6rem;margin:2.6em 0 .7em;padding-top:1.5em;
  border-top:1px solid rgba(240,218,192,.10)}
h3{font-size:1.2rem;margin:2em 0 .5em;color:#e4d2b8}
p{margin:0 0 1.1em}
a{color:#f54e00;text-decoration:none;border-bottom:1px solid rgba(245,78,0,.35)}
a:hover{border-bottom-color:#f54e00}
strong{color:#f0dac0}
code{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:.88em;
  background:#1c1a22;border:1px solid #2a2a33;border-radius:5px;padding:.12em .4em;color:#c08532}
pre{background:#0e0e10;border:1px solid #2a2a30;border-radius:12px;padding:22px 24px;
  overflow-x:auto;margin:0 0 1.6em}
pre code{background:none;border:0;padding:0;color:#c8c8d0;font-size:.92em;line-height:1.62}
blockquote{margin:0 0 1.6em;padding:18px 24px;background:rgba(245,78,0,.05);
  border-left:4px solid #f54e00;border-radius:0 10px 10px 0;color:#e0d8c8}
blockquote strong{color:#f54e00}
table{width:100%;border-collapse:collapse;margin:0 0 1.8em;font-size:.94rem;display:block;
  overflow-x:auto}
th,td{border:1px solid #2a2a33;padding:11px 14px;text-align:left;vertical-align:top}
th{background:#1c1a22;color:#f0dac0;font-weight:700}
tr:nth-child(even) td{background:rgba(255,255,255,.012)}
ul,ol{margin:0 0 1.3em;padding-left:1.3em}
li{margin:.34em 0}
hr{border:0;border-top:1px solid rgba(240,218,192,.10);margin:2.6em 0}
figure.d{margin:0 0 2em;padding:26px 20px;background:#131118;border:1px solid #2a2a33;
  border-radius:14px;overflow-x:auto;text-align:center}
figure.d svg{max-width:100%;height:auto}
.nav{display:flex;flex-wrap:wrap;gap:9px;margin:0 0 44px}
.nav a{padding:8px 15px;border:1px solid #2a2a33;border-radius:999px;background:#1a1820;
  font:600 13px/1 'JetBrains Mono',monospace;color:#c8c8d0;border-bottom:1px solid #2a2a33}
.nav a:hover{border-color:#f54e00;color:#f54e00}
.foot{margin-top:80px;padding-top:26px;border-top:1px solid rgba(240,218,192,.10);
  color:#86868f;font-size:.86rem}
@media (max-width:640px){.wrap{padding:44px 16px 80px}h1{font-size:1.9rem}}
"""


def build(system):
    src = os.path.join(HERE, system)
    docs = sorted(f for f in os.listdir(src) if re.match(r"^\d\d-.*\.md$", f))
    if not docs:
        raise SystemExit("no numbered docs in %s" % src)
    work = os.path.join(src, "_site")
    os.makedirs(work, exist_ok=True)

    nav, body = [], []
    readme = os.path.join(src, "README.md")
    if os.path.exists(readme):
        md = io.open(readme, encoding="utf-8").read()
        body.append('<section id="top">%s</section>' % render(md, mermaid_svgs(md, work, "readme")))
    for f in docs:
        md = io.open(os.path.join(src, f), encoding="utf-8").read()
        # the cross-doc links point at .md files that do not exist on this page
        md = re.sub(r"\]\((\d\d-[a-z-]+)\.md\)", r"](#\1)", md)
        anchor = f[:-3]
        title = re.search(r"^#\s+(.*)$", md, re.M)
        nav.append('<a href="#%s">%s</a>' % (anchor, html.escape(f[:2])))
        body.append('<section id="%s">%s</section>'
                    % (anchor, render(md, mermaid_svgs(md, work, anchor))))
        _ = title

    fonts = (font_face("JetBrains Mono", 400, "jetbrainsmono-400.woff2") +
             font_face("Inter", 400, "inter-500.woff2") +
             font_face("Inter", 700, "inter-800.woff2") +
             font_face("Inter", 800, "inter-900.woff2"))
    page = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>%s &middot; System Designs with Deva</title>"
            "<style>%s%s</style></head><body><div class=\"wrap\">"
            "<nav class=\"nav\"><a href=\"#top\">README</a>%s</nav>%s"
            "<div class=\"foot\">System Designs with Deva &middot; CC BY 4.0 &middot; "
            "self-contained: fonts embedded, diagrams pre-rendered, no network needed."
            "</div></div></body></html>"
            % (system, fonts, CSS, "".join(nav), "".join(body)))
    out = os.path.join(src, "index.html")
    io.open(out, "w", encoding="utf-8").write(page)
    print("%s/index.html  %.0f kB  ·  %d docs" % (system, os.path.getsize(out) / 1024.0,
                                                  len(docs) + 1))


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["video-player"]):
        build(s)
