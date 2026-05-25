"""
同形字/零宽字符 标准化防御

针对 SilverSpeak (ACL 2025) 等字符级攻击的防御:
  1. 同形字符 → 标准字符 (如 西里尔 'а' → 拉丁 'a')
  2. 零宽字符移除 (U+200B, U+200C, U+200D, U+FEFF)
  3. 全角/半角统一
  4. 不可见控制字符清理

参考: Unicode Confusables (UTR#39)
"""

import re
import unicodedata


# 零宽字符 + 不可见字符
ZERO_WIDTH_CHARS = {
    0x200B,  # ZERO WIDTH SPACE
    0x200C,  # ZERO WIDTH NON-JOINER
    0x200D,  # ZERO WIDTH JOINER
    0xFEFF,  # ZERO WIDTH NO-BREAK SPACE (BOM)
    0x00AD,  # SOFT HYPHEN
    0x2060,  # WORD JOINER
    0x2061,  # FUNCTION APPLICATION
    0x2062,  # INVISIBLE TIMES
    0x2063,  # INVISIBLE SEPARATOR
    0x2064,  # INVISIBLE PLUS
    0x180E,  # MONGOLIAN VOWEL SEPARATOR
    0x034F,  # COMBINING GRAPHEME JOINER
    0x061C,  # ARABIC LETTER MARK
}

# 常见同形字符映射 (Latin/Cyrillic/ Greek → ASCII)
# 扩展自 Unicode Consortium confusables.txt
HOMOGLYPH_MAP = {
    # Cyrillic → Latin
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p',
    'с': 'c', 'у': 'y', 'х': 'x', 'ѕ': 's',
    'Ԍ': 'G', 'Ԑ': 'G', 'Ԓ': 'H', 'Ԕ': 'I',
    # Greek → Latin
    'Α': 'A', 'Β': 'B', 'Ε': 'E', 'Ζ': 'Z',
    'Η': 'H', 'Ι': 'I', 'Κ': 'K', 'Μ': 'M',
    'Ν': 'N', 'Ο': 'O', 'Ρ': 'P', 'Τ': 'T',
    'Υ': 'Y', 'Χ': 'X', 'ο': 'o', 'ρ': 'p',
    'υ': 'u', 'ν': 'v', 'ι': 'i', 'κ': 'k',
    # Full-width → ASCII
    'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E',
    'ａ': 'a', 'ｂ': 'b', 'ｃ': 'c', 'ｄ': 'd', 'ｅ': 'e',
    '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
    # Full-width punctuation → half-width
    '，': ',', '．': '.', '：': ':', '；': ';',
    '（': '(', '）': ')', '「': '"', '」': '"',
    # Mathematical symbols → Latin
    'ℬ': 'B', 'ℰ': 'E', 'ℱ': 'F', 'ℋ': 'H',
    'ℐ': 'I', 'ℒ': 'L', 'ℳ': 'M', 'ℙ': 'P',
    'ℚ': 'Q', 'ℝ': 'R', 'ℤ': 'Z',
    # Modifier letters
    'ʷ': 'w', 'ʹ': "'", 'ˈ': "'",
    # Other confusables
    '̣': '', '̱': '', '⃟': '',  # combining marks
}


def normalize_text(text: str) -> tuple[str, list[str]]:
    """
    标准化文本用于防御检测

    返回: (normalized_text, warnings)
      - normalized_text: 清理后的文本
      - warnings: 检测到的异常描述列表
    """
    warnings = []
    original_len = len(text)

    # 1. 移除零宽字符
    cleaned = []
    for ch in text:
        if ord(ch) in ZERO_WIDTH_CHARS:
            continue
        cleaned.append(ch)
    cleaned_text = ''.join(cleaned)

    if len(cleaned_text) < original_len:
        warnings.append(f"检测到零宽字符 ({original_len - len(cleaned_text)}个)，已清理")

    # 2. 同形字符替换
    normalized = []
    replaced_count = 0
    for ch in cleaned_text:
        if ch in HOMOGLYPH_MAP:
            normalized.append(HOMOGLYPH_MAP[ch])
            replaced_count += 1
        else:
            normalized.append(ch)
    text = ''.join(normalized)

    if replaced_count > 0:
        # 计算替换比例
        ratio = replaced_count / max(len(text), 1) * 100
        warnings.append(f"检测到同形字符替换 ({replaced_count}个, {ratio:.1f}%)，已还原")

    # 3. 全角数字/字母 → 半角
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:  # 全角空格
            result.append(' ')
        else:
            result.append(ch)
    text = ''.join(result)

    # 4. NFC 标准化 (组合字符)
    text = unicodedata.normalize('NFC', text)

    return text, warnings


def has_evasion_attempts(text: str) -> dict:
    """检查文本是否包含已知的对抗逃逸手段"""
    result = {
        "has_zero_width": False,
        "has_homoglyphs": False,
        "has_fullwidth_anomaly": False,
        "details": [],
    }

    for ch in text:
        if ord(ch) in ZERO_WIDTH_CHARS:
            result["has_zero_width"] = True
            result["details"].append(f"零宽字符 U+{ord(ch):04X}")
            break

    for ch in text:
        if ch in HOMOGLYPH_MAP:
            result["has_homoglyphs"] = True
            result["details"].append(f"同形字符: {ch!r} (U+{ord(ch):04X}) -> {HOMOGLYPH_MAP[ch]!r}")
            break

    # 全角异常: 超过 5% 字符是全角 ASCII
    fullwidth_count = sum(1 for ch in text if 0xFF01 <= ord(ch) <= 0xFF5E)
    if fullwidth_count / max(len(text), 1) > 0.05:
        result["has_fullwidth_anomaly"] = True
        result["details"].append(f"异常全角字符比例: {fullwidth_count}/{len(text)}")

    return result
