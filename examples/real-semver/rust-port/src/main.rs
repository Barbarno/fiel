//! Port del ejemplo real: usa el crate `semver` (1.0) en vez de la biblioteca
//! `semver` de Python.
//!
//! Las dos implementan la misma especificacion. Este binario existe para que
//! fiel pueda comprobar si eso es verdad en todos los casos, no solo en los
//! que aparecen en la documentacion.
//!
//! Una version -> sus campos. Dos versiones separadas por un espacio -> -1, 0
//! o 1 segun el orden que define el estandar.

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
            Ok(match left.cmp(&right) {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn completa() {
        assert_eq!(
            render("1.2.3-alpha.1+build.5").unwrap(),
            "1|2|3|alpha.1|build.5|1.2.3-alpha.1+build.5"
        );
    }

    #[test]
    fn orden() {
        assert_eq!(render("1.0.0-alpha 1.0.0-beta").unwrap(), "-1");
        assert_eq!(render("2.0.0 2.0.0").unwrap(), "0");
    }

    #[test]
    fn sin_parche_falla() {
        assert!(render("1.2").is_err());
    }
}
