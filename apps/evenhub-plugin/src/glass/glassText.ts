const MAX_G2_LINES = 10
const MAX_G2_CHARS = 430
const MAX_LINE_CHARS = 48

export function sanitizeForG2Text(value: string, options: { maxLines?: number; maxChars?: number } = {}): string {
  const maxLines = options.maxLines ?? MAX_G2_LINES
  const maxChars = options.maxChars ?? MAX_G2_CHARS
  const normalized = value
    .replace(/\r/g, '')
    .replace(/[◆◇▣▱◌◎]/g, (match) => match)
    .split('\n')
    .flatMap((line) => wrapLine(line.trimEnd(), MAX_LINE_CHARS))
    .slice(0, maxLines)
    .join('\n')
  return normalized.slice(0, maxChars)
}

export function compactForG2(value: string, max = 48): string {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`
}

export function progressBar(value: number, total: number, width = 10): string {
  const safeTotal = Math.max(1, total)
  const filled = Math.max(0, Math.min(width, Math.round((value / safeTotal) * width)))
  return `${'▰'.repeat(filled)}${'▱'.repeat(width - filled)}`
}

function wrapLine(line: string, width: number): string[] {
  if (line.length <= width) return [line]
  const result: string[] = []
  let current = ''
  for (const char of line) {
    if (current.length >= width) {
      result.push(current)
      current = char
    } else {
      current += char
    }
  }
  if (current) result.push(current)
  return result
}
