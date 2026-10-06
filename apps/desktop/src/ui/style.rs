//! The app's look, in Iced's terms.
//!
//! The colours are the web app's design tokens (`apps/web/app/theme.css`),
//! light and dark, so the two apps read as one product. Each style function
//! picks its palette from the theme it is handed, which is what lets the
//! whole window switch with a single theme change.

use iced::widget::{container, pick_list, text_editor, text_input};
use iced::{Background, Border, Color, Shadow, Theme, Vector, color};

pub struct Tokens {
    pub page: Color,
    pub card: Color,
    pub panel: Color,
    pub panel_border: Color,
    pub border: Color,
    pub field: Color,
    pub ink: Color,
    pub ink_subtle: Color,
    pub ink_disabled: Color,
    pub stroke: Color,
    pub primary: Color,
    pub primary_fg: Color,
    pub secondary: Color,
    pub secondary_fg: Color,
    pub secondary_border: Color,
    pub tertiary: Color,
    pub tertiary_fg: Color,
    pub warning: Color,
    pub warning_fg: Color,
    pub negative: Color,
    pub negative_bg: Color,
    pub informative: Color,
    pub positive: Color,
    pub row_hover: Color,
    pub header_ink: Color,
}

const fn alpha(base: Color, a: f32) -> Color {
    Color { a, ..base }
}

pub const LIGHT: Tokens = Tokens {
    page: color!(0xf2f1ed),
    card: color!(0xffffff),
    panel: color!(0xffffff),
    panel_border: color!(0xe8e7e3),
    border: color!(0xe2e2e2),
    field: color!(0xffffff),
    ink: color!(0x32302f),
    ink_subtle: color!(0x615e5c),
    ink_disabled: color!(0x94908d),
    stroke: color!(0x32302f),
    primary: color!(0x32302f),
    primary_fg: color!(0xfcfcfc),
    secondary: color!(0xffffff),
    secondary_fg: color!(0x32302f),
    secondary_border: color!(0xe4e2e1),
    tertiary: alpha(color!(0x32302f), 0.08),
    tertiary_fg: color!(0x615e5c),
    warning: color!(0xfbe4de),
    warning_fg: color!(0xbf3722),
    negative: color!(0xbf3722),
    negative_bg: color!(0xfbe4de),
    informative: color!(0x196ea4),
    positive: color!(0x4c7a15),
    row_hover: color!(0xfaf9f7),
    header_ink: color!(0x6f6c68),
};

pub const DARK: Tokens = Tokens {
    page: color!(0x000000),
    card: color!(0x171717),
    panel: color!(0x101010),
    panel_border: color!(0x232323),
    border: color!(0x2c2c2c),
    field: alpha(color!(0xfcfcfc), 0.03),
    ink: color!(0xe4e2e1),
    ink_subtle: color!(0xbfbebe),
    ink_disabled: color!(0x8f8d8a),
    stroke: color!(0xfcfcfc),
    primary: color!(0xfcfcfc),
    primary_fg: color!(0x32302f),
    secondary: color!(0x000000),
    secondary_fg: color!(0xfcfcfc),
    secondary_border: color!(0x615e5c),
    tertiary: alpha(color!(0xfcfcfc), 0.12),
    tertiary_fg: color!(0xfcfcfc),
    warning: color!(0x411e1a),
    warning_fg: color!(0xf76b5a),
    negative: color!(0xf76b5a),
    negative_bg: color!(0x411e1a),
    informative: color!(0x78bfea),
    positive: color!(0x97c75c),
    row_hover: color!(0x171717),
    header_ink: color!(0x8f8d8a),
};

pub fn tokens(theme: &Theme) -> &'static Tokens {
    if theme.extended_palette().is_dark {
        &DARK
    } else {
        &LIGHT
    }
}

/// The two themes, built from the tokens so Iced's own defaults agree too.
pub fn theme(dark: bool) -> Theme {
    let t = if dark { &DARK } else { &LIGHT };
    Theme::custom(
        if dark {
            "Resume Builder Dark"
        } else {
            "Resume Builder Light"
        },
        iced::theme::Palette {
            background: t.page,
            text: t.ink,
            primary: t.primary,
            success: t.positive,
            warning: t.warning_fg,
            danger: t.negative,
        },
    )
}

