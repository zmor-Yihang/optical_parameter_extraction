import matplotlib.pyplot as plt


def setup_matplotlib():
    """设置matplotlib支持中文显示和浅色主题样式"""
    # 设置matplotlib支持中文显示
    plt.rcParams['font.sans-serif'] = ['KaiTi', 'SimHei', 'Microsoft YaHei', 'SimSun', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
    plt.rcParams['font.size'] = 12  # 设置全局字体大小
    plt.rcParams['axes.labelsize'] = 14  # 设置坐标轴标签字体大小
    plt.rcParams['axes.titlesize'] = 16  # 设置标题字体大小
    plt.rcParams['xtick.labelsize'] = 12  # 设置x轴刻度标签字体大小
    plt.rcParams['ytick.labelsize'] = 12  # 设置y轴刻度标签字体大小
    plt.rcParams['legend.fontsize'] = 12  # 设置图例字体大小
    
    # 设置浅色主题
    plt.rcParams['figure.facecolor'] = '#F5F5F5'  # 图形背景色
    plt.rcParams['axes.facecolor'] = '#F8F8F8'    # 坐标轴背景色
    plt.rcParams['axes.edgecolor'] = '#333333'    # 坐标轴边框颜色
    plt.rcParams['axes.labelcolor'] = '#333333'   # 坐标轴标签颜色
    plt.rcParams['text.color'] = '#333333'        # 文本颜色
    plt.rcParams['xtick.color'] = '#333333'       # x轴刻度颜色
    plt.rcParams['ytick.color'] = '#333333'       # y轴刻度颜色
    plt.rcParams['grid.color'] = '#CCCCCC'        # 网格颜色
    plt.rcParams['legend.facecolor'] = '#F8F8F8'  # 图例背景色
    plt.rcParams['legend.edgecolor'] = '#DDDDDD'  # 图例边框颜色
