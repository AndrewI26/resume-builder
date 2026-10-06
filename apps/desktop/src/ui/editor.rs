//! One resume: the panel that arranges it, and the PDF it compiles to.
//!
//! Every control changes the draft and nothing else; saving is a pause in
//! editing away, the same 800ms the web editor waits, so a burst of clicks
//! becomes one write. The PDF is typeset from the *saved* rows, so a compile
//! saves first, and the preview says plainly when the panel has moved on
//! from what it shows.

use super::resumes::{Choice, contact_choices};
use super::style::{self, Kind};
use super::widgets::{self, BOLD, back, btn, label, panel, subtle};
use super::{Library, Outcome, Route};
use crate::api::models::{Resume, ResumeEdit, ResumeSections, SectionRef, SectionType};
use crate::api::{ApiResult, Client};
use crate::draft::Draft;
use crate::{export, latex, pdf};
use iced::widget::{
    Column, center, column, container, image, pick_list, row, scrollable, space, text,
};
use iced::{Alignment, ContentFit, Element, Length, Subscription, Task};
use std::path::PathBuf;
use std::time::Duration;

const AUTOSAVE_DELAY: Duration = Duration::from_millis(800);
const PANEL_WIDTH: f32 = 380.0;

/// A compiled resume: the file itself, its pages drawn, and the draft it
/// was built from — which is how the screen notices it has gone stale.
struct Compiled {
    bytes: Vec<u8>,
    pages: Vec<image::Handle>,
    signature: String,
}

pub struct State {
    id: String,
    resume: Option<Resume>,
    load_error: Option<String>,
    saved: Option<Draft>,
    draft: Option<Draft>,

    /// Bumped on every edit; an autosave only fires for the latest one.
    generation: u64,
    saving: bool,
    save_failed: bool,
    saved_at: Option<chrono::DateTime<chrono::Local>>,
    /// The signature a save in flight is carrying, so it is not sent twice.
    submitted: Option<String>,

    compiling: bool,
    /// A compile asked for while a save had to land first.
    compile_after_save: bool,
    compile_error: Option<String>,
    pdf: Option<Compiled>,
    notice: Option<String>,
}

#[derive(Debug, Clone)]
pub enum Message {
    Back,
    Loaded(ApiResult<(Resume, ResumeSections)>),
    FullName(String),
    PersonalInfo(Choice),
    MoveHeading(usize, usize),
    MoveRow(SectionType, usize, usize),
    Swap(SectionRef, Choice),
    Detach(SectionRef),
    Attach(SectionType, Choice),
    AutosaveDue(u64),
    Retry,
    Persisted(ApiResult<Resume>, Draft),
    Compile,
    Compiled(Result<(Vec<u8>, Vec<pdf::Page>), String>, String),
    DownloadPdf,
    DownloadTex,
    OpenFullSize,
    Wrote(Result<String, String>),
}

async fn load(client: Client, id: String) -> ApiResult<(Resume, ResumeSections)> {
    tokio::try_join!(client.resume(&id), client.resume_sections(&id))
}

/// Ask where to save a file, then write it. `None` means the dialog was dismissed.
async fn save_as(
    name: String,
    extension: &'static str,
    contents: Vec<u8>,
) -> Option<Result<String, String>> {
    let path: PathBuf = rfd::AsyncFileDialog::new()
        .set_file_name(&name)
        .add_filter(extension.to_uppercase(), &[extension])
        .save_file()
        .await?
        .path()
        .to_path_buf();

    Some(
        tokio::fs::write(&path, contents)
            .await
            .map(|()| format!("Saved {}", path.display()))
            .map_err(|error| format!("Could not save {}: {error}", path.display())),
    )
}

impl State {
    pub fn new(id: String, client: Client) -> (Self, Task<Message>) {
        let task = Task::perform(load(client, id.clone()), Message::Loaded);
        let state = Self {
            id,
            resume: None,
            load_error: None,
            saved: None,
            draft: None,
            generation: 0,
            saving: false,
            save_failed: false,
            saved_at: None,
            submitted: None,
            compiling: false,
            compile_after_save: false,
            compile_error: None,
            pdf: None,
            notice: None,
        };
        (state, task)
    }

