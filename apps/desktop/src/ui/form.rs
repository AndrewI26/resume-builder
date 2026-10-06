//! Adding and editing one library row, for any of the five types.
//!
//! The types differ in which text fields they have, and two of them carry a
//! list: experience and projects have bullet points with bold runs, skills
//! have an ordered list of items. Rather than five near-identical screens,
//! the fields are data here — a key, a label, whether it is required — and
//! only the save step knows which API shape each type wants.

use super::style::{self, Kind as ButtonKind};
use super::widgets::{self, BOLD, back, btn, field, modal, page, panel, subtle, title};
use super::{Library, Outcome, Route};
use crate::api::models::*;
use crate::api::{ApiResult, Client};
use crate::bullets::{self, BulletDraft};
use iced::keyboard::{Key, key::Named};
use iced::widget::text_editor;
use iced::widget::text_editor::{Binding, Content};
use iced::widget::{Column, column, rich_text, row, space, span, text, text_input};
use iced::{Alignment, Element, Length, Task};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Education,
    Experience,
    PersonalInfo,
    Project,
    Skill,
}

impl Kind {
    pub fn plural(self) -> &'static str {
        match self {
            Kind::Education => "Education",
            Kind::Experience => "Experience",
            Kind::PersonalInfo => "Personal info",
            Kind::Project => "Projects",
            Kind::Skill => "Skills",
        }
    }

    fn singular(self) -> &'static str {
        match self {
            Kind::Education => "education",
            Kind::Experience => "experience",
            Kind::PersonalInfo => "personal info",
            Kind::Project => "project",
            Kind::Skill => "skill",
        }
    }

    fn collection(self) -> &'static str {
        match self {
            Kind::Education => "/education/",
            Kind::Experience => "/experience/",
            Kind::PersonalInfo => "/personal-info/",
            Kind::Project => "/project/",
            Kind::Skill => "/skill/",
        }
    }
}

struct Field {
    key: &'static str,
    label: &'static str,
    placeholder: &'static str,
    /// The message shown when it is left blank; `None` means optional.
    required: Option<&'static str>,
    value: String,
    error: Option<&'static str>,
}

fn field_spec(
    key: &'static str,
    label: &'static str,
    placeholder: &'static str,
    required: Option<&'static str>,
    value: impl Into<String>,
) -> Field {
    Field {
        key,
        label,
        placeholder,
        required,
        value: value.into(),
        error: None,
    }
}

/// A bullet's text and bolding, plus the editor widget's own state.
struct Bullet {
    draft: BulletDraft,
    content: Content,
}

impl Bullet {
    fn new(draft: BulletDraft) -> Self {
        let content = Content::with_text(&draft.text);
        Self { draft, content }
    }

    /// The selection as character indices, smallest first.
    ///
    /// The editor reports byte columns; the bolding counts characters, so
    /// "Café" bolds the same letters here as it does in the API.
    fn selection(&self) -> Option<(usize, usize)> {
        let cursor = self.content.cursor();
        let anchor = cursor.selection?;
        let line = self
            .content
            .line(0)
            .map(|line| line.text.to_string())
            .unwrap_or_default();
        let to_chars = |column: usize| line[..column.min(line.len())].chars().count();

        let a = to_chars(cursor.position.column);
        let b = to_chars(anchor.column);
        (a != b).then(|| (a.min(b), a.max(b)))
    }
}

pub struct State {
    kind: Kind,
    id: Option<String>,
    /// The row was asked for but is not in the library any more.
    missing: bool,
    fields: Vec<Field>,
    bullets: Vec<Bullet>,
    items: Vec<String>,
    skill_position: Option<i64>,
    saving: bool,
    deleting: bool,
    confirm_delete: bool,
    error: Option<String>,
}

