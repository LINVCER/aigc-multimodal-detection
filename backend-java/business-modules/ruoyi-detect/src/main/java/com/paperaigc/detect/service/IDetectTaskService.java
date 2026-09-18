package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.DetectTaskQueryDTO;
import com.paperaigc.detect.domain.dto.HumanizeDTO;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.vo.DetectTaskDetailVO;
import com.paperaigc.detect.domain.vo.DetectTaskVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.domain.vo.StatisticsVO;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * 检测任务业务接口
 */
public interface IDetectTaskService {

    /**
     * §3.1 提交检测（支持 text / audio / image 多模态）
     * @param file 上传文件（论文 / 音频 / 图像）
     * @param scenario 场景码（academic_bachelor 等）；null / 空时兜底 other
     * @param degreeType 旧字段兼容：BACHELOR/MASTER/PHD 迁移到 scenario；scenario 非空时忽略
     * @param title 标题；缺省用文件名
     * @param userId 提交用户 ID（Sa-Token 接入后从上下文取；未登录场景 null）
     * @param modality 模态：text / audio / image；null 时按文件后缀猜（DetectConstants.guessModality）
     * @return 新建任务实体
     */
    DetectTask submit(MultipartFile file, String scenario, String degreeType, String title, Long userId, String modality);

    /**
     * §3.2 列表（分页 + 过滤）
     */
    PageVO<DetectTaskVO> page(DetectTaskQueryDTO query);

    /**
     * §3.3 详情
     */
    DetectTaskDetailVO detail(Long id);

    /**
     * §3.4 重试（重置状态 + 重新跑推理）
     */
    DetectTask retry(Long id);

    /**
     * §3.5 取消（置 FAILED）
     */
    void cancel(Long id);

    /**
     * §3.6 删除（含存储文件删除）
     */
    void delete(Long id);

    /**
     * §3.7 C 端 Dashboard 统计
     */
    StatisticsVO statistics();

    /**
     * §4 降 AIGC 改写
     */
    Map<String, Object> humanize(HumanizeDTO dto);

    /**
     * §8.2 单段直接检测（不落任务）
     */
    Map<String, Object> detectParagraph(String text, boolean returnSentences);

    /**
     * 推理服务健康检查
     */
    Map<String, Object> inferenceHealth();
}
