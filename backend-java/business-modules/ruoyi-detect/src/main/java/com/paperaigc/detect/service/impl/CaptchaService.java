package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.domain.vo.CaptchaVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import javax.imageio.ImageIO;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 图形验证码（内存存储，5 分钟有效，一次性）
 *
 * <p>纯 JDK + java.awt，无第三方依赖；无头环境已在 main 启动时置 java.awt.headless=true。</p>
 */
@Slf4j
@Service
public class CaptchaService {

    private static final int TTL_MS = 5 * 60 * 1000;
    private static final int WIDTH = 120;
    private static final int HEIGHT = 44;
    private static final char[] CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789".toCharArray();
    private static final SecureRandom RANDOM = new SecureRandom();

    private final Map<String, Entry> store = new ConcurrentHashMap<>();

    /** 生成验证码，返回 id + base64 图片；同时惰性清理过期条目 */
    public CaptchaVO generate() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 4; i++) sb.append(CHARS[RANDOM.nextInt(CHARS.length)]);
        String code = sb.toString();
        String id = UUID.randomUUID().toString().replace("-", "");
        store.put(id, new Entry(code, System.currentTimeMillis() + TTL_MS));
        cleanExpired();
        return CaptchaVO.builder().captchaId(id).imageBase64(render(code)).build();
    }

    /** 校验并消费验证码（一次性）；不区分大小写 */
    public boolean verify(String captchaId, String captchaCode) {
        if (captchaId == null || captchaCode == null) return false;
        Entry e = store.remove(captchaId);
        if (e == null || e.expiresAt < System.currentTimeMillis()) return false;
        return e.code.equalsIgnoreCase(captchaCode.trim());
    }

    private void cleanExpired() {
        if (store.size() < 1000) return;
        long now = System.currentTimeMillis();
        store.entrySet().removeIf(en -> en.getValue().expiresAt < now);
    }

    /** 画 4 位验证码 + 干扰线，输出 data URI */
    private String render(String code) {
        BufferedImage img = new BufferedImage(WIDTH, HEIGHT, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        try {
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.setColor(new Color(0xF6, 0xF8, 0xF8));
            g.fillRect(0, 0, WIDTH, HEIGHT);
            // 干扰线
            g.setStroke(new BasicStroke(1.2f));
            for (int i = 0; i < 5; i++) {
                g.setColor(new Color(60 + RANDOM.nextInt(140), 60 + RANDOM.nextInt(140), 60 + RANDOM.nextInt(140), 140));
                g.drawLine(RANDOM.nextInt(WIDTH), RANDOM.nextInt(HEIGHT), RANDOM.nextInt(WIDTH), RANDOM.nextInt(HEIGHT));
            }
            // 字符
            g.setFont(new Font("SansSerif", Font.BOLD, 26));
            for (int i = 0; i < code.length(); i++) {
                g.setColor(new Color(RANDOM.nextInt(80), RANDOM.nextInt(120), RANDOM.nextInt(160)));
                g.drawString(String.valueOf(code.charAt(i)), 18 + i * 24, 30 + RANDOM.nextInt(6));
            }
        } finally {
            g.dispose();
        }
        try (ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            ImageIO.write(img, "png", out);
            return "data:image/png;base64," + Base64.getEncoder().encodeToString(out.toByteArray());
        } catch (Exception e) {
            throw new IllegalStateException("验证码图片生成失败", e);
        }
    }

    private record Entry(String code, long expiresAt) {}
}
