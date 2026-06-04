# Cycling Overlay

## English

Indoor cycling workout overlay with BLE sensors, QZ/Wi-Fi, QZ/MQTT,
Intervals.icu workouts, and Zwift `.zwo` files.

### Documentation

- [User guide](docs/user-guide.md)
- [Technical guide](docs/technical-guide.md)

### Quick Start

Requirements:

- Python 3.11 or newer.
- Windows, Linux, or macOS with support for the sensor features you use.
- Bluetooth access for BLE sensors, when applicable.

Run:

```bash
python setup.py
python run.py
```

On Windows, to open without a terminal:

```bash
python run.pyw
```

During development:

```bash
cd cycling_overlay
.venv/bin/python -m pytest
```

Technical note: `pyproject.toml` declares the `cycling-overlay` command, but the
verified launchers in this repository are `setup.py`, `run.py`, and `run.pyw`.

### Features

- Always-on-top overlay with power, cadence, heart rate, target, and interval
  progress.
- English and Portuguese interface, with English as the default.
- Manual profile or Intervals.icu profile synchronization.
- Workouts from a built-in test workout, Intervals.icu text, the Intervals.icu
  API, or a folder of `.zwo` files.
- BLE sensors for power, cadence/speed, heart rate, and FTMS smart trainers.
- QZ integrations through Wi-Fi/DIRCON and MQTT.

### Sensitive Data

The app stores settings in a local `config.json` created through `platformdirs`,
outside this repository. That file may contain an Intervals.icu API key, athlete
ID, saved sensors, QZ host, and MQTT credentials. Do not commit it to GitHub.

### License

This project is distributed under GPLv3.

Part of the BLE compatibility logic was ported/adapted from
[QDomyos-Zwift](https://github.com/cagnulein/qdomyos-zwift), also GPLv3,
including generic device identification rules and parsing fallbacks for
equipment compatible with FTMS, Cycling Power, and CSC.

## Português

Overlay de treino para ciclismo indoor com leitura de sensores BLE, QZ/Wi-Fi,
QZ/MQTT, treinos do Intervals.icu e arquivos Zwift `.zwo`.

### Documentação

- [Guia do usuário](docs/user-guide.md)
- [Guia técnico](docs/technical-guide.md)

### Início rápido

Requisitos:

- Python 3.11 ou superior.
- Windows, Linux ou macOS com suporte aos recursos de sensores usados.
- Acesso Bluetooth para sensores BLE, quando aplicável.

Executar:

```bash
python setup.py
python run.py
```

No Windows, para abrir sem terminal:

```bash
python run.pyw
```

Durante o desenvolvimento:

```bash
cd cycling_overlay
.venv/bin/python -m pytest
```

Nota técnica: `pyproject.toml` declara o comando `cycling-overlay`, mas os
launchers verificados neste repositório são `setup.py`, `run.py` e `run.pyw`.

### Recursos

- Overlay sempre no topo com potência, cadência, frequência cardíaca, alvo e
  progresso do intervalo.
- Interface em inglês e português, com inglês como padrão.
- Perfil manual ou sincronizado pelo Intervals.icu.
- Treinos por exemplo interno, texto do Intervals.icu, API do Intervals.icu ou
  pasta de arquivos `.zwo`.
- Sensores BLE para potência, cadência/velocidade, frequência cardíaca e rolo
  inteligente FTMS.
- Integrações QZ por Wi-Fi/DIRCON e MQTT.

### Dados sensíveis

O app salva configurações em um `config.json` local criado via `platformdirs`,
fora do repositório. Esse arquivo pode conter API Key do Intervals.icu,
identificador de atleta, sensores salvos, host QZ e credenciais MQTT. Não envie
esse arquivo ao GitHub.

### Licença

Este projeto é distribuído sob GPLv3.

Parte da lógica de compatibilidade BLE foi portada/adaptada do
[QDomyos-Zwift](https://github.com/cagnulein/qdomyos-zwift), também GPLv3,
incluindo regras genéricas de identificação de dispositivos e fallbacks de
parsing para equipamentos compatíveis com FTMS, Cycling Power e CSC.
