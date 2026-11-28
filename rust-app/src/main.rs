#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod charts;
mod theme;

use charts::{Charts, GROUPS, sample_color};
use eframe::egui::{self, Frame, Margin, RichText, Stroke, Vec2};
use serde::{Deserialize, Serialize};
use std::{
    path::PathBuf,
    sync::{Arc, mpsc},
    thread,
};
use thz_analyzer_rust::{
    analysis::{self, Analysis, Sample, Settings, Window},
    data::{self, ExportKind, NamedSignal},
};
use theme::{
    ACCENT, BORDER, INK, MUTED, SELECTED, SUBTLE, SURFACE, WORKSPACE, card, primary_button,
};

const TITLE: &str = "THzLab";
const VERSION: &str = env!("CARGO_PKG_VERSION");

fn main() -> eframe::Result {
    let icon = image::load_from_memory(include_bytes!("../app.ico"))
        .ok()
        .map(|image| {
            let rgba = image.to_rgba8();
            let (width, height) = rgba.dimensions();
            Arc::new(egui::IconData {
                rgba: rgba.into_raw(),
                width,
                height,
            })
        });
    let mut viewport = egui::ViewportBuilder::default()
        .with_inner_size([1220.0, 800.0])
        .with_min_inner_size([1080.0, 680.0]);
    if let Some(icon) = icon {
        viewport = viewport.with_icon(icon);
    }
    let options = eframe::NativeOptions {
        viewport,
        ..Default::default()
    };
    eframe::run_native(TITLE, options, Box::new(|cc| Ok(Box::new(App::new(cc)))))
}

fn initialize_fonts(ctx: &egui::Context) -> bool {
    let base = std::env::var_os("WINDIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(r"C:\Windows"))
        .join("Fonts");
    // Use system fonts rather than bundling copies.
    let mut fonts = egui::FontDefinitions::default();
    let cjk = ["msyh.ttc", "simhei.ttf", "simsun.ttc"]
        .into_iter()
        .find_map(|name| std::fs::read(base.join(name)).ok());
    let localized = cjk.is_some();
    if let Some(bytes) = cjk {
        let key = "Windows CJK".to_owned();
        fonts
            .font_data
            .insert(key.clone(), Arc::new(egui::FontData::from_owned(bytes)));
        for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace] {
            fonts.families.entry(family).or_default().push(key.clone());
        }
    }
    let mut brand_fonts = fonts.families[&egui::FontFamily::Proportional].clone();
    if let Ok(bytes) = std::fs::read(base.join("seguisb.ttf")) {
        let key = "Segoe UI Semibold".to_owned();
        fonts
            .font_data
            .insert(key.clone(), Arc::new(egui::FontData::from_owned(bytes)));
        brand_fonts.insert(0, key);
    }
    fonts.families.insert(brand_font(), brand_fonts);
    ctx.set_fonts(fonts);
    localized
}

fn brand_font() -> egui::FontFamily {
    egui::FontFamily::Name("Team badge".into())
}

fn config_path() -> Option<PathBuf> {
    std::env::var_os("LOCALAPPDATA").map(|base| {
        PathBuf::from(base)
            .join("THzAnalyzerRust")
            .join("config.json")
    })
}

#[derive(Serialize, Deserialize)]
#[serde(default)]
struct Preferences {
    thickness: String,
    history: Vec<String>,
    use_window: bool,
    open_dir: PathBuf,
    save_dir: PathBuf,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            thickness: "0.5".into(),
            history: vec!["0.5".into()],
            use_window: false,
            open_dir: PathBuf::new(),
            save_dir: PathBuf::new(),
        }
    }
}
impl Preferences {
    fn load() -> Self {
        config_path()
            .and_then(|p| std::fs::read(p).ok())
            .and_then(|b| serde_json::from_slice(&b).ok())
            .unwrap_or_default()
    }
    fn save(&self) -> Result<(), String> {
        let Some(path) = config_path() else {
            return Ok(());
        };
        std::fs::create_dir_all(path.parent().unwrap()).map_err(|e| e.to_string())?;
        std::fs::write(
            path,
            serde_json::to_vec_pretty(self).map_err(|e| e.to_string())?,
        )
        .map_err(|e| e.to_string())
    }
}

struct LoadedSignal {
    name: String,
    signal: Arc<analysis::Signal>,
}
impl From<NamedSignal> for LoadedSignal {
    fn from(input: NamedSignal) -> Self {
        Self {
            name: input.name,
            signal: Arc::new(input.signal),
        }
    }
}
struct LoadedSample {
    input: LoadedSignal,
    path: PathBuf,
    thickness: Option<f64>,
    window: Option<Window>,
}
struct Completed {
    result: Analysis,
    reference_name: String,
    use_window: bool,
}

type Imported = Vec<(PathBuf, Result<Vec<NamedSignal>, String>)>;
enum Event {
    Import(bool, Option<(PathBuf, Imported)>),
    Analysis(Result<Completed, String>),
    Export(Result<Option<PathBuf>, String>),
}

#[derive(Clone, Copy)]
enum Dialog {
    Thickness,
    Window,
}

