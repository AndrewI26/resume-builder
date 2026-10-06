//! The whole path, against the real API: start the sidecar on a scratch
//! library, build a resume through the client, typeset it, draw the pages.
//!
//! Ignored by default — it needs `uv`, the API's environment and a TeX
//! install. Run it with:
//!
//!     cargo test end_to_end -- --ignored --nocapture

use crate::api::Client;
use crate::api::models::*;
use crate::{bullets, pdf, sidecar};

#[test]
#[ignore = "starts the real API; needs uv and TeX"]
fn a_resume_goes_from_rows_to_drawn_pages() {
    let scratch = tempfile::tempdir().unwrap();
    // SAFETY: set before anything else in this test process reads it, and
    // the test is ignored by default so it never races the parallel suite
    unsafe { std::env::set_var("RESUME_BUILDER_DATA_DIR", scratch.path()) };

    let endpoint = sidecar::start().expect("the sidecar starts");
    let client = Client::new(endpoint.base_url, endpoint.token);
    let runtime = tokio::runtime::Runtime::new().unwrap();

    let outcome = runtime.block_on(async {
        client
            .save_experience(
                None,
                &ExperienceInput {
                    company: "Acme & Sons".into(),
                    position: "Engineer".into(),
                    duration: "2024 – Present".into(),
                    location: "Remote".into(),
                    bullet_points: bullets::to_api(&[bullets::BulletDraft {
                        text: "Cut build times by 50% with remote caching".into(),
                        bolded: vec![(0, 15)],
                    }]),
                },
            )
            .await?;
        client
            .save_skill(
                None,
                &SkillInput {
                    name: "Languages".into(),
                    items: vec!["Rust".into(), "Python".into()],
                    position: None,
                },
            )
            .await?;

        let experience = client.experience().await?;
        let skills = client.skills().await?;
        assert_eq!(experience[0].bullet_points[0].bolded, vec![(0, 14)]);

        let resume = client
            .create_resume(&ResumeCreate {
                title: "Café Résumé".into(),
                template: "jakes".into(),
                full_name: Some("Casey Quinn".into()),
                personal_info_id: None,
                sections: vec![
                    SectionRef {
                        section_type: SectionType::Experience,
                        section_id: experience[0].id.clone(),
                    },
                    SectionRef {
                        section_type: SectionType::Skill,
                        section_id: skills[0].id.clone(),
                    },
                ],
            })
            .await?;

        let membership = client.resume_sections(&resume.id).await?;
        assert_eq!(membership.sections.len(), 2);

        client.compile_pdf(&resume.id).await
    });

    sidecar::stop();

    let bytes = outcome.expect("the resume compiles");
    assert!(bytes.starts_with(b"%PDF"), "a PDF came back");

    // kept for the editor's snapshot test, which draws it in the preview
    if let Some(dir) = std::env::var_os("SNAPSHOT_DIR") {
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(std::path::Path::new(&dir).join("end-to-end.pdf"), &bytes).unwrap();
    }

    let pages = pdf::rasterise(bytes).expect("the PDF rasterises");
    let page = &pages[0];

    // the page as drawn, to look at by eye
    if let Some(dir) = std::env::var_os("SNAPSHOT_DIR") {
        let file =
            std::fs::File::create(std::path::Path::new(&dir).join("end-to-end-page.png")).unwrap();
        let mut encoder = png::Encoder::new(file, page.width, page.height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        encoder
            .write_header()
            .unwrap()
            .write_image_data(&page.pixels)
            .unwrap();
    }
    assert_eq!(page.pixels.len(), (page.width * page.height * 4) as usize);
    let inked = page
        .pixels
        .as_chunks::<4>()
        .0
        .iter()
        .filter(|pixel| pixel[0] < 128)
        .count();
    assert!(
        inked > 1000,
        "the page has text on it ({inked} dark pixels)"
    );
    println!(
        "{} page(s), first {}x{}, {inked} dark pixels",
        pages.len(),
        page.width,
        page.height
    );
}
