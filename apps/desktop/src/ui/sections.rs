//! The library: every section, grouped by type. A row opens its form.

use super::style::{self, Kind, tokens};
use super::widgets::{back, btn, heading, page, subtle, title};
use super::{Library, Message, Route, SectionKind};
use iced::widget::{Column, button, column, container, row, space, text};
use iced::{Alignment, Element, Length};

fn or_dash(value: Option<&str>) -> String {
    match value {
        Some(value) if !value.is_empty() => value.to_string(),
        _ => "—".into(),
    }
}

fn joined(items: &[String]) -> String {
    if items.is_empty() {
        "—".into()
    } else {
        items.join(", ")
    }
}

/// One type's rows, as a titled table with an add button.
fn table<'a>(
    kind: SectionKind,
    headers: &[&'a str],
    rows: Vec<(String, Vec<String>)>,
    empty: &'a str,
) -> Element<'a, Message> {
    let header = row(headers.iter().map(|label| {
        text(label.to_string())
            .size(13)
            .style(|theme| text::Style {
                color: Some(tokens(theme).header_ink),
            })
            .width(Length::Fill)
            .into()
    }))
    .spacing(8)
    .padding([10, 16]);

    let mut body = Column::new().push(header);

    if rows.is_empty() {
        body = body.push(container(subtle(empty)).padding([12, 16]));
    }

    for (id, cells) in rows {
        let cells = row(cells
            .into_iter()
            .map(|cell| text(cell).size(14).width(Length::Fill).into()))
        .spacing(8);

        body = body.push(
            button(cells)
                .padding([12, 16])
                .width(Length::Fill)
                .style(|theme, status| {
                    let mut style = style::button(Kind::Surface)(theme, status);
                    style.border = iced::Border::default();
                    if matches!(status, button::Status::Active) {
                        style.background = None;
                    }
                    style
                })
                .on_press(Message::Navigate(Route::Section(kind, Some(id)))),
        );
    }

    column![
        row![
            heading(kind.plural()),
            space::horizontal(),
            btn(
                "+ Add",
                Kind::Secondary,
                Some(Message::Navigate(Route::Section(kind, None)))
            ),
        ]
        .align_y(Alignment::Center),
        container(body)
            .width(Length::Fill)
            .clip(true)
            .style(style::panel),
    ]
    .spacing(12)
    .into()
}

pub fn view(library: &Library) -> Element<'_, Message> {
    let catalogs = &library.catalogs;

    let education = table(
        SectionKind::Education,
        &["Name", "Subheading", "Duration", "Location"],
        catalogs
            .education
            .iter()
            .map(|row| {
                (
                    row.id.clone(),
                    vec![
                        row.name.clone(),
                        row.subheading.clone(),
                        row.duration.clone(),
                        row.location.clone(),
                    ],
                )
            })
            .collect(),
        "No education added yet.",
    );

    let experience = table(
        SectionKind::Experience,
        &["Position", "Company", "Duration", "Location"],
        catalogs
            .experience
            .iter()
            .map(|row| {
                (
                    row.id.clone(),
                    vec![
                        row.position.clone(),
                        row.company.clone(),
                        row.duration.clone(),
                        row.location.clone(),
                    ],
                )
            })
            .collect(),
        "No experience added yet.",
    );

    let personal_info = table(
        SectionKind::PersonalInfo,
        &["Email", "Phone", "Address", "Links"],
        library
            .personal_info
            .iter()
            .map(|row| {
                let links: Vec<String> = [&row.github, &row.linkedin, &row.portfolio]
                    .into_iter()
                    .flatten()
                    .map(|link| link.label.clone().unwrap_or_else(|| link.url.clone()))
                    .collect();
                (
                    row.id.clone(),
                    vec![
                        or_dash(row.email.as_deref()),
                        or_dash(row.phone_number.as_deref()),
                        or_dash(row.address.as_deref()),
                        joined(&links),
                    ],
                )
            })
            .collect(),
        "No personal info added yet.",
    );

    let projects = table(
        SectionKind::Project,
        &["Name", "Technologies", "Link"],
        catalogs
            .project
            .iter()
            .map(|row| {
                (
                    row.id.clone(),
                    vec![
                        row.name.clone(),
                        joined(&row.technologies),
                        or_dash(row.link.as_deref()),
                    ],
                )
            })
            .collect(),
        "No projects added yet.",
    );

    let skills = table(
        SectionKind::Skill,
        &["Name", "Items"],
        catalogs
            .skill
            .iter()
            .map(|row| (row.id.clone(), vec![row.name.clone(), joined(&row.items)]))
            .collect(),
        "No skills added yet.",
    );

    page(
        column![
            back("Back to dashboard", Message::Navigate(Route::Dashboard)),
            space::vertical().height(16),
            title("Sections"),
            space::vertical().height(8),
            subtle("Everything you've added, grouped by section type. Click a row to edit or delete it."),
            space::vertical().height(32),
            column![education, experience, personal_info, projects, skills].spacing(40),
        ]
        .width(Length::Fill),
    )
}
