#!/usr/bin/env bash
# Validate and install the macOS development prerequisites for these dotfiles.
# Dry-run by default. --apply performs the supported changes.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap.sh [--dry-run|--apply] [--with-apps]

  --dry-run     Check only and report missing prerequisites (default).
  --apply       Install or fix supported missing prerequisites.
  --with-apps   Also install the optional GUI apps in Brewfile.apps.
  -h, --help    Show this help.

Personal state (Git identity, GitHub auth, macOS preferences) is checked but
never written automatically.
EOF
}

apply=false
with_apps=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) ;;
    --apply) apply=true ;;
    --with-apps) with_apps=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

# Resolve the repository root through possible symlinks.
script_path="${BASH_SOURCE[0]}"
while [[ -L "$script_path" ]]; do
  script_parent="$(cd -- "$(dirname -- "$script_path")" && pwd -P)"
  script_target="$(readlink "$script_path")"
  [[ "$script_target" = /* ]] || script_target="$script_parent/$script_target"
  script_path="$script_target"
done
repo_dir="$(cd -- "$(dirname -- "$script_path")/.." && pwd -P)"
brewfile="$repo_dir/Brewfile"
apps_brewfile="$repo_dir/Brewfile.apps"

cleanup_paths=()
cleanup() {
  [[ ${#cleanup_paths[@]} -gt 0 ]] || return 0
  for path in "${cleanup_paths[@]}"; do
    rm -rf -- "$path"
  done
}
trap cleanup EXIT

missing=0
section() { printf '\n%s\n' "$*"; }
ok() { printf '  ok    %s\n' "$*"; }
miss() { printf '  miss  %s\n' "$*"; missing=$((missing + 1)); }
info() { printf '  info  %s\n' "$*"; }
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

[[ "$(uname -s)" == Darwin ]] || fail 'This bootstrap supports macOS only.'
[[ -f "$brewfile" ]] || fail "Missing $brewfile"
[[ -f "$apps_brewfile" ]] || fail "Missing $apps_brewfile"

section 'Base tools'
if command -v curl >/dev/null 2>&1; then ok 'curl'; else fail 'curl is required'; fi
if xcode-select -p >/dev/null 2>&1; then
  ok 'Xcode Command Line Tools'
else
  miss 'Xcode Command Line Tools'
  if "$apply"; then
    xcode-select --install >/dev/null 2>&1 || true
    fail 'Requested Xcode Command Line Tools. Finish the installer, then rerun.'
  fi
fi

section 'Homebrew'
if command -v brew >/dev/null 2>&1; then
  ok "Homebrew ($(brew --prefix))"
elif "$apply"; then
  info 'Downloading the official Homebrew installer for inspection'
  installer="$(mktemp)"
  cleanup_paths+=("$installer")
  curl -fsSL --retry 3 https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$installer" \
    || fail 'Could not download the Homebrew installer'
  [[ -s "$installer" ]] || fail 'Downloaded Homebrew installer is empty'
  bash -n "$installer" || fail 'Downloaded Homebrew installer failed a syntax check'
  NONINTERACTIVE=1 /bin/bash "$installer" \
    || fail 'Homebrew installation failed. Install it manually from https://brew.sh and rerun.'
  rm -f -- "$installer"
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
  command -v brew >/dev/null 2>&1 || fail 'Homebrew installed but is not on PATH; open a new shell and rerun.'
  ok "Homebrew ($(brew --prefix))"
else
  miss 'Homebrew (run with --apply, or install from https://brew.sh)'
  info 'Skipping Homebrew package checks until it is installed.'
fi

if command -v brew >/dev/null 2>&1; then
  command -v git >/dev/null 2>&1 || fail 'git is required; install Xcode Command Line Tools first.'

  section 'CLI tools'
  missing_tools=()
  for tool in git jq wget htop gh go pyenv node; do
    command -v "$tool" >/dev/null 2>&1 || missing_tools+=("$tool")
  done
  # macOS Java launchers can exist even when no usable JDK is installed.
  for tool in java javac; do
    if ! command -v "$tool" >/dev/null 2>&1 || ! "$tool" -version >/dev/null 2>&1; then
      missing_tools+=("$tool")
    fi
  done
  if [[ ! -s "$HOME/.nvm/nvm.sh" && ! -d /opt/homebrew/opt/nvm && ! -d /usr/local/opt/nvm ]]; then
    missing_tools+=('nvm')
  fi
  if [[ ${#missing_tools[@]} -gt 0 ]]; then
    miss "CLI tools: ${missing_tools[*]}"
    if "$apply"; then
      info 'Installing CLI tools from Brewfile (this can take a while)'
      brew bundle install --file "$brewfile" || fail "brew bundle failed for $brewfile"
      ok 'CLI tools installed'
    fi
  else
    ok 'CLI tools'
  fi
fi

section 'GUI applications'
missing_apps=()
check_gui_app() {
  local name="$1" app_path="$2"
  if [[ -d "$app_path" ]]; then
    ok "$name"
  else
    miss "$name"
    missing_apps+=("$name")
  fi
}
check_gui_app iterm2 '/Applications/iTerm.app'
check_gui_app maccy '/Applications/Maccy.app'
check_gui_app visual-studio-code '/Applications/Visual Studio Code.app'
check_gui_app postman '/Applications/Postman.app'
check_gui_app intellij-idea-ce '/Applications/IntelliJ IDEA CE.app'
check_gui_app docker '/Applications/Docker.app'
if command -v ngrok >/dev/null 2>&1; then
  ok 'ngrok'
else
  miss 'ngrok'
  missing_apps+=('ngrok')
fi
if [[ ${#missing_apps[@]} -gt 0 ]]; then
  if "$apply" && "$with_apps"; then
    info 'Installing GUI apps from Brewfile.apps (this can take a while)'
    brew bundle install --file "$apps_brewfile" || fail "brew bundle failed for $apps_brewfile"
    ok 'GUI apps installed'
  else
    info 'Install missing GUI apps with: scripts/bootstrap.sh --apply --with-apps'
  fi
fi

section 'Shell'
shell_path="${SHELL:-}"
if [[ "$shell_path" == */zsh ]]; then
  ok "Login shell ($shell_path)"
