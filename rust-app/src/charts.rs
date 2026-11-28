use eframe::egui::{self, Color32, RichText};
use egui_plot::{Legend, Line, LineStyle, Plot, PlotBounds, PlotPoint};
use thz_analyzer_rust::analysis::{Analysis, SampleResult};

use crate::theme::{ACCENT, BORDER, INK, MUTED, SELECTED, SUBTLE, SURFACE, color, compact_toolbar};

pub const GROUPS: [(&str, &[usize]); 3] = [
    ("时域 / 频域", &[0, 1]),
    ("光学参数", &[2, 3, 4]),
    ("介电特性", &[5, 6, 7]),
];
const TITLES: [&str; 8] = [
    "时域信号",
    "频域信号",
    "折射率",
    "消光系数",
    "吸收系数",
    "介电常数实部",
    "介电常数虚部",
    "介电损耗",
];
const Y_LABELS: [&str; 8] = [
    "振幅",
    "振幅 (dB)",
    "折射率",
    "消光系数",
    "吸收系数 (cm⁻¹)",
    "介电常数实部 ε′",
    "介电常数虚部 ε″",
    "介电损耗 tan δ",
];
const SAMPLE_COLORS: [u32; 8] = [
    0x2a78d6, 0xeb6834, 0x1baf7a, 0xeda100, 0xe87ba4, 0x008300, 0x6250d6, 0xe34948,
];

pub fn sample_color(index: usize) -> Color32 {
    // Beyond the eight swatches use neutral ink, with dash styling and labels.
    SAMPLE_COLORS.get(index).copied().map_or(MUTED, color)
}

fn sample_values(sample: &SampleResult, metric: usize) -> &[f64] {
    match metric {
        0 => &sample.time,
        1 => &sample.magnitude,
        2 => &sample.refractive_index,
        3 => &sample.extinction,
        4 => &sample.absorption,
        5 => &sample.dielectric_real,
        6 => &sample.dielectric_imag,
        7 => &sample.loss_tangent,
        _ => unreachable!(),
    }
}

struct Series {
    name: String,
    segments: Vec<Vec<PlotPoint>>,
}

fn metric_series(data: &Analysis, metric: usize) -> Vec<Series> {
    let x = if metric == 0 {
        &data.time
    } else {
        &data.frequency
    };
    let build = |name: String, y: &[f64]| {
        let mut segments = Vec::new();
        let mut run = Vec::new();
        for (&x, &y) in x.iter().zip(y) {
            let y = if metric == 1 { 20.0 * y.log10() } else { y };
            if x.is_finite() && y.is_finite() {
                run.push(PlotPoint::new(x, y));
            } else if !run.is_empty() {
                segments.push(std::mem::take(&mut run));
            }
        }
        if !run.is_empty() {
            segments.push(run);
        }
        Series { name, segments }
    };
    let mut series: Vec<_> = data
        .samples
        .iter()
        .enumerate()
        .map(|(i, s)| {
            // Keep duplicate source names independently addressable in the legend.
            build(format!("{} · {}", i + 1, s.name), sample_values(s, metric))
        })
        .collect();
    if metric < 2 {
        let reference = if metric == 0 {
            &data.reference_time
        } else {
            &data.reference_magnitude
        };
        series.push(build("参考信号".to_owned(), reference));
    }
    series
}

#[derive(Clone, Copy, Default, PartialEq, Eq)]
enum Tool {
    #[default]
    Inspect,
    Pan,
    Zoom,
}

#[derive(Default)]
struct ViewHistory {
    home: Option<PlotBounds>,
    entries: Vec<PlotBounds>,
    cursor: usize,
}

impl ViewHistory {
    fn current(&self) -> Option<PlotBounds> {
        self.entries.get(self.cursor).copied()
    }

    fn record(&mut self, bounds: PlotBounds) {
        if !valid_bounds(bounds) || self.current() == Some(bounds) {
            return;
        }
        self.home.get_or_insert(bounds);
        self.entries.truncate(self.cursor + 1);
        self.entries.push(bounds);
        self.cursor = self.entries.len() - 1;
    }

    fn back(&mut self) {
        self.cursor = self.cursor.saturating_sub(1);
    }

    fn can_forward(&self) -> bool {
        self.cursor + 1 < self.entries.len()
    }

