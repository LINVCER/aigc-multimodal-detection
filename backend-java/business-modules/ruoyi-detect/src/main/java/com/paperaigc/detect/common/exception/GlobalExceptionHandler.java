package com.paperaigc.detect.common.exception;

import com.paperaigc.detect.common.enums.ErrorCode;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.http.HttpStatus;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

import java.util.stream.Collectors;

/**
 * 全局异常处理器
 *
 * <p>覆盖：业务异常 · 参数校验（@Valid / @Validated）· HTTP 反序列化 · 上传超限 · 兜底 Exception</p>
 * <p>返回统一 {@link R} 结构，前端 client.ts 拦截器已按 code 分派。</p>
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /** 业务异常：由 Service 层主动抛出 */
    @ExceptionHandler(BizException.class)
    public R<Void> handleBiz(BizException e) {
        log.warn("BizException [code={}] {}", e.getCode(), e.getMessage());
        return R.fail(e.getCode(), e.getMessage());
    }

    /** @Valid @RequestBody 参数校验失败 */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public R<Void> handleBodyValid(MethodArgumentNotValidException e) {
        String detail = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + " " + f.getDefaultMessage())
                .collect(Collectors.joining("; "));
        log.warn("参数校验失败: {}", detail);
        return R.fail(ErrorCode.PARAM_INVALID.getCode(), detail);
    }

    /** @Validated + @RequestParam / @PathVariable 校验失败 */
    @ExceptionHandler(ConstraintViolationException.class)
    public R<Void> handleParamValid(ConstraintViolationException e) {
        String detail = e.getConstraintViolations().stream()
                .map(ConstraintViolation::getMessage)
                .collect(Collectors.joining("; "));
        log.warn("参数校验失败: {}", detail);
        return R.fail(ErrorCode.PARAM_INVALID.getCode(), detail);
    }

    /** 缺 required 参数 */
    @ExceptionHandler(MissingServletRequestParameterException.class)
    public R<Void> handleMissing(MissingServletRequestParameterException e) {
        return R.fail(ErrorCode.PARAM_MISSING.getCode(), "缺少参数：" + e.getParameterName());
    }

    /** JSON 反序列化失败 */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public R<Void> handleUnreadable(HttpMessageNotReadableException e) {
        log.warn("请求体解析失败: {}", e.getMessage());
        return R.fail(ErrorCode.PARAM_INVALID.getCode(), "请求体格式错误");
    }

    /** 上传超过 spring.servlet.multipart.max-file-size */
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public R<Void> handleUploadTooLarge(MaxUploadSizeExceededException e) {
        return R.fail(ErrorCode.DETECT_FILE_TOO_LARGE.getCode(), ErrorCode.DETECT_FILE_TOO_LARGE.getMsg());
    }

    /** IllegalArgumentException 视为参数错误 */
    @ExceptionHandler(IllegalArgumentException.class)
    public R<Void> handleIllegalArg(IllegalArgumentException e) {
        log.warn("非法参数: {}", e.getMessage());
        return R.fail(ErrorCode.PARAM_INVALID.getCode(), e.getMessage());
    }

    /** 兜底 Exception —— 打全栈日志，返回通用 500 */
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public R<Void> handleAny(Exception e) {
        log.error("未处理异常", e);
        return R.fail(ErrorCode.SERVER_ERROR.getCode(), "服务器繁忙，请稍后重试");
    }
}