struct App {
    prefs: Preferences,
    localized: bool,
    reference: Option<(LoadedSignal, PathBuf)>,
    reference_window: Option<Window>,
    samples: Vec<LoadedSample>,
    selected: Vec<usize>,
    result: Option<Arc<Completed>>,
    charts: Charts,
    focused: bool,
    pending: Option<mpsc::Receiver<Event>>,
    file_dialog: rfd::FileDialog,
    status: String,
    error: bool,
    notice: Option<String>,
    dialog: Option<Dialog>,
    thickness_edits: Vec<String>,
    window_edits: Vec<[String; 3]>,
    dialog_error: Option<String>,
    side_width: f32,
}

impl App {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        let ctx = &cc.egui_ctx;
        let localized = initialize_fonts(ctx);
        let prefs = Preferences::load();
        theme::apply(ctx);
        Self {
            prefs,
            localized,
            reference: None,
            reference_window: None,
            samples: vec![],
            selected: vec![],
            result: None,
            charts: Charts::default(),
            focused: false,
            pending: None,
            file_dialog: rfd::FileDialog::new().set_parent(cc),
            status: "准备就绪".into(),
            error: false,
            notice: None,
            dialog: None,
            thickness_edits: vec![],
            window_edits: vec![],
            dialog_error: None,
            side_width: 310.0,
        }
    }

    fn status(&mut self, message: impl Into<String>, error: bool) {
        self.status = message.into();
        self.error = error;
    }

    fn save_prefs(&mut self) {
        if let Err(err) = self.prefs.save() {
            self.status(format!("未能保存设置：{err}"), true);
        }
    }

    fn spawn(
        &mut self,
        ctx: &egui::Context,
        status: &str,
        f: impl FnOnce() -> Event + Send + 'static,
    ) {
        if self.pending.is_some() {
            return;
        }
        let (tx, rx) = mpsc::channel();
        let ctx = ctx.clone();
        match thread::Builder::new()
            .name("thz-worker".into())
            .spawn(move || {
                // A guard wakes the UI even if the worker unwinds and drops its sender.
                struct Wake(egui::Context);
                impl Drop for Wake {
                    fn drop(&mut self) {
                        self.0.request_repaint();
                    }
                }
                let wake = Wake(ctx);
                let _ = tx.send(f());
                drop(tx);
                drop(wake);
            }) {
            Ok(_) => {
                self.pending = Some(rx);
                self.status(status, false);
            }
            Err(e) => {
                self.status(format!("无法启动后台任务：{e}"), true);
            }
        }
    }

    fn poll(&mut self) {
        let Some(rx) = &self.pending else {
            return;
        };
        let event = match rx.try_recv() {
            Ok(event) => event,
            Err(mpsc::TryRecvError::Empty) => return,
            Err(mpsc::TryRecvError::Disconnected) => {
                self.pending = None;
                self.status("后台任务意外结束", true);
                return;
            }
        };
        self.pending = None;
        match event {
            Event::Import(_, None) | Event::Export(Ok(None)) => self.status("操作已取消", false),
            Event::Import(is_ref, Some((directory, imported))) => {
                self.prefs.open_dir = directory;
                let mut added = 0;
                let mut notes = Vec::new();
                for (path, result) in imported {
                    match result {
                        Ok(mut inputs) if is_ref && !inputs.is_empty() => {
                            if inputs.len() > 1 {
                                notes.push(format!(
                                    "文件包含 {} 条扫描，已取第 1 条作为参考。",
                                    inputs.len()
                                ));
                            }
                            self.reference = Some((inputs.remove(0).into(), path));
                            self.reference_window = None;
                            added += 1;
                        }
                        Ok(inputs) if !inputs.is_empty() => {
                            added += inputs.len();
                            self.samples
                                .extend(inputs.into_iter().map(|input| LoadedSample {
                                    input: input.into(),
                                    path: path.clone(),
                                    thickness: None,
                                    window: None,
                                }));
                        }
                        Ok(_) => notes.push(format!("{}：没有可用信号", path.display())),
                        Err(e) => notes.push(format!("{}：{e}", path.display())),
                    }
                }
                if !notes.is_empty() {
                    self.notice = Some(notes.join("\n"));
                }
                if is_ref && added != 0 {
                    self.status("已选择参考文件（已自动标准化）", false);
                } else if added != 0 {
                    self.status(format!("已添加 {added} 个样品（已自动标准化）"), false);
                } else {
                    self.status("没有导入可用文件", true);
                }
            }
            Event::Analysis(Ok(done)) => {
                if !done.result.warnings.is_empty() {
                    self.notice = Some(done.result.warnings.join("\n"));
                }
                self.result = Some(Arc::new(done));
                self.charts.new_result();
                self.status("计算完成", false);
            }
            Event::Analysis(Err(error)) | Event::Export(Err(error)) => {
                self.notice = Some(error.clone());
                self.status(error, true);
            }
            Event::Export(Ok(Some(path))) => {
                if let Some(dir) = path.parent() {
                    self.prefs.save_dir = dir.to_owned();
                }
                self.status(format!("已保存：{}", path.display()), false);
            }
        }
    }

    fn import(&mut self, ctx: &egui::Context, is_ref: bool, paths: Option<Vec<PathBuf>>) {
        let directory = self.prefs.open_dir.clone();
        let base_dialog = self.file_dialog.clone();
        self.spawn(ctx, "正在读取和标准化文件…", move || {
            let paths = paths.or_else(|| {
                let mut dialog = base_dialog
                    .set_title(if is_ref {
                        "选择参考文件（原始或标准）"
                    } else {
                        "选择样品文件（原始或标准）"
                    })
                    .add_filter("支持的测量文件", &["txt", "csv", "xlsx", "dat", "tsv"])
                    .add_filter("所有文件", &["*"]);
                if directory.is_dir() {
                    dialog = dialog.set_directory(directory);
                }
                if is_ref {
                    dialog.pick_file().map(|p| vec![p])
                } else {
                    dialog.pick_files()
                }
            });
            let outcome = paths.and_then(|paths| {
                let directory = paths.first()?.parent()?.to_owned();
                let items = paths
                    .into_iter()
                    .take(if is_ref { 1 } else { usize::MAX })
                    .map(|path| {
                        let loaded = data::load_signals(&path);
                        (path, loaded)
                    })
                    .collect();
                Some((directory, items))
            });
            Event::Import(is_ref, outcome)
        });
    }

    fn run_analysis(&mut self, ctx: &egui::Context) {
        let Some((reference, _)) = &self.reference else {
            self.status("请先选择参考文件", true);
            return;
        };
        if self.samples.is_empty() {
            self.status("请添加至少一个样品文件", true);
            return;
        }
        let Some(thickness) = positive(&self.prefs.thickness) else {
            self.status("样品厚度必须为有限正数", true);
            return;
        };
        let settings = Settings {
            thickness_mm: thickness,
            use_window: self.prefs.use_window,
            reference_window: self.reference_window,
        };
        // Share file data with the worker; no large array copy on the UI thread.
        let reference = Arc::clone(&reference.signal);
        let reference_name = self.reference.as_ref().unwrap().0.name.clone();
        let samples: Vec<_> = self
            .samples
            .iter()
            .map(|entry| {
                (
                    entry.input.name.clone(),
                    Arc::clone(&entry.input.signal),
                    entry.thickness,
                    entry.window,
                )
            })
            .collect();
        let input = thickness.to_string();
        self.prefs
            .history
            .retain(|v| positive(v) != Some(thickness));
        self.prefs.history.insert(0, input);
        self.prefs.history.truncate(3);
        self.save_prefs();
        self.spawn(ctx, "正在计算，请稍候…", move || {
            let samples: Vec<_> = samples
                .into_iter()
                .map(|(name, signal, thickness_mm, window)| Sample {
                    name,
                    signal: (*signal).clone(),
                    thickness_mm,
                    window,
                })
                .collect();
            Event::Analysis(
                analysis::analyze(&reference, &samples, &settings).map(|result| Completed {
                    result,
                    reference_name,
                    use_window: settings.use_window,
                }),
            )
        });
    }

    fn export(&mut self, ctx: &egui::Context, kind: ExportKind, caption: &'static str) {
        let Some(result) = self.result.clone() else {
            return;
        };
        let directory = self.prefs.save_dir.clone();
        let base_dialog = self.file_dialog.clone();
        self.spawn(ctx, "正在导出 Excel…", move || {
            let mut dialog = base_dialog
                .set_title(caption)
                .add_filter("Excel 工作簿", &["xlsx"])
                .set_file_name(format!("{caption}.xlsx"));
            if directory.is_dir() {
                dialog = dialog.set_directory(directory);
            }
            Event::Export(dialog.save_file().map_or(Ok(None), |path| {
                let path = if path
                    .extension()
                    .is_some_and(|ext| ext.eq_ignore_ascii_case("xlsx"))
                {
                    path
                } else {
                    path.with_extension("xlsx")
                };
                data::export_xlsx(
                    &path,
                    &result.result,
                    kind,
                    &result.reference_name,
                    result.use_window,
                )
                .map(|_| Some(path))
            }))
        });
    }

    fn status_indicator(&self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            if self.pending.is_some() {
                ui.spinner();
            } else {
                ui.colored_label(
                    if self.error {
                        ui.visuals().error_fg_color
                    } else {
                        ACCENT
                    },
                    if self.error { "!" } else { "●" },
                );
            }
            ui.add(egui::Label::new(RichText::new(&self.status).small().color(MUTED)).truncate())
                .on_hover_text(&self.status);
        });
    }

    fn header(&self, ui: &mut egui::Ui) {
        Frame::new()
            .fill(SURFACE)
            .inner_margin(Margin::symmetric(16, 7))
            .show(ui, |ui| {
                ui.horizontal(|ui| {
                    let (rect, _) =
                        ui.allocate_exact_size(egui::vec2(32.0, 32.0), egui::Sense::hover());
                    ui.painter().rect_filled(rect, 7, SELECTED);
                    let points = (0..=30)
                        .map(|i| {
                            let t = i as f32 / 30.0;
                            rect.center()
                                + egui::vec2(
                                    (t - 0.5) * 20.0,
                                    (t * 2.0 * std::f32::consts::TAU).sin() * 4.0,
                                )
                        })
                        .collect();
                    ui.painter().add(egui::Shape::line(
                        points,
                        Stroke::new(1.8_f32, ACCENT),
                    ));
                    ui.add_space(3.0);
                    ui.label(RichText::new(TITLE).size(21.0).strong().color(INK));
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        Frame::new()
                            .fill(SUBTLE)
                            .stroke(Stroke::new(1.0_f32, BORDER))
                            .corner_radius(8)
                            .inner_margin(Margin::symmetric(10, 4))
                            .show(ui, |ui| {
                                ui.spacing_mut().item_spacing.x = 8.0;
                                ui.label(
                                    RichText::new(format!("v{VERSION}"))
                                        .monospace()
                                        .size(11.0)
                                        .color(ACCENT),
                                );
                                let (divider, _) =
                                    ui.allocate_exact_size(egui::vec2(1.0, 13.0), egui::Sense::hover());
                                ui.painter().rect_filled(divider, 0, BORDER);
                                ui.with_layout(
                                    egui::Layout::right_to_left(egui::Align::Center),
                                    |ui| {
                                        ui.spacing_mut().item_spacing.x = 5.0;
                                        ui.label(
                                            RichText::new("THz Group")
                                                .font(egui::FontId::new(12.0, brand_font()))
                                                .color(MUTED),
                                        );
                                        ui.label(
                                            RichText::new("NUAA")
                                                .font(egui::FontId::new(12.0, brand_font()))
                                                .color(ACCENT),
                                        );
                                    },
                                );
                            });
                    });
                });
            });
    }

    fn sidebar(&mut self, ui: &mut egui::Ui) {
        let busy = self.pending.is_some();
        ui.heading(RichText::new("分析设置").strong());
        ui.add_space(6.0);
        let height = (ui.available_height() - 50.0).max(10.0);
        egui::ScrollArea::vertical()
            .id_salt("settings scroll")
            .max_height(height)
            .min_scrolled_height(0.0)
            .auto_shrink([false, true])
            .show(ui, |ui| {
                ui.add_enabled_ui(!busy, |ui| {
                    ui.spacing_mut().item_spacing = egui::vec2(7.0, 4.0);
                    ui.spacing_mut().interact_size.y = 25.0;
                    sidebar_section(ui, "数据导入");
                    ui.horizontal(|ui| {
                        ui.strong("参考文件");
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            if ui.button("＋ 添加").on_hover_text("选择参考文件").clicked()
                            {
                                self.import(ui.ctx(), true, None);
                            }
                        });
                    });
                    let reference_area = drop_area(ui, 39.0, |ui| {
                        if let Some((input, path)) = &self.reference {
                            ui.horizontal(|ui| {
                                ui.colored_label(INK, "●");
                                ui.add(egui::Label::new(&input.name).truncate())
                                    .on_hover_text(format!("{}\n{}", input.name, path.display()));
                            });
                        } else {
                            ui.centered_and_justified(|ui| {
                                ui.colored_label(MUTED, "拖放参考文件到此处");
                            });
                        }
                    });
                    if let Some(paths) = reference_area {
                        self.import(ui.ctx(), true, Some(paths));
                    }
                    ui.add_space(7.0);
                    ui.horizontal(|ui| {
                        ui.strong("样品文件");
                        ui.label(RichText::new(format!("{} 个", self.samples.len())).color(ACCENT));
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            if ui.button("＋ 添加").clicked() {
                                self.import(ui.ctx(), false, None);
                            }
                        });
                    });
                    let sample_rows = self.samples.len().min(4) as f32;
                    let list_height = (13.0 + sample_rows * 30.0).max(56.0);
                    let sample_area = drop_area(ui, list_height, |ui| {
                        if self.samples.is_empty() {
                            ui.centered_and_justified(|ui| {
                                ui.colored_label(MUTED, "拖放样品文件到此处");
                            });
                        } else {
                            egui::ScrollArea::vertical()
                                .id_salt("sample list")
                                .max_height(ui.available_height())
                                .min_scrolled_height(0.0)
                                .auto_shrink([false, true])
                                .show_rows(ui, 25.0, self.samples.len(), |ui, indices| {
                                    for i in indices {
                                        let sample = &self.samples[i];
                                        ui.horizontal(|ui| {
                                            ui.colored_label(sample_color(i), "●");
                                            let checked = self.selected.contains(&i);
                                            let response = ui
                                                .add(
                                                    egui::Button::selectable(
                                                        checked,
                                                        &sample.input.name,
                                                    )
                                                    .truncate()
                                                    .min_size(egui::vec2(
                                                        ui.available_width(),
                                                        25.0,
                                                    )),
                                                )
                                                .on_hover_text(format!(
                                                    "{}\n{}",
                                                    sample.input.name,
                                                    sample.path.display()
                                                ));
                                            if response.clicked() {
                                                if ui.input(|i| {
                                                    i.modifiers.ctrl || i.modifiers.shift
                                                }) {
                                                    if checked {
                                                        self.selected.retain(|x| *x != i);
                                                    } else {
                                                        self.selected.push(i);
                                                    }
                                                } else {
                                                    self.selected = vec![i];
                                                }
                                            }
                                        });
                                    }
                                });
                        }
                    });
                    if let Some(paths) = sample_area {
                        self.import(ui.ctx(), false, Some(paths));
                    }
                    if !self.samples.is_empty() {
                        self.sample_actions(ui);
                    }
                    ui.add_space(6.0);
                    sidebar_section(ui, "分析参数");
                    self.sidebar_parameters(ui);
                });
            });
        let remaining = ui.available_height().max(35.0);
        ui.add_space((remaining - 36.0).max(0.0));
        if primary_button(ui, !busy, "▶  运行分析", egui::vec2(ui.available_width(), 34.0)).clicked() {
            self.run_analysis(ui.ctx());
        }
    }

    fn sample_actions(&mut self, ui: &mut egui::Ui) {
        let (_, (remove, clear)) = egui::containers::Sides::new().show(
            ui,
            |ui| {
                if !self.selected.is_empty() {
                    ui.colored_label(MUTED, format!("已选 {} 个", self.selected.len()));
                }
            },
            |ui| {
                let clear = ui.button("清空").clicked();
                let remove = ui
                    .add_enabled(!self.selected.is_empty(), egui::Button::new("删除选中"))
                    .clicked();
                (remove, clear)
            },
        );
        if clear {
            self.samples.clear();
            self.selected.clear();
        } else if remove {
            self.selected.sort_unstable();
            for i in self.selected.drain(..).rev() {
                self.samples.remove(i);
            }
        }
    }

    fn sidebar_parameters(&mut self, ui: &mut egui::Ui) {
        // Keep all three utility actions on the same right-hand column.
        let action_size = egui::vec2(88.0, 26.0);
        Frame::new()
            .fill(SUBTLE)
            .stroke(Stroke::new(1.0_f32, BORDER))
            .corner_radius(9)
            .inner_margin(Margin::symmetric(10, 8))
            .show(ui, |ui| {
                ui.spacing_mut().item_spacing.y = 5.0;
                let (_, edit_thickness) = egui::containers::Sides::new().show(
                    ui,
                    |ui| {
                        ui.horizontal(|ui| {
                            ui.strong("样品厚度");
                            ui.label(RichText::new("mm").small().color(MUTED));
                        });
                    },
                    |ui| {
                        ui.add_enabled(
                            !self.samples.is_empty(),
                            egui::Button::new("按样品设置").min_size(action_size),
                        )
                        .clicked()
                    },
                );
                if edit_thickness {
                    self.thickness_edits = self
                        .samples
                        .iter()
                        .map(|s| s.thickness.map(|t| t.to_string()).unwrap_or_default())
                        .collect();
                    self.dialog_error = None;
                    self.dialog = Some(Dialog::Thickness);
                }
                let (_, recent) = egui::containers::Sides::new().shrink_left().show(
                    ui,
                    |ui| {
                        ui.add(
                            egui::TextEdit::singleline(&mut self.prefs.thickness)
                                .desired_width(f32::INFINITY)
                                .min_size(egui::vec2(0.0, action_size.y))
                                .margin(Margin::symmetric(8, 3))
                                .vertical_align(egui::Align::Center)
                                .hint_text("默认厚度"),
                        );
                    },
                    |ui| {
                        let mut recent = None;
                        egui::containers::menu::MenuButton::from_button(
                            egui::Button::new("历史 ▼").min_size(action_size),
                        )
                        .ui(ui, |ui| {
                            for value in &self.prefs.history {
                                if ui.button(value).clicked() {
                                    recent = Some(value.clone());
                                    ui.close();
                                }
                            }
                        })
                        .0
                        .on_hover_text("最近使用的厚度");
                        recent
                    },
                );
                if let Some(value) = recent {
                    self.prefs.thickness = value;
                }
                ui.separator();
                let mut use_window = self.prefs.use_window;
                let (_, edit_window) = egui::containers::Sides::new().show(
                    ui,
                    |ui| ui.checkbox(&mut use_window, "Tukey 窗函数"),
                    |ui| {
                        ui.add_enabled(
                            self.prefs.use_window,
                            egui::Button::new("窗口参数").min_size(action_size),
                        )
                        .clicked()
                    },
                );
                self.prefs.use_window = use_window;
                if self.prefs.use_window && edit_window {
                    self.window_edits = std::iter::once(self.reference_window)
                        .chain(self.samples.iter().map(|s| s.window))
                        .map(window_fields)
                        .collect();
                    self.dialog_error = None;
                    self.dialog = Some(Dialog::Window);
                }
                if self.prefs.use_window {
                    let count = usize::from(self.reference_window.is_some())
                        + self.samples.iter().filter(|s| s.window.is_some()).count();
                    if count > 0 {
                        ui.colored_label(MUTED, format!("已自定义 {count} 组窗口参数"));
                    }
                }
            });
    }

    fn results(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            theme::compact_toolbar(ui);
            for (index, (name, _)) in GROUPS.iter().enumerate() {
                let selected = self.charts.group == index;
                let label = RichText::new(*name).strong().color(if selected { ACCENT } else { INK });
                ui.selectable_value(&mut self.charts.group, index, label);
            }
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.menu_button("更多操作 ▼", |ui| {
                    if ui.button(if self.focused { "退出专注" } else { "专注图表" }).clicked() {
                        self.focused = !self.focused;
                        ui.close();
                    }
                    ui.separator();
                    ui.add_enabled_ui(self.result.is_some() && self.pending.is_none(), |ui| {
                        for (kind, caption) in [
                            (ExportKind::Optical, "保存光学参数"),
                            (ExportKind::Time, "保存时域数据"),
                            (ExportKind::Frequency, "保存频域数据"),
                        ] {
                            if ui.button(caption).clicked() {
                                self.export(ui.ctx(), kind, caption);
                                ui.close();
                            }
                        }
                    });
                });
            });
        });
        ui.separator();
        if let Some(done) = &self.result {
            self.charts.show(ui, &done.result);
        } else {
            let space = ui.available_height();
            ui.add_space((space * 0.5 - 72.0).max(0.0));
            ui.vertical_centered(|ui| {
                let (rect, _) =
                    ui.allocate_exact_size(egui::vec2(46.0, 46.0), egui::Sense::hover());
                ui.painter().rect_filled(rect, 9, SELECTED);
                let c = rect.center();
                let stroke = Stroke::new(1.8_f32, ACCENT);
                ui.painter().add(egui::Shape::line(
                    vec![
                        c + egui::vec2(-12.0, -10.0),
                        c + egui::vec2(-12.0, 10.0),
                        c + egui::vec2(12.0, 10.0),
                    ],
                    stroke,
                ));
                ui.painter().add(egui::Shape::line(
                    vec![
                        c + egui::vec2(-8.0, 5.0),
                        c + egui::vec2(-3.0, -3.0),
                        c + egui::vec2(3.0, 1.0),
                        c + egui::vec2(11.0, -8.0),
                    ],
                    stroke,
                ));
                ui.heading("尚无分析结果");
                ui.weak("添加参考文件和样品文件后，点击「运行分析」。");
                if !self.localized {
                    ui.label("Windows Chinese font not found (Microsoft YaHei / SimHei / SimSun).");
                }
            });
        }
    }

    fn show_dialog(&mut self, ctx: &egui::Context) {
        if let Some(message) = &self.notice {
            let mut close = false;
            egui::Modal::new(egui::Id::new("notice")).show(ctx, |ui| {
                ui.set_max_width(660.0);
                ui.heading(if self.error {
                    "处理未完成"
                } else {
                    "提示"
                });
                egui::ScrollArea::vertical()
                    .max_height(340.0)
                    .show(ui, |ui| {
                        ui.label(message);
                    });
                close = ui.button("确定").clicked();
            });
            if close || ctx.input(|i| i.key_pressed(egui::Key::Escape)) {
                self.notice = None;
            }
            return;
        }
        let Some(dialog) = self.dialog else {
            return;
        };
        self.show_parameter_dialog(ctx, dialog);
    }

    fn show_parameter_dialog(&mut self, ctx: &egui::Context, dialog: Dialog) {
        let is_window = matches!(dialog, Dialog::Window);
        let (id, title, width) = if is_window {
            ("window parameters", "Tukey 窗口参数", 560.0)
        } else {
            ("sample thickness", "按样品设置厚度", 410.0)
        };
        let mut close = false;
        egui::Modal::new(egui::Id::new(id))
            .frame(Frame::popup(&ctx.style()).inner_margin(Margin::same(18)))
            .show(ctx, |ui| {
                ui.set_width(width);
                ui.spacing_mut().item_spacing = egui::vec2(8.0, 6.0);
                ui.spacing_mut().interact_size.y = 28.0;
                ui.label(RichText::new(title).size(19.0).strong());
                let hint = if is_window {
                    "起止时间单位为 ps，α 范围为 0–1。每行全部留空时使用默认窗口。".to_owned()
                } else if let Some(default) = positive(&self.prefs.thickness) {
                    format!("留空使用全局厚度（{default} mm）；填写后仅覆盖该样品。")
                } else {
                    "留空使用主界面设置的全局厚度；填写后仅覆盖该样品。".to_owned()
                };
                ui.colored_label(MUTED, hint);
                ui.add_space(4.0);
                egui::containers::Sides::new().show(
                    ui,
                    |ui| ui.colored_label(MUTED, format!("{} 个样品", self.samples.len())),
                    |ui| {
                        if is_window
                            && ui
                                .button("自动定位")
                                .on_hover_text("按各信号的主脉冲填充窗口参数，保存后生效")
                                .clicked()
                        {
                            if let Some((input, _)) = &self.reference {
                                self.window_edits[0] =
                                    window_fields(Some(analysis::suggest_window(&input.signal)));
                            }
                            for (sample, fields) in self
                                .samples
                                .iter()
                                .zip(self.window_edits.iter_mut().skip(1))
                            {
                                *fields = window_fields(Some(analysis::suggest_window(
                                    &sample.input.signal,
                                )));
                            }
                            self.dialog_error = None;
                        }
                    },
                );
                self.parameter_table(
                    ui,
                    is_window,
                    (ctx.screen_rect().height() - 230.0).clamp(120.0, 328.0),
                );
                ui.add_space(4.0);
                ui.separator();
                let (cancel, save) = ui
                    .with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        let save = primary_button(ui, true, "保存设置", egui::vec2(92.0, 30.0))
                            .clicked();
                        let cancel = ui
                            .add(egui::Button::new("取消").min_size(egui::vec2(66.0, 30.0)))
                            .clicked();
                        (cancel, save)
                    })
                    .inner;
                close = cancel || (save && self.save_parameter_edits(is_window));
                if let Some(error) = &self.dialog_error {
                    ui.colored_label(ui.visuals().error_fg_color, error);
                }
            });
        if close || ctx.input(|i| i.key_pressed(egui::Key::Escape)) {
            self.dialog = None;
        }
    }

    fn parameter_table(&mut self, ui: &mut egui::Ui, is_window: bool, max_height: f32) {
        let columns: &[(&str, f32)] = if is_window {
            &[
                ("信号 / 样品", 203.0),
                ("起始 (ps)", 99.0),
                ("结束 (ps)", 99.0),
                ("α", 88.0),
            ]
        } else {
            &[("样品", 218.0), ("厚度 (mm)", 145.0)]
        };
        let start = usize::from(is_window);
        let has_reference = self.reference.is_some();
        let rows = self.samples.len() + usize::from(is_window && has_reference);
        Frame::new()
            .fill(SURFACE)
            .stroke(Stroke::new(1.0_f32, BORDER))
            .corner_radius(7)
            .show(ui, |ui| {
                Frame::new()
                    .fill(SELECTED)
                    .inner_margin(Margin::symmetric(10, 5))
                    .show(ui, |ui| {
                        ui.set_min_width(ui.available_width());
                        ui.horizontal(|ui| {
                            for &(label, width) in columns {
                                parameter_cell(
                                    ui,
                                    width,
                                    RichText::new(label).strong().color(ACCENT),
                                );
                            }
                        });
                    });
                ui.spacing_mut().item_spacing.y = 0.0;
                if rows == 0 {
                    ui.add_space(10.0);
                    ui.vertical_centered(|ui| {
                        ui.colored_label(MUTED, "暂无信号，请先导入参考文件或样品。");
                    });
                    ui.add_space(10.0);
                    return;
                }
                egui::ScrollArea::vertical()
                    .max_height(max_height)
                    .auto_shrink([false, true])
                    .show_rows(ui, 39.0, rows, |ui, range| {
                        for row in range {
                            ui.push_id(row, |ui| {
                                let reference_row = is_window && has_reference && row == 0;
                                let sample =
                                    row.saturating_sub(usize::from(is_window && has_reference));
                                let name = if reference_row {
                                    "参考信号"
                                } else {
                                    &self.samples[sample].input.name
                                };
                                Frame::new()
                                    .fill(if row % 2 == 0 { SURFACE } else { SUBTLE })
                                    .inner_margin(Margin::symmetric(10, 5))
                                    .show(ui, |ui| {
                                        ui.set_min_width(ui.available_width());
                                        ui.horizontal(|ui| {
                                            let label = if reference_row {
                                                RichText::new(name).strong().color(ACCENT)
                                            } else {
                                                RichText::new(name)
                                            };
                                            parameter_cell(ui, columns[0].1, label)
                                                .on_hover_text(name);
                                            if is_window {
                                                let fields = &mut self.window_edits[if reference_row
                                                {
                                                    0
                                                } else {
                                                    sample + start
                                                }];
                                                for (edit, &(label, width)) in
                                                    fields.iter_mut().zip(&columns[1..])
                                                {
                                                    parameter_input(ui, edit, width, "—")
                                                        .on_hover_text(label);
                                                }
                                            } else {
                                                parameter_input(
                                                    ui,
                                                    &mut self.thickness_edits[sample],
                                                    columns[1].1,
                                                    "使用全局厚度",
                                                );
                                            }
                                        });
                                    });
                            });
                        }
                    });
            });
    }

    fn save_parameter_edits(&mut self, is_window: bool) -> bool {
        if is_window {
            let windows: Result<Vec<_>, _> = self
                .window_edits
                .iter()
                .enumerate()
                .map(|(i, fields)| {
                    parse_window(fields).map_err(|error| {
                        if i == 0 {
                            format!("参考信号：{error}")
                        } else {
                            format!(
                                "样品 {:02}（{}）：{error}",
                                i,
                                self.samples[i - 1].input.name
                            )
                        }
                    })
                })
                .collect();
            match windows {
                Ok(windows) => {
                    let mut windows = windows.into_iter();
                    self.reference_window = windows.next().flatten();
                    for (sample, window) in self.samples.iter_mut().zip(windows) {
                        sample.window = window;
                    }
                }
                Err(error) => {
                    self.dialog_error = Some(error);
                    return false;
                }
            }
        } else {
            if let Some((i, _)) = self
                .thickness_edits
                .iter()
                .enumerate()
                .find(|(_, edit)| !edit.trim().is_empty() && positive(edit).is_none())
            {
                self.dialog_error = Some(format!(
                    "样品 {:02}（{}）：厚度必须为有限正数或留空。",
                    i + 1,
                    self.samples[i].input.name
                ));
                return false;
            }
            for (sample, edit) in self.samples.iter_mut().zip(&self.thickness_edits) {
                sample.thickness = positive(edit);
            }
        }
        self.dialog_error = None;
        true
    }
}

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.poll();
        if !self.focused {
            egui::TopBottomPanel::top("brand")
                .frame(Frame::NONE)
                .show(ctx, |ui| self.header(ui));
        }
        egui::TopBottomPanel::bottom("status")
            .frame(
                Frame::new()
                    .fill(WORKSPACE)
                    .inner_margin(Margin::symmetric(16, 4)),
            )
            .show(ctx, |ui| self.status_indicator(ui));
        egui::CentralPanel::default()
            .frame(
                Frame::new()
                    .fill(WORKSPACE)
                    .inner_margin(Margin::symmetric(14, 10)),
            )
            .show(ctx, |ui| {
                let available = ui.available_size();
                ui.horizontal_top(|ui| {
                    if !self.focused {
                        let width = self.side_width.min(available.x - 655.0).max(282.0);
                        ui.allocate_ui_with_layout(
                            Vec2::new(width, available.y),
                            egui::Layout::top_down(egui::Align::Min),
                            |ui| {
                                card().show(ui, |ui| {
                                    ui.set_min_size(ui.available_size());
                                    self.sidebar(ui);
                                });
                            },
                        );
                        let (rect, split) = ui
                            .allocate_exact_size(egui::vec2(5.0, available.y), egui::Sense::drag());
                        let split = split.on_hover_cursor(egui::CursorIcon::ResizeHorizontal);
                        if split.hovered() || split.dragged() {
                            ui.painter().rect_filled(rect, 2, BORDER);
                        }
                        if split.dragged() {
                            self.side_width = (width + split.drag_motion().x)
                                .clamp(282.0, (available.x - 655.0).max(282.0));
                        }
                    }
                    ui.allocate_ui_with_layout(
                        ui.available_size(),
                        egui::Layout::top_down(egui::Align::Min),
                        |ui| {
                            card().show(ui, |ui| {
                                ui.set_min_size(ui.available_size());
                                self.results(ui);
                            });
                        },
                    );
                });
            });
        self.show_dialog(ctx);
    }

    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        self.save_prefs();
    }
}

