# Cycling Overlay

<p align="center">
  <strong>Indoor cycling workout overlay with BLE sensors, QZ/Wi-Fi, QZ/MQTT, Intervals.icu, and Zwift <code>.zwo</code> files.</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPLv3-green" alt="License GPLv3"></a>
</p>

<p align="center">
  <a href="https://www.buymeacoffee.com/andrelimarch" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" style="height: 40px !important;width: 145px !important;"></a>
  <a href="https://ko-fi.com/E8G020T9M3" target="_blank"><img height="40" style="border:0px;height:40px;" src="https://storage.ko-fi.com/cdn/kofi6.png?v=6" border="0" alt="Buy Me a Coffee at ko-fi.com" /></a>
</p>

---

## Table of Contents

- [English](#english)
  - [Why Cycling Overlay?](#why-cycling-overlay)
  - [Features](#features)
  - [Quick Start](#quick-start)
  - [Documentation](#documentation)
  - [Compatibility](#compatibility)
  - [Sensitive Data](#sensitive-data)
  - [Contributing](#contributing)
  - [Acknowledgments](#acknowledgments)
  - [License](#license)
- [Português](#português)
  - [Por que Cycling Overlay?](#por-que-cycling-overlay)
  - [Recursos](#recursos)
  - [Início Rápido](#início-rápido)
  - [Documentação](#documentação)
  - [Compatibilidade](#compatibilidade-1)
  - [Dados Sensíveis](#dados-sensíveis)
  - [Como Contribuir](#como-contribuir)
  - [Agradecimentos](#agradecimentos)
  - [Licença](#licença)

---

## English

### Why Cycling Overlay?

Most indoor cycling platforms lock you into their ecosystem. Cycling Overlay is different: it sits on top of whatever you're already using — Zwift, TrainerRoad, YouTube — and shows you the metrics that matter, in real time, from your own sensors.

- **No subscription required.** Free and open source, forever.
- **Works with your sensors.** BLE power meters, heart rate straps, cadence sensors, and FTMS smart trainers.
- **Connects to QDomyos-Zwift.** Via Wi-Fi/DIRCON or MQTT for treadmill and bike data.
- **Imports workouts anywhere.** From Intervals.icu API, pasted text, or Zwift `.zwo` files.
- **Always-on-top overlay.** Drag it anywhere on your screen. See power, cadence, HR, target, W/kg, and interval progress without leaving your video or app.

### Features

| Category | Details |
|---|---|
| **Overlay** | Always-on-top window with power, cadence, heart rate, target power, W/kg, interval name, and progress bar |
| **Workouts** | Built-in test workout, Intervals.icu text paste, Intervals.icu API fetch, Zwift `.zwo` folder |
| **Profile** | Manual weight/FTP or automatic sync with Intervals.icu API |
| **BLE Sensors** | Power, cadence/speed, heart rate, FTMS smart trainer — auto-detect and connect |
| **QZ Integrations** | Wi-Fi/DIRCON (mDNS auto-discovery or manual), MQTT with credentials |
| **Languages** | English (default) and Portuguese, toggle with one click |
| **Platforms** | Windows, Linux, macOS (sensor support varies by platform) |

### Quick Start

**Requirements:**

- Python 3.11 or newer
- `pip` available in the Python installation
- Bluetooth enabled for BLE sensors (when applicable)
- Local network access for QZ Wi-Fi/DIRCON or QZ MQTT (when applicable)

**Install and run:**

```bash
python setup.py
python run.py
```

On Windows, to open without a terminal:

```bash
python run.pyw
```

**Run tests:**

```bash
cd cycling_overlay
.venv/bin/python -m pytest
```

> **Note:** `pyproject.toml` declares the `cycling-overlay` command, but the verified launchers in this repository are `setup.py`, `run.py`, and `run.pyw`.

### Documentation

| Document | Description |
|---|---|
| [User Guide](docs/user-guide.md) | How to use the app: profile, workouts, sensors, QZ, overlay |
| [Tutorial](docs/tutorial.md) | Step-by-step tutorials for common scenarios |
| [Technical Guide](docs/technical-guide.md) | Architecture, modules, runtime flow, configuration |
| [Contributing](CONTRIBUTING.md) | How to set up the dev environment and send pull requests |

### Compatibility

**Platforms:**

| Platform | BLE | QZ Wi-Fi | QZ MQTT | Overlay |
|---|---|---|---|---|
| Windows 10/11 | Yes | Yes | Yes | Yes |
| Linux (Ubuntu 22+) | Yes | Yes | Yes | Yes |
| macOS 13+ | Yes | Yes | Yes | Yes |

**BLE sensor types:**

| Service | Examples |
|---|---|
| Heart Rate | Wahoo TICKR, Polar H10, Garmin HRM-Dual |
| Power | Assioma, Quarq, 4iiii |
| Cadence/Speed (CSC) | Wahoo RPM, Garmin Cadence Sensor |
| FTMS Smart Trainer | Wahoo KICKR, Tacx Neo, Elite Direto |

> Other BLE devices may work through the compatibility fallback layer. Device names and parsing are adapted from QDomyos-Zwift.

### Sensitive Data

The app stores settings in a local `config.json` created through `platformdirs`, outside this repository. That file may contain:

- Intervals.icu API key and athlete ID
- Saved sensors and known BLE devices
- QZ host, port, and MQTT credentials

**Do not commit `config.json` to GitHub.** Remove credentials before attaching files to issues.

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and pull request guidelines.

### Acknowledgments

- [QDomyos-Zwift](https://github.com/cagnulein/qdomyos-zwift) — BLE compatibility logic and device identification rules (GPLv3).
- [Intervals.icu](https://intervals.icu/) — Workout API and profile sync.
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — Modern UI framework for Tkinter.

### License

This project is distributed under **GPLv3**. See [LICENSE](LICENSE) for details.

---

## Português

### Por que Cycling Overlay?

A maioria das plataformas de ciclismo indoor prende você no ecossistema delas. O Cycling Overlay é diferente: ele fica por cima do que você já usa — Zwift, TrainerRoad, YouTube — e mostra as métricas que importam, em tempo real, dos seus próprios sensores.

- **Sem assinatura.** Gratuito e open source, para sempre.
- **Funciona com seus sensores.** Medidores de potência BLE, cintas cardíacas, sensores de cadência e rolos inteligentes FTMS.
- **Conecta ao QDomyos-Zwift.** Via Wi-Fi/DIRCON ou MQTT para dados de bike e esteira.
- **Importa treinos de qualquer lugar.** API do Intervals.icu, texto colado ou arquivos `.zwo` do Zwift.
- **Overlay sempre no topo.** Arraste para qualquer lugar da tela. Veja potência, cadência, FC, alvo, W/kg e progresso do intervalo sem sair do vídeo ou app.

### Recursos

| Categoria | Detalhes |
|---|---|
| **Overlay** | Janela sempre no topo com potência, cadência, FC, potência alvo, W/kg, nome do intervalo e barra de progresso |
| **Treinos** | Treino de teste interno, texto colado do Intervals.icu, busca pela API do Intervals.icu, pasta de `.zwo` do Zwift |
| **Perfil** | Peso/FTP manual ou sincronização automática com API do Intervals.icu |
| **Sensores BLE** | Potência, cadência/velocidade, frequência cardíaca, rolo inteligente FTMS — detecção e conexão automática |
| **Integrações QZ** | Wi-Fi/DIRCON (descoberta mDNS automática ou manual), MQTT com credenciais |
| **Idiomas** | Inglês (padrão) e português, troca com um clique |
| **Plataformas** | Windows, Linux, macOS (suporte a sensores varia por plataforma) |

### Início Rápido

**Requisitos:**

- Python 3.11 ou superior
- `pip` disponível na instalação do Python
- Bluetooth ativo para sensores BLE (quando aplicável)
- Rede local configurada para QZ Wi-Fi/DIRCON ou QZ MQTT (quando aplicável)

**Instalar e executar:**

```bash
python setup.py
python run.py
```

No Windows, para abrir sem terminal:

```bash
python run.pyw
```

**Rodar testes:**

```bash
cd cycling_overlay
.venv/bin/python -m pytest
```

> **Nota:** `pyproject.toml` declara o comando `cycling-overlay`, mas os launchers verificados neste repositório são `setup.py`, `run.py` e `run.pyw`.

### Documentação

| Documento | Descrição |
|---|---|
| [Guia do Usuário](docs/user-guide.md) | Como usar o app: perfil, treinos, sensores, QZ, overlay |
| [Tutorial](docs/tutorial.md) | Tutoriais passo-a-passo para cenários comuns |
| [Guia Técnico](docs/technical-guide.md) | Arquitetura, módulos, fluxo de execução, configuração |
| [Como Contribuir](CONTRIBUTING.md) | Como configurar o ambiente de desenvolvimento e enviar PRs |

### Compatibilidade

**Plataformas:**

| Plataforma | BLE | QZ Wi-Fi | QZ MQTT | Overlay |
|---|---|---|---|---|
| Windows 10/11 | Sim | Sim | Sim | Sim |
| Linux (Ubuntu 22+) | Sim | Sim | Sim | Sim |
| macOS 13+ | Sim | Sim | Sim | Sim |

**Tipos de sensores BLE:**

| Serviço | Exemplos |
|---|---|
| Frequência Cardíaca | Wahoo TICKR, Polar H10, Garmin HRM-Dual |
| Potência | Assioma, Quarq, 4iiii |
| Cadência/Velocidade (CSC) | Wahoo RPM, Garmin Cadence Sensor |
| Rolo Inteligente (FTMS) | Wahoo KICKR, Tacx Neo, Elite Direto |

> Outros dispositivos BLE podem funcionar pela camada de compatibilidade com fallback. Nomes de dispositivos e parsing são adaptados do QDomyos-Zwift.

### Dados Sensíveis

O app salva configurações em um `config.json` local criado via `platformdirs`, fora do repositório. Esse arquivo pode conter:

- API Key e Athlete ID do Intervals.icu
- Sensores salvos e dispositivos BLE conhecidos
- Host, porta e credenciais MQTT do QZ

**Não envie `config.json` ao GitHub.** Remova credenciais antes de anexar arquivos em issues.

### Como Contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para setup de desenvolvimento, testes e diretrizes para pull requests.

### Agradecimentos

- [QDomyos-Zwift](https://github.com/cagnulein/qdomyos-zwift) — lógica de compatibilidade BLE e regras de identificação de dispositivos (GPLv3).
- [Intervals.icu](https://intervals.icu/) — API de treinos e sincronização de perfil.
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — framework de UI moderno para Tkinter.

### Licença

Este projeto é distribuído sob **GPLv3**. Veja [LICENSE](LICENSE) para detalhes.
