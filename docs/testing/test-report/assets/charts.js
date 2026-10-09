/* 知源 AIGC 检测平台 · 功能测试报告 — 图表脚本
 * 所有颜色均从 :root 的 --chart-* / 语义令牌读取，保证与页面同一套 Product Teal 调色。
 */
(function () {
  'use strict';

  function tokens() {
    var css = getComputedStyle(document.documentElement);
    var get = function (name) {
      return css.getPropertyValue(name).trim();
    };
    return {
      series: [get('--chart-series-1'), get('--chart-series-2'), get('--chart-series-3'), get('--chart-series-4')],
      other: get('--chart-other'),
      grid: get('--chart-grid'),
      axis: get('--chart-axis'),
      label: get('--chart-label'),
      tooltipBg: get('--chart-tooltip-bg'),
      ink: get('--ink')
    };
  }

  function tooltipBase(t) {
    return {
      appendToBody: true,
      backgroundColor: t.tooltipBg,
      borderColor: t.grid,
      borderWidth: 1,
      textStyle: { color: t.ink, fontSize: 12 },
      extraCssText: 'border-radius:8px;box-shadow:0 6px 20px rgba(27,36,33,0.12);'
    };
  }

  function mount(id, option) {
    var el = document.getElementById(id);
    if (!el) return;
    var chart = echarts.init(el, null, { renderer: 'svg' });
    chart.setOption(option);
    window.addEventListener('resize', function () { chart.resize(); });
  }

  function emptyState(id) {
    var el = document.getElementById(id);
    if (el) el.hidden = false;
  }

  function renderScope(t) {
    var data = [
      { name: '后端单元测试', value: 99 },
      { name: '后端接口契约', value: 13 },
      { name: '后端集成冒烟', value: 12 },
      { name: '前端 E2E', value: 27 }
    ];
    if (!data.length) { emptyState('chart-scope-empty'); return; }

    mount('chart-scope', {
      animation: false,
      color: [t.series[0], t.series[1], t.series[2], t.series[3]],
      tooltip: Object.assign({ trigger: 'item', formatter: '{b}：{c} 条（{d}%）' }, tooltipBase(t)),
      legend: {
        bottom: 0,
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
        textStyle: { color: t.label, fontSize: 12 }
      },
      series: [
        {
          type: 'pie',
          radius: ['46%', '68%'],
          center: ['50%', '46%'],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: t.tooltipBg, borderWidth: 2, borderRadius: 4 },
          label: { color: t.ink, fontSize: 12, formatter: '{b}\n{c} 条' },
          labelLine: { length: 12, length2: 12, lineStyle: { color: t.grid } },
          data: data
        }
      ]
    });
  }

  function renderBackend(t) {
    // 按用例数降序；数据来自 target/surefire-reports 汇总；第三列为 true 表示集成冒烟（需真实 MySQL/Redis）
    var rows = [
      ['检测任务服务', 22, false],
      ['认证服务', 18, false],
      ['检测接口契约', 13, false],
      ['文本处理', 13, false],
      ['参数取值工具', 10, false],
      ['Redis 集成冒烟', 7, true],
      ['场景阈值服务', 6, false],
      ['检测常量', 5, false],
      ['密码散列', 5, false],
      ['图形验证码', 5, false],
      ['MySQL 集成冒烟', 5, true],
      ['业务错误码', 4, false],
      ['登录失败锁定', 4, false],
      ['场景阈值常量', 4, false],
      ['IP 限流', 3, false]
    ];
    if (!rows.length) { emptyState('chart-backend-empty'); return; }

    var names = rows.map(function (r) { return r[0]; }).reverse();
    var values = rows.map(function (r) {
      return {
        value: r[1],
        itemStyle: { color: r[2] ? t.series[2] : t.series[0], borderRadius: [0, 4, 4, 0] }
      };
    }).reverse();

    mount('chart-backend', {
      animation: false,
      grid: { left: 8, right: 40, top: 12, bottom: 8, containLabel: true },
      tooltip: Object.assign(
        { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: '{b}：{c} 条' },
        tooltipBase(t)
      ),
      xAxis: {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { color: t.grid, width: 1 } },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: t.label, fontSize: 11 }
      },
      yAxis: {
        type: 'category',
        data: names,
        axisLine: { lineStyle: { color: t.grid } },
        axisTick: { show: false },
        axisLabel: { color: t.label, fontSize: 12 }
      },
      series: [
        {
          type: 'bar',
          data: values,
          barWidth: '56%',
          label: { show: true, position: 'right', color: t.label, fontSize: 11, formatter: '{c}' }
        }
      ]
    });
  }

  function boot() {
    if (typeof echarts === 'undefined') {
      emptyState('chart-scope-empty');
      emptyState('chart-backend-empty');
      return;
    }
    var t = tokens();
    renderScope(t);
    renderBackend(t);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
