# Guia técnico / Technical Guide

## Português

### Visão geral

O Cycling Overlay é um aplicativo Python empacotado pelo diretório
`cycling_overlay`. A interface usa `customtkinter` e o overlay usa `tkinter`.
O `pyproject.toml` declara o comando `cycling-overlay`, além dos launchers de
raiz `setup.py`, `run.py` e `run.pyw`. No código atual, os launchers de raiz são
o caminho de execução verificado.

### Estrutura principal

- `cycling_overlay/main.py`: cria a aplicação, conecta sinais e coordena
  janela principal, sensores, estado, motor de treino e overlay.
- `app/ui/main_window.py`: janela de configuração, perfil, abas de treino,
  sensores e QZ.
- `app/ui/overlay_window.py`: overlay sempre no topo exibido durante o treino.
- `app/ui/workout_loader.py`: fontes de treino, Intervals.icu e `.zwo`.
- `app/ui/sensor_selector.py`: scan, seleção e status visual dos sensores.
- `app/core/config_manager.py`: persistência local de configurações.
- `app/core/workout_engine.py`: execução dos intervalos e progresso.
- `app/core/state_manager.py`: estado agregado enviado ao overlay.
- `app/sensors/`: BLE, QZ WebSocket, QZ Wi-Fi/DIRCON e QZ MQTT.
- `app/intervals_icu/`: cliente, autenticação de perfil e conversão de treinos.
- `app/workouts/`: parsers de texto e arquivos `.zwo`.

### Fluxo de execução

1. `CyclingOverlayApp` inicializa `ConfigManager`, `StateManager`,
   `WorkoutEngine`, `SensorReader`, `OverlayWindow` e `MainWindow`.
2. `MainWindow` salva preferências, seleciona treino e sensores, e emite sinais
   para iniciar/parar treino ou trocar idioma.
3. `SensorReader` agrega dados vindos de BLE, QZ Wi-Fi/DIRCON, QZ MQTT e QZ
   WebSocket.
4. `WorkoutEngine` recebe o treino selecionado e avança intervalos conforme
   tempo, pausa e dados de sensores.
5. `StateManager` combina perfil, sensores e intervalo atual.
6. `OverlayWindow` renderiza o estado final para o usuário.

### Configuração

`ConfigManager` usa `platformdirs.user_config_dir("cycling-overlay")` para criar
o diretório de configuração do usuário e salvar `config.json`.

Campos persistidos incluem:

- `ui_language`: `en` ou `pt`, com fallback para `en`.
- Perfil manual e Intervals.icu: peso, FTP e fonte ativa.
- `intervals_api_key` e `intervals_athlete_id`.
- Última pasta `.zwo`.
- Posição do overlay.
- Sensores selecionados e dispositivos BLE conhecidos.
- Configurações QZ WebSocket, QZ Wi-Fi/DIRCON e QZ MQTT.

Esse arquivo é local e não deve ser versionado. Ele pode conter segredos.

### Internacionalização

Textos fixos da interface ficam em `app/ui/i18n.py`. O helper `t(language, key,
**params)` resolve a tradução e `normalize_language` aplica fallback. O idioma
padrão é inglês.

A tradução cobre textos criados pela interface. Dados vindos de APIs, sensores,
nomes de dispositivos, nomes de treinos e mensagens externas permanecem como
foram recebidos.

### Sensores e integrações

O app usa `bleak` para BLE e reconhece serviços de frequência cardíaca,
potência, cadência/velocidade e FTMS. A camada de compatibilidade adiciona
identificação e fallbacks para equipamentos compatíveis.

QZ pode ser usado por:

- Wi-Fi/DIRCON com descoberta mDNS via `zeroconf`.
- Conexão DIRCON manual por host e porta.
- MQTT via `paho-mqtt`.
- WebSocket interno legado, mantido na camada de sensores.

Intervals.icu usa `requests` com autenticação básica `("API_KEY", api_key)` e
busca perfil, eventos próximos e documentos de treino.

### Comandos úteis

Instalar dependências em modo editável:

```bash
python setup.py
```

Executar com terminal:

```bash
python run.py
```

Executar sem terminal no Windows:

```bash
python run.pyw
```

Executar direto a partir do diretório do pacote:

```bash
cd cycling_overlay
python main.py
```

O comando `cycling-overlay` está declarado em `pyproject.toml`, mas aponta para
`app.main:main`. Como o código atual possui `main.py` no diretório
`cycling_overlay`, valide esse entrypoint antes de depender dele em empacotamento
ou distribuição.

Executar testes:

```bash
cd cycling_overlay
.venv/bin/python -m pytest
```

### Segurança antes de publicar

