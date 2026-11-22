//! Port en Rust de original.py (target 'toml').
//!
//! Port honesto: cubre el 100% del corpus normal. Se rompe donde el lenguaje
//! de destino no llega:
//!
//!   1. `i64` desborda con un entero grande que Python maneja sin problema.
//!   2. Al quitar los guiones bajos sin mirar donde estan, acepta `1__0` que
//!      el original rechaza (falla en la direccion contraria).
//!   3. No implementa el escape `\uXXXX`.
//!   4. Solo admite arrays de enteros.

use std::io::{self, Read};

fn strip_comment(line: &str) -> String {
    let mut out = String::new();
    let mut inside = false;
    let mut escaped = false;
    for ch in line.chars() {
        if inside {
            out.push(ch);
            if escaped {
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                inside = false;
            }
        } else if ch == '"' {
            inside = true;
            out.push(ch);
        } else if ch == '#' {
            break;
        } else {
            out.push(ch);
        }
    }
    out
}

fn valid_key(key: &str) -> bool {
    !key.is_empty()
        && key
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '.' | '-'))
}

fn display(text: &str) -> String {
    text.replace('\\', "\\\\").replace('\n', "\\n").replace('\t', "\\t")
}

fn parse_string(text: &str) -> Result<(String, usize), String> {
    let bytes: Vec<char> = text.chars().collect();
    if bytes.first() != Some(&'"') {
        return Err("cadena invalida".to_string());
    }
    let mut out = String::new();
    let mut i = 1;
    while i < bytes.len() {
        let ch = bytes[i];
        if ch == '"' {
            return Ok((out, i + 1));
        }
        if ch == '\\' {
            i += 1;
            if i >= bytes.len() {
                return Err("escape incompleto".to_string());
            }
            match bytes[i] {
                'n' => out.push('\n'),
                't' => out.push('\t'),
                '"' => out.push('"'),
                '\\' => out.push('\\'),
                _ => return Err("escape desconocido".to_string()),
            }
            i += 1;
            continue;
        }
        out.push(ch);
        i += 1;
    }
    Err("cadena sin cerrar".to_string())
}

/// Entero del subconjunto TOML: signo, digitos, guiones bajos entre digitos.
fn parse_int(token: &str) -> Result<i64, String> {
    let cleaned: String = token.chars().filter(|c| *c != '_').collect();
    if cleaned.is_empty() {
        return Err("entero invalido".to_string());
    }
    let digits = cleaned.trim_start_matches(['+', '-']);
    if digits.is_empty() || !digits.chars().all(|c| c.is_ascii_digit()) {
        return Err("entero invalido".to_string());
    }
    if digits.len() > 1 && digits.starts_with('0') {
        return Err("cero a la izquierda".to_string());
    }
    cleaned
        .parse::<i64>()
        .map_err(|_| "entero fuera de rango".to_string())
}

fn parse_array(text: &str) -> Result<(Vec<String>, usize), String> {
    let chars: Vec<char> = text.chars().collect();
    let mut items: Vec<String> = Vec::new();
    let mut i = 1;
    loop {
        while i < chars.len() && (chars[i] == ' ' || chars[i] == '\t') {
            i += 1;
        }
        if i >= chars.len() {
            return Err("array sin cerrar".to_string());
        }
        if chars[i] == ']' {
            return Ok((items, i + 1));
        }
        if chars[i] == '"' {
            return Err("array de cadenas no soportado".to_string());
        }
        let start = i;
        while i < chars.len() && chars[i] != ',' && chars[i] != ']' {
            i += 1;
        }
        let token: String = chars[start..i].iter().collect();
        items.push(parse_int(token.trim())?.to_string());
        while i < chars.len() && (chars[i] == ' ' || chars[i] == '\t') {
            i += 1;
        }
        if i >= chars.len() {
            return Err("array sin cerrar".to_string());
        }
        if chars[i] == ',' {
            i += 1;
            continue;
        }
        if chars[i] == ']' {
            return Ok((items, i + 1));
        }
        return Err("separador invalido".to_string());
    }
}

fn parse(line: &str) -> Result<String, String> {
    let clean = strip_comment(line).trim().to_string();
    if clean.is_empty() {
        return Err("linea vacia".to_string());
    }
    let (key, value) = clean.split_once('=').ok_or("falta el signo igual")?;
    let key = key.trim();
    if !valid_key(key) {
        return Err("clave invalida".to_string());
    }
    let value = value.trim();
    if value.is_empty() {
        return Err("valor vacio".to_string());
    }

    if value.starts_with('"') {
        let (text, used) = parse_string(value)?;
        let tail: String = value.chars().skip(used).collect();
        if !tail.trim().is_empty() {
            return Err("texto de sobra".to_string());
        }
        return Ok(format!("{}|string|{}", key, display(&text)));
    }

    if value == "true" || value == "false" {
        return Ok(format!("{}|bool|{}", key, value));
    }

    if value.starts_with('[') {
        let (items, used) = parse_array(value)?;
        let tail: String = value.chars().skip(used).collect();
        if !tail.trim().is_empty() {
            return Err("texto de sobra".to_string());
        }
        return Ok(format!("{}|array|{}", key, items.join(",")));
    }

    let number = parse_int(value)?;
    Ok(format!("{}|int|{}", key, number))
}

fn main() {
    let mut input = String::new();
    if io::stdin().read_to_string(&mut input).is_err() {
        std::process::exit(1);
    }
    match parse(&input) {
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
    fn entero() {
        assert_eq!(parse("puerto = 8080").unwrap(), "puerto|int|8080");
    }

    #[test]
    fn cadena() {
        assert_eq!(parse("nombre = \"hola\"").unwrap(), "nombre|string|hola");
    }

    #[test]
    fn array() {
        assert_eq!(parse("ids = [1, 2, 3]").unwrap(), "ids|array|1,2,3");
    }
}
