import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class MplCanvas(FigureCanvas):
    """matplotlib图表画布类"""
    
    def __init__(self, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        # 设置图表样式
        self.fig.patch.set_facecolor('#F5F5F5')  # 设置图表背景色
        
        # 应用seaborn样式美化图表
        plt.style.use('seaborn-v0_8-whitegrid')
        
        super(MplCanvas, self).__init__(self.fig)
        self.setMinimumSize(400, 300)