Antes de enviar ao GitHub, verifique se arquivos locais com credenciais não
foram adicionados:

- `config.json` de usuário.
- Logs de erro com API Key, Athlete ID ou senha MQTT.
- Ambientes virtuais, caches e artefatos locais.

O diretório atual não possui `.git`; inicializar ou conectar o repositório deve
ser feito separadamente antes do primeiro push.

## English

### Overview

Cycling Overlay is a Python application packaged under the `cycling_overlay`
directory. The setup UI uses `customtkinter`, and the overlay uses `tkinter`.
`pyproject.toml` declares the `cycling-overlay` command, in addition to the root
launchers `setup.py`, `run.py`, and `run.pyw`. In the current code, the root
launchers are the verified startup path.

### Main Structure

- `cycling_overlay/main.py`: creates the app, connects signals, and coordinates
  the main window, sensors, state, workout engine, and overlay.
- `app/ui/main_window.py`: setup window, profile, workout, sensor, and QZ tabs.
- `app/ui/overlay_window.py`: always-on-top overlay displayed during workouts.
- `app/ui/workout_loader.py`: workout sources, Intervals.icu, and `.zwo` files.
- `app/ui/sensor_selector.py`: scan, selection, and visual sensor status.
- `app/core/config_manager.py`: local settings persistence.
- `app/core/workout_engine.py`: interval execution and progress.
- `app/core/state_manager.py`: aggregated state sent to the overlay.
- `app/sensors/`: BLE, QZ WebSocket, QZ Wi-Fi/DIRCON, and QZ MQTT.
- `app/intervals_icu/`: client, profile sync, and workout conversion.
- `app/workouts/`: text and `.zwo` parsers.

### Runtime Flow

1. `CyclingOverlayApp` initializes `ConfigManager`, `StateManager`,
   `WorkoutEngine`, `SensorReader`, `OverlayWindow`, and `MainWindow`.
2. `MainWindow` saves preferences, selects workout and sensors, and emits
   signals to start/stop workouts or change the UI language.
3. `SensorReader` aggregates data from BLE, QZ Wi-Fi/DIRCON, QZ MQTT, and QZ
   WebSocket.
4. `WorkoutEngine` receives the selected workout and advances intervals based on
   time, pauses, and sensor data.
5. `StateManager` combines profile, sensors, and current interval.
6. `OverlayWindow` renders the final state for the user.

### Configuration

`ConfigManager` uses `platformdirs.user_config_dir("cycling-overlay")` to create
the user's configuration directory and save `config.json`.

Persisted fields include:

- `ui_language`: `en` or `pt`, with fallback to `en`.
- Manual and Intervals.icu profile: weight, FTP, and active source.
- `intervals_api_key` and `intervals_athlete_id`.
- Last `.zwo` folder.
- Overlay position.
- Selected sensors and known BLE devices.
- QZ WebSocket, QZ Wi-Fi/DIRCON, and QZ MQTT settings.

This file is local and must not be versioned. It may contain secrets.

### Internationalization

Fixed interface text lives in `app/ui/i18n.py`. The `t(language, key, **params)`
helper resolves translations, and `normalize_language` applies fallback. The
default language is English.

Translation covers text created by the interface. API data, sensor data, device
names, workout names, and external messages remain unchanged.

### Sensors and Integrations

The app uses `bleak` for BLE and recognizes heart rate, power, cadence/speed,
and FTMS services. The compatibility layer adds identification and fallback
parsing for compatible equipment.

QZ can be used through:

- Wi-Fi/DIRCON with mDNS discovery through `zeroconf`.
- Manual DIRCON connection by host and port.
- MQTT through `paho-mqtt`.
- Legacy internal WebSocket support kept in the sensor layer.

Intervals.icu uses `requests` with basic authentication `("API_KEY", api_key)`
and fetches profile, upcoming events, and workout documents.

### Useful Commands

Install dependencies in editable mode:

```bash
python setup.py
```

Run with terminal:

```bash
python run.py
```

Run without terminal on Windows:

```bash
python run.pyw
```

Run directly from the package directory:

```bash
cd cycling_overlay
python main.py
```

The `cycling-overlay` command is declared in `pyproject.toml`, but it points to
`app.main:main`. Since the current code has `main.py` under the `cycling_overlay`
directory, validate this entrypoint before relying on it for packaging or
distribution.

Run tests:

```bash
cd cycling_overlay
.venv/bin/python -m pytest
```

### Security Before Publishing

Before pushing to GitHub, verify that local credential files were not added:

- User `config.json`.
- Error logs containing API Key, Athlete ID, or MQTT password.
- Virtual environments, caches, and local artifacts.

The current directory does not contain `.git`; initializing or connecting the
repository must be handled separately before the first push.
