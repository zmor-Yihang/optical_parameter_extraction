use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

use calamine::{Data, Reader, Xlsx, open_workbook};
use rust_xlsxwriter::Workbook;
use thz_analyzer_rust::analysis::{Analysis, SampleResult};
use thz_analyzer_rust::data::{ExportKind, export_xlsx, load_signals};

struct Scratch(PathBuf);

impl Scratch {
    fn new() -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let parent = std::env::temp_dir();
        loop {
            let next = NEXT.fetch_add(1, Ordering::Relaxed);
            let path = parent.join(format!(
                "thz-data-format-test-{}-{next}",
                std::process::id()
            ));
            match fs::create_dir(&path) {
                Ok(()) => return Self(path),
                Err(err) if err.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(err) => panic!("cannot create test directory: {err}"),
            }
        }
    }

    fn join(&self, name: &str) -> PathBuf {
        self.0.join(name)
    }

    fn write(&self, name: &str, bytes: impl AsRef<[u8]>) -> PathBuf {
        let path = self.join(name);
        fs::write(&path, bytes).unwrap();
        path
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn standard_txt_uses_metadata_name_and_keeps_pairs_aligned() {
    let scratch = Scratch::new();
    let text = "\u{feff}\r\n# THz-STD-1.0\r\n# name: 样品A\r\n# Time[ps]\tAmplitude\r\n0\t10\r\n1\tabc\r\n2\t20\r\n3\tNaN\r\n";
    let path = scratch.write("example.txt", text);
    let signals = load_signals(&path).unwrap();
    assert_eq!(signals.len(), 1);
    assert_eq!(signals[0].name, "样品A");
    assert_eq!(signals[0].signal.time, vec![0., 2.]);
    assert_eq!(signals[0].signal.amplitude, vec![10., 20.]);
}

#[test]
fn delimited_import_detects_table_and_does_not_shift_empty_columns() {
    let scratch = Scratch::new();
    let path = scratch.write(
        "试样.csv",
        "序号,数据点\r\n1,5\r\n时间,振幅\r\n0,3\r\n0.1,4\r\n0.2,5\r\n0.3,6\r\n0.4,7\r\n0.5,,8\r\n0.6,9\r\n\t9\t10\r\n",
    );
    let signals = load_signals(&path).unwrap();
    assert_eq!(signals[0].name, "试样");
    assert_eq!(signals[0].signal.time, vec![0., 0.1, 0.2, 0.3, 0.4, 0.6]);
    assert_eq!(signals[0].signal.amplitude, vec![3., 4., 5., 6., 7., 9.]);
}

#[test]
fn utf16_and_gb18030_text_are_accepted() {
    let scratch = Scratch::new();
    let text = "# THz-STD-1.0\r# name: 样品\r0.0 10\r0.2 11\r";
    let utf16 = [0xff, 0xfe]
        .into_iter()
        .chain(text.encode_utf16().flat_map(u16::to_le_bytes))
        .collect::<Vec<_>>();
    let (legacy, _, errors) = encoding_rs::GB18030.encode(text);
    assert!(!errors);
    for (name, bytes) in [
        ("utf16.dat", utf16.as_slice()),
        ("legacy.asc", legacy.as_ref()),
    ] {
        let signals = load_signals(&scratch.write(name, bytes)).unwrap();
        assert_eq!(signals[0].name, "样品");
        assert_eq!(signals[0].signal.time, vec![0., 0.2]);
        assert_eq!(signals[0].signal.amplitude, vec![10., 11.]);
    }
}

#[test]
fn bt_fts_splits_scans_and_rejects_missing_delay_or_amplitude() {
    let scratch = Scratch::new();
    let path = scratch.write(
        "BT.txt",
        "Instrument\tBT-FTS\n\nSCAN\tx0[um]\tdx [um]\tTD Values -->\n0\t-299.792458\t149.896229\t2\t3\t5\n1\t0\t299.792458\t4\t6\t8\n",
    );
    let scans = load_signals(&path).unwrap();
    assert_eq!(scans.len(), 2);
    assert_eq!(scans[0].name, "BT_scan1");
    assert_eq!(scans[1].name, "BT_scan2");
    assert_eq!(scans[0].signal.time, vec![-1., -0.5, 0.]);
    assert_eq!(scans[1].signal.time, vec![0., 1., 2.]);
    assert_eq!(scans[1].signal.amplitude, vec![4., 6., 8.]);
    for (text, expected) in [
        ("SCAN\tTD Values -->\n0\t2\t3", "x0/dx"),
        ("x0\tdx\tTD Values -->\n0\t1\t2\t\t3", "幅值缺失"),
        ("x0\tdx\tFD Values -->\n0\t1\t2\t3", "频域"),
    ] {
        let error = load_signals(&scratch.write("invalid.txt", text))
            .err()
            .unwrap();
        assert!(error.contains(expected), "{error}");
    }
}

#[test]
fn excel_reads_only_first_two_columns_of_the_active_sheet() {
    let scratch = Scratch::new();
    let path = scratch.join("example.xlsx");
    let mut book = Workbook::new();
    let first = book.add_worksheet();
    first.set_name("Inactive").unwrap();
    for row in 0..2 {
        first.write_number(row, 0, row as f64).unwrap();
        first.write_number(row, 1, 999.).unwrap();
    }
    let active = book.add_worksheet();
    active.set_name("活动表").unwrap().set_active(true);
    active.write_number(0, 0, -1.).unwrap();
    active.write_number(0, 1, -1.).unwrap();
    active.write_string(1, 0, "Time[ps]").unwrap();
    for i in 0..5 {
        active.write_number(i + 2, 0, i as f64).unwrap();
        active
            .write_string(i + 2, 1, ((i + 1) * 10).to_string())
            .unwrap();
    }
    active.write_number(70_000, 16_000, 9999.).unwrap();
    book.save(&path).unwrap();
    let signals = load_signals(&path).unwrap();
    assert_eq!(signals[0].signal.time, vec![0., 1., 2., 3., 4.]);
    assert_eq!(signals[0].signal.amplitude, vec![10., 20., 30., 40., 50.]);
    assert!(
        load_signals(&scratch.join("old.xls"))
            .err()
            .unwrap()
            .contains("另存为 .xlsx")
    );
}

fn sample(name: &str) -> SampleResult {
    SampleResult {
        name: name.into(),
        time: vec![1.2, 3.4],
        magnitude: vec![5., 6.],
        refractive_index: vec![1.5, f64::NAN],
        extinction: vec![0.1, 0.2],
        absorption: vec![0.3, 0.4],
        dielectric_real: vec![1., 2.],
        dielectric_imag: vec![3., 4.],
        loss_tangent: vec![3., 2.],
        phase_fit_band: (0.1, 2.),
    }
}

fn analysis() -> Analysis {
    Analysis {
        time: vec![0., 1.],
        frequency: vec![0.1, 0.2],
        reference_time: vec![9., 8.],
        reference_magnitude: vec![7., 6.],
        samples: vec![sample("test/样品"), sample("TEST[样品")],
        warnings: Vec::new(),
    }
}

fn workbook(path: &Path) -> Xlsx<std::io::BufReader<fs::File>> {
    open_workbook(path).unwrap()
}

#[test]
fn excel_export_preserves_headers_values_and_uses_unique_valid_tabs() {
    let scratch = Scratch::new();
    let results = analysis();
    for (file, kind) in [
        ("optical.xlsx", ExportKind::Optical),
        ("time.xlsx", ExportKind::Time),
        ("frequency.xlsx", ExportKind::Frequency),
    ] {
        export_xlsx(&scratch.join(file), &results, kind, "参考", true).unwrap();
    }
    let mut optical = workbook(&scratch.join("optical.xlsx"));
    assert_eq!(optical.sheet_names(), vec!["test_样品", "TEST_样品_2"]);
    let sheet = optical.worksheet_range_at(0).unwrap().unwrap();
    let expected_headers = [
        "Frequency[THz]",
        "n",
        "k",
        "alpha[cm^-1]",
        "eps_real",
        "eps_imag",
        "tan_delta",
    ];
    assert_eq!(
        sheet.rows().next().unwrap(),
        expected_headers.map(|h| Data::String(h.into()))
    );
    assert_eq!(sheet[(1, 1)], Data::Float(1.5));
    assert_eq!(sheet[(2, 1)], Data::Empty);
    assert_eq!(sheet[(1, 6)], Data::Float(3.));

    let mut time = workbook(&scratch.join("time.xlsx"));
    assert_eq!(time.sheet_names(), vec!["参考", "test_样品", "TEST_样品_2"]);
    let reference_time = time.worksheet_range_at(0).unwrap().unwrap();
    assert_eq!(
        reference_time[(0, 1)],
        Data::String("Reference|windowed".into())
    );
    assert_eq!(reference_time[(1, 1)], Data::Float(9.));
    let sample_time = time.worksheet_range_at(1).unwrap().unwrap();
    assert_eq!(
        sample_time[(0, 1)],
        Data::String("test/样品|windowed".into())
    );
    assert_eq!(sample_time[(1, 1)], Data::Float(1.2));

    let mut frequency = workbook(&scratch.join("frequency.xlsx"));
    let reference_frequency = frequency.worksheet_range_at(0).unwrap().unwrap();
    assert_eq!(
        reference_frequency[(0, 1)],
        Data::String("Reference|magnitude".into())
    );
    assert_eq!(reference_frequency[(2, 1)], Data::Float(6.));
    let sample_frequency = frequency.worksheet_range_at(1).unwrap().unwrap();
    assert_eq!(
        sample_frequency[(0, 0)],
        Data::String("Frequency[THz]".into())
    );
    assert_eq!(sample_frequency[(2, 0)], Data::Float(0.2));
}
