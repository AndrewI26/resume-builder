//! The editable state of a resume, and every change the editor can make to it.
//!
//! A port of `apps/web/app/lib/resume/document.ts`. Two orderings live here
//! and they are not the same thing: `order` is which headings print and in
//! what order, and `sections` is which rows are attached — where only the
//! order *within* one type means anything to the API.

use crate::api::models::{
    Education, Experience, PersonalInfo, Project, ResumeDocument, SectionBlock, SectionRef,
    SectionType, Skill,
};

/// Everything the user could attach, by type.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Catalogs {
    pub education: Vec<Education>,
    pub experience: Vec<Experience>,
    pub project: Vec<Project>,
    pub skill: Vec<Skill>,
}

impl Catalogs {
    /// Every row of a type, as (id, one-line description) for pickers.
    pub fn choices(&self, kind: SectionType) -> Vec<(String, String)> {
        match kind {
            SectionType::Education => self
                .education
                .iter()
                .map(|row| (row.id.clone(), row.name.clone()))
                .collect(),
            SectionType::Experience => self
                .experience
                .iter()
                .map(|row| {
                    (
                        row.id.clone(),
                        format!("{} at {}", row.position, row.company),
                    )
                })
                .collect(),
            SectionType::Project => self
                .project
                .iter()
                .map(|row| (row.id.clone(), row.name.clone()))
                .collect(),
            SectionType::Skill => self
                .skill
                .iter()
                .map(|row| (row.id.clone(), row.name.clone()))
                .collect(),
        }
    }

    /// The description of one row, or `None` if it has been deleted.
    pub fn describe(&self, reference: &SectionRef) -> Option<String> {
        self.choices(reference.section_type)
            .into_iter()
            .find(|(id, _)| *id == reference.section_id)
            .map(|(_, label)| label)
    }