    pub fn title(&self) -> String {
        self.resume
            .as_ref()
            .map(|resume| resume.title.clone())
            .unwrap_or_else(|| "Resume".into())
    }

    pub fn subscription(&self) -> Subscription<Message> {
        Subscription::none()
    }

    /// The draft's signature, so a test can hand over a PDF that matches it.
    #[cfg(test)]
    pub fn signature(&self) -> String {
        self.draft
            .as_ref()
            .map(Draft::signature)
            .unwrap_or_default()
    }

    fn dirty(&self) -> bool {
        match (&self.draft, &self.saved) {
            (Some(draft), Some(saved)) => draft.signature() != saved.signature(),
            _ => false,
        }
    }

    fn stale(&self) -> bool {
        match (&self.draft, &self.pdf) {
            (Some(draft), Some(pdf)) => pdf.signature != draft.signature(),
            _ => false,
        }
    }

    /// Change the draft, and schedule the save a pause in editing will make.
    fn edit(&mut self, change: impl FnOnce(&mut Draft)) -> Outcome<Message> {
        let Some(draft) = &mut self.draft else {
            return Outcome::none();
        };
        change(draft);
        self.generation += 1;
        let generation = self.generation;
        Outcome::task(Task::perform(
            // made inside the future, so the timer is only created once the
            // executor polls it — not here on the UI thread, outside any runtime
            async { tokio::time::sleep(AUTOSAVE_DELAY).await },
            move |()| Message::AutosaveDue(generation),
        ))
    }

    /// Write the draft back: order and header on the resume, membership in
    /// the join table. Both have to land for the page to match the panel.
    fn persist(&mut self, client: Client) -> Task<Message> {
        let (Some(draft), Some(resume)) = (self.draft.clone(), &self.resume) else {
            return Task::none();
        };

        self.saving = true;
        self.save_failed = false;
        self.submitted = Some(draft.signature());

        let id = self.id.clone();
        let body = ResumeEdit {
            title: resume.title.clone(),
            template: resume.template.clone(),
            full_name: Some(draft.full_name.trim().to_string()).filter(|name| !name.is_empty()),
            personal_info_id: draft.personal_info_id.clone(),
            section_order: draft.order.clone(),
        };
        let sections = ResumeSections {
            sections: draft.sections.clone(),
        };

        Task::perform(
            async move {
                let saved = client.update_resume(&id, &body).await?;
                client.replace_sections(&id, &sections).await?;
                Ok(saved)
            },
            move |result| Message::Persisted(result, draft.clone()),
        )
    }

    /// Save anything still waiting, for a window that is about to close.
    pub fn flush(&mut self, client: Client) -> Task<Message> {
        if self.dirty() && !self.saving {
            self.persist(client)
        } else {
            Task::none()
        }
    }

    fn compile(&mut self, client: Client) -> Task<Message> {
        let Some(draft) = &self.draft else {
            return Task::none();
        };
        self.compiling = true;
        self.compile_error = None;
        let signature = draft.signature();
        let id = self.id.clone();

        Task::perform(
            async move {
                let bytes = client.compile_pdf(&id).await.map_err(|error| error.0)?;
                let copy = bytes.clone();
                let pages = tokio::task::spawn_blocking(move || pdf::rasterise(copy))
                    .await
                    .map_err(|error| format!("The preview could not be drawn: {error}"))??;
                Ok((bytes, pages))
            },
            move |result| Message::Compiled(result, signature.clone()),
        )
    }

    fn slug(&self, extension: &str) -> String {
        export::filename(&self.title(), extension)
    }