fn parameter_cell(ui: &mut egui::Ui, width: f32, text: RichText) -> egui::Response {
    ui.add_sized(
        [width, 29.0],
        egui::Label::new(text).truncate().halign(egui::Align::Min),
    )
}

fn parameter_input(
    ui: &mut egui::Ui,
    value: &mut String,
    width: f32,
    hint: &str,
) -> egui::Response {
    ui.add(
        egui::TextEdit::singleline(value)
            .desired_width(width - 14.0)
            .min_size(egui::vec2(width, 29.0))
            .margin(Margin::symmetric(7, 4))
            .vertical_align(egui::Align::Center)
            .hint_text(RichText::new(hint).color(theme::color(0x78879a))),
    )
}

fn sidebar_section(ui: &mut egui::Ui, title: &str) {
    ui.horizontal(|ui| {
        let (mark, _) = ui.allocate_exact_size(egui::vec2(3.0, 13.0), egui::Sense::hover());
        ui.painter().rect_filled(mark, 2, ACCENT);
        ui.label(RichText::new(title).strong().color(ACCENT));
    });
}

fn drop_area(
    ui: &mut egui::Ui,
    height: f32,
    add: impl FnOnce(&mut egui::Ui),
) -> Option<Vec<PathBuf>> {
    let (_, rect) = ui.allocate_space(egui::vec2(ui.available_width(), height));
    let (dragging_file, pointer, client_origin) = ui.input(|i| {
        (
            !i.raw.hovered_files.is_empty() || !i.raw.dropped_files.is_empty(),
            i.pointer.latest_pos(),
            i.viewport().inner_rect.map(|rect| rect.min),
        )
    });
    let pointer = if dragging_file {
        file_drag_position(client_origin, ui.ctx().pixels_per_point()).or(pointer)
    } else {
        pointer
    };
    let targeted = pointer.is_some_and(|p| rect.intersect(ui.clip_rect()).contains(p));
    let hovered = targeted && ui.input(|i| !i.raw.hovered_files.is_empty());
    ui.painter().rect(
        rect,
        8,
        if hovered { SELECTED } else { SUBTLE },
        Stroke::new(1.0_f32, if hovered { ACCENT } else { BORDER }),
        egui::StrokeKind::Inside,
    );
    let mut inner = ui.new_child(
        egui::UiBuilder::new()
            .max_rect(rect.shrink(6.0))
            .layout(egui::Layout::top_down(egui::Align::Min)),
    );
    inner.set_clip_rect(rect.intersect(ui.clip_rect()));
    add(&mut inner);
    let paths: Vec<_> = if targeted && ui.clip_rect().intersects(rect) {
        ui.input(|i| {
            i.raw
                .dropped_files
                .iter()
                .filter_map(|f| f.path.clone())
                .collect()
        })
    } else {
        vec![]
    };
    (!paths.is_empty()).then_some(paths)
}

