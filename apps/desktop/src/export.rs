//! Exporting every resume as a PDF into a folder the person picked.
//!
//! The same folder `scripts/export_resumes.py` produces: the same names, from
//! the same titles, numbered the same way when two resumes share a title. The
//! folder's existing PDFs are deleted first, so what lands there is this
//! export and nothing else — which is why the screen warns with a count.
//!
//! In Electron these checks stood between a sandboxed page and the disk. The
//! window is no longer a web page that could be talked into anything, but a
//! wrong path here still deletes someone's files, so the rules stay: only
//! PDFs, only directly inside the chosen folder, only names with no path in.

use std::path::{Path, PathBuf};

/// A safe file stem for a title: one hyphen per non-alphanumeric character,
/// trimmed, lower-cased. Matches the API's download name and the script.
fn slug(title: &str) -> String {
    let stem: String = title
        .chars()
        .map(|character| {
            if character.is_alphanumeric() {
                character
            } else {
                '-'
            }
        })
        .collect();
    let stem = stem.trim_matches('-').to_lowercase();
    if stem.is_empty() {
        "resume".into()
    } else {
        stem
    }
}

/// The name a single resume downloads under.
pub fn filename(title: &str, extension: &str) -> String {
    format!("{}.{extension}", slug(title))
}

/// One `.pdf` name per title, in order, with collisions numbered from two.
pub fn filenames(titles: &[String]) -> Vec<String> {
    let mut seen = std::collections::HashMap::<String, usize>::new();
    titles
        .iter()
        .map(|title| {
            let stem = slug(title);
            let count = seen.entry(stem.clone()).or_insert(0);
            *count += 1;
            if *count == 1 {
                format!("{stem}.pdf")
            } else {
                format!("{stem}-{count}.pdf")
            }
        })
        .collect()
}

/// A name ending in `.pdf` with something in front of it and no path in it.
///
/// The length check excludes a file called plainly ".pdf", which Python reads
/// as a stem with no extension — so the script leaves it alone, and so does this.
pub fn is_pdf_name(name: &str) -> bool {
    name.len() > ".pdf".len()
        && !name.contains(['/', '\\'])
        && name.to_lowercase().ends_with(".pdf")
}

/// The PDFs an export into this folder would delete: files sitting directly
/// in it, never sub-folders and never anything that is not a PDF.
pub fn pdfs_in(directory: &Path) -> Vec<PathBuf> {
    let Ok(entries) = std::fs::read_dir(directory) else {
        return vec![];
    };

    let mut pdfs: Vec<PathBuf> = entries
        .filter_map(Result::ok)
        .filter(|entry| entry.file_type().is_ok_and(|kind| kind.is_file()))
        .filter(|entry| entry.file_name().to_str().is_some_and(is_pdf_name))
        .map(|entry| entry.path())
        .filter(|path| path.parent() == Some(directory))
        .collect();
    pdfs.sort();
    pdfs
}

/// Delete those PDFs. A file that vanished in the meantime is not an error.
pub fn clear(directory: &Path) -> std::io::Result<usize> {
    let mut deleted = 0;
    for path in pdfs_in(directory) {
        match std::fs::remove_file(&path) {
            Ok(()) => deleted += 1,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(error),
        }
    }
    Ok(deleted)
}

/// Write one PDF directly into the folder, refusing any name with a path in it.
pub fn write(directory: &Path, name: &str, contents: &[u8]) -> std::io::Result<()> {
    if !is_pdf_name(name) || Path::new(name).file_name().and_then(|n| n.to_str()) != Some(name) {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("refusing to write {name}"),
        ));
    }
    std::fs::write(directory.join(name), contents)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slugs_one_hyphen_per_character_like_the_script() {
        assert_eq!(filename("C++ / Rust", "pdf"), "c-----rust.pdf");
        assert_eq!(filename("Café Résumé", "pdf"), "café-résumé.pdf");
        assert_eq!(filename("!!!", "tex"), "resume.tex");
    }

    #[test]
    fn numbers_collisions_from_two() {
        let titles = vec![
            "Backend".to_string(),
            "backend".into(),
            "Frontend".into(),
            "Backend".into(),
        ];
        assert_eq!(
            filenames(&titles),
            vec![
                "backend.pdf",
                "backend-2.pdf",
                "frontend.pdf",
                "backend-3.pdf"
            ]
        );
    }

    #[test]
    fn judges_pdf_names() {
        assert!(is_pdf_name("a.pdf"));
        assert!(is_pdf_name("A.PDF"));
        assert!(!is_pdf_name(".pdf"));
        assert!(!is_pdf_name("notes.txt"));
        assert!(!is_pdf_name("../a.pdf"));
    }

    #[test]
    fn clears_only_pdfs_directly_in_the_folder() {
        let folder = tempfile::tempdir().unwrap();
        let root = folder.path();
        std::fs::write(root.join("old.pdf"), b"x").unwrap();
        std::fs::write(root.join("keep.txt"), b"x").unwrap();
        std::fs::create_dir(root.join("nested")).unwrap();
        std::fs::write(root.join("nested/inner.pdf"), b"x").unwrap();

        assert_eq!(pdfs_in(root).len(), 1);
        assert_eq!(clear(root).unwrap(), 1);
        assert!(root.join("keep.txt").exists());
        assert!(root.join("nested/inner.pdf").exists());
    }

    #[test]
    fn refuses_to_write_outside_the_folder() {
        let folder = tempfile::tempdir().unwrap();
        assert!(write(folder.path(), "../escape.pdf", b"x").is_err());
        assert!(write(folder.path(), "notes.txt", b"x").is_err());
        assert!(write(folder.path(), "fine.pdf", b"x").is_ok());
    }
}
