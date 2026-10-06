//! The handful of building blocks every screen is made from.

use super::style::{self, Kind, tokens};
use iced::widget::{
    Button, Column, button, center, column, container, opaque, row, scrollable, space, stack, text,
    text_input,
};
use iced::{Alignment, Element, Font, Length, Padding, font};

pub const BOLD: Font = Font {
    weight: font::Weight::Bold,
    ..Font::DEFAULT
};

/// The widest a reading column gets, like the web app's `max-w-3xl`.
pub const COLUMN_WIDTH: f32 = 768.0;

pub fn title<'a, M>(value: impl text::IntoFragment<'a>) -> Element<'a, M> {
    text(value).size(36).into()
}

pub fn heading<'a, M>(value: impl text::IntoFragment<'a>) -> Element<'a, M> {
    text(value).size(22).into()
}

pub fn label<'a, M>(value: impl text::IntoFragment<'a>) -> Element<'a, M> {
    text(value).size(14).font(BOLD).into()
}

pub fn subtle<'a>(value: impl text::IntoFragment<'a>) -> text::Text<'a> {
    text(value).size(14).style(|theme| text::Style {
        color: Some(tokens(theme).ink_subtle),
    })
}

pub fn negative<'a>(value: impl text::IntoFragment<'a>) -> text::Text<'a> {
    text(value).size(14).style(|theme| text::Style {
        color: Some(tokens(theme).negative),
    })
}

/// A button in one of the app's variants. `on_press: None` disables it.
pub fn btn<'a, M: Clone + 'a>(
    content: impl text::IntoFragment<'a>,
    kind: Kind,
    on_press: Option<M>,
) -> Button<'a, M> {
    let padding = match kind {
        Kind::Link => Padding::ZERO,
        Kind::Icon => Padding::from([4, 8]),
        _ => Padding::from([9, 18]),
    };
    button(text(content).size(15))
        .padding(padding)
        .style(style::button(kind))
        .on_press_maybe(on_press)
}

pub fn back<'a, M: Clone + 'a>(value: &'a str, on_press: M) -> Element<'a, M> {
    btn(format!("←  {value}"), Kind::Link, Some(on_press)).into()
}

/// A labelled text field, with its validation message under it.
pub fn field<'a, M: Clone + 'a>(
    label: &'a str,
    placeholder: &'a str,
    value: &'a str,
    on_input: impl Fn(String) -> M + 'a,
    error: Option<&'a str>,
) -> Element<'a, M> {
    let input = text_input(placeholder, value)
        .on_input(on_input)
        .padding([9, 14])
        .size(15)
        .style(style::input(error.is_some()));

    let mut out = column![subtle(label), input].spacing(6);
    if let Some(error) = error {
        out = out.push(negative(error));
    }
    out.into()
}

pub fn banner<'a, M: 'a>(message: &'a str) -> Element<'a, M> {
    container(text(message).size(14))
        .padding([10, 16])
        .width(Length::Fill)
        .style(style::error_banner)
        .into()
}

pub fn panel<'a, M: 'a>(content: impl Into<Element<'a, M>>) -> Element<'a, M> {
    container(content)
        .padding(16)
        .width(Length::Fill)
        .style(style::panel)
        .into()
}

/// A screen's content, centred in a reading column and scrollable.
pub fn page<'a, M: 'a>(content: Column<'a, M>) -> Element<'a, M> {
    scrollable(
        container(content.max_width(COLUMN_WIDTH).spacing(0))
            .center_x(Length::Fill)
            .padding(Padding::from([40, 24])),
    )
    .height(Length::Fill)
    .style(style::scroll)
    .into()
}

/// A question the person has to answer before something destructive runs.
pub struct Confirm<'a, M> {
    pub title: &'a str,
    pub body: Element<'a, M>,
    pub confirm: &'a str,
    pub pending: Option<&'a str>,
    pub error: Option<&'a str>,
    pub on_cancel: M,
    pub on_confirm: M,
}

/// Lay `dialog` over `base`, dimming the page and swallowing its clicks.
pub fn modal<'a, M: Clone + 'a>(
    base: impl Into<Element<'a, M>>,
    dialog: Option<Confirm<'a, M>>,
) -> Element<'a, M> {
    let Some(dialog) = dialog else {
        return base.into();
    };

    let busy = dialog.pending.is_some();
    let mut body = column![heading(dialog.title), dialog.body].spacing(12);
    if let Some(error) = dialog.error {
        body = body.push(banner(error));
    }
    body = body.push(
        row![
            space::horizontal(),
            btn(
                "Cancel",
                Kind::Secondary,
                (!busy).then(|| dialog.on_cancel.clone())
            ),
            btn(
                dialog.pending.unwrap_or(dialog.confirm),
                Kind::Danger,
                (!busy).then(|| dialog.on_confirm.clone()),
            ),
        ]
        .spacing(10)
        .align_y(Alignment::Center),
    );

    let card = container(body.spacing(16))
        .padding(28)
        .max_width(480)
        .style(style::card);

    stack![base.into(), opaque(center(card).style(style::scrim))].into()
}
