package com.paperaigc.inference.client;

import org.dromara.common.core.exception.ServiceException;
import com.paperaigc.inference.grpc.DetectBatchRequest;
import com.paperaigc.inference.grpc.DetectBatchResponse;
import com.paperaigc.inference.grpc.DetectParagraphRequest;
import com.paperaigc.inference.grpc.DetectParagraphResponse;
import com.paperaigc.inference.grpc.DetectionServiceGrpc;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.StatusRuntimeException;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.concurrent.TimeUnit;

/**
 * Python 推理服务 gRPC 客户端
 * 熔断（Resilience4j）+ deadline 超时；降级策略：抛业务异常由编排层退款重试
 */
@Slf4j
@Component
public class DetectionInferenceClient {

    private final ManagedChannel channel;
    private final DetectionServiceGrpc.DetectionServiceBlockingStub stub;
    private final long deadlineSeconds;

    public DetectionInferenceClient(
            @Value("${platform.inference.host:localhost}") String host,
            @Value("${platform.inference.port:9090}") int port,
            @Value("${platform.inference.deadline-seconds:10}") long deadlineSeconds) {
        this.channel = ManagedChannelBuilder.forAddress(host, port)
                .usePlaintext()  // 集群内网通信；跨网必须换 TLS
                .build();
        this.stub = DetectionServiceGrpc.newBlockingStub(channel);
        this.deadlineSeconds = deadlineSeconds;
    }

    /**
     * 单段检测
     * @param text 段落文本
     * @param returnSentences 是否返回句子级打分
     * @return 检测结果
     */
    @CircuitBreaker(name = "inference", fallbackMethod = "detectFallback")
    public DetectParagraphResponse detectParagraph(String text, boolean returnSentences) {
        try {
            return stub.withDeadlineAfter(deadlineSeconds, TimeUnit.SECONDS)
                    .detectParagraph(DetectParagraphRequest.newBuilder()
                            .setText(text)
                            .setReturnCalibrated(true)
                            .setReturnSentences(returnSentences)
                            .build());
        } catch (StatusRuntimeException e) {
            log.warn("inference detectParagraph failed: {}", e.getStatus());
            throw new ServiceException("检测服务暂时不可用，请稍后重试");
        }
    }

    /**
     * 批量检测（一批 ≤ 32 段）
     * @param request 批量请求
     * @return 批量结果
     */
    @CircuitBreaker(name = "inference", fallbackMethod = "detectBatchFallback")
    public DetectBatchResponse detectBatch(DetectBatchRequest request) {
        try {
            return stub.withDeadlineAfter(deadlineSeconds * 3, TimeUnit.SECONDS)
                    .detectBatch(request);
        } catch (StatusRuntimeException e) {
            log.warn("inference detectBatch failed: {}", e.getStatus());
            throw new ServiceException("检测服务暂时不可用，请稍后重试");
        }
    }

    @SuppressWarnings("unused")
    private DetectParagraphResponse detectFallback(String text, boolean returnSentences, Throwable t) {
        throw new ServiceException("检测服务暂时不可用，请稍后重试");
    }

    @SuppressWarnings("unused")
    private DetectBatchResponse detectBatchFallback(DetectBatchRequest request, Throwable t) {
        throw new ServiceException("检测服务暂时不可用，请稍后重试");
    }

    @PreDestroy
    public void shutdown() throws InterruptedException {
        channel.shutdown().awaitTermination(5, TimeUnit.SECONDS);
    }
}