#[derive(Debug, Clone)]
pub enum Message {
    Back,
    Text(usize, String),
    Bullet(usize, text_editor::Action),
    Bold(usize),
    AddBullet,
    RemoveBullet(usize),
    MoveBullet(usize, usize),
    Item(usize, String),
    AddItem,
    RemoveItem(usize),
    MoveItem(usize, usize),
    Save,
    Saved(ApiResult<()>),
    AskDelete,
    CancelDelete,
    Delete,
    Deleted(ApiResult<()>),
}

fn link_parts(link: &Option<Link>) -> (String, String) {
    link.as_ref()
        .map(|link| (link.url.clone(), link.label.clone().unwrap_or_default()))
        .unwrap_or_default()
}

/// A URL plus its label, once a URL is given at all.
fn build_link(url: &str, label: &str) -> Option<Link> {
    let url = url.trim();
    (!url.is_empty()).then(|| Link {
        url: url.into(),
        label: Some(label.trim().to_string()).filter(|label| !label.is_empty()),
    })
}

fn optional(value: &str) -> Option<String> {
    Some(value.trim().to_string()).filter(|value| !value.is_empty())
}

fn split_list(value: &str) -> Vec<String> {
    value
        .split(',')
        .map(str::trim)
        .filter(|item| !item.is_empty())
        .map(String::from)
        .collect()
}

