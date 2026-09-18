package com.paperaigc.detect.service;

import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;

/**
 * 文件存储抽象（对应用户诊断 #6 · MinIO 未用）
 *
 * <p>当前 LocalFileSystemStorageService 走本地 FS（storage/uploads/{yyyymm}/{taskId}.{ext}），
 * 未来切 MinIO / OSS 只换实现，业务代码不感知。</p>
 */
public interface IStorageService {

    /**
     * 保存上传文件；生成的相对路径回填到 DetectTask.filePath
     * @param file 上传的 MultipartFile
     * @param taskId 任务 ID（作路径 key）
     * @return 存储路径（相对 storage root 或 OSS bucket key）
     */
    String save(MultipartFile file, long taskId);

    /**
     * 读取存储文件为 InputStream（供 retry 时反读原稿重跑推理）
     * @param path save() 返回的路径
     * @return 输入流；调用方负责 close
     * @throws com.paperaigc.detect.common.exception.BizException 文件不存在或读失败
     */
    InputStream read(String path);

    /**
     * 是否存在
     * @param path save() 返回的路径
     * @return 存在返回 true
     */
    boolean exists(String path);

    /**
     * 删除
     * @param path save() 返回的路径
     * @return 删除成功返回 true
     */
    boolean delete(String path);
}
