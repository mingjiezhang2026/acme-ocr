use std::fs::{create_dir_all, OpenOptions};
use std::io::Write;
use std::path::Path;

pub fn append_log(log_file: &Path, message: &str) -> std::io::Result<()> {
    if let Some(parent) = log_file.parent() {
        create_dir_all(parent)?;
    }

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_file)?;

    writeln!(file, "{}", message)?;
    Ok(())
}