    fn forward(&mut self) {
        if self.can_forward() {
            self.cursor += 1;
        }
    }

    fn home(&mut self) {
        if let Some(bounds) = self.home {
            self.record(bounds);
        }
    }
}

fn valid_bounds(bounds: PlotBounds) -> bool {
    bounds.is_valid() && (0..2).all(|i| (bounds.max()[i] - bounds.min()[i]).is_finite())
}

#[derive(Default)]
struct TableScroll(Option<(usize, usize)>);

impl TableScroll {
    fn start_at_top(&mut self, metric: usize, series: usize) -> bool {
        self.0.replace((metric, series)) != Some((metric, series))
    }

    fn reset(&mut self) {
        self.0 = None;
    }
}

#[derive(Default)]
pub struct Charts {
    pub group: usize,
    views: [usize; 3],
    cache: [Option<Vec<Series>>; 8],
    bounds: [Option<PlotBounds>; 8],
    history: [ViewHistory; 8],
    tool: Tool,
    zoom_start: Option<(usize, egui::PointerButton, egui::Pos2)>,
    edits: [[String; 4]; 8],
    range_open: bool,
    range_error: Option<&'static str>,
    generation: u64,
    table: bool,
    table_series: usize,
    table_scroll: TableScroll,
    range_metric: usize,
}

fn view_actions(
    ui: &mut egui::Ui,
    history: &mut ViewHistory,
    tool_mode: &mut Tool,
    zoom_start: &mut Option<(usize, egui::PointerButton, egui::Pos2)>,
) -> bool {
    let mut restore = false;
    if ui
        .add_enabled(history.cursor > 0, egui::Button::new("←"))
        .on_hover_text("后退")
        .clicked()
    {
        history.back();
        restore = true;
    }
    if ui
        .add_enabled(history.can_forward(), egui::Button::new("→"))
        .on_hover_text("前进")
        .clicked()
    {
        history.forward();
        restore = true;
    }
    ui.separator();
    if ui
        .add_enabled(history.home.is_some(), egui::Button::new("初始视图"))
        .on_hover_text("回到本图初始范围；可用后退返回")
        .clicked()
    {
        history.home();
        restore = true;
    }
    for (tool, label, help) in [
        (Tool::Pan, "平移", "按住左键拖动以平移；再次点击退出"),
        (
            Tool::Zoom,
            "框选缩放",
            "按住左键框选放大；右键框选缩小；再次点击退出",
        ),
    ] {
        if ui
            .selectable_label(*tool_mode == tool, label)
            .on_hover_text(help)
            .clicked()
        {
            *tool_mode = if *tool_mode == tool {
                Tool::Inspect
            } else {
                tool
            };
            *zoom_start = None;
        }
    }
    restore
}

impl Charts {
    pub fn new_result(&mut self) {
        self.generation += 1;
        self.cache = Default::default();
        self.bounds = Default::default();
        self.history = Default::default();
        self.tool = Tool::Inspect;
        self.zoom_start = None;
        self.edits = Default::default();
        self.range_error = None;
        self.table_series = 0;
        self.table_scroll.reset();
    }