impl State {
    pub fn new(kind: Kind, id: Option<&str>, library: &Library) -> Self {
        let catalogs = &library.catalogs;
        let mut bullets = Vec::new();
        let mut items = Vec::new();
        let mut skill_position = None;

        let missing;
        let fields = match kind {
            Kind::Education => {
                let row = id.and_then(|id| catalogs.education.iter().find(|row| row.id == id));
                missing = id.is_some() && row.is_none();
                let get =
                    |pick: fn(&Education) -> &String| row.map(pick).cloned().unwrap_or_default();
                vec![
                    field_spec(
                        "name",
                        "School",
                        "University of Waterloo",
                        Some("Enter a school."),
                        get(|r| &r.name),
                    ),
                    field_spec(
                        "subheading",
                        "Subheading",
                        "Computer Science (B.A.Sc.)",
                        Some("Enter a subheading."),
                        get(|r| &r.subheading),
                    ),
                    field_spec(
                        "duration",
                        "Duration",
                        "2022 – 2026",
                        Some("Enter a duration."),
                        get(|r| &r.duration),
                    ),
                    field_spec(
                        "location",
                        "Location",
                        "Waterloo, Ontario",
                        Some("Enter a location."),
                        get(|r| &r.location),
                    ),
                ]
            }
            Kind::Experience => {
                let row = id.and_then(|id| catalogs.experience.iter().find(|row| row.id == id));
                missing = id.is_some() && row.is_none();
                bullets = bullets::from_api(row.map(|r| r.bullet_points.as_slice()).unwrap_or(&[]))
                    .into_iter()
                    .map(Bullet::new)
                    .collect();
                let get =
                    |pick: fn(&Experience) -> &String| row.map(pick).cloned().unwrap_or_default();
                vec![
                    field_spec(
                        "position",
                        "Position",
                        "Software Engineer",
                        Some("Enter a position."),
                        get(|r| &r.position),
                    ),
                    field_spec(
                        "company",
                        "Company",
                        "Acme Corp",
                        Some("Enter a company."),
                        get(|r| &r.company),
                    ),
                    field_spec(
                        "duration",
                        "Duration",
                        "2022 – Present",
                        Some("Enter a duration."),
                        get(|r| &r.duration),
                    ),
                    field_spec(
                        "location",
                        "Location",
                        "Remote",
                        Some("Enter a location."),
                        get(|r| &r.location),
                    ),
                ]
            }
            Kind::Project => {
                let row = id.and_then(|id| catalogs.project.iter().find(|row| row.id == id));
                missing = id.is_some() && row.is_none();
                bullets = bullets::from_api(row.map(|r| r.bullet_points.as_slice()).unwrap_or(&[]))
                    .into_iter()
                    .map(Bullet::new)
                    .collect();
                vec![
                    field_spec(
                        "name",
                        "Name",
                        "Resume Builder",
                        Some("Enter a name."),
                        row.map(|r| r.name.clone()).unwrap_or_default(),
                    ),
                    field_spec(
                        "link",
                        "Link",
                        "https://github.com/you/project",
                        None,
                        row.and_then(|r| r.link.clone()).unwrap_or_default(),
                    ),
                    field_spec(
                        "technologies",
                        "Technologies, separated by commas",
                        "Rust, Iced, FastAPI",
                        None,
                        row.map(|r| r.technologies.join(", ")).unwrap_or_default(),
                    ),
                ]
            }
            Kind::Skill => {
                let row = id.and_then(|id| catalogs.skill.iter().find(|row| row.id == id));
                missing = id.is_some() && row.is_none();
                items = row.map(|r| r.items.clone()).unwrap_or_default();
                if items.is_empty() {
                    items.push(String::new());
                }
                skill_position = row.map(|r| r.position);
                vec![field_spec(
                    "name",
                    "Name",
                    "Languages",
                    Some("Enter a name."),
                    row.map(|r| r.name.clone()).unwrap_or_default(),
                )]
            }
            Kind::PersonalInfo => {
                let row = id.and_then(|id| library.personal_info.iter().find(|row| row.id == id));
                missing = id.is_some() && row.is_none();
                let (github_url, github_label) = link_parts(&row.and_then(|r| r.github.clone()));
                let (linkedin_url, linkedin_label) =
                    link_parts(&row.and_then(|r| r.linkedin.clone()));
                let (portfolio_url, portfolio_label) =
                    link_parts(&row.and_then(|r| r.portfolio.clone()));
                let get = |pick: fn(&PersonalInfo) -> &Option<String>| {
                    row.and_then(|r| pick(r).clone()).unwrap_or_default()
                };
                vec![
                    field_spec("email", "Email", "you@example.com", None, get(|r| &r.email)),
                    field_spec(
                        "phone_number",
                        "Phone",
                        "(555) 123-4567",
                        None,
                        get(|r| &r.phone_number),
                    ),
                    field_spec(
                        "address",
                        "Address",
                        "Toronto, Ontario",
                        None,
                        get(|r| &r.address),
                    ),
                    field_spec(
                        "github_url",
                        "GitHub URL",
                        "https://github.com/you",
                        None,
                        github_url,
                    ),
                    field_spec(
                        "github_label",
                        "GitHub label",
                        "github.com/you",
                        None,
                        github_label,
                    ),
                    field_spec(
                        "linkedin_url",
                        "LinkedIn URL",
                        "https://linkedin.com/in/you",
                        None,
                        linkedin_url,
                    ),
                    field_spec(
                        "linkedin_label",
                        "LinkedIn label",
                        "linkedin.com/in/you",
                        None,
                        linkedin_label,
                    ),
                    field_spec(
                        "portfolio_url",
                        "Portfolio URL",
                        "https://you.dev",
                        None,
                        portfolio_url,
                    ),
                    field_spec(
                        "portfolio_label",
                        "Portfolio label",
                        "Portfolio",
                        None,
                        portfolio_label,
                    ),
                ]
            }
        };

        Self {
            kind,
            id: id.map(String::from),
            missing,
            fields,
            bullets,
            items,
            skill_position,
            saving: false,
            deleting: false,
            confirm_delete: false,
            error: None,
        }
    }

    pub fn title(&self) -> String {
        let verb = if self.id.is_some() { "Edit" } else { "Add" };
        format!("{verb} {}", self.kind.singular())
    }

    fn value(&self, key: &str) -> &str {
        self.fields
            .iter()
            .find(|field| field.key == key)
            .map(|field| field.value.as_str())
            .unwrap_or("")
    }

