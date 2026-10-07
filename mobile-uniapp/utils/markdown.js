/**
 * 极简白名单 Markdown 渲染（与 web/src/utils/markdown.ts 同一套规则），输出给 <rich-text :nodes>
 * 支持：# ## ### 标题、**粗体**、*斜体*、`行内代码`、``` 代码块、- / 1. 列表、> 引用、段落与换行
 * 先整体转义再解析，不会注入标签；rich-text 支持 p/strong/em/code/pre/ul/ol/li/h4-h6/blockquote/br
 */

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function inline(s) {
  return s
    .replace(/`([^`]+)`/g, '<code class="md-code">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')
}

export function renderMarkdown(src) {
  if (!src) return ''
  const lines = escapeHtml(String(src).replace(/\r\n?/g, '\n')).split('\n')
  const out = []
  let i = 0
  let para = []
  const flushPara = () => {
    if (para.length) { out.push(`<p class="md-p">${para.map(inline).join('<br/>')}</p>`); para = [] }
  }
  while (i < lines.length) {
    const line = lines[i]
    if (/^```/.test(line)) {
      flushPara()
      const buf = []
      i++
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++ }
      i++
      out.push(`<pre class="md-pre">${buf.join('\n')}</pre>`)
      continue
    }
    const h = /^(#{1,3})\s+(.+)$/.exec(line)
    if (h) { flushPara(); out.push(`<h${h[1].length + 3} class="md-h">${inline(h[2])}</h${h[1].length + 3}>`); i++; continue }
    if (/^\s*[-*•]\s+/.test(line) || /^\s*\d+[.)]\s+/.test(line)) {
      flushPara()
      const ordered = /^\s*\d+[.)]\s+/.test(line)
      const items = []
      while (i < lines.length && (ordered ? /^\s*\d+[.)]\s+/.test(lines[i]) : /^\s*[-*•]\s+/.test(lines[i]))) {
        items.push(`<li class="md-li">${inline(lines[i].replace(ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*•]\s+/, ''))}</li>`)
        i++
      }
      out.push(ordered ? `<ol class="md-list">${items.join('')}</ol>` : `<ul class="md-list">${items.join('')}</ul>`)
      continue
    }
    if (/^&gt;\s?/.test(line)) {
      flushPara()
      const buf = []
      while (i < lines.length && /^&gt;\s?/.test(lines[i])) { buf.push(inline(lines[i].replace(/^&gt;\s?/, ''))); i++ }
      out.push(`<blockquote class="md-quote">${buf.join('<br/>')}</blockquote>`)
      continue
    }
    if (!line.trim()) { flushPara(); i++; continue }
    para.push(line)
    i++
  }
  flushPara()
  return out.join('')
}