else
  info "Login shell is '${shell_path:-unknown}'; run: chsh -s /bin/zsh"
fi

omz="$HOME/.oh-my-zsh"
if [[ -f "$omz/oh-my-zsh.sh" ]]; then
  ok 'Oh My Zsh'
else
  miss 'Oh My Zsh'
  if "$apply"; then
    if [[ -e "$omz" ]]; then
      fail "$omz exists but is incomplete; inspect it before rerunning"
    fi
    git clone --depth 1 https://github.com/ohmyzsh/ohmyzsh.git "$omz" || fail 'Could not clone Oh My Zsh'
    ok 'Oh My Zsh installed'
  fi
fi

zsh_custom="${ZSH_CUSTOM:-$omz/custom}"
for plugin in zsh-autosuggestions zsh-syntax-highlighting; do
  destination="$zsh_custom/plugins/$plugin"
  if [[ -d "$destination" ]]; then
    ok "$plugin"
  else
    miss "$plugin"
    if "$apply"; then
      if [[ -e "$destination" ]]; then
        fail "$destination exists but is not a directory; inspect it before rerunning"
      fi
      mkdir -p "$zsh_custom/plugins"
      git clone --depth 1 "https://github.com/zsh-users/$plugin.git" "$destination" \
        || fail "Could not clone $plugin"
      ok "$plugin installed"
    fi
  fi
done

section 'Terminal integration'
iterm_integration="$HOME/.iterm2_shell_integration.zsh"
if [[ -f "$iterm_integration" ]]; then
  ok 'iTerm2 shell integration'
else
  miss 'iTerm2 shell integration'
  if "$apply"; then
    command -v zsh >/dev/null 2>&1 || fail 'zsh is required for shell integration'
    downloaded="$(mktemp)"
    cleanup_paths+=("$downloaded")
    curl -fsSL --retry 3 https://iterm2.com/shell_integration/zsh -o "$downloaded" \
      || fail 'Could not download iTerm2 shell integration'
    [[ -s "$downloaded" ]] || fail 'Downloaded iTerm2 integration is empty'
    zsh -n "$downloaded" || fail 'Downloaded iTerm2 integration failed a syntax check'
    mv -- "$downloaded" "$iterm_integration"
    ok 'iTerm2 shell integration installed'
  fi
fi

font_dir="$HOME/Library/Fonts"
fonts=(
  'Meslo LG M Regular for Powerline.ttf'
  'Meslo LG M Bold for Powerline.ttf'
  'Meslo LG M Italic for Powerline.ttf'
  'Meslo LG M Bold Italic for Powerline.ttf'
)
fonts_missing=false
for font in "${fonts[@]}"; do
  [[ -f "$font_dir/$font" ]] || fonts_missing=true
done
if "$fonts_missing"; then
  miss 'Meslo LG M Powerline fonts'
  if "$apply"; then
    font_checkout="$(mktemp -d)"
    cleanup_paths+=("$font_checkout")
    git clone --depth 1 https://github.com/powerline/fonts.git "$font_checkout/fonts" \
      || fail 'Could not clone powerline fonts'
    mkdir -p "$font_dir"
    for font in "${fonts[@]}"; do
      source_font="$font_checkout/fonts/Meslo Slashed/$font"
      [[ -f "$source_font" ]] || fail "Missing font in powerline repository: $font"
      cp -- "$source_font" "$font_dir/$font"
    done
    ok 'Meslo LG M Powerline fonts installed'
  fi
else
  ok 'Meslo LG M Powerline fonts'
fi

section 'Editors'
code_app='/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'
if command -v code >/dev/null 2>&1; then
  ok 'VS Code CLI'
elif [[ -x "$code_app" ]]; then
  miss 'VS Code CLI'
  if "$apply"; then
    mkdir -p "$HOME/.local/bin"
    ln -sf -- "$code_app" "$HOME/.local/bin/code"
    ok 'VS Code CLI linked into ~/.local/bin'
  fi
else
  miss 'VS Code (install it with --with-apps or from https://code.visualstudio.com)'
fi

section 'Personal state (read-only)'
if command -v git >/dev/null 2>&1; then
  if git config --includes --global user.name >/dev/null 2>&1 \
    && git config --includes --global user.email >/dev/null 2>&1; then
    ok 'Git identity'
  else
    miss 'Git identity (copy git/gitconfig.local.example to ~/.gitconfig.local and fill it in)'
  fi
fi
if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    ok 'GitHub CLI authentication'
  else
    miss 'GitHub CLI authentication (run: gh auth login)'
  fi
else
  info 'GitHub CLI not installed; skipping authentication check.'
fi

section 'Summary'
if "$apply"; then
  printf 'Bootstrap actions finished. Rerun without --apply to verify.\n'
  printf 'Next: ./install.sh --apply\n'
  exit 0
fi
if [[ "$missing" -eq 0 ]]; then
  printf 'All checks passed.\n'
  exit 0
fi
printf '%d check(s) need attention.\n' "$missing"
printf 'Run %s --apply to install or fix supported items.\n' "$0"
exit 1
