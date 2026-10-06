//! Every screen, rendered headlessly.
//!
//! The library is the shared sample document — the same one the LaTeX golden
//! test uses — so the screens are drawn with realistic rows, and nothing here
//! needs the sidecar. Set `SNAPSHOT_DIR` to also write each screen as a PNG,
//! light and dark, for looking at by eye.

use super::*;
use crate::api::models::{ResumeDocument, ResumeSections, SectionBlock};
use iced_test::simulator::Simulator;

const SAMPLE: &str = include_str!("../../../api/tests/fixtures/sample_document.json");

fn library() -> Library {
    let document: ResumeDocument = serde_json::from_str(SAMPLE).unwrap();
    let mut catalogs = Catalogs::default();
    for section in document.sections {
        match section {
            SectionBlock::Education(items) => catalogs.education = items,
            SectionBlock::Experience(items) => catalogs.experience = items,
            SectionBlock::Project(items) => catalogs.project = items,
            SectionBlock::Skill(items) => catalogs.skill = items,
        }
    }

    let contact = document.personal_info.as_ref().map(|info| info.id.clone());
    let resume = |id: &str, title: &str| Resume {
        id: id.into(),
        title: title.into(),
        template: "jakes".into(),
        full_name: Some("Andrew Iammancini".into()),
        personal_info_id: contact.clone(),
        section_order: vec![
            SectionType::Experience,
            SectionType::Project,
            SectionType::Skill,
        ],
        updated_at: "2026-10-06T14:30:00".into(),
    };

    Library {
        catalogs,
        personal_info: document.personal_info.into_iter().collect(),
        resumes: vec![resume("r1", "Frontend"), resume("r2", "Platform")],
    }
}

use crate::api::models::SectionType;

fn app(route: Route, dark: bool) -> App {
    let mut app = App {
        phase: Phase::Ready(Client::new("http://127.0.0.1:9".into(), "test".into())),
        dark,
        library: Some(library()),
        library_error: None,
        screen: Screen::Dashboard(dashboard::State::default()),
        closing: false,
    };
    let _ = app.open(route);
    app
}

/// The editor, with its resume loaded as if the API had answered.
fn editor(dark: bool) -> App {
    let mut app = app(Route::Editor("r1".into()), dark);
    let library = library();
    let resume = library.resumes[0].clone();
    let sections = ResumeSections {
        sections: vec![
            SectionRef {
                section_type: SectionType::Experience,
                section_id: library.catalogs.experience[1].id.clone(),
            },
            SectionRef {
                section_type: SectionType::Experience,
                section_id: library.catalogs.experience[0].id.clone(),
            },
            SectionRef {
                section_type: SectionType::Project,
                section_id: library.catalogs.project[0].id.clone(),
            },
            SectionRef {
                section_type: SectionType::Skill,
                section_id: library.catalogs.skill[0].id.clone(),
            },
        ],
    };
    let _ = app.update(Message::Editor(editor::Message::Loaded(Ok((
        resume, sections,
    )))));
    app
}

use crate::api::models::SectionRef;

fn simulate(app: &App) -> Simulator<'_, Message> {
    Simulator::with_size(
        iced::Settings::default(),
        iced::Size::new(1280.0, 860.0),
        app.view(),
    )
}

/// Write the screen to `SNAPSHOT_DIR/<name>-<theme>.png`, if one is set.
fn snapshot(app: &App, name: &str) {
    let Some(dir) = std::env::var_os("SNAPSHOT_DIR") else {
        return;
    };
    let theme = if app.dark { "dark" } else { "light" };
    let path = std::path::Path::new(&dir).join(format!("{name}-{theme}"));
    let _ = std::fs::remove_file(path.with_extension("png"));
    simulate(app)
        .snapshot(&app.theme())
        .unwrap()
        .matches_image(&path)
        .unwrap();
}

fn assert_shows(app: &App, texts: &[&str]) {
    let mut ui = simulate(app);
    for text in texts {
        assert!(ui.find(*text).is_ok(), "expected to find {text:?}");
    }
}

fn every_theme(name: &str, build: impl Fn(bool) -> App) {
    for dark in [false, true] {
        snapshot(&build(dark), name);
    }
}

#[test]
fn the_dashboard_counts_the_library() {
    let app = app(Route::Dashboard, false);
    // four section types; personal info is the header, not a section
    let sections = library().section_count().to_string();
    assert_shows(
        &app,
        &["Dashboard", "Resumes", "2", &sections, "Back up now"],
    );
    every_theme("dashboard", |dark| self::app(Route::Dashboard, dark));
}

