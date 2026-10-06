//! The resumes: making a new one, exporting them all, and deleting one.

use super::style::{self, Kind, tokens};
use super::widgets::{self, back, btn, label, modal, page, panel, subtle, title};
use super::{Library, Outcome, Route};
use crate::api::models::{Resume, ResumeCreate, SectionRef, SectionType};
use crate::api::{ApiResult, Client};
use crate::export;
use iced::futures::SinkExt;
use iced::widget::{Column, button, column, pick_list, row, space, text, text_input};
use iced::{Alignment, Element, Length, Task};
use std::fmt;
use std::path::PathBuf;

/// The only template the renderer implements. Stated rather than left to the
/// server's default, so adding a second one surfaces here.
const TEMPLATE: &str = "jakes";

/// A pickable option: an id, and what the person reads.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Choice {
    pub id: String,
    pub label: String,
}

impl fmt::Display for Choice {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.label)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TypeChoice(pub SectionType);

impl fmt::Display for TypeChoice {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self.0 {
            SectionType::Education => "Education",
            SectionType::Experience => "Experience",
            SectionType::Project => "Project",
            SectionType::Skill => "Skill",
        })
    }
}

/// The contact-details options, with `None` as the way back out of a pick.
/// An empty library offers nothing, so the picker can say so.
pub fn contact_choices(library: &Library) -> Vec<Choice> {
    if library.personal_info.is_empty() {
        return vec![];
    }
    std::iter::once(Choice {
        id: String::new(),
        label: "None".into(),
    })
    .chain(library.personal_info.iter().map(|info| Choice {
        id: info.id.clone(),
        label: info.describe(),
    }))
    .collect()
}

/// "Oct 6, 2026", from whatever timestamp shape the API sent.
fn format_date(value: &str) -> String {
    chrono::DateTime::parse_from_rfc3339(value)
        .map(|date| date.naive_local())
        .or_else(|_| chrono::NaiveDateTime::parse_from_str(value, "%Y-%m-%dT%H:%M:%S%.f"))
        .map(|date| date.format("%b %-d, %Y").to_string())
        .unwrap_or_else(|_| value.to_string())
}

#[derive(Debug, Clone)]
pub enum ExportEvent {
    Progress {
        done: usize,
        total: usize,
        title: String,
    },
    Finished(ExportReport),
    Failed(String),
}

#[derive(Debug, Clone)]
pub struct ExportReport {
    directory: PathBuf,
    deleted: usize,
    written: usize,
    /// Named rather than counted: "3 failed" leaves someone opening every
    /// resume to work out which three.
    failures: Vec<(String, String)>,
}

#[derive(Debug, Default)]
pub struct State {
    title: String,
    title_error: bool,
    full_name: String,
    personal_info: Option<String>,
    pick_type: Option<SectionType>,
    pick_item: Option<Choice>,
    sections: Vec<(SectionRef, String)>,
    creating: bool,
    create_error: Option<String>,

    pending_delete: Option<Resume>,
    deleting: bool,
    delete_error: Option<String>,

    progress: Option<(usize, usize, String)>,
    report: Option<ExportReport>,
    export_error: Option<String>,
    /// The folder waiting on the warning, and how many PDFs it would lose.
    pending_clear: Option<(PathBuf, usize)>,
}

#[derive(Debug, Clone)]
pub enum Message {
    Open(Route),
    Title(String),
    FullName(String),
    PersonalInfo(Choice),
    PickType(TypeChoice),
    PickItem(Choice),
    AddSection,
    MoveSection(usize, usize),
    RemoveSection(usize),
    Create,
    Created(ApiResult<Resume>),
    AskDelete(Resume),
    CancelDelete,
    Delete,
    Deleted(ApiResult<()>),
    ChooseFolder,
    FolderChosen(Option<PathBuf>),
    CancelClear,
    ConfirmClear,
    Export(ExportEvent),
}

