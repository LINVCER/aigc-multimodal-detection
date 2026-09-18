/**
 * 中文短文本 diff：按字符切分做 LCS，输出 [{type: 'equal'|'add'|'remove', text}]
 * 用于原文↔改写对比高亮。段落级别（几百字）足够快，无需引入 diff 库。
 *
 * @param {string} a 原文
 * @param {string} b 改写后
 * @returns 分块结果数组
 */
export function diffChars(a, b) {
  const m = a.length
  const n = b.length
  if (m === 0) return b ? [{ type: 'add', text: b }] : []
  if (n === 0) return [{ type: 'remove', text: a }]

  // LCS 长度表
  const dp = Array.from({ length: m + 1 }, () => new Int32Array(n + 1))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) dp[i][j] = dp[i - 1][j - 1] + 1
      else dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }

  // 回溯生成分块
  const out = []
  let i = m, j = n
  const push = (type, ch) => {
    const last = out[out.length - 1]
    if (last && last.type === type) last.text = ch + last.text
    else out.push({ type, text: ch })
  }
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) { push('equal', a[i - 1]); i--; j-- }
    else if (dp[i - 1][j] >= dp[i][j - 1]) { push('remove', a[i - 1]); i-- }
    else { push('add', b[j - 1]); j-- }
  }
  while (i > 0) { push('remove', a[--i + 1 - 1]); }
  while (j > 0) { push('add',    b[--j + 1 - 1]); }

  return out.reverse()
}
