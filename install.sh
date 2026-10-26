#!/bin/sh
set -eu

REPO="Ekomjah/doxify"
DEFAULT_VERSION="0.1.0"
UV_INSTALL_URL="https://astral.sh/uv/install.sh"

usage() {
    cat <<'EOF'
Doxify installer

Usage:
  sh install.sh [--version VERSION] [--help]

Options:
  --version VERSION   Doxify release to install (default: 0.1.0)
  --help              Show this help

Environment:
  DOXIFY_VERSION      Doxify release to install
  DOXIFY_SOURCE_DIR   Install from a local source tree (maintainer testing)
  UV_TOOL_DIR         Override uv's tool environment directory
  UV_TOOL_BIN_DIR     Override uv's executable directory

The installer uses uv to create an isolated per-user install.
It does not use sudo, install Ollama, or download a model.
EOF
}

log() {
    printf '%s\n' "doxify-install: $*"
}

fail() {
    printf '%s\n' "doxify-install: error: $*" >&2
    exit 1
}

download_file() {
    url=$1
    dest=$2
    attempts=0
    while [ "$attempts" -lt 3 ]; do
        if curl -fsSL --http1.1 "$url" -o "$dest"; then
            return 0
        fi
        attempts=$((attempts + 1))
        if [ "$attempts" -lt 3 ]; then
            log "Download failed; retrying (${attempts}/3)..."
            sleep 2
        fi
    done
    return 1
}

VERSION="${DOXIFY_VERSION:-$DEFAULT_VERSION}"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            [ "$#" -ge 2 ] || fail "--version requires a value"
            VERSION="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            fail "unknown argument: $1 (use --help)"
            ;;
    esac
done

VERSION="${VERSION#v}"
[ -n "$VERSION" ] || fail "version cannot be empty"
case "$VERSION" in
    *[!0-9A-Za-z._-]*)
        fail "invalid version: $VERSION"
        ;;
esac

case "$(uname -s)" in
    Linux*)
        if grep -qi microsoft /proc/version 2>/dev/null; then
            log "Detected WSL."
        fi
        ;;
    Darwin*)
        ;;
    MINGW*|MSYS*|CYGWIN*)
        fail "native Windows is not supported; use WSL or a Linux shell"
        ;;
    *)
        fail "unsupported operating system: $(uname -s)"
        ;;
esac

command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v git >/dev/null 2>&1 || fail "git is required"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

if [ -n "${DOXIFY_SOURCE_DIR:-}" ]; then
    source_dir=$(cd "$DOXIFY_SOURCE_DIR" && pwd -P)
    [ -f "$source_dir/pyproject.toml" ] || fail "DOXIFY_SOURCE_DIR does not contain pyproject.toml"
    log "Installing from local source: $source_dir"
else
    command -v tar >/dev/null 2>&1 || fail "tar is required"
    archive="$tmp_dir/doxify-${VERSION}.tar.gz"
    url="https://github.com/${REPO}/archive/refs/tags/v${VERSION}.tar.gz"
    log "Downloading Doxify v${VERSION}..."
    download_file "$url" "$archive" || fail "could not download $url"
    tar -xzf "$archive" -C "$tmp_dir" || fail "downloaded archive was invalid"
    source_dir="$tmp_dir/doxify-${VERSION}"
    [ -f "$source_dir/pyproject.toml" ] || fail "downloaded archive did not contain a Doxify source tree"
fi

if command -v uv >/dev/null 2>&1; then
    uv_bin=$(command -v uv)
elif [ -x "$HOME/.local/bin/uv" ]; then
    uv_bin="$HOME/.local/bin/uv"
else
    command -v tar >/dev/null 2>&1 || fail "tar is required to install uv"
    log "uv not found; installing it to $HOME/.local/bin"
    download_file "$UV_INSTALL_URL" "$tmp_dir/uv-install.sh" || fail "could not download uv"
    UV_NO_MODIFY_PATH=1 sh "$tmp_dir/uv-install.sh"
    if [ -x "$HOME/.local/bin/uv" ]; then
        uv_bin="$HOME/.local/bin/uv"
    else
        uv_bin=$(command -v uv || true)
    fi
    [ -n "$uv_bin" ] || fail "uv installation did not produce a uv executable"
fi

log "Installing Doxify ${VERSION} with uv..."
"$uv_bin" tool install --force --python 3.12 "$source_dir"

tool_bin="${UV_TOOL_BIN_DIR:-$("$uv_bin" tool dir --bin)}"
doxify_bin="$tool_bin/doxify"
if [ ! -x "$doxify_bin" ]; then
    doxify_bin=$(command -v doxify || true)
fi
[ -n "$doxify_bin" ] || fail "Doxify was installed but the doxify executable was not found"

installed_version=$("$doxify_bin" --version)
if [ -z "${DOXIFY_SOURCE_DIR:-}" ] && [ "$installed_version" != "$VERSION" ]; then
    fail "expected Doxify ${VERSION}, but the installed version is ${installed_version}"
fi
log "Installed Doxify ${installed_version}"
"$doxify_bin" self-check --json >/dev/null || fail "Doxify self-check failed"

case ":$PATH:" in
    *":$tool_bin:"*) ;;
    *) log "Add $tool_bin to PATH if 'doxify' is not found in a new shell." ;;
esac

cat <<EOF

Doxify is ready.

  doxify --version
  doxify self-check
  doxify scan /path/to/repo

For the full local compile:
  ollama serve
  ollama pull gemma3:1b
  doxify readme /path/to/repo

EOF
