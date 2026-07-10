#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"

install_with_apt() {
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends build-essential openjdk-17-jdk
  else
    apt-get update
    apt-get install -y --no-install-recommends build-essential openjdk-17-jdk
  fi
}

if ! command -v g++ >/dev/null 2>&1 || ! command -v javac >/dev/null 2>&1; then
  install_with_apt
fi

# Some CNB images expose python3 but not python. Add a workspace-local alias
# without overwriting anything the user may have created.
mkdir -p /workspace/.local/bin
if ! command -v python >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1 && [ ! -e /workspace/.local/bin/python ]; then
  ln -s "$(command -v python3)" /workspace/.local/bin/python
fi

export PATH="/workspace/.local/bin:/workspace/.venv/bin:${PATH}"

shell_rc="${HOME}/.zshrc"
path_line='export PATH="/workspace/.local/bin:/workspace/.venv/bin:${PATH}"'
java_home_line='export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"'

if [ -d "${HOME}" ] && [ -w "${HOME}" ]; then
  touch "${shell_rc}"
  grep -Fqx "${path_line}" "${shell_rc}" || printf '\n%s\n' "${path_line}" >> "${shell_rc}"
  grep -Fqx "${java_home_line}" "${shell_rc}" || printf '%s\n' "${java_home_line}" >> "${shell_rc}"
fi

python --version || python3 --version
g++ --version
java -version
javac -version
