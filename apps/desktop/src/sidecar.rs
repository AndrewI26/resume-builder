//! The API, running as a child of this app.
//!
//! The desktop app runs the same FastAPI the hosted service does, in local
//! mode: one SQLite file, nobody signed in, typesetting done in-process. It is
//! a separate process because it is Python, not because it is remote — it
//! listens on loopback and answers only this app.
//!
//! The port is picked at runtime, because another program may hold any
//! default we chose. The token exists because loopback is not private on a
//! shared machine: without it, any program running as this person could read
//! the whole library by asking a server that has no sign-in.

use std::collections::VecDeque;
use std::io::{BufRead, BufReader, Read};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};

const STARTUP_TIMEOUT: Duration = Duration::from_secs(30);
const POLL_INTERVAL: Duration = Duration::from_millis(200);
/// The tail of the sidecar's output kept for an error message, in lines.
const KEPT_LINES: usize = 60;

/// Where a running sidecar answers, and the secret it expects.
#[derive(Debug, Clone)]
pub struct Endpoint {
    pub base_url: String,
    pub token: String,
}

/// The one child process, held where every way out of the app can reach it.
///
/// A surviving child is the worst failure here: it keeps the SQLite file open
/// and holds a port, so the next launch finds a database another process is
/// writing to. So it lives in a static that both the window-close path and
/// the end of `main` stop, rather than only in state that might not drop.
static CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

fn slot() -> &'static Mutex<Option<Child>> {
    CHILD.get_or_init(|| Mutex::new(None))
}

/// The folder the database lives in: the same one the Electron app used, so
/// an existing library opens in the new app untouched.
///
/// `RESUME_BUILDER_DATA_DIR` points it somewhere else, so a development run
/// can use a scratch library instead of the one this machine actually keeps.
pub fn data_dir() -> PathBuf {
    if let Some(dir) = std::env::var_os("RESUME_BUILDER_DATA_DIR") {
        return PathBuf::from(dir);
    }
    dirs::data_dir()
        .unwrap_or_else(std::env::temp_dir)
        .join("Resume Builder")
}

/// Where the packaged app keeps its bundled resources, if this is one.
///
/// macOS puts them in `Contents/Resources` beside `Contents/MacOS`; the
/// Windows installer puts them next to the executable.
fn resources_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    [
        dir.join("../Resources"),
        dir.to_path_buf(),
        dir.join("resources"),
    ]
    .into_iter()
    .find(|candidate| candidate.join("api").is_dir())
}

fn bundled_api() -> Option<PathBuf> {
    let name = if cfg!(windows) {
        "resume-api.exe"
    } else {
        "resume-api"
    };
    let path = resources_dir()?.join("api").join(name);
    path.is_file().then_some(path)
}

/// The bundled TeX distribution's binaries, under a platform-named folder.
///
/// Read rather than assumed: TeX finds its own files by walking up from the
/// running binary, so it cannot be flattened to a fixed path.
fn texlive_bin() -> Option<PathBuf> {
    let root = resources_dir()?.join("texlive").join("bin");
    std::fs::read_dir(&root)
        .ok()?
        .filter_map(Result::ok)
        .find(|entry| entry.file_type().is_ok_and(|kind| kind.is_dir()))
        .map(|entry| entry.path())
}

/// How to start the API: the PyInstaller binary in a packaged app, and the
/// real source tree under `uv` in a checkout — so an edit to a router shows
/// up without rebuilding anything.
fn command(port: u16) -> Command {
    let port = port.to_string();

    if let Some(binary) = bundled_api() {
        let mut command = Command::new(binary);
        command.args(["--port", &port]);
        return command;
    }

    let api = Path::new(env!("CARGO_MANIFEST_DIR")).join("../api");
    let mut command = Command::new("uv");
    command
        .args([
            "run",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            &port,
        ])
        .current_dir(api);
    command
}

/// A port the operating system says is free. Racy in principle, but only by
/// the milliseconds between this closing and the sidecar binding.
fn free_port() -> std::io::Result<u16> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
}

