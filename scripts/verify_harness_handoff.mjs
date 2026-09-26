// Exercise the installed harness MCP bridge against a real procurement endpoint,
// then hand its selected reference to the real APC connector with a local portal
// fixture. No APC account is used and no supplier interest is registered.
// node scripts/verify_harness_handoff.mjs HARNESS_DIR BASE_URL REPORT_PATH
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { createServer } from 'node:http'
import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const [harnessArg, endpoint, reportPath] = process.argv.slice(2)
assert(harnessArg && endpoint && reportPath, 'Expected HARNESS_DIR BASE_URL REPORT_PATH')
await mkdir(dirname(resolve(reportPath)), { recursive: true })
const harness = resolve(harnessArg)
const requireMcp = createRequire(join(harness, 'packages/mcp/mcp-client/package.json'))
const requireTools = createRequire(join(harness, 'packages/core/tools/package.json'))
const load = (resolver, name) => import(pathToFileURL(resolver.resolve(name)).href)
const { Context } = await load(requireMcp, '@deepseek-ai/cordis')
const { default: ToolRuntime } = await load(requireMcp, '@deepseek-ai/dsh-tools')
const { default: SystemPrompt } = await load(requireTools, '@deepseek-ai/dsh-system-prompt')
const { CallId } = await load(requireMcp, '@deepseek-ai/dsh-llm')
const { apply } = await load(requireMcp, '@deepseek-ai/dsh-mcp-client')
const home = await mkdtemp(join(tmpdir(), 'wa-harness-acceptance-'))
let authorized = false
const portal = createServer((request, response) => {
  if (request.url.startsWith('/file/')) {
    response.writeHead(200, { 'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename="fixture.pdf"' })
    response.end(`%PDF-1.4\n${request.url}\n%%EOF\n`)
  } else {
    response.writeHead(200, { 'Content-Type': 'text/html' })
    response.end(authorized
      ? '<button>Account</button><table>' + [0, 1].map(i => `<tr><td>Fixture document ${i}</td><td><button onclick="location.href='/file/${i}'">Download</button></td></tr>`).join('') + '</table>'
      : '<h1>Supplier sign in</h1>')
  }
})
await new Promise(resolve => portal.listen(0, '127.0.0.1', resolve))
const ctx = new Context()
const report = { endpoint, document_source: 'local portal fixture, not live APC',
  harness_revision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: harness, encoding: 'utf8' }).trim(),
  harness_has_local_changes: Boolean(execFileSync('git', ['status', '--porcelain'], { cwd: harness, encoding: 'utf8' }).trim()),
  calls: [] }
try {
  await ctx.plugin(SystemPrompt)
  await ctx.plugin(ToolRuntime)
  await apply(ctx, { transport: 'streamable-http', serverName: 'workspace_alberta',
    url: endpoint.replace(/\/$/, '') + '/mcp', headers: {}, toolCallTimeoutMs: 60_000,
    failOnStartupError: true, reconnect: { enabled: false } })
  const call = async (name, args) => {
    const started = performance.now()
    const result = await ctx.tools.execute({ signal: AbortSignal.timeout(60_000),
      callId: CallId(`acceptance-${report.calls.length}`), name, arguments: args })
    assert.equal(result.isError, false, JSON.stringify(result.content))
    report.calls.push({ name, seconds: Math.round((performance.now() - started) / 10) / 100 })
    console.log(`Verified harness call ${name}`)
    return result
  }
  const search = await call('mcp__workspace_alberta__search_opportunities', {
    source: 'alberta', keywords: 'data platforms and software engineering', limit: 5 })
  const data = search.value.structuredContent
  assert(data.opportunities.length > 0)
  const rendered = search.content.filter(c => c.type === 'text').map(c => c.text).join('\n')
  for (const warning of data.warnings) assert(rendered.includes(warning))
  report.warnings = data.warnings
  const reference = data.opportunities[0].reference
  report.reference = reference
  const details = await call('mcp__workspace_alberta__get_opportunity_details', { reference })
  assert(JSON.stringify(details.content).includes(reference))
  await apply(ctx, { transport: 'stdio', serverName: 'apc_local',
    command: join(harness, 'integrations/apc/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'),
    args: [join(harness, 'integrations/apc/example.py'), '--server', home, String(portal.address().port)],
    cwd: harness, env: {}, toolCallTimeoutMs: 60_000, failOnStartupError: true,
    reconnect: { enabled: false } })
  const decode = result => JSON.parse(result.value.content.find(c => c.type === 'text').text)
  const handoff = decode(await call('mcp__apc_local__apc_download', { opportunity: reference }))
  assert.equal(handoff.status, 'sign_in_required')
  assert.equal(handoff.reference, reference)
  authorized = true
  const receipt = decode(await call('mcp__apc_local__apc_resume', {}))
  assert.equal(receipt.status, 'downloaded')
  assert.equal(receipt.reference, reference)
  assert.equal(receipt.complete, true)
  assert.equal(receipt.documents.length, 2)
  for (const document of receipt.documents) {
    const bytes = await readFile(document.path)
    assert.equal(bytes.length, document.bytes)
    assert.equal(createHash('sha256').update(bytes).digest('hex'), document.sha256)
  }
  report.receipt = receipt
} finally {
  await ctx.fiber.dispose()
  await new Promise(resolve => portal.close(resolve))
}
for (const document of report.receipt.documents) await readFile(document.path)
report.documents_survive_shutdown = true
await writeFile(reportPath, JSON.stringify(report, null, 2) + '\n')
console.log(`Harness handoff evidence: ${reportPath}`)
