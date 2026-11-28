//! Input format recognition and full-resolution XLSX export.

use std::collections::{BTreeMap, HashSet};
use std::fs::{self, File};
use std::io::{BufReader, Read};
use std::path::Path;

use calamine::{DataRef, Reader as _, Xlsx, open_workbook};
use encoding_rs::{Encoding, GB18030};
use quick_xml::{Reader, events::Event};
use rust_xlsxwriter::{Workbook, XlsxError};
use zip::ZipArchive;

use crate::analysis::{Analysis, Signal};

const SPEED_OF_LIGHT_UM_PER_PS: f64 = 299.792_458;
const MIN_TABLE_RUN: usize = 5;
const FORMAT_HEADER_LINES: usize = 80;

pub struct NamedSignal {
    pub name: String,
    pub signal: Signal,
}

#[derive(Clone, Copy, Debug)]
pub enum ExportKind {
    Optical,
    Time,
    Frequency,
}

/// Read a file directly into time (ps) and amplitude arrays without writing staging TXT files.
pub fn load_signals(path: &Path) -> Result<Vec<NamedSignal>, String> {
    let name = path
        .file_stem()
        .map_or_else(|| "信号".into(), |s| s.to_string_lossy().into_owned());
    let result = match path.extension().and_then(|ext| ext.to_str()) {
        Some(ext) if ext.eq_ignore_ascii_case("xlsx") => import_excel(path, name).map(|s| vec![s]),
        Some(ext) if ext.eq_ignore_ascii_case("xls") => {
            Err("不支持旧版 .xls 格式，请另存为 .xlsx 后再导入".into())
        }
        _ => fs::read(path)
            .map_err(|err| err.to_string())
            .and_then(|bytes| import_text(&decode_text(&bytes), name)),
    };
    result.map_err(|err| format!("{}：{err}", path.display()))
}

fn decode_text(bytes: &[u8]) -> std::borrow::Cow<'_, str> {
    if let Some((encoding, skip)) = Encoding::for_bom(bytes) {
        return encoding.decode_without_bom_handling(&bytes[skip..]).0;
    }
    match std::str::from_utf8(bytes) {
        Ok(text) => text.into(),
        Err(_) => GB18030.decode_without_bom_handling(bytes).0,
    }
}

fn import_text(text: &str, name: String) -> Result<Vec<NamedSignal>, String> {
    let line_iter = || split_lines(text);
    let first = line_iter().take(5).find(|line| !line.trim().is_empty());
    if first.is_some_and(|line| {
        line.trim_start()
            .trim_start_matches('#')
            .trim()
            .starts_with("THz-STD")
    }) {
        return import_standard(line_iter(), name).map(|s| vec![s]);
    }
    if let Some(index) = line_iter()
        .take(FORMAT_HEADER_LINES)
        .position(|line| line.contains("TD Values"))
    {
        return import_bt_fts(line_iter().skip(index), &name);
    }
    if line_iter()
        .take(FORMAT_HEADER_LINES)
        .any(|line| line.contains("FD Values"))
    {
        return Err("该文件是频域数据（FD Values），请选择仪器导出的 Time / TD 时域文件".into());
    }
    let first_data = table_start(
        line_iter()
            .take(30)
            .enumerate()
            .filter_map(|(row, line)| parse_delimited_pair(line).map(|_| row)),
    );
    let pairs = line_iter()
        .skip(first_data)
        .filter_map(parse_delimited_pair);
    signal_from_pairs(name, pairs).map(|s| vec![s])
}

fn import_standard<'a>(
    lines: impl Iterator<Item = &'a str>,
    mut name: String,
) -> Result<NamedSignal, String> {
    let mut pairs = Vec::new();
    for line in lines {
        let line = line.trim();
        if let Some(comment) = line.strip_prefix('#') {
            if let Some((key, value)) = comment.trim_start_matches('#').split_once(':')
                && key.trim() == "name"
                && !value.trim().is_empty()
            {
                name = value.trim().to_owned();
            }
            continue;
        }
        let mut fields = line
            .split(|ch: char| ch == ',' || ch.is_whitespace())
            .filter(|f| !f.is_empty());
        if let Some(pair) = fields
            .next()
            .zip(fields.next())
            .and_then(|(x, y)| finite_pair(x, y))
        {
            pairs.push(pair);
        }
    }
    signal_from_pairs(name, pairs)
}

