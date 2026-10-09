package com.paperaigc.detect.common.util;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Locale;
import java.util.UUID;

/**
 * 密码 hash / 校验 / 临时密码生成（salt + SHA-256；课题期无 spring-security-crypto，生产切 BCrypt）
 */
public final class PasswordHasher {

    private static final SecureRandom RANDOM = new SecureRandom();
    private static final char[] TEMP_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789".toCharArray();

    private PasswordHasher() {}

    /**
     * 生成存储格式 {@code salt:sha256(salt + raw)}
     * @param raw 明文
     * @return 可直接落库的 hash
     */
    public static String hash(String raw) {
        String salt = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        return salt + ":" + sha256(salt + raw);
    }

    /**
     * 校验明文是否匹配存储 hash
     * @param raw 明文
     * @param stored 库里的 salt:hash
     * @return 是否匹配
     */
    public static boolean verify(String raw, String stored) {
        if (raw == null || stored == null || !stored.contains(":")) return false;
        String[] parts = stored.split(":", 2);
        return parts.length == 2 && sha256(parts[0] + raw).equals(parts[1]);
    }

    /**
     * 生成一次性临时密码：10 位，去掉易混字符，保证同时含字母和数字
     * @return 临时密码明文
     */
    public static String tempPassword() {
        StringBuilder sb = new StringBuilder(10);
        for (int i = 0; i < 8; i++) sb.append(TEMP_CHARS[RANDOM.nextInt(TEMP_CHARS.length)]);
        sb.append((char) ('2' + RANDOM.nextInt(8)));
        sb.append((char) ('a' + RANDOM.nextInt(26)));
        return sb.toString();
    }

    private static String sha256(String s) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) sb.append(String.format(Locale.ROOT, "%02x", b));
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 不可用", e);
        }
    }
}