/// Compile every resume, one at a time, into `directory`.
///
/// One at a time on purpose: typesetting is CPU-bound in the process serving
/// the request, so twenty at once would not finish sooner. A resume that will
/// not compile is reported and skipped; a folder that refuses a write stops
/// the run, because every remaining resume would fail the same way.
fn run_export(client: Client, resumes: Vec<Resume>, directory: PathBuf) -> Task<Message> {
    let stream = iced::stream::channel(8, async move |mut events| {
        let deleted = match export::clear(&directory) {
            Ok(deleted) => deleted,
            Err(error) => {
                let _ = events
                    .send(ExportEvent::Failed(format!(
                        "Could not use that folder: {error}"
                    )))
                    .await;
                return;
            }
        };

        let titles: Vec<String> = resumes.iter().map(|resume| resume.title.clone()).collect();
        let names = export::filenames(&titles);
        let total = resumes.len();
        let mut written = 0;
        let mut failures = Vec::new();

        for (index, resume) in resumes.iter().enumerate() {
            let _ = events
                .send(ExportEvent::Progress {
                    done: index,
                    total,
                    title: resume.title.clone(),
                })
                .await;

            match client.compile_pdf(&resume.id).await {
                Ok(pdf) => {
                    if let Err(error) = export::write(&directory, &names[index], &pdf) {
                        let _ = events
                            .send(ExportEvent::Failed(format!(
                                "Could not use that folder: {error}"
                            )))
                            .await;
                        return;
                    }
                    written += 1;
                }
                Err(error) => {
                    // the engine's complaint runs to pages; its last line names the problem
                    let reason = error.0.trim().lines().last().unwrap_or("").to_string();
                    failures.push((resume.title.clone(), reason));
                }
            }
        }

        let _ = events
            .send(ExportEvent::Finished(ExportReport {
                directory,
                deleted,
                written,
                failures,
            }))
            .await;
    });

    Task::run(stream, Message::Export)
}

