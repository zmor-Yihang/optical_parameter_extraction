//! Signal preprocessing and optical properties, ported from the Python core.

use std::f64::consts::{PI, TAU};

use realfft::{RealFftPlanner, num_complex::Complex64};

/// Vacuum light speed, shared with the instrument delay-to-time conversion.
pub const LIGHT_SPEED_UM_PER_PS: f64 = 299.792_458;
const C_LIGHT: f64 = LIGHT_SPEED_UM_PER_PS * 1e6;
const PHASE_FIT_REF_DB: f64 = -25.0;
const PHASE_FIT_SNR_DB: f64 = 10.0;
const PHASE_FIT_MIN_THZ: f64 = 0.1;
const PHASE_FIT_MIN_POINTS: usize = 8;
const NOISE_BAND_THZ: (f64, f64) = (5.0, 6.8);
const NOISE_ESTIMATION_MIN_POINTS: usize = 16;

#[derive(Clone, Debug)]
pub struct Signal {
    pub time: Vec<f64>,
    pub amplitude: Vec<f64>,
}

#[derive(Clone, Debug)]
pub struct Sample {
    pub name: String,
    pub signal: Signal,
    pub thickness_mm: Option<f64>,
    pub window: Option<Window>,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Window {
    pub start_ps: f64,
    pub end_ps: f64,
    pub alpha: f64,
}

#[derive(Clone, Copy, Debug)]
pub struct Settings {
    pub thickness_mm: f64,
    pub use_window: bool,
    pub reference_window: Option<Window>,
}

#[derive(Debug)]
pub struct Analysis {
    pub time: Vec<f64>,
    pub frequency: Vec<f64>,
    /// Reference amplitudes after baseline removal and optional windowing.
    pub reference_time: Vec<f64>,
    /// Reference spectrum in linear units, normalized by the time-domain point count.
    pub reference_magnitude: Vec<f64>,
    pub samples: Vec<SampleResult>,
    pub warnings: Vec<String>,
}

#[derive(Debug)]
pub struct SampleResult {
    pub name: String,
    /// Sample amplitudes on `Analysis::time` after preprocessing.
    pub time: Vec<f64>,
    pub magnitude: Vec<f64>,
    pub refractive_index: Vec<f64>,
    /// Absorption coefficient in cm⁻¹.
    pub absorption: Vec<f64>,
    pub extinction: Vec<f64>,
    pub dielectric_real: Vec<f64>,
    pub dielectric_imag: Vec<f64>,
    pub loss_tangent: Vec<f64>,
    /// Frequency interval in THz selected for resolving the phase branch.
    pub phase_fit_band: (f64, f64),
}

/// Truncate to a common length, remove each baseline, apply optional Tukey
/// windows, then calculate the one-sided spectra and optical properties.
pub fn analyze(
    reference: &Signal,
    samples: &[Sample],
    settings: &Settings,
) -> Result<Analysis, String> {
    if !positive_finite(settings.thickness_mm) {
        return Err("样品厚度必须为正数".into());
    }
    validate_signal(reference, "参考信号")?;
    let reference_length = reference.amplitude.len();
    let mut count = reference_length;
    for (index, sample) in samples.iter().enumerate() {
        validate_signal(&sample.signal, &sample.name)?;
        if let Some(thickness) = sample.thickness_mm
            && !positive_finite(thickness)
        {
            return Err(format!(
                "第 {} 个样品的厚度必须为正数，当前为 {thickness}",
                index + 1
            ));
        }
        count = count.min(sample.signal.amplitude.len());
    }
    let time = reference.time[..count].to_vec();
    let interval = time[1] - time[0];
    if !interval.is_finite() || interval == 0.0 {
        return Err("时间采样间隔必须为非零有限值".into());
    }
    let mut warnings: Vec<_> = samples
        .iter()
        .filter(|sample| sample.signal.amplitude.len() != reference_length)
        .map(|sample| {
            format!(
                "文件 {} 的数据点数与参考文件不匹配，已自动截断至 {count} 个点",
                sample.name
            )
        })
        .collect();

    let default_window = Window {
        start_ps: time[0],
        end_ps: time[count - 1],
        alpha: 0.5,
    };
    let window = |window: Option<Window>| {
        settings
            .use_window
            .then(|| window.unwrap_or(default_window))
    };
    let reference_time = prepare(
        &time,
        &reference.amplitude,
        window(settings.reference_window),
        "参考信号",
        &mut warnings,
    )?;
    let mut planner = RealFftPlanner::<f64>::new();
    let fft = planner.plan_fft_forward(count);
    let mut fft_input = fft.make_input_vec();
    let mut scratch = fft.make_scratch_vec();
    let mut reference_fft = fft.make_output_vec();
    let mut sample_fft = fft.make_output_vec();
    let mut spectrum = |signal: &[f64], output: &mut [Complex64]| {
        // RealFFT uses its input as scratch; the display/export arrays stay unchanged.
        fft_input.copy_from_slice(signal);
        fft.process_with_scratch(&mut fft_input, output, &mut scratch)
            .map_err(|err| format!("FFT 计算失败：{err}"))
    };
    spectrum(&reference_time, &mut reference_fft)?;
    let step = (1.0 / interval) / count as f64;
    let frequency: Vec<_> = (0..reference_fft.len())
        .map(|index| index as f64 * step)
        .collect();
    let reference_magnitude = magnitude(&reference_fft, count);
    let noise_floor = estimate_noise_floor(&reference_magnitude, &frequency);
    let mut results = Vec::with_capacity(samples.len());

    for sample in samples {
        let prepared = prepare(
            &time,
            &sample.signal.amplitude,
            window(sample.window),
            &sample.name,
            &mut warnings,
        )?;
        spectrum(&prepared, &mut sample_fft)?;
        let sample_magnitude = magnitude(&sample_fft, count);
        let band = suggest_phase_band(
            &frequency,
            &reference_magnitude,
            &sample_magnitude,
            noise_floor,
        );
        let mut result = SampleResult {
            name: sample.name.clone(),
            time: prepared,
            magnitude: sample_magnitude,
            refractive_index: Vec::with_capacity(frequency.len()),
            absorption: Vec::with_capacity(frequency.len()),
            extinction: Vec::with_capacity(frequency.len()),
            dielectric_real: Vec::with_capacity(frequency.len()),
            dielectric_imag: Vec::with_capacity(frequency.len()),
            loss_tangent: Vec::with_capacity(frequency.len()),
            phase_fit_band: band,
        };
        let thickness_mm = sample.thickness_mm.unwrap_or(settings.thickness_mm);
        calculate_properties(
            &frequency,
            &reference_fft,
            &sample_fft,
            thickness_mm,
            &mut result,
        );
        results.push(result);
    }

    Ok(Analysis {
        time,
        frequency,
        reference_time,
        reference_magnitude,
        samples: results,
        warnings,
    })
}

fn positive_finite(value: f64) -> bool {
    value.is_finite() && value > 0.0
}

fn validate_signal(signal: &Signal, name: &str) -> Result<(), String> {
    if signal.time.len() != signal.amplitude.len() {
        return Err(format!("{name} 的时间轴与振幅长度不一致"));
    }
    if signal.time.len() < 2 {
        return Err(format!("{name}：信号至少需要两个数据点"));
    }
    if !signal
        .time
        .iter()
        .chain(&signal.amplitude)
        .all(|v| v.is_finite())
    {
        return Err(format!("{name} 含有非有限数值"));
    }
    Ok(())
}

/// Recommend a window extending 3 ps before and 25 ps after the main pulse.
pub fn suggest_window(signal: &Signal) -> Window {
    let count = signal.time.len().min(signal.amplitude.len());
    let (first, last) = if count < 2 {
        let first = signal.time.first().copied().unwrap_or_default();
        (first, first)
    } else {
        let peak = signal.time[peak_index(&signal.amplitude[..count])];
        (
            signal.time[0].max(peak - 3.0),
            signal.time[count - 1].min(peak + 25.0),
        )
    };
    Window {
        start_ps: first,
        end_ps: last,
        alpha: 0.15,
    }
}

fn mean(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

fn median(values: &mut [f64]) -> f64 {
    let mid = values.len() / 2;
    let odd = values.len() % 2 == 1;
    let (lower, upper_middle, _) = values.select_nth_unstable_by(mid, f64::total_cmp);
    if odd {
        *upper_middle
    } else {
        let lower_middle = lower.iter().copied().reduce(f64::max).unwrap();
        (lower_middle + *upper_middle) * 0.5
    }
}

fn first_max_index(values: impl IntoIterator<Item = f64>) -> usize {
    let mut highest = f64::NEG_INFINITY;
    let mut index = 0;
    for (candidate, value) in values.into_iter().enumerate() {
        if value > highest {
            highest = value;
            index = candidate;
        }
    }
    index
}

fn peak_index(values: &[f64]) -> usize {
    let middle = median(&mut values.to_vec());
    first_max_index(values.iter().map(|x| (x - middle).abs()))
}

fn prepare(
    time: &[f64],
    amplitude: &[f64],
    window: Option<Window>,
    name: &str,
    warnings: &mut Vec<String>,
) -> Result<Vec<f64>, String> {
    // As in the original, windows and the FFT for all samples use the reference time axis.
    let values = &amplitude[..time.len()];
    let baseline_count = if values.len() < 16 {
        values.len()
    } else {
        8.max((peak_index(values) / 2).min(values.len() / 20))
    };
    let baseline = mean(&values[..baseline_count]);
    let mut prepared: Vec<_> = values.iter().map(|value| value - baseline).collect();
    if let Some(Window {
        start_ps,
        end_ps,
        alpha,
    }) = window
    {
        if !start_ps.is_finite() || !end_ps.is_finite() || !alpha.is_finite() {
            return Err(format!("{name}: 窗口参数必须为有限值"));
        }
        let in_window = |t: f64| t >= start_ps && t <= end_ps;
        let peak = peak_index(&prepared);
        let peak_time = time[peak];
        let count = time.iter().filter(|&&t| in_window(t)).count();
        if end_ps <= start_ps {
            warnings.push(format!(
                "{name}: 窗口起止时间无效（{start_ps:.2} ~ {end_ps:.2} ps）"
            ));
        } else if !in_window(peak_time) {
            warnings.push(format!("{name}: 主脉冲位于 {peak_time:.2} ps，落在窗口 {start_ps:.2} ~ {end_ps:.2} ps 之外，结果不可信，请调整窗口范围"));
        } else {
            let position = time[..peak].iter().filter(|&&t| in_window(t)).count();
            let weight = tukey_weight(position, count, alpha);
            if weight < 0.9 {
                warnings.push(format!("{name}: 主脉冲位于 {peak_time:.2} ps，落在窗口 {start_ps:.2} ~ {end_ps:.2} ps 的渐变区内（幅度被压到 {:.0}%），结果不可信，请放宽窗口或减小 alpha", weight * 100.0));
            }
        }
        let mut index = 0;
        for (&t, value) in time.iter().zip(&mut prepared) {
            if in_window(t) {
                *value *= tukey_weight(index, count, alpha);
                index += 1;
            } else {
                *value = 0.0;
            }
        }
    }
    Ok(prepared)
}

fn tukey_weight(index: usize, count: usize, alpha: f64) -> f64 {
    if count <= 1 || alpha <= 0.0 {
        return 1.0;
    }
    let last = (count - 1) as f64;
    let i = index as f64;
    if alpha >= 1.0 {
        return 0.5 - 0.5 * (TAU * i / last).cos();
    }
    let width = (alpha * last / 2.0).floor() as usize;
    if index <= width {
        0.5 * (1.0 + (PI * (-1.0 + 2.0 * i / alpha / last)).cos())
    } else if index >= count - width - 1 {
        0.5 * (1.0 + (PI * (-2.0 / alpha + 1.0 + 2.0 * i / alpha / last)).cos())
    } else {
        1.0
    }
}

fn magnitude(spectrum: &[Complex64], count: usize) -> Vec<f64> {
    spectrum
        .iter()
        .map(|z| z.scale(1.0 / count as f64).norm())
        .collect()
}

fn estimate_noise_floor(magnitude: &[f64], frequency: &[f64]) -> f64 {
    let select = |include: &dyn Fn(f64) -> bool| {
        frequency
            .iter()
            .zip(magnitude)
            .filter_map(|(&f, &m)| include(f).then_some(m))
            .collect::<Vec<_>>()
    };
    let mut values = select(&|f| f >= NOISE_BAND_THZ.0 && f <= NOISE_BAND_THZ.1);
    if values.len() < NOISE_ESTIMATION_MIN_POINTS {
        let lower = frequency[frequency.len() - 1] * 0.9;
        values = select(&|f| f >= lower);
    }
    if values.is_empty() {
        0.0
    } else {
        median(&mut values)
    }
}

fn suggest_phase_band(
    frequency: &[f64],
    reference_magnitude: &[f64],
    sample_magnitude: &[f64],
    noise_floor: f64,
) -> (f64, f64) {
    if frequency.len() < PHASE_FIT_MIN_POINTS {
        return (0.0, 0.0);
    }
    let reference_peak = first_max_index(reference_magnitude.iter().copied());
    let threshold = reference_magnitude[reference_peak] * 10.0_f64.powf(PHASE_FIT_REF_DB / 20.0);
    let snr_threshold = noise_floor * 10.0_f64.powf(PHASE_FIT_SNR_DB / 20.0);
    let good: Vec<_> = (0..frequency.len())
        .filter(|&i| {
            frequency[i] >= PHASE_FIT_MIN_THZ
                && reference_magnitude[i] > threshold
                && (noise_floor <= 0.0 || sample_magnitude[i] > snr_threshold)
        })
        .collect();
    if good.len() < PHASE_FIT_MIN_POINTS {
        let lo = 1.max(reference_peak / 2);
        let hi = (frequency.len() - 1).min(reference_peak * 2);
        return (frequency[lo], frequency[hi]);
    }
    let sample_peak = first_max_index(sample_magnitude.iter().copied());
    let position = good
        .partition_point(|&i| i < sample_peak)
        .min(good.len() - 1);
    let mut lo = position;
    let mut hi = position;
    while lo > 0 && good[lo] - good[lo - 1] == 1 {
        lo -= 1;
    }
    while hi + 1 < good.len() && good[hi + 1] - good[hi] == 1 {
        hi += 1;
    }
    (frequency[good[lo]], frequency[good[hi]])
}

// Match NumPy's scaled complex division, including division by a zero bin.
fn transfer(sample: Complex64, reference: Complex64) -> Complex64 {
    let Complex64 { re: a, im: b } = sample;
    let Complex64 { re: c, im: d } = reference;
    if c.abs() >= d.abs() {
        if c == 0.0 && d == 0.0 {
            return Complex64::new(a / c.abs(), b / d.abs());
        }
        let ratio = d / c;
        let scale = 1.0 / (c + d * ratio);
        Complex64::new((a + b * ratio) * scale, (b - a * ratio) * scale)
    } else {
        let ratio = c / d;
        let scale = 1.0 / (d + c * ratio);
        Complex64::new((a * ratio + b) * scale, (b * ratio - a) * scale)
    }
}

fn unwrap_phase(frequency: &[f64], transfer: &[Complex64], band: (f64, f64)) -> Vec<f64> {
    let mut phase = Vec::with_capacity(transfer.len());
    let mut previous: Option<f64> = None;
    let mut correction = 0.0;
    for z in transfer {
        let raw = z.arg();
        if let Some(prior) = previous {
            let difference = raw - prior;
            if difference.is_nan() {
                // np.unwrap accumulates phase corrections; NaN propagates to all later bins.
                correction = f64::NAN;
            } else if difference.abs() >= PI {
                let mut wrapped = (difference + PI).rem_euclid(TAU) - PI;
                if wrapped == -PI && difference > 0.0 {
                    wrapped = PI;
                }
                correction += wrapped - difference;
            }
        }
        phase.push(raw + correction);
        previous = Some(raw);
    }
    let (low, high) = band;
    if !low.is_finite() || !high.is_finite() || high <= low {
        return phase;
    }
    let start = frequency.partition_point(|&value| value < low);
    let end = frequency.partition_point(|&value| value <= high);
    if end.saturating_sub(start) < PHASE_FIT_MIN_POINTS {
        return phase;
    }
    let x = &frequency[start..end];
    let x_mean = mean(x);
    let x_square_sum: f64 = x.iter().map(|v| (v - x_mean) * (v - x_mean)).sum();
    if !positive_finite(x_square_sum) {
        return phase;
    }
    for _ in 0..5 {
        let y = &phase[start..end];
        if y.iter().any(|v| !v.is_finite()) {
            break;
        }
        let y_mean = mean(y);
        let covariance: f64 = x
            .iter()
            .zip(y)
            .map(|(x, y)| (x - x_mean) * (y - y_mean))
            .sum();
        let intercept = y_mean - covariance / x_square_sum * x_mean;
        let shift = (intercept / TAU).round_ties_even();
        if shift == 0.0 {
            break;
        }
        for value in &mut phase {
            *value -= TAU * shift;
        }
    }
    phase
}

fn calculate_properties(
    frequency: &[f64],
    reference: &[Complex64],
    sample: &[Complex64],
    thickness_mm: f64,
    result: &mut SampleResult,
) {
    let thickness_m = thickness_mm * 1e-3;
    let transfer: Vec<_> = sample
        .iter()
        .zip(reference)
        .map(|(&s, &r)| transfer(s, r))
        .collect();
    let phase = unwrap_phase(frequency, &transfer, result.phase_fit_band);

    for index in 0..frequency.len() {
        // DC is reported as the first non-zero bin instead of dividing by zero.
        let bin = index.max(1);
        let omega = TAU * frequency[bin] * 1e12;
        let n = 1.0 - phase[bin] * C_LIGHT / (omega * thickness_m);
        let k = (4.0 * n / transfer[bin].norm() / ((n + 1.0) * (n + 1.0))).ln() * C_LIGHT
            / (omega * thickness_m);
        let absorption = 2.0 * omega * k / C_LIGHT / 100.0;
        let real = n * n - k * k;
        let imag = 2.0 * n * k;
        result.refractive_index.push(n);
        result.extinction.push(k);
        result.absorption.push(absorption);
        result.dielectric_real.push(real);
        result.dielectric_imag.push(imag);
        result
            .loss_tangent
            .push(if real == 0.0 { 0.0 } else { imag / real });
    }
}
