use std::collections::HashMap;

use thz_analyzer_rust::analysis::{Sample, Settings, Signal, Window, analyze, suggest_window};

fn verify_python_case(fixture: &str, use_window: bool) {
    let mut fields = HashMap::new();
    let mut warnings = Vec::new();
    for line in fixture.lines().filter(|line| !line.starts_with('#')) {
        let (key, values) = line.split_once('\t').unwrap();
        if key == "warning" {
            warnings.push(values);
        } else {
            let row: Vec<f64> = values.split('\t').map(|v| v.parse().unwrap()).collect();
            assert!(fields.insert(key, row).is_none(), "duplicate field {key}");
        }
    }
    let signal = |name: &str| Signal {
        time: fields[format!("{name}_input_time").as_str()].clone(),
        amplitude: fields[format!("{name}_input").as_str()].clone(),
    };
    let reference = signal("reference");
    let samples = [
        Sample {
            name: "branch".into(),
            signal: signal("branch"),
            thickness_mm: None,
            window: None,
        },
        Sample {
            name: "custom".into(),
            signal: signal("custom"),
            thickness_mm: Some(0.29),
            window: Some(Window {
                start_ps: 3.3,
                end_ps: 5.25,
                alpha: 1.0,
            }),
        },
    ];
    let settings = Settings {
        thickness_mm: 0.42,
        use_window,
        reference_window: Some(Window {
            start_ps: 1.5,
            end_ps: 5.5,
            alpha: 0.5,
        }),
    };
    let result = analyze(&reference, &samples, &settings).unwrap();
    assert_eq!(result.warnings, warnings);
    let verify = |name: &str, actual: &[f64]| {
        let expected = &fields[name];
        assert_eq!(actual.len(), expected.len(), "{name} length");
        for (bin, (&actual, &expected)) in actual.iter().zip(expected).enumerate() {
            // Permit minor FFT, transcendental and least-squares rounding differences.
            let tolerance = 1e-10 + 1e-9 * expected.abs();
            assert!(
                (actual - expected).abs() <= tolerance,
                "{name}[{bin}]: Rust {actual:.15e}, Python {expected:.15e}, tolerance {tolerance:.3e}"
            );
        }
    };
    verify("time", &result.time);
    verify("frequency", &result.frequency);
    verify("reference_time", &result.reference_time);
    verify("reference_magnitude", &result.reference_magnitude);
    assert_eq!(result.samples.len(), samples.len());
    for (sample, input) in result.samples.iter().zip(samples) {
        assert_eq!(sample.name, input.name);
        for (name, values) in [
            ("time", sample.time.as_slice()),
            ("magnitude", &sample.magnitude),
            (
                "phase_fit_band",
                &[sample.phase_fit_band.0, sample.phase_fit_band.1],
            ),
            ("refractive_index", &sample.refractive_index),
            ("absorption", &sample.absorption),
            ("extinction", &sample.extinction),
            ("dielectric_real", &sample.dielectric_real),
            ("dielectric_imag", &sample.dielectric_imag),
            ("loss_tangent", &sample.loss_tangent),
        ] {
            verify(&format!("{}_{name}", sample.name), values);
        }
    }
}

#[test]
fn agrees_with_python_on_odd_length_without_window() {
    verify_python_case(include_str!("fixtures/analysis/63_points.txt"), false);
}

#[test]
fn agrees_with_python_on_even_length_with_custom_windows() {
    verify_python_case(include_str!("fixtures/analysis/160_points.txt"), true);
}

#[test]
fn window_suggestion_uses_absolute_pulse_peak_and_clamps_range() {
    let signal = Signal {
        time: vec![-10.0, -2.0, 4.0, 6.0, 13.0],
        amplitude: vec![5.0, 5.0, 1.0, 7.0, 5.0],
    };
    assert_eq!(
        suggest_window(&signal),
        Window {
            start_ps: 1.0,
            end_ps: 13.0,
            alpha: 0.15
        }
    );
}

#[test]
fn rejects_invalid_input_before_planning_fft() {
    let signal = Signal {
        time: vec![0.0, 1.0],
        amplitude: vec![1.0, 2.0],
    };
    let settings = Settings {
        thickness_mm: 1.0,
        use_window: false,
        reference_window: None,
    };
    let mismatch = Signal {
        time: vec![0.0],
        amplitude: signal.amplitude.clone(),
    };
    assert!(
        analyze(&mismatch, &[], &settings)
            .unwrap_err()
            .contains("长度不一致")
    );
    let duplicate_times = Signal {
        time: vec![0.0, 0.0],
        amplitude: signal.amplitude.clone(),
    };
    assert!(
        analyze(&duplicate_times, &[], &settings)
            .unwrap_err()
            .contains("时间采样间隔")
    );
    let sample = Sample {
        name: "invalid".into(),
        signal: signal.clone(),
        thickness_mm: Some(-1.0),
        window: None,
    };
    assert!(
        analyze(&signal, &[sample], &settings)
            .unwrap_err()
            .contains("第 1 个样品的厚度")
    );
}

#[test]
fn zero_reference_keeps_undefined_optical_values_instead_of_faking_results() {
    let reference = Signal {
        time: vec![0.0, 1.0, 2.0, 3.0],
        amplitude: vec![0.0; 4],
    };
    let sample = Sample {
        name: "sample".into(),
        signal: Signal {
            time: reference.time.clone(),
            amplitude: vec![0.0, 1.0, 0.0, -1.0],
        },
        thickness_mm: None,
        window: None,
    };
    let settings = Settings {
        thickness_mm: 1.0,
        use_window: false,
        reference_window: None,
    };
    let values = analyze(&reference, &[sample], &settings).unwrap();
    assert_eq!(values.reference_magnitude, vec![0.0; 3]);
    assert!(
        values.samples[0]
            .refractive_index
            .iter()
            .all(|n| n.is_nan())
    );
}
