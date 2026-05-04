import { existsSync } from 'node:fs'
import { readdir, readFile, stat } from 'node:fs/promises'
import { resolve } from 'node:path'

export interface MemoryHit {
  path: string
  title: string
  snippet: string
  score: number
  updatedAt?: string
}

export interface MemorySearchResult {
  query: string
  root: string
  hits: MemoryHit[]
}

const allowedExtensions = new Set(['.md', '.txt', '.json'])
const blockedNamePattern = /(env|key|token|secret|credential|webhook|pem|p12)/i

export function getMemoryRoot(env: NodeJS.ProcessEnv = process.env): string {
  return resolve(env.G2_MEMORY_ROOT ?? 'data/remote-memory-cache')
}

export async function searchMemory(
  query: string,
  options: { root?: string; limit?: number; maxFiles?: number } = {},
): Promise<MemorySearchResult> {
  const root = resolve(options.root ?? getMemoryRoot())
  if (!existsSync(root)) return { query, root, hits: [] }

  const terms = tokenize(query)
  if (terms.length === 0) return { query, root, hits: [] }

  const files = await listMemoryFiles(root, options.maxFiles ?? 4000)
  const hits: MemoryHit[] = []

  for (const file of files) {
    const content = await readFile(file, 'utf8').catch(() => '')
    if (!content.trim()) continue

    const score = scoreContent(content, file, terms)
    if (score <= 0) continue

    const fileStat = await stat(file).catch(() => undefined)
    hits.push({
      path: file.replace(`${root}/`, ''),
      title: inferTitle(content, file),
      snippet: buildSnippet(content, terms),
      score,
      updatedAt: fileStat?.mtime.toISOString(),
    })
  }

  return {
    query,
    root,
    hits: hits.sort((a, b) => b.score - a.score).slice(0, options.limit ?? 6),
  }
}

export function formatMemoryContext(hits: MemoryHit[], maxChars = 2600): string {
  const blocks: string[] = []
  let used = 0

  for (const hit of hits) {
    const block = [
      `来源：${hit.path}`,
      `标题：${hit.title}`,
      `内容：${hit.snippet}`,
    ].join('\n')

    if (used + block.length > maxChars) break
    blocks.push(block)
    used += block.length
  }

  return blocks.join('\n\n')
}

async function listMemoryFiles(root: string, maxFiles: number): Promise<string[]> {
  const output: string[] = []

  async function walk(dir: string): Promise<void> {
    if (output.length >= maxFiles) return
    const entries = await readdir(dir, { withFileTypes: true }).catch(() => [])

    for (const entry of entries) {
      if (output.length >= maxFiles) return
      if (entry.name.startsWith('.') || blockedNamePattern.test(entry.name)) continue

      const fullPath = resolve(dir, entry.name)
      if (entry.isDirectory()) {
        await walk(fullPath)
        continue
      }

      if (!entry.isFile()) continue
      const ext = entry.name.slice(entry.name.lastIndexOf('.')).toLowerCase()
      if (allowedExtensions.has(ext)) output.push(fullPath)
    }
  }

  await walk(root)
  return output
}

function tokenize(value: string): string[] {
  const compact = value
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}\u4e00-\u9fff]+/gu, ' ')
    .trim()

  const rawTerms = compact.split(/\s+/).filter(Boolean)
  const chineseTerms = Array.from(compact.matchAll(/[\u4e00-\u9fff]{2,}/g)).flatMap((match) =>
    expandChineseTerm(match[0]),
  )

  return Array.from(new Set([...rawTerms, ...chineseTerms])).filter((term) => term.length >= 2)
}

function expandChineseTerm(value: string): string[] {
  const terms = [value]
  const maxWindow = Math.min(4, value.length)

  for (let size = 2; size <= maxWindow; size += 1) {
    for (let index = 0; index <= value.length - size; index += 1) {
      terms.push(value.slice(index, index + size))
    }
  }

  return terms
}

function scoreContent(content: string, file: string, terms: string[]): number {
  const haystack = `${file}\n${content}`.toLowerCase()
  let score = 0

  for (const term of terms) {
    const escaped = escapeRegExp(term.toLowerCase())
    const matches = haystack.match(new RegExp(escaped, 'g'))?.length ?? 0
    score += Math.min(matches, 8) * (term.length >= 4 ? 2 : 1)
  }

  if (/v6\.5|交易|机器人|openclaw|天禄|even|g2/i.test(file)) score += 2
  return score
}

function inferTitle(content: string, file: string): string {
  const heading = content.match(/^#{1,3}\s+(.+)$/m)?.[1]?.trim()
  if (heading) return heading.slice(0, 80)
  return file.split('/').pop()?.replace(/\.(md|txt|json)$/i, '') ?? 'memory'
}

function buildSnippet(content: string, terms: string[]): string {
  const normalized = content.replace(/\s+/g, ' ').trim()
  const index = terms
    .map((term) => normalized.toLowerCase().indexOf(term.toLowerCase()))
    .filter((position) => position >= 0)
    .sort((a, b) => a - b)[0]

  const start = Math.max(0, (index ?? 0) - 180)
  return normalized.slice(start, start + 520)
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
