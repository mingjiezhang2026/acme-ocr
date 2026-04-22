use std::process::Child;
use std::sync::Mutex;

#[derive(Default)]
pub struct AppRuntimeState {
    pub worker: Mutex<Option<Child>>,
}

