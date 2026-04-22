use std::fmt::{Display, Formatter};

#[derive(Debug)]
pub struct AppError(pub String);

impl Display for AppError {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for AppError {}

impl From<anyhow::Error> for AppError {
    fn from(value: anyhow::Error) -> Self {
        Self(value.to_string())
    }
}

impl From<std::io::Error> for AppError {
    fn from(value: std::io::Error) -> Self {
        Self(value.to_string())
    }
}

impl From<serde_json::Error> for AppError {
    fn from(value: serde_json::Error) -> Self {
        Self(value.to_string())
    }
}

impl From<reqwest::Error> for AppError {
    fn from(value: reqwest::Error) -> Self {
        Self(value.to_string())
    }
}

impl From<zip::result::ZipError> for AppError {
    fn from(value: zip::result::ZipError) -> Self {
        Self(value.to_string())
    }
}

pub type AppResult<T> = Result<T, AppError>;

