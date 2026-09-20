package org.dromara.common.core.exception;

import lombok.Getter;

/**
 * 服务异常 · 兼容若依 ServiceException
 *
 * <p>独立启动时用此实现替代 {@code org.dromara.common.core.exception.ServiceException}。
 * ruoyi-inference 模块的 gRPC 客户端会抛出此异常。</p>
 */
@Getter
public class ServiceException extends RuntimeException {

    private final int code;

    public ServiceException(String message) {
        super(message);
        this.code = 500;
    }

    public ServiceException(int code, String message) {
        super(message);
        this.code = code;
    }
}
