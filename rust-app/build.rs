use std::{env, fs, path::PathBuf, process::Command};

fn main() {
    println!("cargo:rerun-if-changed=app.rc");
    println!("cargo:rerun-if-changed=app.ico");
    if env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("windows")
        || env::var("CARGO_CFG_TARGET_ENV").as_deref() != Ok("msvc")
    {
        return;
    }

    println!("cargo:rerun-if-env-changed=WindowsSdkDir");
    let resource = PathBuf::from(env::var_os("OUT_DIR").unwrap()).join("app.res");
    let status = Command::new(resource_compiler())
        .arg("/nologo")
        .arg("/fo")
        .arg(&resource)
        .arg("app.rc")
        .status()
        .expect("Could not launch the Windows SDK resource compiler (rc.exe)");
    assert!(status.success(), "Could not compile the Windows app icon");
    println!(
        "cargo:rustc-link-arg-bin=thz-analyzer-rust={}",
        resource.display()
    );
}

fn resource_compiler() -> PathBuf {
    let on_path = env::var_os("PATH").into_iter().flat_map(|p| {
        env::split_paths(&p)
            .map(|dir| dir.join("rc.exe"))
            .collect::<Vec<_>>()
    });
    let sdk_roots = env::var_os("WindowsSdkDir")
        .map(PathBuf::from)
        .into_iter()
        .chain(
            env::var_os("ProgramFiles(x86)")
                .map(|base| PathBuf::from(base).join("Windows Kits").join("10")),
        );
    on_path
        .chain(sdk_roots.flat_map(|sdk| {
            let mut versions: Vec<_> = fs::read_dir(sdk.join("bin"))
                .into_iter()
                .flatten()
                .filter_map(Result::ok)
                .map(|entry| entry.path())
                .collect();
            versions.sort_unstable();
            versions.into_iter().rev().map(|dir| dir.join("x64").join("rc.exe"))
        }))
        .find(|path| path.is_file())
        .expect("Windows SDK rc.exe not found; install the Windows SDK or build in a Visual Studio Developer Command Prompt")
}