pub const RADIUS_PILL: f32 = 999.0;
pub const RADIUS_CARD: f32 = 24.0;
pub const RADIUS_PANEL: f32 = 12.0;

/// Barely-there lift: enough to separate a white card from the canvas.
fn raised() -> Shadow {
    Shadow {
        color: Color::from_rgba(0.0, 0.0, 0.0, 0.06),
        offset: Vector::new(0.0, 1.0),
        blur_radius: 3.0,
    }
}

// -- containers ---------------------------------------------------------------

pub fn page(theme: &Theme) -> container::Style {
    let t = tokens(theme);
    container::Style {
        background: Some(t.page.into()),
        text_color: Some(t.ink),
        ..container::Style::default()
    }
}

pub fn card(theme: &Theme) -> container::Style {
    let t = tokens(theme);
    container::Style {
        background: Some(t.card.into()),
        border: Border {
            color: t.border,
            width: 1.0,
            radius: RADIUS_CARD.into(),
        },
        shadow: raised(),
        ..container::Style::default()
    }
}

pub fn panel(theme: &Theme) -> container::Style {
    let t = tokens(theme);
    container::Style {
        background: Some(t.panel.into()),
        border: Border {
            color: t.panel_border,
            width: 1.0,
            radius: RADIUS_PANEL.into(),
        },
        ..container::Style::default()
    }
}

/// A dashed-looking well for "not on this resume"; Iced has no dashed
/// borders, so a transparent fill with a quiet edge stands in.
pub fn well(theme: &Theme) -> container::Style {
    let t = tokens(theme);
    container::Style {
        border: Border {
            color: t.border,
            width: 1.0,
            radius: RADIUS_PANEL.into(),
        },
        ..container::Style::default()
    }
}

pub fn row(theme: &Theme) -> container::Style {
    let t = tokens(theme);
    container::Style {
        background: Some(t.field.into()),
        border: Border {
            color: t.panel_border,
            width: 1.0,
            radius: 8.0.into(),
        },
        ..container::Style::default()
    }
}

pub fn error_banner(theme: &Theme) -> container::Style {
    let t = tokens(theme);
    container::Style {
        background: Some(t.negative_bg.into()),
        text_color: Some(t.negative),
        border: Border {
            radius: RADIUS_PANEL.into(),
            ..Border::default()
        },
        ..container::Style::default()
    }
}

/// The page behind a modal, dimmed so the dialog is the only thing to read.
pub fn scrim(_theme: &Theme) -> container::Style {
    container::Style {
        background: Some(Color::from_rgba(0.0, 0.0, 0.0, 0.45).into()),
        ..container::Style::default()
    }
}

/// The white sheet the compiled PDF sits on, in either theme.
pub fn paper(theme: &Theme) -> container::Style {
    let t = tokens(theme);
    container::Style {
        background: Some(Color::WHITE.into()),
        border: Border {
            color: t.border,
            width: 1.0,
            radius: RADIUS_PANEL.into(),
        },
        ..container::Style::default()
    }
}

// -- buttons ------------------------------------------------------------------

#[derive(Debug, Clone, Copy)]
pub enum Kind {
    Primary,
    Secondary,
    Tertiary,
    Danger,
    /// Text that reads as a link: the back links, a row's title.
    Link,
    /// A small glyph button: ↑, ↓, remove.
    Icon,
    /// A whole row or card that opens something.
    Surface,
}

