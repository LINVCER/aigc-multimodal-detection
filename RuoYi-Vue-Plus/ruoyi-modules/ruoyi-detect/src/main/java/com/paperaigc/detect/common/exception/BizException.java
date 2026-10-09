package com.paperaigc.detect.common.exception;

import com.paperaigc.detect.common.enums.ErrorCode;
import lombok.Getter;

/**
 * 业务异常 —— Service 层抛出，由 {@link GlobalExceptionHandler} 统一转 R
 *
 * <p>用法：
 * <pre>
 *   throw new BizException(ErrorCode.DETECT_TASK_NOT_FOUND);
 *   throw new BizException(ErrorCode.DETECT_EXTRACT_FAILED, "PDF 加密文档");
 *   throw new BizException(9999, "自定义 msg");
 * </pre>
 */
@Getter
public class BizException extends RuntimeException {

    private final int code;

    public BizException(ErrorCode ec) {
        super(ec.getMsg());
        this.code = ec.getCode();
    }

    public BizException(ErrorCode ec, String extraDetail) {
        super(ec.getMsg() + "：" + extraDetail);
        this.code = ec.getCode();
    }

    public BizException(int code, String msg) {
        super(msg);
        this.code = code;
    }
}