    /// Flag every blank required field; true when there were none.
    fn validate(&mut self) -> bool {
        let mut valid = true;
        for field in &mut self.fields {
            field.error = field.required.filter(|_| field.value.trim().is_empty());
            valid &= field.error.is_none();
        }
        valid
    }

    fn save(&self, client: Client) -> Task<Message> {
        let id = self.id.clone();
        let bullets = bullets::to_api(
            &self
                .bullets
                .iter()
                .map(|b| b.draft.clone())
                .collect::<Vec<_>>(),
        );
        let text = |key: &str| self.value(key).trim().to_string();

        match self.kind {
            Kind::Education => {
                let body = EducationInput {
                    name: text("name"),
                    subheading: text("subheading"),
                    duration: text("duration"),
                    location: text("location"),
                };
                Task::perform(
                    async move { client.save_education(id.as_deref(), &body).await },
                    Message::Saved,
                )
            }
            Kind::Experience => {
                let body = ExperienceInput {
                    position: text("position"),
                    company: text("company"),
                    duration: text("duration"),
                    location: text("location"),
                    bullet_points: bullets,
                };
                Task::perform(
                    async move { client.save_experience(id.as_deref(), &body).await },
                    Message::Saved,
                )
            }
            Kind::Project => {
                let body = ProjectInput {
                    name: text("name"),
                    link: optional(self.value("link")),
                    technologies: split_list(self.value("technologies")),
                    bullet_points: bullets,
                };
                Task::perform(
                    async move { client.save_project(id.as_deref(), &body).await },
                    Message::Saved,
                )
            }
            Kind::Skill => {
                let body = SkillInput {
                    name: text("name"),
                    items: self
                        .items
                        .iter()
                        .map(|item| item.trim().to_string())
                        .filter(|item| !item.is_empty())
                        .collect(),
                    // a replace has to say where the skill sits; a create appends
                    position: self.skill_position,
                };
                Task::perform(
                    async move { client.save_skill(id.as_deref(), &body).await },
                    Message::Saved,
                )
            }
            Kind::PersonalInfo => {
                let body = PersonalInfoInput {
                    email: optional(self.value("email")),
                    phone_number: optional(self.value("phone_number")),
                    address: optional(self.value("address")),
                    github: build_link(self.value("github_url"), self.value("github_label")),
                    linkedin: build_link(self.value("linkedin_url"), self.value("linkedin_label")),
                    portfolio: build_link(
                        self.value("portfolio_url"),
                        self.value("portfolio_label"),
                    ),
                };
                Task::perform(
                    async move { client.save_personal_info(id.as_deref(), &body).await },
                    Message::Saved,
                )
            }
        }
    }