fn import_bt_fts<'a>(
    mut lines: impl Iterator<Item = &'a str>,
    stem: &str,
) -> Result<Vec<NamedSignal>, String> {
    let header = lines.next().expect("TD Values header already located");
    let headers: Vec<_> = header.split('\t').map(str::trim).collect();
    let td_start = headers
        .iter()
        .position(|name| name.starts_with("TD Values"))
        .ok_or("未找到独立的 'TD Values' 数据列")?;
    let find_position = |target: &str| {
        headers[..td_start].iter().position(|name| {
            name.split('[')
                .next()
                .is_some_and(|base| base.trim().eq_ignore_ascii_case(target))
        })
    };
    let missing_delay = "缺少有效的 x0/dx 位移列，无法生成以 ps 为单位的时间轴";
    let (Some(x0), Some(dx)) = (find_position("x0"), find_position("dx")) else {
        return Err(missing_delay.into());
    };
    let mut signals = Vec::new();
    for (index, row) in lines.filter(|row| !row.trim().is_empty()).enumerate() {
        let row = row.trim_end_matches(['\t', ' ']);
        let mut x0_value = None;
        let mut dx_value = None;
        let mut amplitude = Vec::new();
        for (col, field) in row.split('\t').enumerate() {
            if col == x0 {
                x0_value = finite_number(field);
            } else if col == dx {
                dx_value = finite_number(field);
            } else if col >= td_start {
                let value = finite_number(field).ok_or_else(|| {
                    format!(
                        "第 {} 条扫描的第 {} 个幅值缺失或无效",
                        index + 1,
                        col - td_start + 1
                    )
                })?;
                amplitude.push(value);
            }
        }
        if amplitude.len() < 2 {
            return Err(format!("第 {} 条扫描不足两个数据点", index + 1));
        }
        let (Some(x0_value), Some(dx_value)) = (x0_value, dx_value.filter(|dx| *dx != 0.0)) else {
            return Err(format!("第 {} 条扫描：{missing_delay}", index + 1));
        };
        let time: Vec<_> = (0..amplitude.len())
            .map(|i| (x0_value + i as f64 * dx_value) / SPEED_OF_LIGHT_UM_PER_PS)
            .collect();
        if time.iter().any(|t| !t.is_finite()) {
            return Err(format!("第 {} 条扫描的时间轴超出了有效范围", index + 1));
        }
        signals.push(NamedSignal {
            name: stem.to_owned(),
            signal: Signal { time, amplitude },
        });
    }
    if signals.is_empty() {
        return Err("时域扫描文件不包含数据行".into());
    }
    if signals.len() > 1 {
        for (index, signal) in signals.iter_mut().enumerate() {
            signal.name = format!("{stem}_scan{}", index + 1);
        }
    }
    Ok(signals)
}

fn finite_number(text: &str) -> Option<f64> {
    text.trim().parse::<f64>().ok().filter(|x| x.is_finite())
}

fn finite_pair(first: &str, second: &str) -> Option<(f64, f64)> {
    Some((finite_number(first)?, finite_number(second)?))
}

fn parse_delimited_pair(line: &str) -> Option<(f64, f64)> {
    let line = line.trim_matches(|ch: char| ch.is_whitespace() && ch != '\t');
    if line.trim_start().starts_with('#') {
        return None;
    }
    // Keep empty CSV/TSV columns in place: a missing amplitude isn't column three.
    if line.contains('\t') {
        let mut fields = line.split('\t');
        finite_pair(fields.next()?, fields.next()?)
    } else if line.contains(',') {
        let mut fields = line.split(',');
        finite_pair(fields.next()?, fields.next()?)
    } else {
        let mut fields = line.split_whitespace();
        finite_pair(fields.next()?, fields.next()?)
    }
}

fn table_start(rows: impl IntoIterator<Item = usize>) -> usize {
    let mut run = 0;
    let mut previous = None;
    for row in rows {
        if previous != row.checked_sub(1) || run == 0 {
            run = 0;
        }
        run += 1;
        if run == MIN_TABLE_RUN {
            return row + 1 - MIN_TABLE_RUN;
        }
        previous = Some(row);
    }
    0
}

fn signal_from_pairs(
    name: String,
    pairs: impl IntoIterator<Item = (f64, f64)>,
) -> Result<NamedSignal, String> {
    let (time, amplitude): (Vec<_>, Vec<_>) = pairs.into_iter().unzip();
    if time.len() < 2 {
        return Err("未能识别至少两行时域数据，请检查第 1 列时间（ps）和第 2 列幅值".into());
    }
    Ok(NamedSignal {
        name,
        signal: Signal { time, amplitude },
    })
}

