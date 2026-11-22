//! Port en Rust de original.py.
//!
//! Compila, pasa los casos obvios, y aun asi no se comporta igual: `int()` de
//! Python acepta separadores `_`, espacios internos y enteros de cualquier
//! tamano. `parse::<i32>()` de Rust no acepta nada de eso.
//!
//! Ese es exactamente el fallo que una migracion real comete y que los tests
//! escritos a mano no ven.

use std::io::{self, Read};

fn parse(expr: &str) -> Result<Vec<i32>, String> {
    let value = expr.trim();
    if value.is_empty() {
        return Err("expresion vacia".to_string());
    }
    if let Some(rest) = value.strip_prefix("*/") {
        let step: i32 = rest.parse().map_err(|_| "paso invalido".to_string())?;
        if step <= 0 {
            return Err("el paso debe ser positivo".to_string());
        }
        return Ok((0..60).step_by(step as usize).collect());
    }
    if let Some((left, right)) = value.split_once('-') {
        let start: i32 = left.parse().map_err(|_| "rango invalido".to_string())?;
        let end: i32 = right.parse().map_err(|_| "rango invalido".to_string())?;
        if start > end {
            return Err("rango invertido".to_string());
        }
        return Ok((start..=end).collect());
    }
    let only: i32 = value.parse().map_err(|_| "numero invalido".to_string())?;
    Ok(vec![only])
}

fn main() {
    let mut input = String::new();
    if io::stdin().read_to_string(&mut input).is_err() {
        std::process::exit(1);
    }
    match parse(&input) {
        Ok(values) => {
            let rendered: Vec<String> = values.iter().map(|v| v.to_string()).collect();
            print!("{}", rendered.join(","));
        }
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
    fn paso() {
        assert_eq!(parse("*/15").unwrap(), vec![0, 15, 30, 45]);
    }

    #[test]
    fn rango() {
        assert_eq!(parse("5-9").unwrap(), vec![5, 6, 7, 8, 9]);
    }

    #[test]
    fn paso_cero_falla() {
        assert!(parse("*/0").is_err());
    }
}
