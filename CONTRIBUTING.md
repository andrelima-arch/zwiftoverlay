# Contributing to Cycling Overlay / Contribuindo com o Cycling Overlay

Thank you for your interest in contributing! This guide covers development setup, conventions, and how to submit changes.

Obrigado pelo interesse em contribuir! Este guia cobre setup de desenvolvimento, convenções e como enviar mudanças.

---

## Table of Contents / Sumário

- [Development Setup / Setup de Desenvolvimento](#development-setup--setup-de-desenvolvimento)
- [Project Structure / Estrutura do Projeto](#project-structure--estrutura-do-projeto)
- [Running Tests / Rodando Testes](#running-tests--rodando-testes)
- [Code Style / Estilo de Código](#code-style--estilo-de-código)
- [Adding Translations / Adicionando Traduções](#adding-translations--adicionando-traduções)
- [Security / Segurança](#security--segurança)
- [Submitting Changes / Enviando Mudanças](#submitting-changes--enviando-mudanças)
- [Reporting Bugs / Reportando Bugs](#reporting-bugs--reportando-bugs)

---

## Development Setup / Setup de Desenvolvimento

### English

1. **Clone the repository:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/zwiftoverlay.git
   cd zwiftoverlay
   ```

2. **Install Python 3.11 or newer.** Verify with:

   ```bash
   python --version
   ```

3. **Create a virtual environment** (recommended):

   ```bash
   cd cycling_overlay
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

4. **Install dependencies in editable mode:**

   ```bash
   pip install -e .
   pip install -e ".[dev]"
   ```

5. **Run the app:**

   ```bash
   # From the repository root:
   python run.py

   # Or from the cycling_overlay directory:
   cd cycling_overlay
   python main.py
   ```

### Português

1. **Clone o repositório:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/zwiftoverlay.git
   cd zwiftoverlay
   ```

2. **Instale Python 3.11 ou superior.** Verifique com:

   ```bash
   python --version
   ```

3. **Crie um ambiente virtual** (recomendado):

   ```bash
   cd cycling_overlay
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

4. **Instale dependências em modo editável:**

   ```bash
   pip install -e .
   pip install -e ".[dev]"
   ```

5. **Rode o app:**

   ```bash
   # Da raiz do repositório:
   python run.py

   # Ou a partir do diretório cycling_overlay:
   cd cycling_overlay
   python main.py
   ```

---

## Project Structure / Estrutura do Projeto

```
zwiftoverlay/
├── run.py                          # Launcher with terminal (debug)
├── run.pyw                         # Launcher without terminal (Windows)
├── setup.py                        # Dependency installer
├── README.md                       # Project documentation
├── CONTRIBUTING.md                 # This file
├── docs/
│   ├── user-guide.md               # User guide (EN + PT)
│   ├── technical-guide.md          # Technical guide (EN + PT)
│   └── tutorial.md                 # Step-by-step tutorials (EN + PT)
└── cycling_overlay/
    ├── pyproject.toml              # Package configuration and dependencies
    ├── main.py                     # App entry point
    ├── app/
    │   ├── launcher.py             # Dependency check, install, and startup
    │   ├── core/
    │   │   ├── config_manager.py   # Local settings persistence (platformdirs)
    │   │   ├── events.py           # Signal/slot event system
    │   │   ├── state_manager.py    # Aggregated state sent to overlay
    │   │   └── workout_engine.py   # Interval execution and progress
    │   ├── intervals_icu/
    │   │   ├── auth.py             # Intervals.icu authentication
    │   │   ├── client.py           # API client (profile, events, workouts)
    │   │   └── converter.py        # Workout format conversion
    │   ├── models/
    │   │   ├── app_state.py        # Application state model
    │   │   ├── sensor_data.py      # Sensor data model
    │   │   └── workout.py          # Workout and interval models
    │   ├── sensors/
    │   │   ├── ble_parsers.py      # BLE advertisement parsing
    │   │   ├── ble_worker.py       # BLE connection and data reading
    │   │   ├── compatibility.py    # Device identification and fallbacks
    │   │   ├── qz_dircon.py        # QZ DIRCON protocol
    │   │   ├── qz_mqtt.py          # QZ MQTT integration
    │   │   ├── qz_websocket.py     # QZ legacy WebSocket
    │   │   ├── qz_wifi.py          # QZ Wi-Fi/mDNS discovery
    │   │   ├── reader.py           # Sensor data aggregation
    │   │   └── scanner.py          # BLE and network device scanning
    │   ├── ui/
    │   │   ├── i18n.py             # Translations (EN + PT)
    │   │   ├── main_window.py      # Setup window with tabs
    │   │   ├── overlay_window.py   # Always-on-top overlay
    │   │   ├── sensor_selector.py  # Sensor scan, selection, and status
    │   │   └── workout_loader.py   # Workout sources and loading UI
    │   └── workouts/
    │       ├── parser_text.py      # Intervals.icu text parser
    │       └── parser_zwo.py       # Zwift .zwo XML parser
    ├── scripts/
    │   ├── check-sensitive-data.py # Pre-commit sensitive data check
    │   └── clean-local-data.py    # Clean local config and caches
    └── tests/                      # pytest test suite
```

---

## Running Tests / Rodando Testes

### English

Tests use **pytest** and live in `cycling_overlay/tests/`.

```bash
cd cycling_overlay

# Run all tests
.venv/bin/python -m pytest

# Run with verbose output
.venv/bin/python -m pytest -v

# Run a specific test file
.venv/bin/python -m pytest tests/test_workout_loader.py

# Run tests matching a keyword
.venv/bin/python -m pytest -k "sensor"
```

### Português

Testes usam **pytest** e ficam em `cycling_overlay/tests/`.

```bash
cd cycling_overlay

# Rodar todos os testes
.venv/bin/python -m pytest

# Rodar com output verboso
.venv/bin/python -m pytest -v

# Rodar um arquivo de teste específico
.venv/bin/python -m pytest tests/test_workout_loader.py

# Rodar testes que contenham uma palavra-chave
.venv/bin/python -m pytest -k "sensor"
```

**Before submitting a PR, make sure all tests pass.**

**Antes de enviar um PR, certifique-se de que todos os testes passam.**

---

## Code Style / Estilo de Código

### English

- **Python 3.11+** features are allowed (type hints, `match` statements, `X | Y` union types).
- Use **type hints** for function signatures: `def connect(address: str, service: str) -> bool`.
- Follow **PEP 8** naming conventions: `snake_case` for functions and variables, `PascalCase` for classes.
- Keep functions focused and small. Extract helpers when a function exceeds ~40 lines.
- Use `Signal` from `app/core/events.py` for inter-component communication instead of direct coupling.
- Prefer composition over inheritance.
- Do not add print statements in production code. Use the terminal launcher (`run.py`) for debug output.

**Linting:** The project uses `ruff` for linting. Check with:

```bash
cd cycling_overlay
.venv/bin/python -m ruff check .
```

### Português

- Recursos do **Python 3.11+** são permitidos (type hints, `match`, tipos union `X | Y`).
- Use **type hints** nas assinaturas de funções: `def connect(address: str, service: str) -> bool`.
- Siga as convenções de nomenclatura **PEP 8**: `snake_case` para funções e variáveis, `PascalCase` para classes.
- Mantenha funções focadas e pequenas. Extraia helpers quando uma função passar de ~40 linhas.
- Use `Signal` de `app/core/events.py` para comunicação entre componentes em vez de acoplamento direto.
- Prefira composição em vez de herança.
- Não adicione print statements em código de produção. Use o launcher com terminal (`run.py`) para output de debug.

**Linting:** O projeto usa `ruff` para linting. Verifique com:

```bash
cd cycling_overlay
.venv/bin/python -m ruff check .
```

---

## Adding Translations / Adicionando Traduções

### English

All user-facing text goes through the i18n system in `app/ui/i18n.py`.

1. Add a new key to the `TRANSLATIONS` dictionary for both `en` and `pt`:

   ```python
   TRANSLATIONS = {
       "en": {
           "my_feature.title": "My Feature",
       },
       "pt": {
           "my_feature.title": "Minha Funcionalidade",
       },
   }
   ```

2. Use the `t()` helper in UI code:

   ```python
   label = ctk.CTkLabel(frame, text=self._text("my_feature.title"))
   ```

3. For dynamic values, use format parameters:

   ```python
   self._text("workout.info", title="Endurance", count=12)
   ```

**Rules:**

- Always add both English and Portuguese translations.
- Do not translate data from sensors, APIs, device names, or workout names.
- Use descriptive key names: `sensor.scan`, `loader.no_events`.

### Português

Todo texto visível ao usuário passa pelo sistema i18n em `app/ui/i18n.py`.

1. Adicione uma nova chave no dicionário `TRANSLATIONS` para `en` e `pt`:

   ```python
   TRANSLATIONS = {
       "en": {
           "my_feature.title": "My Feature",
       },
       "pt": {
           "my_feature.title": "Minha Funcionalidade",
       },
   }
   ```

2. Use o helper `t()` no código da UI:

   ```python
   label = ctk.CTkLabel(frame, text=self._text("my_feature.title"))
   ```

3. Para valores dinâmicos, use parâmetros de formatação:

   ```python
   self._text("workout.info", title="Endurance", count=12)
   ```

**Regras:**

- Sempre adicione traduções em inglês e português.
- Não traduza dados de sensores, APIs, nomes de dispositivos ou nomes de treinos.
- Use nomes de chave descritivos: `sensor.scan`, `loader.no_events`.

---

## Security / Segurança

### English

- **Never commit `config.json`** or any file containing API keys, passwords, or credentials.
- **Never log sensitive data** (API keys, MQTT passwords) to stdout or log files.
- The `.gitignore` already excludes `config.json`, `.env`, `*.local.json`, and `*.log`.
- Before pushing, run the sensitive data check script:

  ```bash
  cd cycling_overlay
  python scripts/check-sensitive-data.py
  ```

- Review your diff before committing: `git diff --staged`.

### Português

- **Nunca commite `config.json`** ou qualquer arquivo contendo API keys, senhas ou credenciais.
- **Nunca logue dados sensíveis** (API keys, senhas MQTT) no stdout ou arquivos de log.
- O `.gitignore` já exclui `config.json`, `.env`, `*.local.json` e `*.log`.
- Antes de fazer push, rode o script de verificação de dados sensíveis:

  ```bash
  cd cycling_overlay
  python scripts/check-sensitive-data.py
  ```

- Revise seu diff antes de commitar: `git diff --staged`.

---

## Submitting Changes / Enviando Mudanças

### English

1. **Fork** the repository and create a feature branch:

   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make small, focused commits.** Each commit should do one thing.

3. **Write tests** for new functionality. Update existing tests when behavior changes.

4. **Run all tests** before pushing:

   ```bash
   cd cycling_overlay
   .venv/bin/python -m pytest
   ```

5. **Run linting:**

   ```bash
   .venv/bin/python -m ruff check .
   ```

6. **Push and open a Pull Request** with a clear description of what changed and why.

7. **Describe how to test** your changes manually (e.g., "Connect a BLE heart rate sensor and verify the overlay shows BPM").

### Português

1. **Faça fork** do repositório e crie uma branch de feature:

   ```bash
   git checkout -b feature/minha-nova-feature
   ```

2. **Faça commits pequenos e focados.** Cada commit deve fazer uma coisa.

3. **Escreva testes** para funcionalidades novas. Atualize testes existentes quando o comportamento mudar.

4. **Rode todos os testes** antes de fazer push:

   ```bash
   cd cycling_overlay
   .venv/bin/python -m pytest
   ```

5. **Rode linting:**

   ```bash
   .venv/bin/python -m ruff check .
   ```

6. **Faça push e abra um Pull Request** com descrição clara do que mudou e por quê.

7. **Descreva como testar** suas mudanças manualmente (ex: "Conecte um sensor BLE de frequência cardíaca e verifique se o overlay mostra BPM").

---

## Reporting Bugs / Reportando Bugs

### English

When reporting a bug, include:

- **Python version:** `python --version`
- **Operating system:** Windows 11, Ubuntu 24.04, macOS 15, etc.
- **Steps to reproduce:** What you did, what you expected, what happened.
- **Sensor details:** Device name, type (BLE/QZ), and connection method.
- **Error log:** If the app crashed, attach `~/cycling-overlay-error.log` (remove any credentials first).

### Português

Ao reportar um bug, inclua:

- **Versão do Python:** `python --version`
- **Sistema operacional:** Windows 11, Ubuntu 24.04, macOS 15, etc.
- **Passos para reproduzir:** O que você fez, o que esperava, o que aconteceu.
- **Detalhes do sensor:** Nome do dispositivo, tipo (BLE/QZ) e método de conexão.
- **Log de erro:** Se o app travou, anexe `~/cycling-overlay-error.log` (remova credenciais antes).

---

## Questions? / Dúvidas?

Open an issue on GitHub. We're happy to help.

Abra uma issue no GitHub. Estamos felizes em ajudar.