    pub fn show(&mut self, ui: &mut egui::Ui, data: &Analysis) {
        let metrics = GROUPS[self.group].1;
        if !self.table && ui.input(|i| i.key_pressed(egui::Key::Escape)) {
            self.tool = Tool::Inspect;
        }
        let view = &mut self.views[self.group];
        let mut restore = ui
            .horizontal(|ui| {
                compact_toolbar(ui);
                let views = metrics
                    .iter()
                    .map(|&metric| TITLES[metric])
                    .chain(["多图总览"]);
                if !self.table && ui.available_width() < 770.0 {
                    let selected = metrics
                        .get(*view)
                        .map_or("多图总览", |&metric| TITLES[metric]);
                    egui::ComboBox::from_id_salt("chart view")
                        .width(104.0)
                        .selected_text(selected)
                        .show_ui(ui, |ui| {
                            for (i, label) in views.enumerate() {
                                ui.selectable_value(view, i, label);
                            }
                        });
                } else {
                    for (i, label) in views.enumerate() {
                        ui.selectable_value(view, i, label);
                    }
                }
                let mut restore = false;
                if !self.table {
                    let current = metrics
                        .get(*view)
                        .copied()
                        .unwrap_or_else(|| metrics[self.range_metric.min(metrics.len() - 1)]);
                    ui.separator();
                    restore = view_actions(
                        ui,
                        &mut self.history[current],
                        &mut self.tool,
                        &mut self.zoom_start,
                    );
                }
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    let table_label = if self.table {
                        "返回曲线"
                    } else {
                        "查看数据"
                    };
                    let show_range = !self.table;
                    if ui.button(table_label).clicked() {
                        self.table = !self.table;
                        self.table_scroll.reset();
                        self.zoom_start = None;
                    }
                    if show_range {
                        let label = if self.range_open {
                            "坐标范围 ▲"
                        } else {
                            "坐标范围 ▼"
                        };
                        if ui.button(label).clicked() {
                            self.range_open = !self.range_open;
                        }
                    }
                });
                restore
            })
            .inner;
        ui.separator();
        let view = *view;
        let overview = view == metrics.len();
        if overview {
            self.range_metric = self.range_metric.min(metrics.len() - 1);
        }
        if self.table {
            if overview {
                egui::ComboBox::from_id_salt("table metric")
                    .selected_text(TITLES[metrics[self.range_metric]])
                    .show_ui(ui, |ui| {
                        for (i, &metric) in metrics.iter().enumerate() {
                            ui.selectable_value(&mut self.range_metric, i, TITLES[metric]);
                        }
                    });
            }
            self.show_table(
                ui,
                data,
                metrics[if overview { self.range_metric } else { view }],
            );
            return;
        }
        let current = metrics[if overview { self.range_metric } else { view }];
        if self.tool != Tool::Zoom {
            self.zoom_start = None;
        }
        let (mut apply, mut sync) = (None, false);
        if self.range_open {
            ui.horizontal(|ui| {
                compact_toolbar(ui);
                if overview {
                    egui::ComboBox::from_id_salt("range metric")
                        .selected_text(TITLES[current])
                        .show_ui(ui, |ui| {
                            for (i, &metric) in metrics.iter().enumerate() {
                                ui.selectable_value(&mut self.range_metric, i, TITLES[metric]);
                            }
                        });
                }
                let edits = &mut self.edits[current];
                for (i, (label, edit)) in ["X 最小", "X 最大", "Y 最小", "Y 最大"]
                    .into_iter()
                    .zip(edits.iter_mut())
                    .enumerate()
                {
                    if i == 2 {
                        ui.add_space(4.0);
                    }
                    ui.add_sized(
                        [68.0, 24.0],
                        egui::TextEdit::singleline(edit)
                            .margin(egui::Margin::symmetric(5, 2))
                            .vertical_align(egui::Align::Center)
                            .hint_text(label),
                    )
                    .on_hover_text(label);
                }
                ui.separator();
                if ui
                    .button("读取")
                    .on_hover_text("读取当前坐标范围")
                    .clicked()
                {
                    sync = true;
                }
                if ui
                    .add(egui::Button::new(
                        RichText::new("应用").strong().color(ACCENT),
                    ))
                    .clicked()
                {
                    match parse_bounds(edits, self.bounds[current]) {
                        Some(bounds) => {
                            self.range_error = None;
                            apply = Some(bounds);
                            self.history[current].record(bounds);
                        }
                        None => self.range_error = Some("范围必须为有限数值，且最小值小于最大值"),
                    }
                }
                if ui.button("自动").clicked() {
                    edits.fill(String::new());
                    self.range_error = None;
                    self.history[current].home();
                    restore = true;
                }
            });
            if let Some(err) = self.range_error {
                ui.label(RichText::new(err).color(ui.visuals().error_fg_color));
            }
        }
        if sync && let Some(bounds) = self.bounds[current] {
            let [xmin, ymin] = bounds.min();
            let [xmax, ymax] = bounds.max();
            self.edits[current] = [xmin, xmax, ymin, ymax].map(|x| format!("{x:.6e}"));
        }
        let selected: &[usize] = if overview {
            metrics
        } else {
            std::slice::from_ref(&current)
        };
        let plot_height = ui.available_height().max(88.0);
        let (_, rect) = ui.allocate_space(egui::vec2(ui.available_width(), plot_height));
        let mut plot_ui = ui.new_child(egui::UiBuilder::new().max_rect(rect));
        // egui_plot derives its grid from text_color; use secondary ink so curves stand out.
        plot_ui.visuals_mut().override_text_color = Some(MUTED);
        let height =
            ((plot_height - 25.0 * selected.len() as f32) / selected.len() as f32).max(55.0);
        for (i, &metric) in selected.iter().enumerate() {
            let series = self.cache[metric].get_or_insert_with(|| metric_series(data, metric));
            plot_ui.vertical_centered(|ui| {
                ui.label(RichText::new(TITLES[metric]).strong().size(15.0));
            });
            let mut plot = Plot::new(("curve", self.generation, metric))
                .height(height)
                .allow_drag(self.tool == Tool::Pan)
                .allow_zoom(false)
                .allow_scroll(false)
                .allow_axis_zoom_drag(false)
                .allow_boxed_zoom(false)
                .allow_double_click_reset(false)
                .show_x(self.tool == Tool::Inspect)
                .show_y(self.tool == Tool::Inspect)
                .y_axis_label(Y_LABELS[metric])
                .label_formatter(|name, point| {
                    format!("{name}\nX: {:.6e}   Y: {:.6e}", point.x, point.y)
                });
            if !overview || i + 1 == selected.len() {
                plot = plot.x_axis_label(if metric == 0 {
                    "延迟 (ps)"
                } else {
                    "频率 (THz)"
                });
            }
            if metric != 0 {
                plot = plot.default_x_bounds(0.0, 5.0);
            }
            if series.len() >= 2 && i == 0 {
                plot = plot.legend(Legend::default());
            }
            let history = &mut self.history[metric];
            // Supply the last bounds on every frame: egui_plot otherwise resets a
            // fixed-default frequency axis to 0–5 THz on idle frames.
            let requested = if metric == current && (restore || apply.is_some()) {
                history.current()
            } else {
                self.bounds[metric]
            };
            let result = plot.show(&mut plot_ui, |p| {
                if let Some(bounds) = requested {
                    p.set_plot_bounds(bounds);
                }
                for (index, series) in series.iter().enumerate() {
                    let is_ref = metric < 2 && index == data.samples.len();
                    let stroke = if is_ref { INK } else { sample_color(index) };
                    let style = if index >= 8 && !is_ref {
                        LineStyle::Dashed {
                            length: 4.0 + 2.0 * (index % 7) as f32,
                        }
                    } else {
                        LineStyle::Solid
                    };
                    for points in &series.segments {
                        if let [point] = points.as_slice() {
                            p.points(
                                egui_plot::Points::new(&series.name, std::slice::from_ref(point))
                                    .radius(2.0_f32)
                                    .color(stroke),
                            );
                        } else {
                            p.line(
                                Line::new(&series.name, points.as_slice())
                                    .color(stroke)
                                    .width(if is_ref { 2.0_f32 } else { 1.4_f32 })
                                    .style(style),
                            );
                        }
                    }
                }
            });
            let visible = *result.transform.bounds();
            self.bounds[metric] = Some(visible);
            let pan_finished = self.tool == Tool::Pan
                && result
                    .response
                    .drag_stopped_by(egui::PointerButton::Primary);
            if history.home.is_none() || pan_finished {
                history.record(visible);
                plot_ui.ctx().request_repaint();
            }
            if overview && pan_finished {
                self.range_metric = i;
            }
            match self.tool {
                Tool::Inspect => {
                    if overview && result.response.double_clicked() {
                        self.views[self.group] = i;
                        plot_ui.ctx().request_repaint();
                    }
                }
                Tool::Pan => {
                    let cursor = if result.response.dragged_by(egui::PointerButton::Primary) {
                        egui::CursorIcon::Grabbing
                    } else {
                        egui::CursorIcon::Grab
                    };
                    result.response.on_hover_cursor(cursor);
                }
                Tool::Zoom => {
                    let frame = *result.transform.frame();
                    let (origin, position) =
                        plot_ui.input(|i| (i.pointer.press_origin(), i.pointer.latest_pos()));
                    if result.response.drag_started()
                        && let Some(origin) = origin.filter(|p| frame.contains(*p))
                        && let Some(button) =
                            [egui::PointerButton::Primary, egui::PointerButton::Secondary]
                                .into_iter()
                                .find(|&b| result.response.dragged_by(b))
                    {
                        self.zoom_start = Some((metric, button, origin));
                    }
                    if let Some((target, button, origin)) = self.zoom_start
                        && target == metric
                    {
                        if let Some(pos) = position {
                            let selection = egui::Rect::from_two_pos(origin, frame.clamp(pos));
                            if result.response.drag_stopped_by(button)
                                && let Some(bounds) = zoom_selection(
                                    &result.transform,
                                    selection,
                                    button == egui::PointerButton::Secondary,
                                )
                            {
                                history.record(bounds);
                                self.bounds[metric] = Some(bounds);
                                if overview {
                                    self.range_metric = i;
                                }
                                plot_ui.ctx().request_repaint();
                            } else if result.response.dragged_by(button) {
                                let painter = plot_ui.painter().with_clip_rect(frame);
                                painter.rect_filled(selection, 0, ACCENT.gamma_multiply(0.13));
                                painter.rect_stroke(
                                    selection,
                                    0,
                                    egui::Stroke::new(1.5_f32, ACCENT),
                                    egui::StrokeKind::Inside,
                                );
                            }
                        }
                        if !plot_ui.input(|i| i.pointer.button_down(button)) {
                            self.zoom_start = None;
                        }
                    }
                    result.response.on_hover_cursor(egui::CursorIcon::Crosshair);
                }
            }
        }
    }

    fn show_table(&mut self, ui: &mut egui::Ui, data: &Analysis, metric: usize) {
        let count = data.samples.len() + usize::from(metric < 2);
        if count == 0 {
            ui.colored_label(MUTED, "没有可查看的数据");
            return;
        }
        self.table_series = self.table_series.min(count - 1);
        let name = |i: usize| {
            data.samples.get(i).map_or_else(
                || "参考信号".to_owned(),
                |sample| format!("{} · {}", i + 1, sample.name),
            )
        };
        let (_, top) = egui::containers::Sides::new().show(
            ui,
            |ui| {
                ui.label("信号");
                egui::ComboBox::from_id_salt("table series")
                    .width(200.0)
                    .truncate()
                    .selected_text(name(self.table_series))
                    .show_ui(ui, |ui| {
                        for i in 0..count {
                            ui.selectable_value(&mut self.table_series, i, name(i));
                        }
                    });
            },
            |ui| ui.button("回到顶部").clicked(),
        );
        let (x, y) = table_values(data, metric, self.table_series);
        let count = x.len().min(y.len());
        ui.colored_label(MUTED, format!("共 {count} 条数据"));
        ui.add_space(4.0);

        let reset_scroll = self.table_scroll.start_at_top(metric, self.table_series) || top;
        egui::Frame::new()
            .stroke(egui::Stroke::new(1.0_f32, BORDER))
            .corner_radius(5)
            .show(ui, |ui| {
                ui.spacing_mut().item_spacing.y = 0.0;
                let width = ui.available_width();
                let x_label = if metric == 0 {
                    "延迟 (ps)"
                } else {
                    "频率 (THz)"
                };
                table_row(
                    ui,
                    width,
                    SELECTED,
                    ["序号", x_label, Y_LABELS[metric]]
                        .map(|text| RichText::new(text).strong().color(INK)),
                );
                data_rows(ui, count, reset_scroll, |ui, i| {
                    let value = if metric == 1 {
                        20.0 * y[i].log10()
                    } else {
                        y[i]
                    };
                    let fill = if i % 2 == 0 { SURFACE } else { SUBTLE };
                    table_row(
                        ui,
                        width,
                        fill,
                        [
                            RichText::new((i + 1).to_string()).monospace().color(MUTED),
                            RichText::new(format!("{:.9e}", x[i])).monospace(),
                            RichText::new(if value.is_finite() {
                                format!("{value:.9e}")
                            } else {
                                "—".into()
                            })
                            .monospace(),
                        ],
                    );
                });
            });
    }
}

