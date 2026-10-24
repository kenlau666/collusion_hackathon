// Render/parse the Mermaid source for QA only. Never writes the user's PNG.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('/Users/kenlau/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async () => {
  const root = path.resolve(__dirname, '../..');
  const source = fs.readFileSync(path.join(root, 'mermaid-diagram.mmd'), 'utf8');
  const png = path.join(root, 'mermaid-diagram.png');
  const before = crypto.createHash('sha256').update(fs.readFileSync(png)).digest('hex');
  const options = { headless: true };
  if (!fs.existsSync(chromium.executablePath()) && fs.existsSync('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')) {
    options.channel = 'chrome';
  }
  const browser = await chromium.launch(options);
  try {
    const page = await browser.newPage({ viewport: { width: 1800, height: 1400 } });
    await page.setContent('<!doctype html><html><body style="margin:0;font-family:Arial"></body></html>');
    const result = await Promise.race([
      page.evaluate(async (text) => {
        const { default: mermaid } = await import('https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.esm.min.mjs');
        mermaid.initialize({ startOnLoad: false, theme: 'neutral', fontFamily: 'Arial', securityLevel: 'strict', flowchart: { useMaxWidth: false } });
        const parsed = await mermaid.parse(text);
        const { svg } = await mermaid.render('recovery_architecture_validation', text);
        document.body.innerHTML = svg;
        const root = document.querySelector('svg');
        const bounds = root.getBoundingClientRect();
        const clipped = [...root.querySelectorAll('g.node')].filter(node => {
          const r = node.getBoundingClientRect();
          return r.left < bounds.left - 1 || r.right > bounds.right + 1 || r.top < bounds.top - 1 || r.bottom > bounds.bottom + 1;
        }).map(n => n.id);
        return { diagramType: parsed.diagramType, node_count: root.querySelectorAll('g.node').length,
                 edge_count: root.querySelectorAll('.edgePath, .flowchart-link').length,
                 viewBox: root.getAttribute('viewBox'), nodes_outside_svg: clipped,
                 labels: [...root.querySelectorAll('g.node .nodeLabel')].map(n => n.textContent.trim()) };
      }, source),
      new Promise((_, reject) => setTimeout(() => reject(new Error('Mermaid validation exceeded 45 seconds')), 45000).unref())
    ]);
    if (result.diagramType !== 'flowchart-v2' || result.nodes_outside_svg.length || result.node_count < 20) {
      throw new Error('Diagram parse/layout check failed: ' + JSON.stringify(result));
    }
    const after = crypto.createHash('sha256').update(fs.readFileSync(png)).digest('hex');
    if (before !== after) throw new Error('Unexpected PNG change');
    const output = { mermaid_version: '12.2.0', source_sha256: crypto.createHash('sha256').update(source).digest('hex'),
                     png_unchanged: true, ...result };
    fs.writeFileSync(path.join(__dirname, 'diagram_validation.json'), JSON.stringify(output, null, 2) + '\n');
    console.log(JSON.stringify({ status: 'passed', mermaid_version: output.mermaid_version,
                               node_count: result.node_count, nodes_outside_svg: result.nodes_outside_svg,
                               png_unchanged: true }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.stack || String(error)); process.exitCode = 1; });
