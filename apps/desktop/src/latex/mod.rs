//! A resume document as Jake's Resume LaTeX source.
//!
//! A port of `apps/web/app/lib/latex/serialize.ts`, checked against the same
//! golden file the web app and the API test with — so the `.tex` this app
//! saves is the one the other two would produce.

pub mod escape;

use crate::api::models::{
    BulletPoint, Education, Experience, PersonalInfo, Project, ResumeDocument, SectionBlock, Skill,
};
use escape::{escape, escape_url};

/// Everything down to `\begin{document}`, lifted verbatim from `resume.tex`.
const PREAMBLE: &str = include_str!("preamble.tex");

fn href(url: &str, body: &str) -> String {
    format!("\\href{{{}}}{{{body}}}", escape_url(url))
}

/// An underline whose rule lands at the same depth whatever the label spells.
fn underlined(label: &str) -> String {
    format!("\\underline{{\\smash{{{label}}}\\vphantom{{gj/}}}}")
}

fn contact(icon: &str, label: &str, url: Option<&str>) -> String {
    let body = format!("\\raisebox{{-0.2\\height}}\\{icon}\\ {}", underlined(label));
    match url {
        Some(url) => href(url, &body),
        None => body,
    }
}

/// The scheme and any trailing slash stripped, the way the template prints links.
fn display_url(url: &str) -> String {
    let bare = url
        .strip_prefix("https://")
        .or_else(|| url.strip_prefix("http://"))
        .unwrap_or(url);
    escape(bare.strip_suffix('/').unwrap_or(bare))
}

fn link_label(label: &Option<String>, fallback: String) -> String {
    match label {
        Some(label) if !label.is_empty() => escape(label),
        _ => fallback,
    }
}

fn header(full_name: &str, info: Option<&PersonalInfo>) -> String {
    let mut entries = Vec::new();

    if let Some(info) = info {
        if let Some(phone) = info
            .phone_number
            .as_deref()
            .filter(|value| !value.is_empty())
        {
            entries.push(contact("faPhone", &escape(phone), None));
        }
        if let Some(email) = info.email.as_deref().filter(|value| !value.is_empty()) {
            entries.push(contact(
                "faEnvelope",
                &escape(email),
                Some(&format!("mailto:{email}")),
            ));
        }
        if let Some(link) = &info.linkedin {
            let label = link_label(&link.label, display_url(&link.url));
            entries.push(contact("faLinkedin", &label, Some(&link.url)));
        }
        if let Some(link) = &info.github {
            let label = link_label(&link.label, display_url(&link.url));
            entries.push(contact("faGithub", &label, Some(&link.url)));
        }
        if let Some(link) = &info.portfolio {
            let label = link_label(&link.label, "Portfolio".into());
            entries.push(contact("faInternetExplorer", &label, Some(&link.url)));
        }
        if let Some(address) = info.address.as_deref().filter(|value| !value.is_empty()) {
            entries.push(contact("faMapMarker", &escape(address), None));
        }
    }

    let mut lines = vec!["\\begin{center}".to_string()];

    if !full_name.trim().is_empty() {
        // ending a `center` block on `\\` is the fatal "no line here to end",
        // so the break only appears when a contact line follows it
        let rule = if entries.is_empty() {
            ""
        } else {
            " \\\\ \\vspace{1pt}"
        };
        lines.push(format!(
            "    {{\\Huge \\scshape {}}}{rule}",
            escape(full_name)
        ));
    }

    lines.extend(entries.into_iter().map(|entry| format!("    {entry} ~")));
    lines.push("\\end{center}".into());
    lines.join("\n")
}

/// The negative space that closes the gap to the next section; the last
/// section has no next, and a trailing vspace there pushes the page apart.
fn closing(is_last: bool, space: &str) -> Vec<String> {
    if is_last { vec![] } else { vec![space.into()] }
}

fn skills(items: &[Skill], is_last: bool) -> String {
    let lines: Vec<String> = items
        .iter()
        .map(|skill| {
            format!(
                "     \\textbf{{{}}}{{: {} }}",
                escape(&skill.name),
                escape(&skill.items.join(", "))
            )
        })
        .collect();

    let mut out = vec![
        "\\section{Skills}".to_string(),
        " \\begin{itemize}[leftmargin=0.15in, label={}]".into(),
        "    \\small{\\item{".into(),
        format!("{} }}}}", lines.join(" \\\\\n")),
        " \\end{itemize}".into(),
    ];
    out.extend(closing(is_last, " \\vspace{-20pt}"));
    out.join("\n")
}

fn bullet_list(bullets: &[BulletPoint]) -> Vec<String> {
    if bullets.is_empty() {
        return vec![];
    }

    let mut out = vec!["      \\resumeItemListStart".to_string()];
    out.extend(
        bullets
            .iter()
            .map(|bullet| format!("         \\resumeItem{{{}}}", escape::bullet(bullet))),
    );
    out.push("      \\resumeItemListEnd".into());
    out
}