#[test]
fn the_dashboard_opens_the_sections() {
    let app = app(Route::Dashboard, false);
    let mut ui = simulate(&app);
    ui.click("Sections").unwrap();
    let messages: Vec<Message> = ui.into_messages().collect();
    assert!(
        messages.iter().any(|message| matches!(
            message,
            Message::Dashboard(dashboard::Message::Open(Route::Sections))
        )),
        "{messages:?}"
    );
}

#[test]
fn the_sections_list_every_type() {
    let app = app(Route::Sections, false);
    assert_shows(
        &app,
        &[
            "Education",
            "Experience",
            "Personal info",
            "Projects",
            "Skills",
            "CampusCart",
            "Eon Media",
        ],
    );
    every_theme("sections", |dark| self::app(Route::Sections, dark));
}

#[test]
fn an_experience_form_carries_its_bullets() {
    let id = library().catalogs.experience[1].id.clone();
    let app = app(
        Route::Section(SectionKind::Experience, Some(id.clone())),
        false,
    );
    assert_shows(
        &app,
        &["Edit experience", "Save changes", "Delete", "Bullet points"],
    );
    every_theme("experience-form", |dark| {
        self::app(
            Route::Section(SectionKind::Experience, Some(id.clone())),
            dark,
        )
    });
}

#[test]
fn a_new_skill_form_offers_one_blank_item() {
    let app = app(Route::Section(SectionKind::Skill, None), false);
    assert_shows(&app, &["Add skill", "Items", "Add item"]);
}

#[test]
fn saving_a_blank_required_field_says_so() {
    let mut app = app(Route::Section(SectionKind::Education, None), false);
    let _ = app.update(Message::Form(form::Message::Save));
    assert_shows(&app, &["Enter a school."]);
}

#[test]
fn the_resumes_screen_lists_and_offers_export() {
    let app = app(Route::Resumes, false);
    assert_shows(
        &app,
        &[
            "Resumes",
            "Create resume",
            "Export all resumes",
            "Frontend",
            "Platform",
            "Oct 6, 2026",
        ],
    );
    every_theme("resumes", |dark| self::app(Route::Resumes, dark));
}

#[test]
fn deleting_a_resume_asks_first() {
    let mut app = app(Route::Resumes, false);
    let resume = library().resumes[0].clone();
    let _ = app.update(Message::Resumes(resumes::Message::AskDelete(resume)));
    assert_shows(&app, &["Delete this resume?", "Cancel"]);
    snapshot(&app, "resumes-delete");
}

#[test]
fn the_editor_lays_out_the_draft() {
    let app = editor(false);
    assert_shows(
        &app,
        &[
            "Frontend",
            "Header",
            "Experience",
            "2 entries",
            "Compiling…",
            "Download .tex",
            "Not on this resume",
        ],
    );
    every_theme("editor", editor);
}

#[test]
fn moving_a_heading_marks_the_draft_unsaved() {
    let mut app = editor(false);
    let _ = app.update(Message::Editor(editor::Message::MoveHeading(0, 1)));
    assert_shows(&app, &["Unsaved changes"]);
}

#[test]
fn a_failed_start_shows_what_went_wrong() {
    let mut app = app(Route::Dashboard, false);
    app.phase = Phase::Failed("uv: command not found".into());
    assert_shows(
        &app,
        &[
            "The app could not open your library",
            "uv: command not found",
            "Try again",
        ],
    );
}

/// The editor with a real compiled PDF in its preview. Runs only after the
/// end-to-end test has left one in `SNAPSHOT_DIR`.
#[test]
fn the_editor_draws_a_compiled_pdf() {
    let Some(dir) = std::env::var_os("SNAPSHOT_DIR") else {
        return;
    };
    let Ok(bytes) = std::fs::read(std::path::Path::new(&dir).join("end-to-end.pdf")) else {
        return;
    };

    let mut app = editor(false);
    let signature = match &app.screen {
        Screen::Editor(state) => state.signature(),
        _ => unreachable!(),
    };
    let pages = crate::pdf::rasterise(bytes.clone()).unwrap();
    let _ = app.update(Message::Editor(editor::Message::Compiled(
        Ok((bytes, pages)),
        signature,
    )));
    assert_shows(
        &app,
        &[
            "Open full size",
            "Download PDF",
            "Compiled from your saved resume.",
        ],
    );
    snapshot(&app, "editor-compiled");
}
