package com.paperaigc.detect.domain.vo;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Collections;
import java.util.List;

/**
 * 通用分页响应
 *
 * <p>Element Plus / vxe-table / 若依 TableDataInfo 消费格式：{ total, rows }。</p>
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PageVO<T> {

    /** 总数（不含分页截断前） */
    private long total;
    /** 当前页数据 */
    private List<T> rows;

    public static <T> PageVO<T> empty() {
        return new PageVO<>(0L, Collections.emptyList());
    }

    public static <T> PageVO<T> of(long total, List<T> rows) {
        return new PageVO<>(total, rows);
    }
}