fn workbook_active_tab(path: &Path) -> Result<usize, String> {
    // calamine does not expose the workbook's selected sheet. Read only the small
    // metadata entry to match openpyxl's `workbook.active` behavior.
    let file = File::open(path).map_err(|err| err.to_string())?;
    let mut archive = ZipArchive::new(file).map_err(|err| err.to_string())?;
    let entry = archive
        .by_name("xl/workbook.xml")
        .map_err(|err| err.to_string())?;
    let mut reader = Reader::from_reader(BufReader::new(entry.take(16 * 1024 * 1024)));
    let mut buf = Vec::new();
    loop {
        match reader
            .read_event_into(&mut buf)
            .map_err(|err| err.to_string())?
        {
            Event::Start(tag) | Event::Empty(tag)
                if tag.local_name().as_ref() == b"workbookView" =>
            {
                for attr in tag.attributes() {
                    let attr = attr.map_err(|err| err.to_string())?;
                    if attr.key.local_name().as_ref() == b"activeTab" {
                        return std::str::from_utf8(&attr.value)
                            .ok()
                            .and_then(|text| text.parse::<usize>().ok())
                            .ok_or_else(|| "工作簿中的活动工作表索引无效".into());
                    }
                }
                return Ok(0);
            }
            Event::Start(tag) if tag.local_name().as_ref() == b"sheets" => return Ok(0),
            Event::Eof => return Ok(0),
            _ => {}
        }
        buf.clear();
    }
}

fn import_excel(path: &Path, name: String) -> Result<NamedSignal, String> {
    let active_tab = workbook_active_tab(path)?;
    let mut workbook: Xlsx<_> =
        open_workbook(path).map_err(|err: calamine::XlsxError| err.to_string())?;
    let sheet_name = workbook
        .sheet_names()
        .into_iter()
        .nth(active_tab)
        .ok_or("Excel 中没有可用的活动工作表")?;
    let mut reader = workbook
        .worksheet_cells_reader(&sheet_name)
        .map_err(|err| err.to_string())?;
    let mut rows: BTreeMap<u32, [Option<f64>; 2]> = BTreeMap::new();
    // Stream cells rather than expanding a sparse worksheet into its full used rectangle.
    while let Some(cell) = reader.next_cell().map_err(|err| err.to_string())? {
        let (row, col) = cell.get_position();
        if col >= 2 {
            continue;
        }
        let value = match cell.get_value() {
            DataRef::Int(n) => Some(*n as f64),
            DataRef::Float(n) if n.is_finite() => Some(*n),
            DataRef::Bool(b) => Some(u8::from(*b) as f64),
            DataRef::SharedString(text) => finite_number(text),
            DataRef::String(text) => finite_number(text),
            _ => None,
        };
        if let Some(value) = value {
            rows.entry(row).or_default()[col as usize] = Some(value);
        }
    }
    let first = table_start(
        rows.range(..35)
            .filter_map(|(row, cols)| cols[0].zip(cols[1]).map(|_| *row as usize)),
    ) as u32;
    let pairs = rows
        .into_iter()
        .filter_map(|(row, cols)| (row >= first).then(|| cols[0].zip(cols[1])).flatten());
    signal_from_pairs(name, pairs)
}

/// Write the same tabs and columns as the Python application's three export actions.
/// The caller supplies the destination (including extension) and original reference stem.
pub fn export_xlsx(
    path: &Path,
    result: &Analysis,
    kind: ExportKind,
    reference_name: &str,
    use_window: bool,
) -> Result<(), String> {
    if result.samples.is_empty() {
        return Err("没有可写出的样品数据".into());
    }
    let mut book = Workbook::new();
    let mut used = HashSet::new();
    populate_workbook(
        &mut book,
        &mut used,
        result,
        kind,
        reference_name,
        use_window,
    )
    .and_then(|()| book.save(path))
    .map_err(|err| format!("无法写入 {}：{err}", path.display()))
}

