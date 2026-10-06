//! Drawing a compiled PDF into the window.
//!
//! The preview is the real file, rasterised — not an HTML likeness of it — so
//! what appears is what downloads. hayro is a pure-Rust rasteriser, which
//! keeps the app free of a native PDF library to ship per platform; pdfTeX
//! embeds every font it uses, so nothing has to be resolved from the system.

use hayro::hayro_interpret::InterpreterSettings;
use hayro::hayro_syntax::Pdf;
use hayro::vello_cpu::color::palette::css::WHITE;
use hayro::{PixmapSettings, RenderCache, RenderSettings, render};

/// Pixels per PDF point. Two keeps body text sharp on a Retina display
/// without the render taking long enough to notice.
const SCALE: f32 = 2.0;

/// One page as straight RGBA, ready to hand to an image widget.
#[derive(Debug, Clone)]
pub struct Page {
    pub width: u32,
    pub height: u32,
    pub pixels: Vec<u8>,
}

/// Rasterise every page. CPU-bound; run it off the UI thread.
pub fn rasterise(bytes: Vec<u8>) -> Result<Vec<Page>, String> {
    let pdf = Pdf::new(bytes).map_err(|error| format!("Could not read the PDF: {error:?}"))?;
    let cache = RenderCache::new();
    let interpreter = InterpreterSettings::default();
    let settings = RenderSettings::default();
    let pixmap = PixmapSettings {
        x_scale: SCALE,
        y_scale: SCALE,
        // opaque, so the premultiplied pixels are already straight RGBA
        bg_color: WHITE,
    };

    let pages = pdf
        .pages()
        .iter()
        .map(|page| {
            let rendered = render(page, &cache, &interpreter, &settings, &pixmap);
            Page {
                width: u32::from(rendered.width()),
                height: u32::from(rendered.height()),
                pixels: rendered.data_as_u8_slice().to_vec(),
            }
        })
        .collect::<Vec<_>>();

    if pages.is_empty() {
        Err("The PDF has no pages.".into())
    } else {
        Ok(pages)
    }
}