    pub fn update(
        &mut self,
        message: Message,
        client: Client,
        library: &Library,
    ) -> Outcome<Message> {
        match message {
            Message::Back => Outcome::navigate(Route::Resumes),
            Message::Loaded(Ok((resume, membership))) => {
                let draft = Draft {
                    order: resume.section_order.clone(),
                    sections: membership.sections,
                    full_name: resume.full_name.clone().unwrap_or_default(),
                    personal_info_id: resume.personal_info_id.clone(),
                };
                self.saved = Some(draft.clone());
                self.draft = Some(draft);
                self.resume = Some(resume);
                // open with the resume on the page, not an empty frame and a button
                Outcome::task(self.compile(client))
            }
            Message::Loaded(Err(error)) => {
                self.load_error = Some(error.0);
                Outcome::none()
            }
            Message::FullName(value) => self.edit(|draft| draft.full_name = value),
            Message::PersonalInfo(choice) => {
                // the empty id is the None row: no contact line under the name
                self.edit(|draft| {
                    draft.personal_info_id = Some(choice.id).filter(|id| !id.is_empty())
                })
            }
            Message::MoveHeading(from, to) => self.edit(|draft| draft.move_heading(from, to)),
            Message::MoveRow(kind, from, to) => {
                self.edit(|draft| draft.move_within(kind, from, to))
            }
            Message::Swap(reference, choice) => {
                self.edit(|draft| draft.swap(&reference, choice.id))
            }
            Message::Detach(reference) => self.edit(|draft| draft.detach(&reference)),
            Message::Attach(kind, choice) => self.edit(|draft| {
                draft.attach(SectionRef {
                    section_type: kind,
                    section_id: choice.id,
                })
            }),
            Message::AutosaveDue(generation) => {
                let current = self.draft.as_ref().map(Draft::signature);
                if generation != self.generation
                    || !self.dirty()
                    || self.saving
                    || self.submitted == current
                {
                    return Outcome::none();
                }
                Outcome::task(self.persist(client))
            }
            Message::Retry => Outcome::task(self.persist(client)),
            Message::Persisted(Ok(resume), submitted) => {
                self.saving = false;
                self.saved = Some(submitted);
                self.resume = Some(resume);
                self.saved_at = Some(chrono::Local::now());

                let mut tasks = vec![];
                if self.compile_after_save {
                    self.compile_after_save = false;
                    tasks.push(self.compile(client.clone()));
                }
                // edits made while that save was in flight still need theirs
                if self.dirty() {
                    tasks.push(self.persist(client));
                }
                Outcome::task(Task::batch(tasks)).reload()
            }
            Message::Persisted(Err(error), _) => {
                self.saving = false;
                self.save_failed = true;
                self.submitted = None;
                if self.compile_after_save {
                    self.compile_after_save = false;
                    self.compiling = false;
                    self.compile_error = Some(format!("Could not save before compiling: {error}"));
                }
                Outcome::none()
            }
            Message::Compile => {
                if self.dirty() {
                    // the worker typesets saved rows, so the draft lands first
                    self.compile_after_save = true;
                    self.compiling = true;
                    if self.saving {
                        return Outcome::none();
                    }
                    return Outcome::task(self.persist(client));
                }
                Outcome::task(self.compile(client))
            }
            Message::Compiled(result, signature) => {
                self.compiling = false;
                match result {
                    Ok((bytes, pages)) => {
                        self.pdf = Some(Compiled {
                            bytes,
                            pages: pages
                                .into_iter()
                                .map(|page| {
                                    image::Handle::from_rgba(page.width, page.height, page.pixels)
                                })
                                .collect(),
                            signature,
                        });
                    }
                    Err(error) => self.compile_error = Some(error),
                }
                Outcome::none()
            }
            Message::DownloadPdf => {
                let Some(pdf) = &self.pdf else {
                    return Outcome::none();
                };
                // the file already in the window, without typesetting it twice
                let task = Task::future(save_as(self.slug("pdf"), "pdf", pdf.bytes.clone()));
                Outcome::task(task.and_then(|result| Task::done(Message::Wrote(result))))
            }
            Message::DownloadTex => {
                let (Some(draft), Some(resume)) = (&self.draft, &self.resume) else {
                    return Outcome::none();
                };
                let document = draft.document(
                    &self.id,
                    &resume.title,
                    &resume.template,
                    &library.catalogs,
                    &library.personal_info,
                );
                let tex = latex::serialize(&document).into_bytes();
                let task = Task::future(save_as(self.slug("tex"), "tex", tex));
                Outcome::task(task.and_then(|result| Task::done(Message::Wrote(result))))
            }
            Message::OpenFullSize => {
                let Some(pdf) = &self.pdf else {
                    return Outcome::none();
                };
                // the system viewer zooms at the PDF's own resolution, which a
                // picture of a page in this window never will
                let path = std::env::temp_dir().join(self.slug("pdf"));
                let bytes = pdf.bytes.clone();
                Outcome::task(Task::perform(
                    async move {
                        tokio::fs::write(&path, bytes)
                            .await
                            .map_err(|error| error.to_string())?;
                        open::that_detached(&path).map_err(|error| error.to_string())?;
                        Ok(String::new())
                    },
                    Message::Wrote,
                ))
            }
            Message::Wrote(Ok(notice)) => {
                self.notice = Some(notice).filter(|notice| !notice.is_empty());
                Outcome::none()
            }
            Message::Wrote(Err(error)) => {
                self.notice = Some(error);
                Outcome::none()
            }
        }
    }

