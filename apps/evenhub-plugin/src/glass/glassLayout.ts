export const GLASS_LINE_WIDTH = 48

export function glassTime(): string {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
}

export function compactGlassText(value: string, max = 34): string {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`
}

export function centerLine(value: string, width = GLASS_LINE_WIDTH): string {
  const text = compactGlassText(value, width)
  const left = Math.max(0, Math.floor((width - text.length) / 2))
  return `${' '.repeat(left)}${text}`
}

export function leftRightLine(left: string, right: string, width = GLASS_LINE_WIDTH): string {
  const l = compactGlassText(left, width)
  const r = compactGlassText(right, width)
  const combined = l.length + r.length
  if (combined >= width) return l + ' ' + r
  return `${l}${' '.repeat(1)}${r}`
}

export function divider(width = 48): string {
  return '━'.repeat(width)
}

export function wrapGlassLines(value: string, width = 48, maxLines = 6): string[] {
  const lines: string[] = []
  let current = ''
  for (const char of value.replace(/\r/g, '')) {
    if (char === '\n' || current.length >= width) {
      lines.push(current)
      current = char === '\n' ? '' : char
    } else {
      current += char
    }
    if (lines.length >= maxLines) break
  }
  if (current && lines.length < maxLines) lines.push(current)
  return lines.length ? lines : ['']
}

export function glassHeader(title: string, battery: string): string {
  return leftRightLine(glassTime(), compactGlassText(battery, 9))
}

export function glassFooter(text: string): string {
  return centerLine(`R1 ${text}`)
}