    pub fn update(&mut self, message: Message, client: Client) -> Outcome<Message> {
        match message {
            Message::Back => Outcome::navigate(Route::Sections),
            Message::Text(index, value) => {
                if let Some(field) = self.fields.get_mut(index) {
                    field.value = value;
                    field.error = None;
                }
                Outcome::none()
            }
            Message::Bullet(index, action) => {
                if let Some(bullet) = self.bullets.get_mut(index) {
                    let edit = action.is_edit();
                    bullet.content.perform(action);
                    if edit {
                        // a bullet is one line; a pasted line break becomes a space
                        let text = bullet.content.text();
                        if text.contains(['\n', '\r']) {
                            let flat = text.replace("\r\n", " ").replace(['\n', '\r'], " ");
                            bullet.content = Content::with_text(&flat);
                            bullet.draft.set_text(flat);
                        } else {
                            bullet.draft.set_text(text);
                        }
                    }
                }
                Outcome::none()
            }
            Message::Bold(index) => {
                if let Some(bullet) = self.bullets.get_mut(index)
                    && let Some((start, end)) = bullet.selection()
                {
                    bullet.draft.toggle_bold(start, end);
                }
                Outcome::none()
            }
            Message::AddBullet => {
                self.bullets.push(Bullet::new(BulletDraft::default()));
                Outcome::none()
            }
            Message::RemoveBullet(index) => {
                if self.bullets.len() > 1 && index < self.bullets.len() {
                    self.bullets.remove(index);
                }
                Outcome::none()
            }
            Message::MoveBullet(from, to) => {
                if from < self.bullets.len() && to < self.bullets.len() {
                    let moved = self.bullets.remove(from);
                    self.bullets.insert(to, moved);
                }
                Outcome::none()
            }
            Message::Item(index, value) => {
                if let Some(item) = self.items.get_mut(index) {
                    *item = value;
                }
                Outcome::none()
            }
            Message::AddItem => {
                self.items.push(String::new());
                Outcome::none()
            }
            Message::RemoveItem(index) => {
                if self.items.len() > 1 && index < self.items.len() {
                    self.items.remove(index);
                }
                Outcome::none()
            }
            Message::MoveItem(from, to) => {
                self.items = crate::draft::move_item(&self.items, from, to);
                Outcome::none()
            }
            Message::Save => {
                if self.saving || !self.validate() {
                    return Outcome::none();
                }
                self.saving = true;
                self.error = None;
                Outcome::task(self.save(client))
            }
            Message::Saved(Ok(())) => Outcome::navigate(Route::Sections).reload(),
            Message::Saved(Err(error)) => {
                self.saving = false;
                self.error = Some(error.0);
                Outcome::none()
            }
            Message::AskDelete => {
                self.confirm_delete = true;
                self.error = None;
                Outcome::none()
            }
            Message::CancelDelete => {
                self.confirm_delete = false;
                Outcome::none()
            }
            Message::Delete => {
                let Some(id) = self.id.clone() else {
                    return Outcome::none();
                };
                self.deleting = true;
                let collection = self.kind.collection();
                Outcome::task(Task::perform(
                    async move { client.delete_row(collection, &id).await },
                    Message::Deleted,
                ))
            }
            Message::Deleted(Ok(())) => Outcome::navigate(Route::Sections).reload(),
            Message::Deleted(Err(error)) => {
                // the dialog stays open, so the message has somewhere to land
                self.deleting = false;
                self.error = Some(error.0);
                Outcome::none()
            }
        }
    }

    pub fn view(&self) -> Element<'_, Message> {
        let mut form = Column::new().spacing(16);

        if self.missing {
            form = form.push(widgets::banner("This entry is no longer in your library."));
        } else {
            for (index, spec) in self.fields.iter().enumerate() {
                form = form.push(field(
                    spec.label,
                    spec.placeholder,
                    &spec.value,
                    move |value| Message::Text(index, value),
                    spec.error,
                ));
            }

            if matches!(self.kind, Kind::Experience | Kind::Project) {
                form = form.push(self.bullets_view());
            }
            if self.kind == Kind::Skill {
                form = form.push(self.items_view());
            }

            if let Some(error) = &self.error
                && !self.confirm_delete
            {
                form = form.push(widgets::banner(error));
            }

            form = form.push(self.actions());
        }

        let content = page(
            column![
                back("Back to sections", Message::Back),
                space::vertical().height(16),
                title(self.title()),
                space::vertical().height(28),
                form,
            ]
            .width(Length::Fill),
        );

