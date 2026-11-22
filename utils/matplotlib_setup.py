import matplotlib.pyplot as plt
from matplotlib.figure import Figure


LIGHT_MPL_THEME = {
    "figure.facecolor": "#FFFFFF",
    "axes.facecolor": "#FFFFFF",
    "legend.facecolor": "#FFFFFF",
    "savefig.facecolor": "#FFFFFF",
    "axes.edgecolor": "#A6B3C4",
    "axes.labelcolor": "#34465E",
    "text.color": "#17263B",
    "xtick.color": "#53647B",
    "ytick.color": "#53647B",
    "grid.color": "#E5EAF1",
    "grid.linewidth": 0.6,
    "grid.linestyle": "-",
    "legend.edgecolor": "#D5DFEB",
}

DARK_MPL_THEME = {
    "figure.facecolor": "#101720",
    "axes.facecolor": "#18212C",
    "legend.facecolor": "#18212C",
    "savefig.facecolor": "#101720",
    "axes.edgecolor": "#64758A",
    "axes.labelcolor": "#DCE6F2",
    "text.color": "#E7EEF7",
    "xtick.color": "#AAB8C9",
    "ytick.color": "#AAB8C9",
    "grid.color": "#344354",
    "grid.linewidth": 0.6,
    "grid.linestyle": "-",
    "legend.edgecolor": "#526378",
}


def setup_matplotlib(dark: bool = False):
    """设置 Matplotlib 中文字体、亮/暗色画布和图表默认样式。"""
    # 英文、数字和符号优先 Arial；缺字（汉字）再回退到微软雅黑
    plt.rcParams["font.family"] = ["Arial", "Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = 10
    plt.rcParams["axes.labelsize"] = 11
    plt.rcParams["axes.titlesize"] = 12
    plt.rcParams["xtick.labelsize"] = 9
    plt.rcParams["ytick.labelsize"] = 9
    plt.rcParams["legend.fontsize"] = 9
    set_matplotlib_theme(dark)


def set_matplotlib_theme(dark: bool) -> None:
    """切换后续 Figure 的默认画布主题。"""
    theme = DARK_MPL_THEME if dark else LIGHT_MPL_THEME
    plt.rcParams.update({**theme, "legend.framealpha": 1.0})


def apply_figure_theme(figure: Figure, dark: bool) -> None:
    """把主题同步到已经显示的 Figure。"""
    theme = DARK_MPL_THEME if dark else LIGHT_MPL_THEME
    figure.patch.set_facecolor(theme["figure.facecolor"])
    for axis in figure.axes:
        axis.set_facecolor(theme["axes.facecolor"])
        axis.tick_params(axis="both", colors=theme["xtick.color"])
        axis.xaxis.label.set_color(theme["axes.labelcolor"])
        axis.yaxis.label.set_color(theme["axes.labelcolor"])
        axis.title.set_color(theme["text.color"])
        for spine in axis.spines.values():
            spine.set_color(theme["axes.edgecolor"])
        for grid_line in axis.get_xgridlines() + axis.get_ygridlines():
            grid_line.set_color(theme["grid.color"])
            grid_line.set_linewidth(theme["grid.linewidth"])
        for line in axis.get_lines():
            if line.get_gid() == "参考信号":
                line.set_color(theme["text.color"])
        legend = axis.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor(theme["legend.facecolor"])
            legend.get_frame().set_edgecolor(theme["legend.edgecolor"])
            for text in legend.get_texts():
                text.set_color(theme["text.color"])
    for legend in figure.legends:
        legend.get_frame().set_facecolor(theme["legend.facecolor"])
        legend.get_frame().set_edgecolor(theme["legend.edgecolor"])
        for text in legend.get_texts():
            text.set_color(theme["text.color"])
    for text in figure.texts:
        text.set_color(theme["text.color"])
        patch = text.get_bbox_patch()
        if patch is not None:
            patch.set_facecolor(theme["legend.facecolor"])
            patch.set_edgecolor(theme["legend.edgecolor"])
    if figure.canvas is not None:
        figure.canvas.draw_idle()
