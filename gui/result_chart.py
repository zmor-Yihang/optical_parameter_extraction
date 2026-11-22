"""结果页的单图阅读与多图总览。"""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backend_bases import MouseButton, MouseEvent
from matplotlib.figure import Figure
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QTabBar, QVBoxLayout, QWidget

from core.plotting import enable_curve_hover

from .axis_range import AxisRangeBar


class _ChartToolbar(NavigationToolbar):
    # 结果图使用自动布局，Matplotlib 的手动子图间距工具在此模式下不生效。
    toolitems = tuple(item for item in NavigationToolbar.toolitems if item[3] != "configure_subplots")


class ResultChart(QWidget):
    """复用同一批坐标轴，让子图切换不改变各自的坐标范围。"""

    def __init__(self, figure: Figure, *, initial_view: int = 0):
        super().__init__()
        self._axes = tuple(figure.axes)
        self._subplot_specs = [axis.get_subplotspec() for axis in self._axes]
        self._full_spec = self._subplot_specs[0].get_gridspec()[:, :]
        self._navigable = [axis.get_navigate() for axis in self._axes]
        self._repeat_x_labels = {
            axis.xaxis.label for axis, next_axis in zip(self._axes, self._axes[1:])
            if axis.get_xlabel() == next_axis.get_xlabel()
        }

        self.canvas = FigureCanvas(figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._clear_hover = enable_curve_hover(self.canvas)
        self._toolbar = _ChartToolbar(self.canvas, self)
        self._toolbar.setObjectName("curveToolbar")
        self._toolbar.setIconSize(QSize(16, 16))
        self._range_bar = AxisRangeBar(self.canvas)

        self.views = QTabBar()
        self.views.setObjectName("curveViews")
        self.views.setAccessibleName("选择曲线或多图总览")
        self.views.setExpanding(False)
        self.views.setDrawBase(False)
        for axis in self._axes:
            self.views.addTab(axis.get_title())
        overview = self.views.addTab("多图总览")
        self.views.setTabToolTip(overview, "同时查看本组全部子图；双击子图可放大")
        self.views.setCurrentIndex(min(max(initial_view, 0), overview))

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(self.views)
        controls.addWidget(self._toolbar, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(controls)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self._range_bar)

        self.views.currentChanged.connect(self._show_view)
        self.canvas.mpl_connect("button_press_event", self._open_subplot)
        self._show_view(self.views.currentIndex())

    @property
    def subplot_index(self) -> int:
        """当前单图，或总览下当前调整坐标的子图。"""
        return self._range_bar.subplot_index

    def _open_subplot(self, event: MouseEvent) -> None:
        if (self.views.currentIndex() == len(self._axes) and event.dblclick
                and event.button == MouseButton.LEFT and not self._toolbar.mode
                and event.inaxes in self._axes):
            self.views.setCurrentIndex(self._axes.index(event.inaxes))

    def _show_view(self, index: int) -> None:
        overview = index == len(self._axes)
        for i, (axis, spec) in enumerate(zip(self._axes, self._subplot_specs, strict=True)):
            focused = not overview and i == index
            visible = overview or focused
            axis.set_subplotspec(self._full_spec if focused else spec)
            axis.set_visible(visible)
            axis.set_in_layout(visible)
            axis.set_navigate(visible and self._navigable[i])
            # 总览只保留一处重复的轴名，数值刻度仍按子图独立显示。
            axis.xaxis.label.set_visible(not overview or axis.xaxis.label not in self._repeat_x_labels)
        self.canvas.setAccessibleName("多图总览" if overview else self._axes[index].get_title())
        self._range_bar.focus_subplot(None if overview else index)
        self._clear_hover()
        # 导航历史记录了坐标轴的位置，跨布局时只保留各轴的当前范围。
        self._toolbar.update()
        self._toolbar.set_message("")
        self.canvas.draw_idle()
