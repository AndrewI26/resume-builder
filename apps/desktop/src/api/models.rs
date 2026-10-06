//! The API's request and response shapes, mirrored from `apps/api/schemas`.
//!
//! Written out by hand rather than generated: there is no OpenAPI generator
//! for Rust that this project trusts, and the shapes are small and stable.
//! When a schema changes, the field here has to change with it — serde will
//! refuse a response that no longer fits, which is where a drift shows up.

use serde::{Deserialize, Serialize};

/// The four kinds of row a resume can list under a heading.
///
/// Personal info is deliberately absent: it prints as the header, not as a
/// section, and is attached through `personal_info_id` instead.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SectionType {
    Education,
    Experience,
    Project,
    Skill,
}

impl SectionType {
    pub const ALL: [SectionType; 4] = [
        SectionType::Education,
        SectionType::Experience,
        SectionType::Project,
        SectionType::Skill,
    ];

    /// The heading the resume prints, and the editor shows.
    pub fn title(self) -> &'static str {
        match self {
            SectionType::Education => "Education",
            SectionType::Experience => "Experience",
            SectionType::Project => "Projects",
            SectionType::Skill => "Skills",
        }
    }
}

/// A line of resume text plus the runs of it that render bold.
///
/// Each range in `bolded` is a pair of **inclusive** character indices into
/// `text` — characters, not bytes, because that is what Python counts.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BulletPoint {
    pub text: String,
    pub bolded: Vec<(usize, usize)>,
}

/// A URL paired with the text a resume shows in its place.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Link {
    pub url: String,
    #[serde(default)]
    pub label: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Education {
    pub id: String,
    pub name: String,
    pub subheading: String,
    pub duration: String,
    pub location: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct EducationInput {
    pub name: String,
    pub subheading: String,
    pub duration: String,
    pub location: String,
}

/// "Expirence" is the API's spelling, kept on the wire and not repeated here.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Experience {
    pub id: String,
    pub company: String,
    pub position: String,
    pub duration: String,
    pub location: String,
    pub bullet_points: Vec<BulletPoint>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExperienceInput {
    pub company: String,
    pub position: String,
    pub duration: String,
    pub location: String,
    pub bullet_points: Vec<BulletPoint>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Project {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub link: Option<String>,
    pub technologies: Vec<String>,
    pub bullet_points: Vec<BulletPoint>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProjectInput {
    pub name: String,
    pub link: Option<String>,
    pub technologies: Vec<String>,
    pub bullet_points: Vec<BulletPoint>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Skill {
    pub id: String,
    pub name: String,
    pub items: Vec<String>,
    pub position: i64,
}

/// A create appends after the existing skills; a replace has to say where.
#[derive(Debug, Clone, Serialize)]
pub struct SkillInput {
    pub name: String,
    pub items: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub position: Option<i64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PersonalInfo {
    pub id: String,
    #[serde(default)]
    pub email: Option<String>,
    #[serde(default)]
    pub phone_number: Option<String>,
    #[serde(default)]
    pub address: Option<String>,
    #[serde(default)]
    pub github: Option<Link>,
    #[serde(default)]
    pub linkedin: Option<Link>,
    #[serde(default)]
    pub portfolio: Option<Link>,
}

impl PersonalInfo {
    /// A one-line stand-in for a set of contact details, which has no name.
    pub fn describe(&self) -> String {
        self.email
            .clone()
            .or_else(|| self.phone_number.clone())
            .or_else(|| self.address.clone())
            .or_else(|| self.github.as_ref().and_then(|link| link.label.clone()))
            .or_else(|| self.github.as_ref().map(|link| link.url.clone()))
            .unwrap_or_else(|| "Contact details".to_string())
    }
}

/// Every field is optional: on a replace, an omitted field is cleared.
#[derive(Debug, Clone, Serialize)]
pub struct PersonalInfoInput {
    pub email: Option<String>,
    pub phone_number: Option<String>,
    pub address: Option<String>,
    pub github: Option<Link>,
    pub linkedin: Option<Link>,
    pub portfolio: Option<Link>,
}

/// A pointer to one of the library's rows, by type and id.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct SectionRef {
    pub section_type: SectionType,
    pub section_id: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Resume {
    pub id: String,
    pub title: String,
    pub template: String,
    #[serde(default)]
    pub full_name: Option<String>,
    #[serde(default)]
    pub personal_info_id: Option<String>,
    pub section_order: Vec<SectionType>,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ResumeCreate {
    pub title: String,
    pub template: String,
    pub full_name: Option<String>,
    pub personal_info_id: Option<String>,
    pub sections: Vec<SectionRef>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ResumeEdit {
    pub title: String,
    pub template: String,
    pub full_name: Option<String>,
    pub personal_info_id: Option<String>,
    pub section_order: Vec<SectionType>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ResumeSections {
    pub sections: Vec<SectionRef>,
}

/// One heading's rows, resolved and in print order.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", content = "items", rename_all = "lowercase")]
pub enum SectionBlock {
    Education(Vec<Education>),
    Experience(Vec<Experience>),
    Project(Vec<Project>),
    Skill(Vec<Skill>),
}

impl SectionBlock {
    pub fn is_empty(&self) -> bool {
        match self {
            SectionBlock::Education(items) => items.is_empty(),
            SectionBlock::Experience(items) => items.is_empty(),
            SectionBlock::Project(items) => items.is_empty(),
            SectionBlock::Skill(items) => items.is_empty(),
        }
    }
}

/// Everything a renderer needs, in the shape `GET /resumes/{id}/document`
/// returns — and the shape the editor assembles from its draft.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ResumeDocument {
    pub id: String,
    pub title: String,
    pub template: String,
    pub full_name: String,
    #[serde(default)]
    pub personal_info: Option<PersonalInfo>,
    pub sections: Vec<SectionBlock>,
}

/// A snapshot of the database that now exists on disk.
#[derive(Debug, Clone, Deserialize)]
pub struct Backup {
    pub path: String,
}
