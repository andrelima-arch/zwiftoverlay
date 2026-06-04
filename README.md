# Cycling Overlay

**PT-BR:** Overlay de treino para ciclismo indoor com leitura de sensores BLE,
QZ/Wi-Fi, QZ/MQTT, treinos do Intervals.icu e arquivos Zwift `.zwo`.

**EN:** Indoor cycling workout overlay with BLE sensors, QZ/Wi-Fi, QZ/MQTT,
Intervals.icu workouts, and Zwift `.zwo` files.

## Documentação / Documentation

- [Guia do usuário / User guide](docs/user-guide.md)
- [Guia técnico / Technical guide](docs/technical-guide.md)

## Início rápido / Quick Start

Requisitos / Requirements:

- Python 3.11 ou superior / Python 3.11 or newer
- Windows, Linux ou macOS com suporte aos recursos de sensores usados
- Acesso Bluetooth para sensores BLE, quando aplicável

Executar / Run:

```bash
python setup.py
python run.py
```

No Windows, para abrir sem terminal:

```bash
python run.pyw
```

Durante o desenvolvimento / During development:

```bash
cd cycling_overlay
.venv/bin/python -m pytest
```

Nota técnica: `pyproject.toml` declara o comando `cycling-overlay`, mas os
launchers verificados neste repositório são `setup.py`, `run.py` e `run.pyw`.

Technical note: `pyproject.toml` declares the `cycling-overlay` command, but the
verified launchers in this repository are `setup.py`, `run.py`, and `run.pyw`.

## Recursos / Features

- Overlay sempre no topo com potência, cadência, frequência cardíaca, alvo e
  progresso do intervalo.
- Interface em inglês e português, com inglês como padrão.
- Perfil manual ou sincronizado pelo Intervals.icu.
- Treinos por exemplo interno, texto do Intervals.icu, API do Intervals.icu ou
  pasta de arquivos `.zwo`.
- Sensores BLE para potência, cadência/velocidade, frequência cardíaca e rolo
  inteligente FTMS.
- Integrações QZ por Wi-Fi/DIRCON e MQTT.

## Dados sensíveis / Sensitive Data

O app salva configurações em um `config.json` local criado via `platformdirs`,
fora do repositório. Esse arquivo pode conter API Key do Intervals.icu,
identificador de atleta, sensores salvos, host QZ e credenciais MQTT. Não envie
esse arquivo ao GitHub.

The app stores settings in a local `config.json` created through `platformdirs`,
outside this repository. That file may contain an Intervals.icu API key, athlete
ID, saved sensors, QZ host, and MQTT credentials. Do not commit it to GitHub.

## Licença / License

Este projeto é distribuído sob GPLv3.

This project is distributed under GPLv3.

Parte da lógica de compatibilidade BLE foi portada/adaptada do
[QDomyos-Zwift](https://github.com/cagnulein/qdomyos-zwift), também GPLv3,
incluindo regras genéricas de identificação de dispositivos e fallbacks de
parsing para equipamentos compatíveis com FTMS, Cycling Power e CSC.

Part of the BLE compatibility logic was ported/adapted from
[QDomyos-Zwift](https://github.com/cagnulein/qdomyos-zwift), also GPLv3,
including generic device identification rules and parsing fallbacks for
equipment compatible with FTMS, Cycling Power, and CSC.