    pub fn view<'a>(&'a self, library: &'a Library) -> Element<'a, Message> {
        if let Some(error) = &self.load_error {
            return center(
                column![
                    widgets::banner(error),
                    back("Back to resumes", Message::Back)
                ]
                .spacing(16),
            )
            .into();
        }
        let (Some(draft), Some(resume)) = (&self.draft, &self.resume) else {
            return center(subtle("Loading resume…")).into();
        };

        let toolbar = row![
            back("Resumes", Message::Back),
            text(&resume.title).size(18).font(BOLD),
            space::horizontal(),
            self.save_status(),
            btn("Download .tex", Kind::Secondary, Some(Message::DownloadTex)),
        ]
        .spacing(16)
        .align_y(Alignment::Center)
        .padding([8, 24]);

        let side = scrollable(
            container(self.panel(draft, library))
                .width(PANEL_WIDTH)
                .padding(iced::Padding {
                    right: 12.0,
                    ..iced::Padding::ZERO
                }),
        )
        .height(Length::Fill)
        .style(style::scroll);

        column![
            toolbar,
            row![side, self.preview()]
                .spacing(24)
                .padding(iced::Padding {
                    top: 8.0,
                    right: 24.0,
                    bottom: 24.0,
                    left: 24.0,
                })
                .height(Length::Fill),
        ]
        .into()
    }

    /// Whether the work is safe. A failure is the one state with a control,
    /// because it is the one the screen cannot resolve on its own.
    fn save_status(&self) -> Element<'_, Message> {
        if self.save_failed {
            return row![
                widgets::negative("Could not save"),
                btn("Retry", Kind::Link, Some(Message::Retry)),
            ]
            .spacing(8)
            .align_y(Alignment::Center)
            .into();
        }

