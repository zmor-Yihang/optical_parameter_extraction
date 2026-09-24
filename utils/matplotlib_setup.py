import matplotlib.pyplot as plt


def setup_matplotlib():
    """设置matplotlib支持中文显示和浅色主题样式"""
    # 英文、数字和符号优先 Arial；缺字（汉字）再回退到微软雅黑
    plt.rcParams['font.family'] = ['Arial', 'Microsoft YaHei', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
    plt.rcParams['font.size'] = 10
    plt.rcParams['axes.labelsize'] = 11  # 坐标轴标签
    plt.rcParams['axes.titlesize'] = 12  # 子图标题
    plt.rcParams['xtick.labelsize'] = 9  # x 轴刻度
    plt.rcParams['ytick.labelsize'] = 9  # y 轴刻度
    plt.rcParams['legend.fontsize'] = 9
    
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
