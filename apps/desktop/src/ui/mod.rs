//! The window: which screen is showing, and the library every screen reads.
//!
//! Screens own their own state and messages, and hand back an [`Outcome`]
//! saying what should happen next — a task to run, a screen to open, or the
//! library to reload because they just changed it. The library is fetched
//! whole and re-fetched after any write, which is the desktop's version of
//! the web app's query invalidation: simple, and never stale for long on a
//! server that answers in a millisecond.

mod dashboard;
mod editor;
mod form;
mod resumes;
mod sections;
pub mod style;
mod widgets;

#[cfg(test)]
mod tests;

use crate::api::models::{PersonalInfo, Resume};
use crate::api::{ApiResult, Client};
use crate::draft::Catalogs;
use crate::sidecar::{self, Endpoint};
use iced::widget::{button, center, column, container, row, scrollable, space, text};
use iced::{Alignment, Element, Length, Subscription, Task, Theme, window};
use style::Kind;
use widgets::{btn, subtle};

pub use form::Kind as SectionKind;

/// Everything in the library, as the screens need it.
#[derive(Debug, Clone, Default)]
pub struct Library {
    pub catalogs: Catalogs,
    pub personal_info: Vec<PersonalInfo>,
    pub resumes: Vec<Resume>,
}

impl Library {
    /// Rows across the four section types. Personal info is the header, not
    /// a section, so it is left out — as it is everywhere else.
    pub fn section_count(&self) -> usize {
        self.catalogs.education.len()
            + self.catalogs.experience.len()
            + self.catalogs.project.len()
            + self.catalogs.skill.len()
    }
}

async fn load(client: Client) -> ApiResult<Library> {
    let (education, experience, project, skill, personal_info, resumes) = tokio::try_join!(
        client.education(),
        client.experience(),
        client.projects(),
        client.skills(),
        client.personal_info(),
        client.resumes(),
    )?;

    Ok(Library {
        catalogs: Catalogs {
            education,
            experience,
            project,
            skill,
        },
        personal_info,
        resumes,
    })
}

#[derive(Debug, Clone, PartialEq)]
pub enum Route {
    Dashboard,
    Sections,
    /// A section form: the type, and the row being edited if it is not new.
    Section(SectionKind, Option<String>),
    Resumes,
    Editor(String),
}

/// What a screen's update wants to happen next.
pub struct Outcome<M> {
    pub task: Task<M>,
    pub navigate: Option<Route>,
    pub reload: bool,
}

impl<M> Outcome<M> {
    pub fn none() -> Self {
        Self {
            task: Task::none(),
            navigate: None,
            reload: false,
        }
    }

    pub fn task(task: Task<M>) -> Self {
        Self {
            task,
            ..Self::none()
        }
    }

    pub fn navigate(route: Route) -> Self {
        Self {
            navigate: Some(route),
            ..Self::none()
        }
    }

    pub fn reload(mut self) -> Self {
        self.reload = true;
        self
    }
}

enum Phase {
    Starting,
    Failed(String),
    Ready(Client),
}

enum Screen {
    Dashboard(dashboard::State),
    Sections,
    Form(Box<form::State>),
    Resumes(Box<resumes::State>),
    Editor(Box<editor::State>),
}

#[derive(Debug, Clone)]
pub enum Message {
    Started(Result<Endpoint, String>),
    Retry,
    Loaded(ApiResult<Library>),
    Navigate(Route),
    ToggleTheme,
    CloseRequested,
    Stopped,
    Dashboard(dashboard::Message),
    Form(form::Message),
    Resumes(resumes::Message),
    Editor(editor::Message),
}

pub struct App {
    phase: Phase,
    dark: bool,
    library: Option<Library>,
    library_error: Option<String>,
    screen: Screen,
    closing: bool,
}

fn start() -> Task<Message> {
    Task::perform(
        async {
            tokio::task::spawn_blocking(sidecar::start)
                .await
                .unwrap_or_else(|error| Err(format!("The startup thread failed: {error}")))
        },
        Message::Started,
    )
}

fn system_is_dark() -> bool {
    matches!(dark_light::detect(), Ok(dark_light::Mode::Dark))
}

