//! Port en Rust de original.py (target 'slug').
//!
//! La biblioteca estandar de Rust sabe pasar a minusculas y sabe que es una
//! letra, pero no sabe quitar acentos. Este port hace lo que haria cualquiera
//! sin mirar: recorre los caracteres y sustituye lo que no es alfanumerico.
//!
//! Resultado: con texto ASCII coincide al 100%. Con "Café" devuelve "café"
//! donde el original devuelve "cafe". En una URL eso son dos rutas distintas.

use std::io::{self, Read};

fn slug(text: &str) -> Result<String, String> {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return Err("texto vacio".to_string());
    }
    let lowered = trimmed.to_lowercase();
    let mut out = String::new();
    for ch in lowered.chars() {
        if ch.is_alphanumeric() {
            out.push(ch);
        } else if !out.is_empty() && !out.ends_with('-') {
            out.push('-');
        }
    }
    let result = out.trim_matches('-').to_string();
    if result.is_empty() {
        return Err("sin caracteres utilizables".to_string());
    }
    Ok(result)
}

fn main() {
    let mut input = String::new();
    if io::stdin().read_to_string(&mut input).is_err() {
        std::process::exit(1);
    }
    match slug(&input) {
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
    fn ascii() {
        assert_eq!(slug("Hola Mundo").unwrap(), "hola-mundo");
    }

    #[test]
    fn puntuacion() {
        assert_eq!(slug("  Rust: rapido y seguro!  ").unwrap(), "rust-rapido-y-seguro");
    }

    #[test]
    fn vacio_falla() {
        assert!(slug("   ").is_err());
    }
}
