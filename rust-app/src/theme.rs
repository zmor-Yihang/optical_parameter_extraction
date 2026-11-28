use eframe::egui::{self, Color32, FontId, Frame, Margin, RichText, Stroke, TextStyle};

pub(crate) const ACCENT: Color32 = color(0x2358b8);
pub(crate) const SURFACE: Color32 = Color32::WHITE;
pub(crate) const WORKSPACE: Color32 = color(0xeff3f8);
pub(crate) const BORDER: Color32 = color(0xd6dfeb);
pub(crate) const INK: Color32 = color(0x18283e);
pub(crate) const MUTED: Color32 = color(0x52647a);
pub(crate) const SELECTED: Color32 = color(0xe6efff);
pub(crate) const SUBTLE: Color32 = color(0xf5f8fc);
const CONTROL_BORDER: Color32 = color(0xbac9db);
const HOVER: Color32 = color(0xdbe8fe);
const PRESSED: Color32 = color(0xcbdcfa);

pub(crate) const fn color(value: u32) -> Color32 {
    let [_, r, g, b] = value.to_be_bytes();
    Color32::from_rgb(r, g, b)
}

pub(crate) fn apply(ctx: &egui::Context) {
    ctx.set_theme(egui::Theme::Light);
    let mut visuals = egui::Visuals::light();
    visuals.panel_fill = WORKSPACE;
    visuals.window_fill = SURFACE;
    visuals.window_stroke = Stroke::new(1.0_f32, BORDER);
    visuals.window_corner_radius = 12.into();
    visuals.menu_corner_radius = 8.into();
    visuals.extreme_bg_color = SURFACE;
    visuals.faint_bg_color = SUBTLE;
    visuals.weak_text_color = Some(MUTED);
    visuals.hyperlink_color = ACCENT;
    visuals.error_fg_color = color(0xac293d);
    visuals.selection.bg_fill = SELECTED;
    visuals.selection.stroke = Stroke::new(1.0_f32, ACCENT);
    for (widget, fill, border) in [
        (&mut visuals.widgets.noninteractive, SUBTLE, BORDER),
        (&mut visuals.widgets.inactive, SURFACE, CONTROL_BORDER),
        (&mut visuals.widgets.hovered, HOVER, ACCENT),
        (&mut visuals.widgets.active, PRESSED, ACCENT),
        (&mut visuals.widgets.open, SELECTED, ACCENT),
    ] {
        widget.bg_fill = fill;
        widget.weak_bg_fill = fill;
        widget.bg_stroke = Stroke::new(1.0_f32, border);
        widget.fg_stroke.color = INK;
        widget.corner_radius = 6.into();
        widget.expansion = 0.0;
    }
    ctx.set_visuals(visuals);
    ctx.style_mut(|style| {
        style.text_styles = [
            (TextStyle::Heading, FontId::proportional(20.0)),
            (TextStyle::Body, FontId::proportional(14.0)),
            (TextStyle::Button, FontId::proportional(14.0)),
            (TextStyle::Small, FontId::proportional(12.0)),
            (TextStyle::Monospace, FontId::monospace(13.0)),
        ]
        .into();
        style.spacing.item_spacing = egui::vec2(7.0, 5.0);
        style.spacing.button_padding = egui::vec2(9.0, 3.0);
        style.spacing.interact_size.y = 26.0;
    });
}

pub(crate) fn card() -> Frame {
    Frame::new()
        .fill(SURFACE)
        .stroke(Stroke::new(1.0_f32, BORDER))
        .corner_radius(12)
        .inner_margin(Margin::symmetric(12, 10))
}

pub(crate) fn compact_toolbar(ui: &mut egui::Ui) {
    let spacing = ui.spacing_mut();
    spacing.item_spacing = egui::vec2(5.0, 3.0);
    spacing.button_padding = egui::vec2(7.0, 2.0);
    spacing.interact_size.y = 24.0;
}

pub(crate) fn primary_button(
    ui: &mut egui::Ui,
    enabled: bool,
    text: &str,
    size: egui::Vec2,
) -> egui::Response {
    ui.scope(|ui| {
        let widgets = &mut ui.visuals_mut().widgets;
        for (widget, fill) in [
            (&mut widgets.inactive, ACCENT),
            (&mut widgets.hovered, color(0x1e4da4)),
            (&mut widgets.active, color(0x173d83)),
        ] {
            widget.weak_bg_fill = fill;
            widget.bg_stroke.color = fill;
        }
        ui.add_enabled(
            enabled,
            egui::Button::new((
                egui::Atom::grow(),
                RichText::new(text).strong().color(SURFACE),
                egui::Atom::grow(),
            ))
            .min_size(size),
        )
    })
    .inner
}
