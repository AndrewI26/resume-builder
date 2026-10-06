//! The first screen: what is in the library, and where to go next.

use super::style::{self, Kind};
use super::widgets::{self, btn, page, panel, subtle, title};
use super::{Library, Outcome, Route};
use crate::api::models::Backup;
use crate::api::{ApiResult, Client};
use iced::widget::{button, column, row, space, text};
use iced::{Alignment, Element, Length, Task};

#[derive(Debug, Default)]
pub struct State {
    backing_up: bool,
    backup: Option<Result<String, String>>,
}

#[derive(Debug, Clone)]
pub enum Message {
    Open(Route),
    BackUp,
    BackedUp(ApiResult<Backup>),
}

impl State {
    pub fn update(&mut self, message: Message, client: Client) -> Outcome<Message> {
        match message {
            Message::Open(route) => Outcome::navigate(route),
            Message::BackUp => {
                self.backing_up = true;
                self.backup = None;
                Outcome::task(Task::perform(
                    async move { client.back_up().await },
                    Message::BackedUp,
                ))
            }
            Message::BackedUp(result) => {
                self.backing_up = false;
                self.backup = Some(result.map(|backup| backup.path).map_err(|error| error.0));
                Outcome::none()
            }
        }
    }

    pub fn view<'a>(&'a self, library: &'a Library) -> Element<'a, Message> {
        let cards = row![
            stat(
                "Resumes",
                library.resumes.len(),
                "Tailored versions you can edit and export.",
                Route::Resumes,
            ),
            stat(
                "Sections",
                library.section_count(),
                "Education, experience, projects and skills.",
                Route::Sections,
            ),
        ]
        .spacing(16);

        page(
            column![
                title("Dashboard"),
                space::vertical().height(8),
                subtle("Everything is kept on this computer."),
                space::vertical().height(32),
                cards,
                space::vertical().height(32),
                self.backup_panel(),
            ]
            .width(Length::Fill),
        )
    }

    /// One SQLite file on one machine, with nobody else holding a copy — so
    /// the desktop offers a backup, and says exactly where it went.
    fn backup_panel(&self) -> Element<'_, Message> {
        let mut content = column![
            row![
                column![
                    text("Back up your data").size(16),
                    subtle(
                        "Copies everything — resumes and sections — into a dated file inside the app's own folder."
                    ),
                ]
                .spacing(4)
                .width(Length::Fill),
                btn(
                    if self.backing_up { "Backing up…" } else { "Back up now" },
                    Kind::Secondary,
                    (!self.backing_up).then_some(Message::BackUp),
                ),
            ]
            .spacing(16)
            .align_y(Alignment::Center)
        ]
        .spacing(12);

        match &self.backup {
            Some(Ok(path)) => content = content.push(subtle(format!("Saved to {path}"))),
            Some(Err(error)) => content = content.push(widgets::banner(error)),
            None => {}
        }

        panel(content)
    }
}

fn stat<'a>(
    label: &'a str,
    value: usize,
    description: &'a str,
    route: Route,
) -> Element<'a, Message> {
    let body = column![
        subtle(label),
        text(value.to_string()).size(44),
        subtle(description),
    ]
    .spacing(6);

    button(body)
        .padding(24)
        .width(Length::Fill)
        .style(style::button(Kind::Surface))
        .on_press(Message::Open(route))
        .into()
}