fn populate_workbook(
    book: &mut Workbook,
    used: &mut HashSet<String>,
    result: &Analysis,
    kind: ExportKind,
    reference_name: &str,
    use_window: bool,
) -> Result<(), XlsxError> {
    const FREQUENCY: &str = "Frequency[THz]";
    const TIME: &str = "Time[ps]";
    let amplitude = if use_window { "windowed" } else { "amplitude" };
    let ref_name = if reference_name.trim().is_empty() {
        "Reference"
    } else {
        reference_name
    };
    match kind {
        ExportKind::Optical => {
            for sample in &result.samples {
                write_table(
                    book,
                    used,
                    &sample.name,
                    &[
                        (FREQUENCY, &result.frequency),
                        ("n", &sample.refractive_index),
                        ("k", &sample.extinction),
                        ("alpha[cm^-1]", &sample.absorption),
                        ("eps_real", &sample.dielectric_real),
                        ("eps_imag", &sample.dielectric_imag),
                        ("tan_delta", &sample.loss_tangent),
                    ],
                )?;
            }
        }
        ExportKind::Time => {
            write_table(
                book,
                used,
                ref_name,
                &[
                    (TIME, &result.time),
                    (&format!("Reference|{amplitude}"), &result.reference_time),
                ],
            )?;
            for sample in &result.samples {
                write_table(
                    book,
                    used,
                    &sample.name,
                    &[
                        (TIME, &result.time),
                        (&format!("{}|{amplitude}", sample.name), &sample.time),
                    ],
                )?;
            }
        }
        ExportKind::Frequency => {
            write_table(
                book,
                used,
                ref_name,
                &[
                    (FREQUENCY, &result.frequency),
                    ("Reference|magnitude", &result.reference_magnitude),
                ],
            )?;
            for sample in &result.samples {
                write_table(
                    book,
                    used,
                    &sample.name,
                    &[
                        (FREQUENCY, &result.frequency),
                        (&format!("{}|magnitude", sample.name), &sample.magnitude),
                    ],
                )?;
            }
        }
    }
    Ok(())
}

fn write_table(
    book: &mut Workbook,
    used: &mut HashSet<String>,
    name: &str,
    columns: &[(&str, &[f64])],
) -> Result<(), XlsxError> {
    const MAX_DATA_ROWS: usize = 1_048_575;
    let row_count = columns.first().map_or(0, |(_, values)| values.len());
    if row_count > MAX_DATA_ROWS {
        return Err(XlsxError::RowColumnLimitError);
    }
    if columns.iter().any(|(_, values)| values.len() != row_count) {
        return Err(XlsxError::ParameterError(format!(
            "{name}：导出数据列长度不一致"
        )));
    }
    let sheet = book.add_worksheet().set_name(safe_sheet_name(name, used))?;
    for (col, (header, values)) in columns.iter().enumerate() {
        sheet.write_string(0, col as u16, *header)?;
        for (row, value) in values.iter().enumerate() {
            // As with openpyxl, undefined numeric values are left blank, not zero.
            if value.is_finite() {
                sheet.write_number((row + 1) as u32, col as u16, *value)?;
            }
        }
    }
    Ok(())
}

fn safe_sheet_name(name: &str, used: &mut HashSet<String>) -> String {
    let base: String = name
        .trim()
        .chars()
        .map(|ch| {
            if ch.is_control() || matches!(ch, '\\' | '/' | ':' | '*' | '?' | '[' | ']') {
                '_'
            } else {
                ch
            }
        })
        .collect();
    let base = base.trim_matches('\'');
    let base = if base.is_empty() { "Sheet" } else { base };
    for counter in 1.. {
        let suffix = if counter == 1 {
            String::new()
        } else {
            format!("_{counter}")
        };
        let mut budget = 31 - suffix.len();
        let prefix: String = base
            .chars()
            .take_while(|ch| {
                let size = ch.len_utf16();
                if size > budget {
                    return false;
                }
                budget -= size;
                true
            })
            .collect();
        let candidate = format!("{}{suffix}", prefix.trim_end_matches('\''));
        if !candidate.eq_ignore_ascii_case("history") && used.insert(candidate.to_lowercase()) {
            return candidate;
        }
    }
    unreachable!("an unbounded suffix sequence provides a unique worksheet name")
}

/// Split lines on CRLF, LF or lone CR without inserting a false blank row for CRLF.
fn split_lines(mut text: &str) -> impl Iterator<Item = &str> {
    std::iter::from_fn(move || {
        if text.is_empty() {
            return None;
        }
        let Some(index) = text.find(['\r', '\n']) else {
            return Some(std::mem::take(&mut text));
        };
        let (line, rest) = text.split_at(index);
        text = if let Some(rest) = rest.strip_prefix("\r\n") {
            rest
        } else {
            &rest[1..]
        };
        Some(line)
    })
}
