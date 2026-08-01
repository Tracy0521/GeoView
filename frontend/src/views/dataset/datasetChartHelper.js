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
            backgroundColor: '#ffffff',
            textStyle: {color: '#333'},
            borderColor: '#e5e7eb',
            borderRadius: 8,
            formatter: function (params) {
                const count = params[0].value
                const percent = total === 0 ? 0 : ((count / total) * 100).toFixed(1)
                return `${params[0].axisValue}<br/>标注框: ${count} (${percent}%)`
            }
        },
        grid: {left: 40, right: 20, top: 40, bottom: 80},
        xAxis: {
            type: 'category',
            axisLabel: {rotate: 35},
            axisLine: {lineStyle: {color: '#e5e7eb'}},
            axisTick: {show: false}
        },
        yAxis: {
            type: 'value',
            splitLine: {lineStyle: {color: '#f0f2f5'}},
            axisLine: {show: false},
            axisTick: {show: false}
        },
        series: [
            {
                type: 'bar',
                data: yData,
                barWidth: '50%',
                barRadius: [6, 6, 0, 0],
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
            backgroundColor: '#ffffff',
            textStyle: {color: '#333'},
            borderColor: '#e5e7eb',
            borderRadius: 8,
            formatter: '{b}<br/>{c} 张 ({d}%)'
        },
        series: [
            {
                type: 'pie',
                radius: ['42%', '72%'],
                avoidLabelOverlap: true,
                itemStyle: {
                    borderRadius: 6,
                    borderColor: '#fff',
                    borderWidth: 2
                },
                data: [
                    {name: 'Train', value: trainCount},
                    {name: 'Validation', value: valCount}
                ],
                label: {show: false},
                emphasis: {
                    label: {show: true, fontSize: 14}
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
            backgroundColor: '#ffffff',
            textStyle: {color: '#333'},
            borderColor: '#e5e7eb',
            borderRadius: 8,
            formatter: '{b}<br/>{c} 框 ({d}%)'
        },
        series: [
            {
                type: 'pie',
                radius: ['42%', '72%'],
                itemStyle: {
                    borderRadius: 6,
                    borderColor: '#fff',
                    borderWidth: 2,
                    color: function (params) {
                        return colorList[params.dataIndex]
                    }
                },
                data: topClassList,
                label: {show: false}
            }
        ]
    }
}

/**
 * 4. Charts页面：单张图片标注数量分布柱状图 Objects per Image
 * @param {Array} countList [1,2,2,3...]
 */
// 单图标注数量分布柱状图
export function getObjPerImageBarOption(objectCountList) {
    // 1. 按标注数量从小到大排序
    const sorted = [...objectCountList].sort((a, b) => a.box - b.box)

    // 2. 提取X轴数据（标注数量）和Y轴数据（图片数量）
    const xData = sorted.map(item => String(item.box))
    const yData = sorted.map(item => item.count)

    return {
        tooltip: {
            trigger: 'axis',
            formatter: '{b} 个标注<br/>图片数量：{c}'
        },
        grid: {
            left: '5%',
            right: '5%',
            bottom: '10%',
            top: '10%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            name: '标注数量',
            nameTextStyle: {color: '#999', fontSize: 12},
            data: xData,
            axisLabel: {color: '#666'},
            axisLine: {lineStyle: {color: '#ddd'}}
        },
        yAxis: {
            type: 'value',
            name: '图片数量',
            nameTextStyle: {color: '#999', fontSize: 12},
            axisLabel: {color: '#666'},
            axisLine: {lineStyle: {color: '#ddd'}},
            splitLine: {lineStyle: {color: '#f0f0f0'}}
        },
        series: [{
            type: 'bar',
            data: yData,
            barWidth: '60%',
            itemStyle: {
                color: '#36cbcb',
                borderRadius: [4, 4, 0, 0]
            }
        }]
    }
}

/**
 * 5. Charts页面：图片宽度&高度分布柱状图 Image Dimensions
 *【重点修复】原始代码直接传入所有宽高会数据爆炸，新增分箱逻辑
 * @param {Array} widthList 所有图片宽度数组
 * @param {Array} heightList 所有图片高度数组
 * @param {number} binSize 区间步长 默认128
 */
export function getImageSizeBarOption(widthList = [], heightList = [], binSize = 128) {
    // 区间统计函数
    function binGroup(arr) {
        const dict = {}
        arr.forEach(v => {
            const bin = Math.floor(v / binSize) * binSize
            const key = `${bin} ~ ${bin + binSize}`
            dict[key] = (dict[key] || 0) + 1
        })
        const keys = Object.keys(dict).sort((a, b) => {
            return parseInt(a) - parseInt(b)
        })
        return {keys, values: keys.map(k => dict[k])}
    }

    const wBin = binGroup(widthList)
    const hBin = binGroup(heightList)

    return {
        tooltip: {
            trigger: 'axis',
            backgroundColor: '#ffffff',
            textStyle: {color: '#333'},
            borderColor: '#e5e7eb',
            borderRadius: 8
        },
        legend: {data: ['Width', 'Height']},
        grid: {left: 60, right: 20, top: 40, bottom: 70},
        xAxis: {
            type: 'category',
            data: wBin.keys,
            axisLabel: {rotate: 30},
            axisLine: {lineStyle: {color: '#e5e7eb'}},
            axisTick: {show: false}
        },
        yAxis: {
            type: 'value',
            splitLine: {lineStyle: {color: '#f0f2f5'}},
            axisLine: {show: false},
            axisTick: {show: false}
        },
        series: [
            {
                name: 'Width',
                type: 'bar',
                data: wBin.values,
                barRadius: [4, 4, 0, 0]
            },
            {
                name: 'Height',
                type: 'bar',
                data: hBin.values,
                barRadius: [4, 4, 0, 0]
            }
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