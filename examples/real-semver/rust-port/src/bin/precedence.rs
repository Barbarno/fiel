//! El mismo port, con la comparacion corregida.
//!
//! El port principal traduce `semver.compare(a, b)` a `a.cmp(&b)`. El crate de
//! Rust define `Ord` incluyendo la metadata de build y expone la comparacion
//! del estandar (que la ignora) como `cmp_precedence`.
//!
//! Un caracter de diferencia en el codigo, y el orden de versiones cambia.
//! Este binario existe para que fiel demuestre que el arreglo funciona: mismo
//! corpus, cero divergencias.

use std::cmp::Ordering;
use std::io::{self, Read};

use semver::Version;

fn fields(version: &Version) -> String {
    let pre = if version.pre.is_empty() {
        "-".to_string()
    } else {
        version.pre.to_string()
    };
    let build = if version.build.is_empty() {
        "-".to_string()
    } else {
        version.build.to_string()
    };
    format!(
        "{}|{}|{}|{}|{}|{}",
        version.major, version.minor, version.patch, pre, build, version
    )
}

fn render(text: &str) -> Result<String, String> {
    let parts: Vec<&str> = text.split_whitespace().collect();
    match parts.len() {
        1 => {
            let version = Version::parse(parts[0]).map_err(|error| error.to_string())?;
            Ok(fields(&version))
        }
        2 => {
            let left = Version::parse(parts[0]).map_err(|error| error.to_string())?;
            let right = Version::parse(parts[1]).map_err(|error| error.to_string())?;
            Ok(match left.cmp_precedence(&right) {
                Ordering::Less => "-1",
                Ordering::Equal => "0",
                Ordering::Greater => "1",
            }
            .to_string())
        }
        _ => Err("entrada invalida".to_string()),
    }
}

fn main() {
    let mut input = String::new();
    if io::stdin().read_to_string(&mut input).is_err() {
        std::process::exit(1);
    }
    match render(input.trim()) {
        Ok(line) => print!("{}", line),
        Err(message) => {
            eprintln!("error: {}", message);
            std::process::exit(1);
        }
    }
}