// Windows OLE file drags need not send ordinary mouse-move events to egui.
fn file_drag_position(origin: Option<egui::Pos2>, scale: f32) -> Option<egui::Pos2> {
    #[cfg(windows)]
    {
        use windows_sys::Win32::{Foundation::POINT, UI::WindowsAndMessaging::GetCursorPos};
        let origin = origin?;
        let mut point = POINT { x: 0, y: 0 };
        // SAFETY: the API writes through a valid pointer to a local POINT.
        (unsafe { GetCursorPos(&mut point) } != 0).then(|| {
            egui::pos2(
                point.x as f32 / scale - origin.x,
                point.y as f32 / scale - origin.y,
            )
        })
    }
    #[cfg(not(windows))]
    {
        let _ = (origin, scale);
        None
    }
}

fn positive(text: &str) -> Option<f64> {
    text.trim()
        .parse::<f64>()
        .ok()
        .filter(|v| v.is_finite() && *v > 0.0)
}
fn window_fields(window: Option<Window>) -> [String; 3] {
    window
        .map(|w| {
            [
                w.start_ps.to_string(),
                w.end_ps.to_string(),
                w.alpha.to_string(),
            ]
        })
        .unwrap_or_default()
}
fn parse_window(fields: &[String; 3]) -> Result<Option<Window>, &'static str> {
    if fields.iter().all(|s| s.trim().is_empty()) {
        return Ok(None);
    }
    let [Ok(start_ps), Ok(end_ps), Ok(alpha)] = fields.each_ref().map(|s| s.trim().parse::<f64>())
    else {
        return Err("请填写起始、结束和 alpha 三个数值。");
    };
    if !start_ps.is_finite()
        || !end_ps.is_finite()
        || start_ps >= end_ps
        || !(0.0..=1.0).contains(&alpha)
    {
        return Err("起始必须小于结束，且 alpha 必须在 0–1 之间。");
    }
    Ok(Some(Window {
        start_ps,
        end_ps,
        alpha,
    }))
}
