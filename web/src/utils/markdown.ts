/**
 * 极简白名单 Markdown 渲染（chat-ui-redesign §3 ①）：不引第三方库，只认助手会输出的子集
 *
 * 支持：# ## ### 标题、**粗体**、*斜体*、`行内代码`、``` 代码块、- / 1. 列表、> 引用、段落与换行
 * 先整体 HTML 转义，再按行解析，所以不可能注入标签；链接刻意不渲染（助手规则里不带链接）
 */

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function inline(s: string): string {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')
}

export function renderMarkdown(src: string): string {
  if (!src) return ''
  const lines = escapeHtml(src.replace(/\r\n?/g, '\n')).split('\n')
  const out: string[] = []
  let i = 0
  let para: string[] = []
  const flushPara = () => {
    if (para.length) { out.push(`<p>${para.map(inline).join('<br>')}</p>`); para = [] }
  }
  while (i < lines.length) {
    const line = lines[i]
    // 代码块
    if (/^```/.test(line)) {
      flushPara()
      const buf: string[] = []
      i++
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++ }
      i++
      out.push(`<pre><code>${buf.join('\n')}</code></pre>`)
      continue
    }
    // 标题
    const h = /^(#{1,3})\s+(.+)$/.exec(line)
    if (h) { flushPara(); out.push(`<h${h[1].length + 3}>${inline(h[2])}</h${h[1].length + 3}>`); i++; continue }
    // 无序 / 有序列表
    if (/^\s*[-*•]\s+/.test(line) || /^\s*\d+[.)]\s+/.test(line)) {
      flushPara()
      const ordered = /^\s*\d+[.)]\s+/.test(line)
      const items: string[] = []
      while (i < lines.length && (ordered ? /^\s*\d+[.)]\s+/.test(lines[i]) : /^\s*[-*•]\s+/.test(lines[i]))) {
        items.push(`<li>${inline(lines[i].replace(ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*•]\s+/, ''))}</li>`)
        i++
      }
      out.push(ordered ? `<ol>${items.join('')}</ol>` : `<ul>${items.join('')}</ul>`)
      continue
    }
    // 引用
    if (/^&gt;\s?/.test(line)) {
      flushPara()
      const buf: string[] = []
      while (i < lines.length && /^&gt;\s?/.test(lines[i])) { buf.push(inline(lines[i].replace(/^&gt;\s?/, ''))); i++ }
      out.push(`<blockquote>${buf.join('<br>')}</blockquote>`)
      continue
    }
    // 空行分段
    if (!line.trim()) { flushPara(); i++; continue }
    para.push(line)
    i++
  }
  flushPara()
  return out.join('')
}