impl State {
    pub fn update(
        &mut self,
        message: Message,
        client: Client,
        library: &Library,
    ) -> Outcome<Message> {
        match message {
            Message::Open(route) => Outcome::navigate(route),
            Message::Title(value) => {
                self.title = value;
                self.title_error = false;
                Outcome::none()
            }
            Message::FullName(value) => {
                self.full_name = value;
                Outcome::none()
            }
            Message::PersonalInfo(choice) => {
                self.personal_info = Some(choice.id).filter(|id| !id.is_empty());
                Outcome::none()
            }
            Message::PickType(TypeChoice(kind)) => {
                self.pick_type = Some(kind);
                self.pick_item = None;
                Outcome::none()
            }
            Message::PickItem(choice) => {
                self.pick_item = Some(choice);
                Outcome::none()
            }
            Message::AddSection => {
                if let (Some(kind), Some(item)) = (self.pick_type, self.pick_item.take()) {
                    self.sections.push((
                        SectionRef {
                            section_type: kind,
                            section_id: item.id,
                        },
                        item.label,
                    ));
                }
                Outcome::none()
            }
            Message::MoveSection(from, to) => {
                self.sections = crate::draft::move_item(&self.sections, from, to);
                Outcome::none()
            }
            Message::RemoveSection(index) => {
                if index < self.sections.len() {
                    self.sections.remove(index);
                }
                Outcome::none()
            }
            Message::Create => {
                if self.title.trim().is_empty() {
                    self.title_error = true;
                    return Outcome::none();
                }
                self.creating = true;
                self.create_error = None;

                // the order the picker shows becomes each type's order; the
                // headings take the API's default order, as on the web
                let body = ResumeCreate {
                    title: self.title.trim().to_string(),
                    template: TEMPLATE.into(),
                    full_name: Some(self.full_name.trim().to_string())
                        .filter(|name| !name.is_empty()),
                    personal_info_id: self.personal_info.clone(),
                    sections: self
                        .sections
                        .iter()
                        .map(|(reference, _)| reference.clone())
                        .collect(),
                };
                Outcome::task(Task::perform(
                    async move { client.create_resume(&body).await },
                    Message::Created,
                ))
            }
            Message::Created(Ok(_)) => {
                *self = Self {
                    report: self.report.take(),
                    ..Self::default()
                };
                Outcome::none().reload()
            }
            Message::Created(Err(error)) => {
                self.creating = false;
                self.create_error = Some(error.0);
                Outcome::none()
            }
            Message::AskDelete(resume) => {
                self.pending_delete = Some(resume);
                self.delete_error = None;
                Outcome::none()
            }
            Message::CancelDelete => {
                self.pending_delete = None;
                self.delete_error = None;
                Outcome::none()
            }
            Message::Delete => {
                let Some(resume) = &self.pending_delete else {
                    return Outcome::none();
                };
                self.deleting = true;
                let id = resume.id.clone();
                Outcome::task(Task::perform(
                    async move { client.delete_resume(&id).await },
                    Message::Deleted,
                ))
            }
            Message::Deleted(Ok(())) => {
                self.deleting = false;
                self.pending_delete = None;
                Outcome::none().reload()
            }
            Message::Deleted(Err(error)) => {
                self.deleting = false;
                self.delete_error = Some(error.0);
                Outcome::none()
            }
            Message::ChooseFolder => {
                self.export_error = None;
                self.report = None;
                Outcome::task(Task::perform(
                    async {
                        rfd::AsyncFileDialog::new()
                            .set_title("Choose a folder for your resumes")
                            .pick_folder()
                            .await
                            .map(|handle| handle.path().to_path_buf())
                    },
                    Message::FolderChosen,
                ))
            }
            // dismissing the picker is a decision, not a failure
            Message::FolderChosen(None) => Outcome::none(),
            Message::FolderChosen(Some(directory)) => {
                let existing = export::pdfs_in(&directory).len();
                if existing > 0 {
                    self.pending_clear = Some((directory, existing));
                    return Outcome::none();
                }
                self.start_export(client, library, directory)
            }
            Message::CancelClear => {
                self.pending_clear = None;
                Outcome::none()
            }
            Message::ConfirmClear => match self.pending_clear.take() {
                Some((directory, _)) => self.start_export(client, library, directory),
                None => Outcome::none(),
            },
            Message::Export(ExportEvent::Progress { done, total, title }) => {
                self.progress = Some((done, total, title));
                Outcome::none()
            }
            Message::Export(ExportEvent::Finished(report)) => {
                self.progress = None;
                self.report = Some(report);
                Outcome::none()
            }
            Message::Export(ExportEvent::Failed(error)) => {
                self.progress = None;
                self.export_error = Some(error);
                Outcome::none()
            }
        }
    }

    fn start_export(
        &mut self,
        client: Client,
        library: &Library,
        directory: PathBuf,
    ) -> Outcome<Message> {
        self.progress = Some((0, library.resumes.len(), String::new()));
        Outcome::task(run_export(client, library.resumes.clone(), directory))
    }

    pub fn view<'a>(&'a self, library: &'a Library) -> Element<'a, Message> {
        let content = page(
            column![
                back("Back to dashboard", Message::Open(Route::Dashboard)),
                space::vertical().height(16),
                title("Resumes"),
                space::vertical().height(28),
                self.create_form(library),
                space::vertical().height(20),
                self.export_panel(library),
                space::vertical().height(28),
                self.table(library),
            ]
            .width(Length::Fill),
        );

        let dialog = if let Some(resume) = &self.pending_delete {
            Some(widgets::Confirm {
                title: "Delete this resume?",
                body: subtle(format!(
                    "{} will be deleted permanently. The education, experience, project and skill entries it uses stay in your sections.",
                    resume.title
                ))
                .into(),
                confirm: "Delete",
                pending: self.deleting.then_some("Deleting…"),
                error: self.delete_error.as_deref(),
                on_cancel: Message::CancelDelete,
                on_confirm: Message::Delete,
            })
        } else {
            self.pending_clear.as_ref().map(|(directory, count)| widgets::Confirm {
                title: "Empty this folder first?",
                body: subtle(format!(
                    "{count} PDF(s) already in {} will be permanently deleted before the export runs — including any this app did not put there. Other files and sub-folders are left alone.",
                    directory.display()
                ))
                .into(),
                confirm: "Delete and export",
                pending: None,
                error: None,
                on_cancel: Message::CancelClear,
                on_confirm: Message::ConfirmClear,
            })
        };

        modal(content, dialog)
    }

