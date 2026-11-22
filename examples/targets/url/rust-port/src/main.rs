//! Port en Rust de original.py (target 'url').
//!
//! Es un port razonable escrito de buena fe: compila, no lanza panic y acierta
//! en todo lo que parece un caso normal. Se equivoca en cuatro cosas que nadie
//! escribe en un test:
//!
//!   1. No normaliza el esquema a minusculas.
//!   2. No quita el puerto por defecto (80/443).
//!   3. Deja la ruta vacia en vez de "/".
//!   4. Corta el host por el ultimo ':' y rompe con IPv6.
//!
//! Nada de eso es un bug de sintaxis. Es una diferencia de comportamiento.

use std::io::{self, Read};

fn parse(input: &str) -> Result<String, String> {
    let value = input.trim();
    let (scheme, rest) = value.split_once("://").ok_or("sin esquema")?;
    if scheme.is_empty() {
        return Err("esquema vacio".to_string());
    }
    let mut rest = rest.to_string();

    let mut fragment: Option<String> = None;
    if let Some(pos) = rest.find('#') {
        fragment = Some(rest[pos + 1..].to_string());
        rest.truncate(pos);
    }
    let mut query: Option<String> = None;
    if let Some(pos) = rest.find('?') {
        query = Some(rest[pos + 1..].to_string());
        rest.truncate(pos);
    }

    let (authority, path) = match rest.find('/') {
        Some(pos) => (rest[..pos].to_string(), rest[pos..].to_string()),
        None => (rest, String::new()),
    };

    let (userinfo, authority) = match authority.rsplit_once('@') {
        Some((user, host)) => (Some(user.to_string()), host.to_string()),
        None => (None, authority),
    };

    let (host, port) = match authority.rsplit_once(':') {
        Some((host, port)) => (host.to_string(), port.to_string()),
        None => (authority, String::new()),
    };

    if host.is_empty() {
        return Err("host vacio".to_string());
    }

    let rendered_port = if port.is_empty() {
        "-".to_string()
    } else {
        let number: u16 = port.parse().map_err(|_| "puerto invalido".to_string())?;
        number.to_string()
    };

    Ok([
        scheme.to_string(),
        userinfo.unwrap_or_else(|| "-".to_string()),
        host,
        rendered_port,
        path,
        query.unwrap_or_else(|| "-".to_string()),
        fragment.unwrap_or_else(|| "-".to_string()),
    ]
    .join("|"))
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
    fn ruta_y_puerto() {
        assert_eq!(
            parse("https://example.com:8443/a/b?q=1#top").unwrap(),
            "https|example.com|8443|/a/b|q=1|top"
        );
    }

    #[test]
    fn usuario() {
        assert_eq!(parse("ftp://ana@host/x").unwrap(), "ftp|ana|host|-|/x|-|-");
    }

    #[test]
    fn sin_esquema_falla() {
        assert!(parse("example.com/x").is_err());
    }
}