        modal(
            content,
            self.confirm_delete.then(|| widgets::Confirm {
                title: "Delete this entry?",
                body: subtle(format!(
                    "This {} entry will be deleted permanently, and taken off every resume that uses it.",
                    self.kind.singular()
                ))
                .into(),
                confirm: "Delete",
                pending: self.deleting.then_some("Deleting…"),
                error: self.error.as_deref(),
                on_cancel: Message::CancelDelete,
                on_confirm: Message::Delete,
            }),
        )
    }

    fn actions(&self) -> Element<'_, Message> {
        let busy = self.saving || self.deleting;
        let mut actions = row![].spacing(12).align_y(Alignment::Center);

        if self.id.is_some() {
            actions = actions.push(btn(
                "Delete",
                ButtonKind::Danger,
                (!busy).then_some(Message::AskDelete),
            ));
        }

        let label = if self.saving {
            "Saving…".to_string()
        } else if self.id.is_some() {
            "Save changes".to_string()
        } else {
            format!("Add {}", self.kind.singular())
        };

        actions
            .push(space::horizontal())
            .push(btn(
                label,
                ButtonKind::Primary,
                (!busy).then_some(Message::Save),
            ))
            .into()
    }

    fn bullets_view(&self) -> Element<'_, Message> {
        let count = self.bullets.len();
        let mut list = Column::new().spacing(10);

        for (index, bullet) in self.bullets.iter().enumerate() {
            let editor = text_editor(&bullet.content)
                .placeholder("Cut p99 latency by 40% by adding a read-through cache")
                .on_action(move |action| Message::Bullet(index, action))
                .key_binding(move |press| {
                    if press.modifiers.command() && press.key == Key::Character("b".into()) {
                        return Some(Binding::Custom(Message::Bold(index)));
                    }
                    // a bullet is a single line on the resume
                    if press.key == Key::Named(Named::Enter) {
                        return None;
                    }
                    Binding::from_key_press(press)
                })
                .padding([9, 14])
                .size(15)
                .min_height(64)
                .style(style::editor);

            let controls = row![
                btn("B", ButtonKind::Secondary, Some(Message::Bold(index))),
                subtle("Select text, then Bold (⌘B)"),
                space::horizontal(),
                btn(
                    "↑",
                    ButtonKind::Icon,
                    (index > 0).then(|| Message::MoveBullet(index, index - 1))
                ),
                btn(
                    "↓",
                    ButtonKind::Icon,
                    (index + 1 < count).then(|| Message::MoveBullet(index, index + 1))
                ),
                btn(
                    "Remove",
                    ButtonKind::Danger,
                    (count > 1).then_some(Message::RemoveBullet(index))
                ),
            ]
            .spacing(8)
            .align_y(Alignment::Center);

            let mut card = column![editor, controls].spacing(10);

            let segments = bullet.draft.segments();
            if !segments.is_empty() {
                let spans: Vec<text::Span<'_, (), iced::Font>> = segments
                    .into_iter()
                    .map(|segment| {
                        let piece = span(segment.text).size(14);
                        if segment.bold {
                            piece.font(BOLD)
                        } else {
                            piece
                        }
                    })
                    .collect();
                let preview = rich_text(spans);
                card = card.push(preview.size(14));
            }

            list = list.push(panel(card));
        }

        column![
            subtle("Bullet points"),
            list,
            btn(
                "Add bullet point",
                ButtonKind::Secondary,
                Some(Message::AddBullet)
            ),
        ]
        .spacing(8)
        .into()
    }

    fn items_view(&self) -> Element<'_, Message> {
        let count = self.items.len();
        let mut list = Column::new().spacing(8);

        for (index, item) in self.items.iter().enumerate() {
            list = list.push(
                row![
                    text_input("Python", item)
                        .on_input(move |value| Message::Item(index, value))
                        .padding([9, 14])
                        .size(15)
                        .style(style::input(false)),
                    btn(
                        "↑",
                        ButtonKind::Icon,
                        (index > 0).then(|| Message::MoveItem(index, index - 1))
                    ),
                    btn(
                        "↓",
                        ButtonKind::Icon,
                        (index + 1 < count).then(|| Message::MoveItem(index, index + 1))
                    ),
                    btn(
                        "Remove",
                        ButtonKind::Danger,
                        (count > 1).then_some(Message::RemoveItem(index))
                    ),
                ]
                .spacing(8)
                .align_y(Alignment::Center),
            );
        }

        column![
            text("Items").size(14),
            list,
            btn("Add item", ButtonKind::Secondary, Some(Message::AddItem)),
        ]
        .spacing(8)
        .into()
    }
}
