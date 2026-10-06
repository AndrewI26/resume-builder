//! Talking to the sidecar.
//!
//! The same FastAPI the hosted service runs, in local mode: nobody signs in,
//! and every request instead carries the token the sidecar was started with,
//! which is what keeps other programs on this machine out of the library.

pub mod models;

use models::*;
use reqwest::{Method, StatusCode};
use serde::Serialize;
use serde::de::DeserializeOwned;
use std::sync::Arc;

/// What the API said went wrong, ready to show to a person.
#[derive(Debug, Clone, PartialEq)]
pub struct ApiError(pub String);

impl std::fmt::Display for ApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

pub type ApiResult<T> = Result<T, ApiError>;

/// Pulls a readable message out of a FastAPI error body.
///
/// `detail` is a string for errors the routers raise and a list of
/// `{msg, ...}` for validation failures; anything else falls back to the
/// status, so a failure never reads as silence.
pub fn error_message(status: StatusCode, body: &str) -> String {
    let detail = serde_json::from_str::<serde_json::Value>(body)
        .ok()
        .and_then(|value| value.get("detail").cloned());

    match detail {
        Some(serde_json::Value::String(detail)) if !detail.is_empty() => detail,
        Some(serde_json::Value::Array(items)) if !items.is_empty() => items
            .iter()
            .filter_map(|item| item.get("msg").and_then(|msg| msg.as_str()))
            .collect::<Vec<_>>()
            .join(" "),
        _ => format!("The server answered {}", status.as_u16()),
    }
}

/// A cheap handle to the sidecar; clone it into every task that needs one.
#[derive(Debug, Clone)]
pub struct Client {
    inner: Arc<Inner>,
}

#[derive(Debug)]
struct Inner {
    http: reqwest::Client,
    base_url: String,
    token: String,
}

impl Client {
    pub fn new(base_url: String, token: String) -> Self {
        Self {
            inner: Arc::new(Inner {
                http: reqwest::Client::new(),
                base_url,
                token,
            }),
        }
    }

    fn request(&self, method: Method, path: &str) -> reqwest::RequestBuilder {
        self.inner
            .http
            .request(method, format!("{}{}", self.inner.base_url, path))
            .header("x-sidecar-token", &self.inner.token)
    }

    async fn send(&self, request: reqwest::RequestBuilder) -> ApiResult<reqwest::Response> {
        let response = request
            .send()
            .await
            .map_err(|error| ApiError(format!("Could not reach the app's server: {error}")))?;

        if response.status().is_success() {
            return Ok(response);
        }

        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        Err(ApiError(error_message(status, &body)))
    }

    async fn json<T: DeserializeOwned>(&self, request: reqwest::RequestBuilder) -> ApiResult<T> {
        self.send(request)
            .await?
            .json::<T>()
            .await
            .map_err(|error| ApiError(format!("The server sent something unexpected: {error}")))
    }

    async fn get<T: DeserializeOwned>(&self, path: &str) -> ApiResult<T> {
        self.json(self.request(Method::GET, path)).await
    }

    async fn with_body<B: Serialize, T: DeserializeOwned>(
        &self,
        method: Method,
        path: &str,
        body: &B,
    ) -> ApiResult<T> {
        self.json(self.request(method, path).json(body)).await
    }

    async fn delete(&self, path: &str) -> ApiResult<()> {
        self.send(self.request(Method::DELETE, path))
            .await
            .map(|_| ())
    }

    // -- the library ---------------------------------------------------------

    pub async fn education(&self) -> ApiResult<Vec<Education>> {
        self.get("/education/").await
    }

    pub async fn experience(&self) -> ApiResult<Vec<Experience>> {
        self.get("/experience/").await
    }

    pub async fn projects(&self) -> ApiResult<Vec<Project>> {
        self.get("/project/").await
    }

    pub async fn skills(&self) -> ApiResult<Vec<Skill>> {
        self.get("/skill/").await
    }

    pub async fn personal_info(&self) -> ApiResult<Vec<PersonalInfo>> {
        self.get("/personal-info/").await
    }