pub fn button(
    kind: Kind,
) -> impl Fn(&Theme, iced::widget::button::Status) -> iced::widget::button::Style {
    use iced::widget::button;
    move |theme, status| {
        let t = tokens(theme);
        let disabled = matches!(status, button::Status::Disabled);
        let hovered = matches!(status, button::Status::Hovered | button::Status::Pressed);
        let pill = Border {
            radius: RADIUS_PILL.into(),
            ..Border::default()
        };

        let (background, text, border) = match kind {
            Kind::Primary => (
                Some(if disabled { t.tertiary } else { t.primary }),
                if disabled {
                    t.ink_disabled
                } else {
                    t.primary_fg
                },
                pill,
            ),
            Kind::Secondary => (
                Some(t.secondary),
                if disabled {
                    t.ink_disabled
                } else {
                    t.secondary_fg
                },
                Border {
                    color: if hovered {
                        t.stroke
                    } else {
                        t.secondary_border
                    },
                    width: 1.0,
                    ..pill
                },
            ),
            Kind::Tertiary => (
                Some(t.tertiary),
                if disabled {
                    t.ink_disabled
                } else {
                    t.tertiary_fg
                },
                pill,
            ),
            Kind::Danger => (
                Some(if disabled { t.tertiary } else { t.warning }),
                if disabled {
                    t.ink_disabled
                } else {
                    t.warning_fg
                },
                pill,
            ),
            Kind::Link => (
                None,
                if hovered { t.ink } else { t.ink_subtle },
                Border::default(),
            ),
            Kind::Icon => (
                if hovered && !disabled {
                    Some(t.tertiary)
                } else {
                    None
                },
                if disabled {
                    alpha(t.ink_subtle, 0.3)
                } else if hovered {
                    t.ink
                } else {
                    t.ink_subtle
                },
                pill,
            ),
            Kind::Surface => (
                Some(if hovered { t.row_hover } else { t.card }),
                t.ink,
                Border {
                    color: t.border,
                    width: 1.0,
                    radius: RADIUS_CARD.into(),
                },
            ),
        };

        let fade = hovered && matches!(kind, Kind::Primary | Kind::Tertiary | Kind::Danger);
        button::Style {
            background: background.map(|color| {
                Background::Color(if fade {
                    alpha(color, color.a * 0.9)
                } else {
                    color
                })
            }),
            text_color: text,
            border,
            shadow: Shadow::default(),
            snap: true,
        }
    }
}

// -- inputs -------------------------------------------------------------------

pub fn input(invalid: bool) -> impl Fn(&Theme, text_input::Status) -> text_input::Style {
    move |theme, status| {
        let t = tokens(theme);
        let focused = matches!(status, text_input::Status::Focused { .. });
        text_input::Style {
            background: t.field.into(),
            border: Border {
                color: if invalid {
                    t.negative
                } else if focused {
                    t.stroke
                } else {
                    t.border
                },
                width: 1.0,
                radius: RADIUS_PANEL.into(),
            },
            icon: t.ink_subtle,
            placeholder: t.ink_disabled,
            value: t.ink,
            selection: alpha(t.informative, 0.3),
        }
    }
}

pub fn editor(theme: &Theme, status: text_editor::Status) -> text_editor::Style {
    let t = tokens(theme);
    let focused = matches!(status, text_editor::Status::Focused { .. });
    text_editor::Style {
        background: t.field.into(),
        border: Border {
            color: if focused { t.stroke } else { t.border },
            width: 1.0,
            radius: RADIUS_PANEL.into(),
        },
        placeholder: t.ink_disabled,
        value: t.ink,
        selection: alpha(t.informative, 0.3),
    }
}

pub fn picker(theme: &Theme, status: pick_list::Status) -> pick_list::Style {
    let t = tokens(theme);
    let active = !matches!(status, pick_list::Status::Active);
    pick_list::Style {
        text_color: t.ink,
        placeholder_color: t.ink_disabled,
        handle_color: t.ink_subtle,
        background: t.field.into(),
        border: Border {
            color: if active { t.stroke } else { t.border },
            width: 1.0,
            radius: RADIUS_PANEL.into(),
        },
    }
}

/// Iced's scrollbars, recoloured: a quiet thumb on no track, darkening while
/// it is held, instead of the theme's accent colour.
pub fn scroll(
    theme: &Theme,
    status: iced::widget::scrollable::Status,
) -> iced::widget::scrollable::Style {
    use iced::widget::scrollable::{self, Status};

    let t = tokens(theme);
    let mut style = scrollable::default(theme, status);
    let engaged = matches!(status, Status::Dragged { .. } | Status::Hovered { .. });
    let thumb = if engaged { t.ink_disabled } else { t.border };

    for rail in [&mut style.vertical_rail, &mut style.horizontal_rail] {
        rail.background = None;
        rail.border = Border::default();
        rail.scroller.background = thumb.into();
        rail.scroller.border = Border {
            radius: RADIUS_PILL.into(),
            ..Border::default()
        };
    }
    style
}