impl App {
    pub fn boot() -> (Self, Task<Message>) {
        let app = Self {
            phase: Phase::Starting,
            dark: crate::settings::load().dark.unwrap_or_else(system_is_dark),
            library: None,
            library_error: None,
            screen: Screen::Dashboard(dashboard::State::default()),
            closing: false,
        };
        (app, start())
    }

    pub fn title(&self) -> String {
        match &self.screen {
            Screen::Dashboard(_) => "Resume Builder".into(),
            Screen::Sections => "Sections · Resume Builder".into(),
            Screen::Form(form) => format!("{} · Resume Builder", form.title()),
            Screen::Resumes(_) => "Resumes · Resume Builder".into(),
            Screen::Editor(editor) => format!("{} · Resume Builder", editor.title()),
        }
    }

    pub fn theme(&self) -> Theme {
        style::theme(self.dark)
    }

    pub fn subscription(&self) -> Subscription<Message> {
        let close = window::close_requests().map(|_| Message::CloseRequested);
        match &self.screen {
            Screen::Editor(editor) => {
                Subscription::batch([close, editor.subscription().map(Message::Editor)])
            }
            _ => close,
        }
    }

    fn client(&self) -> Option<Client> {
        match &self.phase {
            Phase::Ready(client) => Some(client.clone()),
            _ => None,
        }
    }

    fn reload(&self) -> Task<Message> {
        match self.client() {
            Some(client) => Task::perform(load(client), Message::Loaded),
            None => Task::none(),
        }
    }