    fn create_form<'a>(&'a self, library: &'a Library) -> Element<'a, Message> {
        let name = column![
            row![
                text_input("e.g. Frontend Focused", &self.title)
                    .on_input(Message::Title)
                    .on_submit(Message::Create)
                    .padding([9, 14])
                    .size(15)
                    .style(style::input(self.title_error)),
                btn(
                    if self.creating {
                        "Creating…"
                    } else {
                        "Create resume"
                    },
                    Kind::Primary,
                    (!self.creating).then_some(Message::Create),
                ),
            ]
            .spacing(12)
            .align_y(Alignment::Center),
        ]
        .spacing(8);
        let name = if self.title_error {
            name.push(widgets::negative("Enter a resume name."))
        } else {
            name
        };
        let name = match self.create_error.as_deref() {
            Some(error) => name.push(widgets::banner(error)),
            None => name,
        };

        let contacts = contact_choices(library);
        let selected_contact = contacts
            .iter()
            .find(|choice| Some(&choice.id) == self.personal_info.as_ref())
            .cloned();
        let header = panel(
            column![
                label("Header"),
                row![
                    widgets::field(
                        "Name on the resume",
                        "e.g. Casey Quinn",
                        &self.full_name,
                        Message::FullName,
                        None,
                    ),
                    column![
                        subtle("Contact details"),
                        pick_list(contacts, selected_contact, Message::PersonalInfo)
                            .placeholder("Choose contact details…")
                            .padding([9, 14])
                            .width(Length::Fill)
                            .style(style::picker),
                    ]
                    .spacing(6)
                    .width(Length::Fill),
                ]
                .spacing(12),
            ]
            .spacing(10),
        );

        column![name, header, self.section_picker(library)]
            .spacing(16)
            .into()
    }

    fn section_picker<'a>(&'a self, library: &'a Library) -> Element<'a, Message> {
        let types: Vec<TypeChoice> = SectionType::ALL.into_iter().map(TypeChoice).collect();
        let added: Vec<&str> = self
            .sections
            .iter()
            .map(|(reference, _)| reference.section_id.as_str())
            .collect();
        let items: Vec<Choice> = self
            .pick_type
            .map(|kind| library.catalogs.choices(kind))
            .unwrap_or_default()
            .into_iter()
            .filter(|(id, _)| !added.contains(&id.as_str()))
            .map(|(id, label)| Choice { id, label })
            .collect();

        let placeholder = match self.pick_type {
            None => "Choose a type first",
            Some(_) if items.is_empty() => "Nothing left to add for this type.",
            Some(_) => "Choose a section…",
        };

        let picker = row![
            pick_list(types, self.pick_type.map(TypeChoice), Message::PickType)
                .placeholder("Choose a type…")
                .padding([9, 14])
                .width(Length::Fill)
                .style(style::picker),
            pick_list(items, self.pick_item.clone(), Message::PickItem)
                .placeholder(placeholder)
                .padding([9, 14])
                .width(Length::Fill)
                .style(style::picker),
            btn(
                "Add",
                Kind::Secondary,
                self.pick_item.is_some().then_some(Message::AddSection)
            ),
        ]
        .spacing(12)
        .align_y(Alignment::Center);

        let count = self.sections.len();
        let mut list = Column::new().spacing(6);
        for (index, (reference, label)) in self.sections.iter().enumerate() {
            list = list.push(
                iced::widget::container(
                    row![
                        text(format!(
                            "{}. {} — {label}",
                            index + 1,
                            TypeChoice(reference.section_type)
                        ))
                        .size(14)
                        .width(Length::Fill),
                        btn(
                            "↑",
                            Kind::Icon,
                            (index > 0).then(|| Message::MoveSection(index, index - 1))
                        ),
                        btn(
                            "↓",
                            Kind::Icon,
                            (index + 1 < count).then(|| Message::MoveSection(index, index + 1))
                        ),
                        btn("✕", Kind::Icon, Some(Message::RemoveSection(index))),
                    ]
                    .spacing(4)
                    .align_y(Alignment::Center),
                )
                .padding([6, 12])
                .style(style::row),
            );
        }

        panel(column![label("Sections"), picker, list].spacing(10))
    }