    fn block(&self, kind: SectionType, ids: &[String]) -> SectionBlock {
        // a row deleted from under the resume leaves a stale ref; drop it
        fn pick<T: Clone>(rows: &[T], ids: &[String], id_of: fn(&T) -> &str) -> Vec<T> {
            ids.iter()
                .filter_map(|id| rows.iter().find(|row| id_of(row) == id).cloned())
                .collect()
        }

        match kind {
            SectionType::Education => {
                SectionBlock::Education(pick(&self.education, ids, |row| &row.id))
            }
            SectionType::Experience => {
                SectionBlock::Experience(pick(&self.experience, ids, |row| &row.id))
            }
            SectionType::Project => SectionBlock::Project(pick(&self.project, ids, |row| &row.id)),
            SectionType::Skill => SectionBlock::Skill(pick(&self.skill, ids, |row| &row.id)),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Draft {
    pub order: Vec<SectionType>,
    pub sections: Vec<SectionRef>,
    pub full_name: String,
    pub personal_info_id: Option<String>,
}

/// Move the item at `from` so it lands at `to`; out of range is a no-op.
pub fn move_item<T: Clone>(items: &[T], from: usize, to: usize) -> Vec<T> {
    if to >= items.len() || from >= items.len() || from == to {
        return items.to_vec();
    }
    let mut next = items.to_vec();
    let moved = next.remove(from);
    next.insert(to, moved);
    next
}

impl Draft {
    /// The attached refs of one type, in the order the draft lists them.
    pub fn refs_of(&self, kind: SectionType) -> Vec<SectionRef> {
        self.sections
            .iter()
            .filter(|reference| reference.section_type == kind)
            .cloned()
            .collect()
    }

    /// Give one type's refs a new order, leaving every other type untouched.
    fn set_type_order(&mut self, kind: SectionType, ordered: Vec<SectionRef>) {
        let mut next = ordered.into_iter();
        for reference in self.sections.iter_mut() {
            if reference.section_type == kind
                && let Some(replacement) = next.next()
            {
                *reference = replacement;
            }
        }
    }

    pub fn move_heading(&mut self, from: usize, to: usize) {
        self.order = move_item(&self.order, from, to);
    }

    pub fn move_within(&mut self, kind: SectionType, from: usize, to: usize) {
        let moved = move_item(&self.refs_of(kind), from, to);
        self.set_type_order(kind, moved);
    }

    /// Attach a row after the others of its type, giving its type a heading
    /// at the end if it had none — a row with no heading would print nowhere.
    pub fn attach(&mut self, reference: SectionRef) {
        if self.sections.contains(&reference) {
            return;
        }
        if !self.order.contains(&reference.section_type) {
            self.order.push(reference.section_type);
        }
        self.sections.push(reference);
    }

    /// Detach a row, leaving its heading for whatever else is there.
    pub fn detach(&mut self, reference: &SectionRef) {
        self.sections.retain(|existing| existing != reference);
    }

    /// Swap one attached row for another of the same type, in place.
    pub fn swap(&mut self, reference: &SectionRef, next_id: String) {
        if let Some(existing) = self
            .sections
            .iter_mut()
            .find(|existing| *existing == reference)
        {
            existing.section_id = next_id;
        }
    }

    /// A value that changes exactly when the printed resume would.
    ///
    /// It answers two questions that look alike: whether there are unsaved
    /// edits, and whether a compiled PDF still matches the panel.
    pub fn signature(&self) -> String {
        let order: Vec<&str> = self.order.iter().map(|kind| kind_name(*kind)).collect();
        let sections: Vec<String> = self
            .sections
            .iter()
            .map(|reference| {
                format!(
                    "{}:{}",
                    kind_name(reference.section_type),
                    reference.section_id
                )
            })
            .collect();
        format!(
            "{}|{}|{}|{}",
            order.join(","),
            sections.join(","),
            self.full_name,
            self.personal_info_id.as_deref().unwrap_or("")
        )
    }

    /// The document the `.tex` export renders, assembled without a round trip.
    pub fn document(
        &self,
        id: &str,
        title: &str,
        template: &str,
        catalogs: &Catalogs,
        personal_info: &[PersonalInfo],
    ) -> ResumeDocument {
        let sections = self
            .order
            .iter()
            .map(|&kind| {
                let ids: Vec<String> = self
                    .refs_of(kind)
                    .into_iter()
                    .map(|reference| reference.section_id)
                    .collect();
                catalogs.block(kind, &ids)
            })
            .filter(|section| !section.is_empty())
            .collect();

        ResumeDocument {
            id: id.into(),
            title: title.into(),
            template: template.into(),
            full_name: self.full_name.clone(),
            personal_info: personal_info
                .iter()
                .find(|info| Some(&info.id) == self.personal_info_id.as_ref())
                .cloned(),
            sections,
        }
    }
}

fn kind_name(kind: SectionType) -> &'static str {
    match kind {
        SectionType::Education => "education",
        SectionType::Experience => "experience",
        SectionType::Project => "project",
        SectionType::Skill => "skill",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn reference(kind: SectionType, id: &str) -> SectionRef {
        SectionRef {
            section_type: kind,
            section_id: id.into(),
        }
    }

    fn draft() -> Draft {
        Draft {
            order: vec![SectionType::Experience, SectionType::Skill],
            sections: vec![
                reference(SectionType::Experience, "e1"),
                reference(SectionType::Skill, "s1"),
                reference(SectionType::Experience, "e2"),
            ],
            full_name: "Casey".into(),
            personal_info_id: None,
        }
    }

    #[test]
    fn moving_within_a_type_leaves_other_types_in_place() {
        let mut next = draft();
        next.move_within(SectionType::Experience, 0, 1);
        assert_eq!(
            next.sections,
            vec![
                reference(SectionType::Experience, "e2"),
                reference(SectionType::Skill, "s1"),
                reference(SectionType::Experience, "e1"),
            ]
        );
    }

    #[test]
    fn attaching_a_new_type_gives_it_a_heading() {
        let mut next = draft();
        next.attach(reference(SectionType::Education, "ed1"));
        assert_eq!(next.order.last(), Some(&SectionType::Education));
        next.attach(reference(SectionType::Education, "ed1"));
        assert_eq!(next.refs_of(SectionType::Education).len(), 1);
    }

    #[test]
    fn detaching_keeps_the_heading() {
        let mut next = draft();
        next.detach(&reference(SectionType::Skill, "s1"));
        assert!(next.order.contains(&SectionType::Skill));
        assert!(next.refs_of(SectionType::Skill).is_empty());
    }

    #[test]
    fn swapping_keeps_the_place() {
        let mut next = draft();
        next.swap(&reference(SectionType::Experience, "e1"), "e3".into());
        assert_eq!(next.sections[0], reference(SectionType::Experience, "e3"));
    }

    #[test]
    fn the_signature_follows_order_and_header() {
        let base = draft();
        let mut moved = base.clone();
        moved.move_heading(0, 1);
        assert_ne!(base.signature(), moved.signature());

        let mut renamed = base.clone();
        renamed.full_name = "Casey Quinn".into();
        assert_ne!(base.signature(), renamed.signature());
    }

    #[test]
    fn the_document_drops_empty_blocks_and_deleted_rows() {
        let catalogs = Catalogs {
            skill: vec![Skill {
                id: "s1".into(),
                name: "Languages".into(),
                items: vec!["Rust".into()],
                position: 0,
            }],
            ..Catalogs::default()
        };
        let document = draft().document("r", "Title", "jakes", &catalogs, &[]);
        // e1 and e2 are not in the catalog, so experience has nothing to print
        assert_eq!(document.sections.len(), 1);
        assert!(matches!(document.sections[0], SectionBlock::Skill(_)));
    }

    #[test]
    fn move_item_ignores_out_of_range() {
        assert_eq!(move_item(&[1, 2, 3], 0, 3), vec![1, 2, 3]);
        assert_eq!(move_item(&[1, 2, 3], 2, 0), vec![3, 1, 2]);
    }
}