    pub async fn save_education(&self, id: Option<&str>, body: &EducationInput) -> ApiResult<()> {
        self.save("/education/", id, body).await
    }

    pub async fn save_experience(&self, id: Option<&str>, body: &ExperienceInput) -> ApiResult<()> {
        self.save("/experience/", id, body).await
    }

    pub async fn save_project(&self, id: Option<&str>, body: &ProjectInput) -> ApiResult<()> {
        self.save("/project/", id, body).await
    }

    pub async fn save_skill(&self, id: Option<&str>, body: &SkillInput) -> ApiResult<()> {
        self.save("/skill/", id, body).await
    }

    pub async fn save_personal_info(
        &self,
        id: Option<&str>,
        body: &PersonalInfoInput,
    ) -> ApiResult<()> {
        self.save("/personal-info/", id, body).await
    }

    /// Create when there is no id yet, replace when there is.
    async fn save<B: Serialize>(
        &self,
        collection: &str,
        id: Option<&str>,
        body: &B,
    ) -> ApiResult<()> {
        let request = match id {
            None => self.request(Method::POST, collection),
            Some(id) => self.request(Method::PUT, &format!("{collection}{id}")),
        };
        self.send(request.json(body)).await.map(|_| ())
    }

    /// Delete one library row. `collection` is its path, e.g. `/skill/`.
    pub async fn delete_row(&self, collection: &str, id: &str) -> ApiResult<()> {
        self.delete(&format!("{collection}{id}")).await
    }

    // -- resumes -------------------------------------------------------------

    pub async fn resumes(&self) -> ApiResult<Vec<Resume>> {
        self.get("/resumes/").await
    }

    pub async fn resume(&self, id: &str) -> ApiResult<Resume> {
        self.get(&format!("/resumes/{id}")).await
    }

    pub async fn resume_sections(&self, id: &str) -> ApiResult<ResumeSections> {
        self.get(&format!("/resumes/{id}/sections")).await
    }

    pub async fn create_resume(&self, body: &ResumeCreate) -> ApiResult<Resume> {
        self.with_body(Method::POST, "/resumes/", body).await
    }

    pub async fn update_resume(&self, id: &str, body: &ResumeEdit) -> ApiResult<Resume> {
        self.with_body(Method::PUT, &format!("/resumes/{id}"), body)
            .await
    }

    pub async fn replace_sections(&self, id: &str, body: &ResumeSections) -> ApiResult<()> {
        let _: ResumeSections = self
            .with_body(Method::PUT, &format!("/resumes/{id}/sections"), body)
            .await?;
        Ok(())
    }

    pub async fn delete_resume(&self, id: &str) -> ApiResult<()> {
        self.delete(&format!("/resumes/{id}")).await
    }

    /// Typeset a resume from its saved rows and hand back the PDF.
    pub async fn compile_pdf(&self, id: &str) -> ApiResult<Vec<u8>> {
        let response = self
            .send(self.request(Method::POST, &format!("/resumes/{id}/pdf")))
            .await?;
        response
            .bytes()
            .await
            .map(|bytes| bytes.to_vec())
            .map_err(|error| ApiError(format!("The PDF did not arrive: {error}")))
    }

    /// Copy the database into a dated file in the app's own folder.
    pub async fn back_up(&self) -> ApiResult<Backup> {
        self.json(self.request(Method::POST, "/backup/")).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_string_detail_is_shown_as_it_is() {
        let message = error_message(StatusCode::NOT_FOUND, r#"{"detail":"No such skill"}"#);
        assert_eq!(message, "No such skill");
    }

    #[test]
    fn validation_details_are_joined() {
        let body = r#"{"detail":[{"msg":"Field required"},{"msg":"Too long"}]}"#;
        assert_eq!(
            error_message(StatusCode::UNPROCESSABLE_ENTITY, body),
            "Field required Too long"
        );
    }

    #[test]
    fn an_unreadable_body_falls_back_to_the_status() {
        assert_eq!(
            error_message(StatusCode::BAD_GATEWAY, "<html>"),
            "The server answered 502"
        );
    }
}