    fn export_panel<'a>(&'a self, library: &'a Library) -> Element<'a, Message> {
        let count = library.resumes.len();
        let running = self.progress.is_some();

        let description = if count == 0 {
            "Create a resume first.".to_string()
        } else {
            format!(
                "Save all {count} as PDFs in a folder you choose. Any PDFs already there are deleted first."
            )
        };

        let mut content = column![
            row![
                column![text("Export all resumes").size(16), subtle(description)]
                    .spacing(4)
                    .width(Length::Fill),
                btn(
                    if running {
                        "Exporting…"
                    } else {
                        "Choose folder…"
                    },
                    Kind::Secondary,
                    (!running && count > 0).then_some(Message::ChooseFolder),
                ),
            ]
            .spacing(16)
            .align_y(Alignment::Center)
        ]
        .spacing(10);

        if let Some((done, total, title)) = &self.progress {
            content = content.push(subtle(if title.is_empty() {
                format!("Building {total} resume(s)…")
            } else {
                format!("Building {title} — {} of {total}…", done + 1)
            }));
        }
        if let Some(error) = &self.export_error {
            content = content.push(widgets::banner(error));
        }
        if let Some(report) = &self.report {
            let mut summary = format!(
                "Saved {} of {} to {}",
                report.written,
                report.written + report.failures.len(),
                report.directory.display()
            );
            if report.deleted > 0 {
                summary.push_str(&format!(
                    ", after deleting {} PDF(s) that were there",
                    report.deleted
                ));
            }
            summary.push('.');
            content = content.push(subtle(summary));
            for (title, reason) in &report.failures {
                content = content.push(widgets::negative(format!("{title} — {reason}")));
            }
        }

        panel(content)
    }

    fn table<'a>(&'a self, library: &'a Library) -> Element<'a, Message> {
        let header = row![
            text("Name").size(13).width(Length::Fill),
            text("Last modified").size(13),
            space::horizontal().width(40),
        ]
        .padding([10, 16])
        .spacing(16);

        let mut body = Column::new().push(header);

        if library.resumes.is_empty() {
            body = body.push(iced::widget::container(subtle("No resumes yet.")).padding([12, 16]));
        }

        for resume in &library.resumes {
            body = body.push(
                row![
                    button(text(&resume.title).size(15))
                        .padding(0)
                        .style(|theme, status| {
                            let mut style = style::button(Kind::Link)(theme, status);
                            let t = tokens(theme);
                            style.text_color = if matches!(status, button::Status::Hovered) {
                                t.informative
                            } else {
                                t.ink
                            };
                            style
                        })
                        .on_press(Message::Open(Route::Editor(resume.id.clone())))
                        .width(Length::Fill),
                    subtle(format_date(&resume.updated_at)),
                    btn(
                        "Delete",
                        Kind::Icon,
                        Some(Message::AskDelete(resume.clone()))
                    ),
                ]
                .spacing(16)
                .padding([10, 16])
                .align_y(Alignment::Center),
            );
        }

        iced::widget::container(body)
            .width(Length::Fill)
            .style(style::panel)
            .into()
    }
}