fn experience(items: &[Experience], is_last: bool) -> String {
    let mut out = vec![
        "\\section{Experience}".to_string(),
        "  \\resumeSubHeadingListStart".into(),
    ];

    for entry in items {
        out.push("    \\resumeSubheading".into());
        out.push(format!(
            "        {{\\textbf{{{}}}}}{{{}}}",
            escape(&entry.position),
            escape(&entry.duration)
        ));
        out.push(format!(
            "      {{{}}} {{{}}}",
            escape(&entry.company),
            escape(&entry.location)
        ));
        out.extend(bullet_list(&entry.bullet_points));
        out.push(String::new());
    }

    out.push("  \\resumeSubHeadingListEnd".into());
    out.extend(closing(is_last, "\\vspace{-16pt}"));
    out.join("\n")
}

fn projects(items: &[Project], is_last: bool) -> String {
    let mut out = vec![
        "\\section{Projects}".to_string(),
        "    \\vspace{-5pt}".into(),
        "    \\resumeSubHeadingListStart".into(),
    ];

    for (index, project) in items.iter().enumerate() {
        let name = format!("\\textbf{{{}}}", escape(&project.name));
        // a linked project gets a chain glyph before its name
        let title = match project.link.as_deref().filter(|link| !link.is_empty()) {
            Some(link) => format!("{} {name}", href(link, "\\faLink")),
            None => name,
        };
        let technologies = if project.technologies.is_empty() {
            String::new()
        } else {
            format!(
                " $|$ \\emph{{ {} }}",
                escape(&project.technologies.join(", "))
            )
        };

        out.push("      \\resumeProjectHeading".into());
        out.push(format!("          {{{title}{technologies}}}{{}}"));
        out.extend(bullet_list(&project.bullet_points));
        // tightens the gap between entries, but not before the list ends
        if index != items.len() - 1 {
            out.push("          \\vspace{-16pt}".into());
            out.push(String::new());
        }
    }

    out.push("    \\resumeSubHeadingListEnd".into());
    out.extend(closing(is_last, "\\vspace{-16pt}"));
    out.join("\n")
}

fn education(items: &[Education], is_last: bool) -> String {
    let mut out = vec![
        "\\section{Education}".to_string(),
        "  \\resumeSubHeadingListStart".into(),
    ];

    for entry in items {
        out.push("  \\resumeSubheading".into());
        out.push(format!(
            "      {{{}}}{{{}}}",
            escape(&entry.name),
            escape(&entry.duration)
        ));
        out.push(format!(
            "      {{{}}} {{{}}}",
            escape(&entry.subheading),
            escape(&entry.location)
        ));
        out.push(String::new());
    }

    out.push("  \\resumeSubHeadingListEnd".into());
    out.extend(closing(is_last, "\\vspace{-16pt}"));
    out.join("\n")
}

fn block(section: &SectionBlock, is_last: bool) -> String {
    match section {
        SectionBlock::Skill(items) => skills(items, is_last),
        SectionBlock::Experience(items) => experience(items, is_last),
        SectionBlock::Project(items) => projects(items, is_last),
        SectionBlock::Education(items) => education(items, is_last),
    }
}

/// The complete `.tex` source for a resume document.
pub fn serialize(document: &ResumeDocument) -> String {
    // the API drops empty blocks, but a bare heading is worth guarding twice
    let blocks: Vec<&SectionBlock> = document
        .sections
        .iter()
        .filter(|section| !section.is_empty())
        .collect();

    let mut parts = vec![
        PREAMBLE.to_string(),
        String::new(),
        header(&document.full_name, document.personal_info.as_ref()),
        String::new(),
    ];
    for (index, section) in blocks.iter().enumerate() {
        parts.push(block(section, index == blocks.len() - 1));
        parts.push(String::new());
    }
    parts.push("\\end{document}".into());
    parts.push(String::new());
    parts.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = include_str!("../../../api/tests/fixtures/sample_document.json");
    const EXPECTED: &str = include_str!("../../../api/tests/fixtures/expected.tex");

    fn sample() -> ResumeDocument {
        serde_json::from_str(SAMPLE).expect("the fixture is a ResumeDocument")
    }

    #[test]
    fn reproduces_the_shared_golden_file() {
        let tex = serialize(&sample());
        if tex != EXPECTED {
            let line = tex
                .lines()
                .zip(EXPECTED.lines())
                .position(|(a, b)| a != b)
                .unwrap_or(0);
            panic!(
                "first difference on line {}:\n  got:      {:?}\n  expected: {:?}",
                line + 1,
                tex.lines().nth(line),
                EXPECTED.lines().nth(line)
            );
        }
    }

    #[test]
    fn a_name_alone_does_not_end_the_block_on_a_break() {
        let mut document = sample();
        document.personal_info = None;
        let tex = serialize(&document);
        assert!(tex.contains("    {\\Huge \\scshape Andrew Iammancini}\n\\end{center}"));
    }

    #[test]
    fn the_last_section_closes_no_gap() {
        let tex = serialize(&sample());
        let tail = tex.rsplit("\\section{Education}").next().unwrap();
        assert!(!tail.contains("\\vspace{-16pt}"));
    }

    #[test]
    fn an_empty_document_is_still_a_document() {
        let mut document = sample();
        document.sections.clear();
        document.full_name = String::new();
        document.personal_info = None;
        let tex = serialize(&document);
        assert!(tex.ends_with("\\begin{center}\n\\end{center}\n\n\\end{document}\n"));
    }
}
