package com.paperaigc.detect.common.util;

import java.util.Map;

/**
 * 参数取值工具 —— 从原来各 Controller 里散落的 str/numLong 里抽出来复用
 *
 * <p>只处理 null 与类型转换的边界，不做业务判空。</p>
 */
public final class ParamUtils {

    private ParamUtils() {}

    /** 从 Map 取 String，null 返回 null */
    public static String str(Map<String, Object> m, String key) {
        Object v = m == null ? null : m.get(key);
        return v == null ? null : String.valueOf(v);
    }

    /** 从 Map 取 String，null 返回 defaultVal */
    public static String str(Map<String, Object> m, String key, String defaultVal) {
        String v = str(m, key);
        return v == null ? defaultVal : v;
    }

    /** Object 转 Long，兼容 Number / 数字字符串；不可转返回 null */
    public static Long toLong(Object o) {
        if (o == null) return null;
        if (o instanceof Number n) return n.longValue();
        try { return Long.parseLong(String.valueOf(o)); }
        catch (NumberFormatException e) { return null; }
    }

    /** Object 转 Integer；不可转返回 null */
    public static Integer toInt(Object o) {
        if (o == null) return null;
        if (o instanceof Number n) return n.intValue();
        try { return Integer.parseInt(String.valueOf(o)); }
        catch (NumberFormatException e) { return null; }
    }

    /** Object 转 Double；不可转返回 null */
    public static Double toDouble(Object o) {
        if (o == null) return null;
        if (o instanceof Number n) return n.doubleValue();
        try { return Double.parseDouble(String.valueOf(o)); }
        catch (NumberFormatException e) { return null; }
    }

    /** 大小写不敏感包含（用于列表关键字过滤） */
    public static boolean containsIgnoreCase(String s, String kw) {
        return s != null && kw != null && s.toLowerCase().contains(kw.toLowerCase());
    }

    public static boolean isBlank(String s) { return s == null || s.isBlank(); }
}