fn new_token() -> String {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("the OS has a source of randomness");
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

/// Copy a stream to our own stderr, keeping its tail for error messages.
fn forward(stream: impl Read + Send + 'static, log: Arc<Mutex<VecDeque<String>>>) {
    std::thread::spawn(move || {
        for line in BufReader::new(stream).lines().map_while(Result::ok) {
            eprintln!("[api] {line}");
            let mut log = log.lock().unwrap();
            if log.len() == KEPT_LINES {
                log.pop_front();
            }
            log.push_back(line);
        }
    });
}

fn answering(base_url: &str, token: &str) -> bool {
    // a blocking probe on purpose: this runs on its own thread during startup
    let url = format!("{base_url}/openapi.json");
    let Ok(runtime) = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
    else {
        return false;
    };
    runtime.block_on(async {
        reqwest::Client::new()
            .get(url)
            .header("x-sidecar-token", token)
            .timeout(Duration::from_secs(2))
            .send()
            .await
            .is_ok_and(|response| response.status().is_success())
    })
}

/// Start the API and wait until it answers. Blocking; run it off the UI thread.
pub fn start() -> Result<Endpoint, String> {
    let port = free_port().map_err(|error| format!("Could not find a free port: {error}"))?;
    let token = new_token();
    let base_url = format!("http://127.0.0.1:{port}");
    let data = data_dir();
    std::fs::create_dir_all(&data)
        .map_err(|error| format!("Could not create {}: {error}", data.display()))?;

    let mut command = command(port);
    command
        .env("MODE", "local")
        .env("LOCAL_DATA_DIR", &data)
        .env("SIDECAR_TOKEN", &token)
        // Python block-buffers a piped stdout, which would hold back exactly
        // the lines an error message needs
        .env("PYTHONUNBUFFERED", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(bin) = texlive_bin() {
        command.env("TEXLIVE_BIN", bin);
    }

    let program = command.get_program().to_string_lossy().into_owned();
    let mut child = command
        .spawn()
        .map_err(|error| format!("Could not start {program}: {error}"))?;

    let log = Arc::new(Mutex::new(VecDeque::new()));
    if let Some(stdout) = child.stdout.take() {
        forward(stdout, log.clone());
    }
    if let Some(stderr) = child.stderr.take() {
        forward(stderr, log.clone());
    }

    *slot().lock().unwrap() = Some(child);

    let failure = |reason: String| {
        stop();
        let tail: Vec<String> = log.lock().unwrap().iter().cloned().collect();
        if tail.is_empty() {
            reason
        } else {
            format!("{reason}\n\n{}", tail.join("\n"))
        }
    };

    let deadline = Instant::now() + STARTUP_TIMEOUT;
    while Instant::now() < deadline {
        let exited = slot()
            .lock()
            .unwrap()
            .as_mut()
            .and_then(|child| child.try_wait().ok().flatten());
        if let Some(status) = exited {
            return Err(failure(format!(
                "The app's server exited during startup ({status})."
            )));
        }

        if answering(&base_url, &token) {
            return Ok(Endpoint { base_url, token });
        }

        std::thread::sleep(POLL_INTERVAL);
    }

    Err(failure("The app's server did not start in time.".into()))
}

/// Stop the API, and be sure about it.
///
/// SIGTERM first, so the server closes the database properly, with a hard
/// kill behind it for a process that has stopped listening. Windows does not
/// end a process tree with its parent, hence taskkill with /T.
pub fn stop() {
    let Some(mut child) = slot().lock().unwrap().take() else {
        return;
    };
    if child.try_wait().ok().flatten().is_some() {
        return;
    }

    if cfg!(windows) {
        let _ = Command::new("taskkill")
            .args(["/pid", &child.id().to_string(), "/T", "/F"])
            .status();
    } else {
        let _ = Command::new("kill")
            .args(["-TERM", &child.id().to_string()])
            .status();
        let deadline = Instant::now() + Duration::from_secs(3);
        while Instant::now() < deadline {
            if child.try_wait().ok().flatten().is_some() {
                return;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }

    let _ = child.kill();
    let _ = child.wait();
}
