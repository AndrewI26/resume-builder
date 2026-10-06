//! Resume Builder for the desktop: a native Iced window onto the same API the
//! hosted service runs, started here as a child process and kept to this
//! machine. See `sidecar` for how it starts and stops, `ui` for the window.

// a packaged Windows app should not open a console window behind itself
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod api;
mod bullets;
mod draft;
#[cfg(test)]
mod end_to_end;
mod export;
mod latex;
mod pdf;
mod settings;
mod sidecar;
mod ui;

fn main() -> iced::Result {
    // A signal ends a Rust program without running anything after `run`, so
    // a `kill`, a Ctrl-C in the terminal or a logout would otherwise leave
    // the API running with the database open. Stop it on the way out.
    let _ = ctrlc::set_handler(|| {
        sidecar::stop();
        std::process::exit(130);
    });

    let result = iced::application(ui::App::boot, ui::App::update, ui::App::view)
        .title(ui::App::title)
        .theme(ui::App::theme)
        .subscription(ui::App::subscription)
        .window(iced::window::Settings {
            size: iced::Size::new(1280.0, 860.0),
            min_size: Some(iced::Size::new(720.0, 600.0)),
            // closing goes through the app, so it can save and stop the API
            exit_on_close_request: false,
            ..iced::window::Settings::default()
        })
        .antialiasing(true)
        .run();

    // every way out ends here too: a surviving API holds the database open
    sidecar::stop();
    result
}