    /// Fold a screen's outcome into the app: run its task, follow its route,
    /// and refetch the library if it wrote to it.
    fn apply<M: Send + 'static>(
        &mut self,
        outcome: Outcome<M>,
        wrap: fn(M) -> Message,
    ) -> Task<Message> {
        let mut tasks = vec![outcome.task.map(wrap)];
        if outcome.reload {
            tasks.push(self.reload());
        }
        if let Some(route) = outcome.navigate {
            tasks.push(self.open(route));
        }
        Task::batch(tasks)
    }

    fn open(&mut self, route: Route) -> Task<Message> {
        let empty = Library::default();
        let library = self.library.as_ref().unwrap_or(&empty);

        match route {
            Route::Dashboard => {
                self.screen = Screen::Dashboard(dashboard::State::default());
                Task::none()
            }
            Route::Sections => {
                self.screen = Screen::Sections;
                Task::none()
            }
            Route::Section(kind, id) => {
                self.screen =
                    Screen::Form(Box::new(form::State::new(kind, id.as_deref(), library)));
                Task::none()
            }
            Route::Resumes => {
                self.screen = Screen::Resumes(Box::default());
                Task::none()
            }
            Route::Editor(id) => {
                let Some(client) = self.client() else {
                    return Task::none();
                };
                let (state, task) = editor::State::new(id, client);
                self.screen = Screen::Editor(Box::new(state));
                task.map(Message::Editor)
            }
        }
    }

    pub fn update(&mut self, message: Message) -> Task<Message> {
        match message {
            Message::Started(Ok(endpoint)) => {
                self.phase = Phase::Ready(Client::new(endpoint.base_url, endpoint.token));
                self.reload()
            }
            Message::Started(Err(error)) => {
                self.phase = Phase::Failed(error);
                Task::none()
            }
            Message::Retry => {
                self.phase = Phase::Starting;
                start()
            }
            Message::Loaded(Ok(library)) => {
                self.library = Some(library);
                self.library_error = None;
                Task::none()
            }
            Message::Loaded(Err(error)) => {
                self.library_error = Some(error.0);
                Task::none()
            }
            Message::Navigate(route) => {
                // reopening a screen also refreshes what it shows
                let reload = self.reload();
                Task::batch([self.open(route), reload])
            }
            Message::ToggleTheme => {
                self.dark = !self.dark;
                crate::settings::save(&crate::settings::Settings {
                    dark: Some(self.dark),
                });
                Task::none()
            }
            Message::CloseRequested => {
                if self.closing {
                    return Task::none();
                }
                self.closing = true;

                // an edit still waiting on its autosave is written first:
                // closing the window is not a reason to lose it
                let client = self.client();
                let flush = match (&mut self.screen, client) {
                    (Screen::Editor(editor), Some(client)) => {
                        editor.flush(client).map(Message::Editor)
                    }
                    _ => Task::none(),
                };

                flush.chain(Task::perform(
                    async {
                        let _ = tokio::task::spawn_blocking(sidecar::stop).await;
                    },
                    |()| Message::Stopped,
                ))
            }
            Message::Stopped => iced::exit(),
            Message::Dashboard(message) => {
                let client = self.client();
                let (Screen::Dashboard(state), Some(client)) = (&mut self.screen, client) else {
                    return Task::none();
                };
                let outcome = state.update(message, client);
                self.apply(outcome, Message::Dashboard)
            }
            Message::Form(message) => {
                let client = self.client();
                let (Screen::Form(state), Some(client)) = (&mut self.screen, client) else {
                    return Task::none();
                };
                let outcome = state.update(message, client);
                self.apply(outcome, Message::Form)
            }
            Message::Resumes(message) => {
                let client = self.client();
                let (Screen::Resumes(state), Some(client)) = (&mut self.screen, client) else {
                    return Task::none();
                };
                let library = self.library.clone().unwrap_or_default();
                let outcome = state.update(message, client, &library);
                self.apply(outcome, Message::Resumes)
            }
            Message::Editor(message) => {
                let client = self.client();
                let (Screen::Editor(state), Some(client)) = (&mut self.screen, client) else {
                    return Task::none();
                };
                let library = self.library.clone().unwrap_or_default();
                let outcome = state.update(message, client, &library);
                self.apply(outcome, Message::Editor)
            }
        }
    }

    pub fn view(&self) -> Element<'_, Message> {
        let body: Element<'_, Message> = match &self.phase {
            Phase::Starting => center(subtle("Opening your library…")).into(),
            Phase::Failed(error) => self.failed(error),
            Phase::Ready(_) => match (&self.library, &self.library_error) {
                (_, Some(error)) => center(
                    column![
                        widgets::banner(error),
                        btn(
                            "Try again",
                            Kind::Secondary,
                            Some(Message::Navigate(Route::Dashboard))
                        ),
                    ]
                    .spacing(16)
                    .max_width(520),
                )
                .into(),
                (None, None) => center(subtle("Loading…")).into(),
                (Some(library), None) => self.screen(library),
            },
        };

        container(column![self.navbar(), body])
            .width(Length::Fill)
            .height(Length::Fill)
            .style(style::page)
            .into()
    }

    fn screen<'a>(&'a self, library: &'a Library) -> Element<'a, Message> {
        match &self.screen {
            Screen::Dashboard(state) => state.view(library).map(Message::Dashboard),
            Screen::Sections => sections::view(library),
            Screen::Form(state) => state.view().map(Message::Form),
            Screen::Resumes(state) => state.view(library).map(Message::Resumes),
            Screen::Editor(state) => state.view(library).map(Message::Editor),
        }
    }

    fn navbar(&self) -> Element<'_, Message> {
        let home = button(text("Resume Builder").size(18))
            .padding(0)
            .style(style::button(Kind::Link))
            .on_press(Message::Navigate(Route::Dashboard));

        let toggle = btn(
            if self.dark { "☾" } else { "☀" },
            Kind::Tertiary,
            Some(Message::ToggleTheme),
        );

        row![home, space::horizontal(), toggle]
            .align_y(Alignment::Center)
            .padding([12, 20])
            .into()
    }

    /// The sidecar would not start. Say why, in its own words, and offer a retry.
    fn failed<'a>(&'a self, error: &'a str) -> Element<'a, Message> {
        let detail = scrollable(
            container(text(error).size(12).font(iced::Font::MONOSPACE))
                .padding(12)
                .width(Length::Fill),
        )
        .height(Length::Fixed(260.0))
        .style(style::scroll);

        center(
            column![
                widgets::heading("The app could not open your library"),
                subtle(
                    "Its built-in server did not start. The details below are what it reported."
                ),
                container(detail).style(style::error_banner),
                btn("Try again", Kind::Primary, Some(Message::Retry)),
            ]
            .spacing(16)
            .max_width(640),
        )
        .padding(24)
        .into()
    }
}