fn table_values(data: &Analysis, metric: usize, series: usize) -> (&[f64], &[f64]) {
    let x = if metric == 0 {
        &data.time
    } else {
        &data.frequency
    };
    let y = match data.samples.get(series) {
        Some(sample) => sample_values(sample, metric),
        None if metric == 0 => &data.reference_time,
        None => &data.reference_magnitude,
    };
    (x, y)
}

const TABLE_ROW_HEIGHT: f32 = 26.0;

fn data_rows(
    ui: &mut egui::Ui,
    count: usize,
    reset: bool,
    mut draw_row: impl FnMut(&mut egui::Ui, usize),
) -> egui::scroll_area::ScrollAreaOutput<()> {
    // Clear the full scroll state, including any momentum from the previous view.
    let salt = egui::Id::new("data rows");
    if reset {
        egui::scroll_area::State::default().store(ui.ctx(), ui.make_persistent_id(salt));
    }
    egui::ScrollArea::vertical()
        .id_salt("data rows")
        .max_height(ui.available_height())
        .min_scrolled_height(0.0)
        .auto_shrink([false, false])
        .show_rows(ui, TABLE_ROW_HEIGHT, count, |ui, rows| {
            for i in rows {
                draw_row(ui, i);
            }
        })
}

fn table_row(ui: &mut egui::Ui, width: f32, fill: Color32, cells: [RichText; 3]) {
    // The virtual list must allocate exactly the same height per row as it uses to scroll.
    let (rect, _) =
        ui.allocate_exact_size(egui::vec2(width, TABLE_ROW_HEIGHT), egui::Sense::hover());
    if !ui.is_rect_visible(rect) {
        return;
    }
    ui.painter().rect_filled(rect, 0, fill);
    let content = rect.shrink2(egui::vec2(12.0, 0.0));
    let number_end = content.left() + 62.0;
    let middle = number_end + (content.right() - number_end) * 0.5;
    let edges = [content.left(), number_end, middle, content.right()];
    for (i, text) in cells.into_iter().enumerate() {
        let cell = egui::Rect::from_min_max(
            egui::pos2(edges[i] + 6.0, content.top()),
            egui::pos2(edges[i + 1] - 6.0, content.bottom()),
        );
        ui.place(
            cell,
            egui::Label::new(text).truncate().halign(egui::Align::Max),
        );
    }
}

