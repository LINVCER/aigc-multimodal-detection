package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.service.IStorageService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

/**
 * 本地文件系统存储实现
 *
 * <p>用户诊断 #6 决策：不装 MinIO，用本地 FS 兜底。
 * 路径规范：{@code {storage-root}/uploads/{yyyyMM}/{taskId}.{ext}}</p>
 *
 * <p>切换到 MinIO 只要新增 MinioStorageService @Primary 顶替此 bean 即可，业务代码零改动。</p>
 */
@Slf4j
@Service
public class LocalFileSystemStorageService implements IStorageService {

    /** 存储根目录；默认工作目录下 storage，可通过 application-*.yml 覆盖 */
    @Value("${platform.storage.local-root:./storage}")
    private String storageRoot;

    private static final DateTimeFormatter MONTH_FMT = DateTimeFormatter.ofPattern("yyyyMM");

    @Override
    public String save(MultipartFile file, long taskId) {
        String ext = extractExt(file.getOriginalFilename());
        String monthDir = LocalDate.now().format(MONTH_FMT);
        String relative = "uploads/" + monthDir + "/" + taskId + (ext.isEmpty() ? "" : "." + ext);
        Path absolute = Paths.get(storageRoot).resolve(relative);
        try {
            Files.createDirectories(absolute.getParent());
            file.transferTo(absolute.toFile());
            log.info("stored file taskId={} path={} size={}B", taskId, relative, file.getSize());
            return relative;
        } catch (IOException e) {
            log.error("save file failed taskId={}", taskId, e);
            throw new BizException(ErrorCode.SERVER_ERROR, "文件保存失败");
        }
    }

    @Override
    public boolean exists(String path) {
        return path != null && Files.exists(Paths.get(storageRoot).resolve(path));
    }

    @Override
    public boolean delete(String path) {
        if (path == null) return false;
        try { return Files.deleteIfExists(Paths.get(storageRoot).resolve(path)); }
        catch (IOException e) { log.warn("delete file failed path={}", path, e); return false; }
    }

    private String extractExt(String filename) {
        if (filename == null) return "";
        int dot = filename.lastIndexOf('.');
        if (dot < 0 || dot >= filename.length() - 1) return "";
        return filename.substring(dot + 1).toLowerCase();
    }
}
