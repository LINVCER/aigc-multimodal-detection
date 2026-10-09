package org.dromara;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.concurrent.TimeUnit;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.metrics.buffering.BufferingApplicationStartup;

/**
 * 启动程序
 *
 * @author Lion Li
 */

@SpringBootApplication(scanBasePackages = {"org.dromara", "com.paperaigc"})
public class DromaraApplication {

    public static void main(String[] args) {
        startRedisInWsl();
        SpringApplication application = new SpringApplication(DromaraApplication.class);
        application.setApplicationStartup(new BufferingApplicationStartup(2048));
        application.run(args);
        System.out.println("(♥◠‿◠)ﾉﾞ  RuoYi-Vue-Plus启动成功   ლ(´ڡ`ლ)ﾞ");
    }

    // 开发机用 WSL 跑 Redis，后端启动时顺手拉起，避免本地连不上 16379 直接崩
    private static void startRedisInWsl() {
        if (!System.getProperty("os.name", "").toLowerCase().contains("win")) {
            return;
        }
        try {
            exec("wsl", "-d", "Ubuntu", "-u", "root", "--", "systemctl", "start", "redis-server");
        } catch (Exception e) {
            System.out.println("[Redis] 拉起失败: " + e.getMessage());
            return;
        }
        for (int i = 0; i < 40; i++) {
            if (redisReady()) {
                System.out.println("[Redis] 已就绪 (127.0.0.1:16379)");
                return;
            }
            try {
                Thread.sleep(500);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }
        }
        System.out.println("[Redis] 等待超时，请确认 WSL 的 Ubuntu 实例已启动");
    }

    private static boolean redisReady() {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress("127.0.0.1", 16379), 500);
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    private static void exec(String... cmd) throws IOException, InterruptedException {
        Process p = new ProcessBuilder(cmd).redirectErrorStream(true).start();
        if (!p.waitFor(30, TimeUnit.SECONDS)) {
            p.destroyForcibly();
        }
    }

}