/**
 * dataset 数据集图表工具类
 * 对应DatasetDetail.vue Classes、Charts标签页所有echarts配置
 */

/**
 * 1. Classes页面：类别分布柱状图 Class Distribution
 * @param {Array} classList  [{class_id,name,annotation_count}]
 */
export function getClassBarOption(classList = []) {
    const xData = classList.map(item => item.name)
    const yData = classList.map(item => item.annotation_count)
    const total = yData.reduce((sum, val) => sum + val, 0)
    // 根据class_id生成和页面圆点完全一致的颜色
    const colorList = classList.map(item => {
        const hue = (item.class_id * 47) % 360
        return `hsl(${hue}, 70%, 55%)`
    })

    return {
        tooltip: {
            trigger: 'axis',
            formatter: function (params) {
                const count = params[0].value
                const percent = total === 0 ? 0 : ((count / total) * 100).toFixed(1)
                return `${params[0].axisValue}<br/>标注框: ${count} (${percent}%)`
            }
        },
        grid: { left: 30, right: 20, top: 40, bottom: 60 },
        xAxis: {
            type: 'category',
            axisLabel: { rotate: 35 }
        },
        yAxis: { type: 'value' },
        series: [
            {
                type: 'bar',
                data: yData,
                barWidth: '50%',
                itemStyle: {
                    color: function (params) {
                        return colorList[params.dataIndex]
                    }
                }
            }
        ]
    }
}

/**
 * 2. Charts页面：训练集/验证集分布环形饼图 Split Distribution
 * @param {number} trainCount
 * @param {number} valCount
 */
export function getSplitPieOption(trainCount = 0, valCount = 0) {
    return {
        tooltip: {
            trigger: 'item',
            formatter: '{b}<br/>{c} 张 ({d}%)'
        },
        series: [
            {
                type: 'pie',
                radius: ['42%', '72%'],
                avoidLabelOverlap: true,
                data: [
                    { name: 'Train', value: trainCount },
                    { name: 'Validation', value: valCount }
                ],
                label: { show: false },
                emphasis: {
                    label: { show: true, fontSize: 14 }
                }
            }
        ]
    }
}

/**
 * 3. Charts页面：Top N类别环形饼图 Top Classes
 * @param {Array} topClassList [{name, annotation_count, class_id}]
 */
export function getTopClassPieOption(topClassList = []) {
    const colorList = topClassList.map(item => {
        const hue = (item.class_id * 47) % 360
        return `hsl(${hue}, 70%, 55%)`
    })
    return {
        tooltip: {
            trigger: 'item',
            formatter: '{b}<br/>{c} 框 ({d}%)'
        },
        series: [
            {
                type: 'pie',
                radius: ['42%', '72%'],
                data: topClassList,
                label: { show: false },
                itemStyle: {
                    color: function (params) {
                        return colorList[params.dataIndex]
                    }
                }
            }
        ]
    }
}

/**
 * 4. Charts页面：单张图片标注数量分布柱状图 Objects per Image
 * @param {Array} countList [1,2,2,3...]
 */
export function getObjPerImageBarOption(countList = []) {
    // 统计频次
    const map = {}
    countList.forEach(num => {
        map[num] = (map[num] || 0) + 1
    })
    const xData = Object.keys(map).sort((a, b) => Number(a) - Number(b))
    const yData = xData.map(k => map[k])

    return {
        tooltip: { trigger: 'axis' },
        grid: { left: 40, right: 20, top: 30, bottom: 50 },
        xAxis: { type: 'category', name: '标注数量' },
        yAxis: { type: 'value', name: '图片数量' },
        series: [
            {
                type: 'bar',
                data: yData,
                itemStyle: { color: '#26c2b0' }
            }
        ]
    }
}

/**
 * 5. Charts页面：图片宽度&高度分布柱状图 Image Dimensions
 * @param {Array} widthList 所有图片宽度数组
 * @param {Array} heightList 所有图片高度数组
 */
export function getImageSizeBarOption(widthList = [], heightList = []) {
    return {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Width', 'Height'] },
        grid: { left: 50, right: 20, top: 40, bottom: 60 },
        xAxis: { type: 'value' },
        yAxis: { type: 'category' },
        series: [
            { name: 'Width', type: 'bar', data: widthList },
            { name: 'Height', type: 'bar', data: heightList }
        ]
    }
}

/**
 * 通用：销毁echart实例（防止内存泄漏）
 * @param {echarts.Instance} instance
 */
export function disposeChart(instance) {
    if (instance && !instance.isDisposed()) {
        instance.dispose()
    }
}