fn zoom_selection(
    transform: &egui_plot::PlotTransform,
    selection: egui::Rect,
    zoom_out: bool,
) -> Option<PlotBounds> {
    // Ignore clicks and very small rectangles, as Matplotlib's zoom tool does.
    if selection.width() < 5.0 || selection.height() < 5.0 {
        return None;
    }
    let min = transform.value_from_position(selection.left_bottom());
    let max = transform.value_from_position(selection.right_top());
    let mut min = [min.x, min.y];
    let mut max = [max.x, max.y];
    if zoom_out {
        let current = transform.bounds();
        for axis in 0..2 {
            let low = current.min()[axis];
            let span = current.max()[axis] - low;
            let factor = span / (max[axis] - min[axis]);
            min[axis] = low - (min[axis] - low) * factor;
            max[axis] = min[axis] + span * factor;
        }
    }
    let bounds = PlotBounds::from_min_max(min, max);
    valid_bounds(bounds).then_some(bounds)
}

fn parse_bounds(edits: &[String; 4], previous: Option<PlotBounds>) -> Option<PlotBounds> {
    let mut values = [0.0; 4];
    for (i, value) in values.iter_mut().enumerate() {
        *value = if edits[i].trim().is_empty() {
            let prev = previous?;
            if i % 2 == 0 {
                prev.min()[i / 2]
            } else {
                prev.max()[i / 2]
            }
        } else {
            edits[i].trim().parse().ok()?
        };
    }
    let [xmin, xmax, ymin, ymax] = values;
    let bounds = PlotBounds::from_min_max([xmin, ymin], [xmax, ymax]);
    valid_bounds(bounds).then_some(bounds)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn bounds(x: f64) -> PlotBounds {
        PlotBounds::from_min_max([x, -1.0], [x + 5.0, 1.0])
    }

    #[test]
    fn table_resets_scroll_when_reopened_or_when_dataset_changes() {
        let mut scroll = TableScroll::default();
        assert!(scroll.start_at_top(0, 0));
        assert!(!scroll.start_at_top(0, 0));
        assert!(scroll.start_at_top(0, 1));
        assert!(scroll.start_at_top(1, 1));
        scroll.reset();
        assert!(scroll.start_at_top(1, 1));
    }

    #[test]
    fn virtual_table_starts_at_first_row_and_can_display_the_last_row() {
        use egui::scroll_area::State;

        let ctx = egui::Context::default();
        let mut id = None;
        for (offset, reset, expected) in [(0.0, true, 0), (f32::MAX, false, 999), (0.0, true, 0)] {
            let mut visible = Vec::new();
            let mut actual_offset = 0.0;
            let mut content_height = 0.0;
            if let Some(id) = id {
                let mut state = State::load(&ctx, id).unwrap();
                state.offset.y = offset.min(1000.0 * TABLE_ROW_HEIGHT - 182.0);
                state.store(&ctx, id);
            }
            let _ = ctx.run(egui::RawInput::default(), |ctx| {
                egui::CentralPanel::default().show(ctx, |ui| {
                    ui.spacing_mut().item_spacing.y = 0.0;
                    ui.allocate_ui(egui::vec2(440.0, 250.0), |ui| {
                        ui.set_max_height(182.0);
                        let output = data_rows(ui, 1000, reset, |ui, index| {
                            let y = ui.cursor().top();
                            let width = ui.available_width();
                            table_row(ui, width, SURFACE, ["1", "2", "3"].map(RichText::new));
                            if y < ui.clip_rect().bottom()
                                && y + TABLE_ROW_HEIGHT > ui.clip_rect().top()
                            {
                                visible.push(index);
                            }
                        });
                        id = Some(output.id);
                        actual_offset = output.state.offset.y;
                        content_height = output.content_size.y;
                    });
                });
            });
            assert!(visible.contains(&expected), "visible rows: {visible:?}");
            assert_eq!(content_height, 1000.0 * TABLE_ROW_HEIGHT);
            if reset {
                assert_eq!(actual_offset, 0.0);
            }
        }
    }

    #[test]
    fn history_goes_back_and_forward_then_discards_the_abandoned_branch() {
        let mut history = ViewHistory::default();
        history.record(bounds(0.0));
        history.record(bounds(1.0));
        history.record(bounds(2.0));
        history.back();
        assert_eq!(history.current(), Some(bounds(1.0)));
        assert!(history.can_forward());
        history.forward();
        assert_eq!(history.current(), Some(bounds(2.0)));
        history.back();
        history.record(bounds(1.0));
        assert!(history.can_forward());
        history.record(bounds(3.0));
        assert!(!history.can_forward());
        history.home();
        assert_eq!(history.current(), Some(bounds(0.0)));
        history.back();
        assert_eq!(history.current(), Some(bounds(3.0)));
    }

    #[test]
    fn rectangle_zoom_is_reversible_and_ignores_accidental_clicks() {
        let panel = egui::Rect::from_min_max(egui::pos2(0.0, 0.0), egui::pos2(100.0, 100.0));
        let initial = PlotBounds::from_min_max([0.0, -10.0], [20.0, 10.0]);
        let transform = egui_plot::PlotTransform::new(panel, initial, false);
        let rect = egui::Rect::from_min_max(egui::pos2(25.0, 25.0), egui::pos2(75.0, 75.0));
        let inside = zoom_selection(&transform, rect, false).unwrap();
        assert_eq!(inside, PlotBounds::from_min_max([5.0, -5.0], [15.0, 5.0]));
        let transform = egui_plot::PlotTransform::new(panel, inside, false);
        assert_eq!(zoom_selection(&transform, rect, true), Some(initial));
        assert_eq!(
            zoom_selection(&transform, rect.with_max_x(26.0), false),
            None
        );
    }

    #[test]
    fn bounds_allow_partial_input_but_reject_inverted_or_nonfinite_ranges() {
        let prior = Some(PlotBounds::from_min_max([0.0, -1.0], [5.0, 1.0]));
        let edits = |x: [&str; 4]| x.map(str::to_owned);
        assert_eq!(
            parse_bounds(&edits(["", "4", "", ""]), prior)
                .unwrap()
                .max(),
            [4.0, 1.0]
        );
        assert!(parse_bounds(&edits(["5", "4", "", ""]), prior).is_none());
        assert!(parse_bounds(&edits(["NaN", "4", "", ""]), prior).is_none());
    }
}