        subtle(if self.saving {
            "Saving…".to_string()
        } else if self.dirty() {
            "Unsaved changes".to_string()
        } else {
            match self.saved_at {
                Some(at) => format!("Saved {}", at.format("%-I:%M %p")),
                None => "All changes saved".to_string(),
            }
        })
        .into()
    }

    fn panel<'a>(&'a self, draft: &'a Draft, library: &'a Library) -> Element<'a, Message> {
        let contacts = contact_choices(library);
        let selected = contacts
            .iter()
            .find(|choice| Some(&choice.id) == draft.personal_info_id.as_ref())
            .cloned();

        let header = panel(
            column![
                label("Header"),
                widgets::field(
                    "Name on the resume",
                    "e.g. Casey Quinn",
                    &draft.full_name,
                    Message::FullName,
                    None,
                ),
                column![
                    subtle("Contact details"),
                    if contacts.is_empty() {
                        Element::from(subtle("Add your contact details under Sections first."))
                    } else {
                        pick_list(contacts, selected, Message::PersonalInfo)
                            .placeholder("Choose contact details…")
                            .padding([9, 14])
                            .width(Length::Fill)
                            .style(style::picker)
                            .into()
                    },
                ]
                .spacing(6),
            ]
            .spacing(10),
        );

        let mut out = column![label("Sections"), header].spacing(14);

        let headings = draft.order.len();
        for (index, &kind) in draft.order.iter().enumerate() {
            out = out.push(self.heading(draft, library, kind, index, headings));
        }

        // a type with no heading is still addable, so it needs somewhere to live
        let unused: Vec<SectionType> = SectionType::ALL
            .into_iter()
            .filter(|kind| !draft.order.contains(kind))
            .collect();
        if !unused.is_empty() {
            let mut well = column![subtle("Not on this resume")].spacing(10);
            for kind in unused {
                well = well.push(
                    column![
                        text(kind.title()).size(14).font(BOLD),
                        add_row(draft, library, kind)
                    ]
                    .spacing(6),
                );
            }
            out = out.push(
                container(well)
                    .padding(14)
                    .width(Length::Fill)
                    .style(style::well),
            );
        }

        out.into()
    }

    fn heading<'a>(
        &'a self,
        draft: &'a Draft,
        library: &'a Library,
        kind: SectionType,
        index: usize,
        headings: usize,
    ) -> Element<'a, Message> {
        let refs = draft.refs_of(kind);
        let count = refs.len();

        let title = row![
            text(kind.title()).size(15).font(BOLD),
            subtle(match count {
                0 => "hidden".to_string(),
                1 => "1 entry".to_string(),
                n => format!("{n} entries"),
            }),
            space::horizontal(),
            btn(
                "↑",
                Kind::Icon,
                (index > 0).then(|| Message::MoveHeading(index, index - 1))
            ),
            btn(
                "↓",
                Kind::Icon,
                (index + 1 < headings).then(|| Message::MoveHeading(index, index + 1))
            ),
        ]
        .spacing(8)
        .align_y(Alignment::Center);

        let mut rows = Column::new().spacing(6);
        if refs.is_empty() {
            rows = rows.push(subtle(
                "Nothing here yet — this heading will not appear on the resume.",
            ));
        }

        let attached: Vec<&str> = refs
            .iter()
            .map(|reference| reference.section_id.as_str())
            .collect();
        for (position, reference) in refs.iter().enumerate() {
            let control: Element<'a, Message> = match library.catalogs.describe(reference) {
                None => widgets::negative("This entry was deleted.")
                    .width(Length::Fill)
                    .into(),
                Some(current) => {
                    // swapping onto something already attached would silently
                    // drop a row, so offer this row plus whatever is unused
                    let choices: Vec<Choice> = library
                        .catalogs
                        .choices(kind)
                        .into_iter()
                        .filter(|(id, _)| {
                            *id == reference.section_id || !attached.contains(&id.as_str())
                        })
                        .map(|(id, label)| Choice { id, label })
                        .collect();
                    let selected = Choice {
                        id: reference.section_id.clone(),
                        label: current,
                    };
                    let target = reference.clone();
                    pick_list(choices, Some(selected), move |choice| {
                        Message::Swap(target.clone(), choice)
                    })
                    .padding([6, 10])
                    .text_size(14)
                    .width(Length::Fill)
                    .style(style::picker)
                    .into()
                }
            };

            rows = rows.push(
                container(
                    row![
                        control,
                        btn(
                            "↑",
                            Kind::Icon,
                            (position > 0).then(|| Message::MoveRow(kind, position, position - 1))
                        ),
                        btn(
                            "↓",
                            Kind::Icon,
                            (position + 1 < count).then(|| Message::MoveRow(
                                kind,
                                position,
                                position + 1
                            ))
                        ),
                        btn("✕", Kind::Icon, Some(Message::Detach(reference.clone()))),
                    ]
                    .spacing(2)
                    .align_y(Alignment::Center),
                )
                .padding(4)
                .style(style::row),
            );
        }

        panel(column![title, rows, add_row(draft, library, kind)].spacing(10))
    }

    fn preview(&self) -> Element<'_, Message> {
        let status: Element<'_, Message> = if self.compiling {
            subtle("Compiling…").into()
        } else if self.stale() {
            row![
                text("Out of date.").size(14).font(BOLD),
                subtle("This PDF was built before your latest changes — recompile to see them."),
            ]
            .spacing(6)
            .into()
        } else if self.pdf.is_some() {
            subtle("Compiled from your saved resume.").into()
        } else {
            subtle("Not compiled yet.").into()
        };

        let has_pdf = self.pdf.is_some();
        let actions = row![
            container(status).width(Length::Fill),
            btn(
                "Open full size",
                Kind::Tertiary,
                has_pdf.then_some(Message::OpenFullSize)
            ),
            btn(
                if self.compiling {
                    "Compiling…"
                } else {
                    "Recompile"
                },
                Kind::Secondary,
                (!self.compiling).then_some(Message::Compile),
            ),
            btn(
                "Download PDF",
                Kind::Primary,
                (has_pdf && !self.compiling).then_some(Message::DownloadPdf),
            ),
        ]
        .spacing(10)
        .align_y(Alignment::Center);

        let mut out = column![actions].spacing(12).width(Length::Fill);

        if let Some(notice) = &self.notice {
            out = out.push(subtle(notice));
        }

        // a failed compile carries the engine's own complaint, worth showing whole
        if let Some(error) = &self.compile_error {
            out = out.push(
                container(
                    scrollable(text(error).size(12).font(iced::Font::MONOSPACE))
                        .height(Length::Shrink)
                        .style(style::scroll),
                )
                .padding([10, 16])
                .max_height(160)
                .width(Length::Fill)
                .style(style::error_banner),
            );
        }

        let pages: Element<'_, Message> = match &self.pdf {
            Some(pdf) => {
                let opacity: f32 = if self.compiling { 0.4 } else { 1.0 };
                scrollable(
                    Column::with_children(pdf.pages.iter().map(|page| {
                        container(
                            image(page.clone())
                                .width(Length::Fill)
                                .content_fit(ContentFit::Contain)
                                .opacity(opacity),
                        )
                        .padding(1)
                        .style(style::paper)
                        .into()
                    }))
                    .spacing(16),
                )
                .height(Length::Fill)
                .style(style::scroll)
                .into()
            }
            None => container(center(subtle(if self.compiling {
                "Building the PDF…"
            } else if self.compile_error.is_some() {
                "The last compile failed."
            } else {
                "Nothing compiled yet."
            })))
            .height(Length::Fill)
            .width(Length::Fill)
            .style(style::well)
            .into(),
        };

        out.push(pages).into()
    }
}

fn singular(kind: SectionType) -> &'static str {
    match kind {
        SectionType::Education => "education",
        SectionType::Experience => "experience",
        SectionType::Project => "project",
        SectionType::Skill => "skill",
    }
}

/// Add one more row of a type, offering only what is not already on.
fn add_row<'a>(draft: &Draft, library: &'a Library, kind: SectionType) -> Element<'a, Message> {
    let attached: Vec<String> = draft
        .refs_of(kind)
        .into_iter()
        .map(|reference| reference.section_id)
        .collect();
    let available: Vec<Choice> = library
        .catalogs
        .choices(kind)
        .into_iter()
        .filter(|(id, _)| !attached.contains(id))
        .map(|(id, label)| Choice { id, label })
        .collect();

    if available.is_empty() {
        return subtle("Everything you have of this type is already on the resume.")
            .size(12)
            .into();
    }

    pick_list(available, None::<Choice>, move |choice| {
        Message::Attach(kind, choice)
    })
    .placeholder(format!("Add {}…", singular(kind)))
    .padding([6, 10])
    .text_size(14)
    .width(Length::Fill)
    .style(style::picker)
    .into()
}
