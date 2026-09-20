package org.dromara.common.core.domain;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * 统一响应结果 · 兼容若依 R 类
 *
 * <p>独立启动时用此实现替代 {@code org.dromara.common.core.domain.R}，
 * 保持 Controller 层返回签名不变。</p>
 *
 * <p>约定：
 * <ul>
 *   <li>{@code code = 200} 表示成功</li>
 *   <li>非 200 表示失败，msg 为错误提示</li>
 * </ul>
 */
@Data
@NoArgsConstructor
public class R<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 成功码 */
    public static final int CODE_SUCCESS = 200;

    /** 失败码（通用） */
    public static final int CODE_FAIL = 500;

    private int code;
    private String msg;
    private T data;

    // ==================== 静态工厂 ====================

    public static <T> R<T> ok() {
        R<T> r = new R<>();
        r.setCode(CODE_SUCCESS);
        r.setMsg("操作成功");
        return r;
    }

    public static <T> R<T> ok(T data) {
        R<T> r = new R<>();
        r.setCode(CODE_SUCCESS);
        r.setMsg("操作成功");
        r.setData(data);
        return r;
    }

    public static <T> R<T> fail() {
        R<T> r = new R<>();
        r.setCode(CODE_FAIL);
        r.setMsg("操作失败");
        return r;
    }

    public static <T> R<T> fail(String msg) {
        R<T> r = new R<>();
        r.setCode(CODE_FAIL);
        r.setMsg(msg);
        return r;
    }

    public static <T> R<T> fail(int code, String msg) {
        R<T> r = new R<>();
        r.setCode(code);
        r.setMsg(msg);
        return r;
    }
}
