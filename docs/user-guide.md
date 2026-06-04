# Guia do usuário / User Guide

## Português

### O que é

Cycling Overlay é um aplicativo de desktop para treinos de ciclismo indoor. Ele
mostra um overlay sempre no topo com potência, cadência, frequência cardíaca,
alvo do intervalo, watts por quilo e progresso do treino.

O aplicativo pode ler sensores BLE, dados do QDomyos-Zwift (QZ) por Wi-Fi/DIRCON
ou MQTT, e treinos vindos de texto do Intervals.icu, API do Intervals.icu ou
arquivos Zwift `.zwo`.

### Requisitos

- Python 3.11 ou superior.
- `pip` disponível na instalação do Python.
- Bluetooth ativo para sensores BLE.
- Rede local configurada quando usar QZ Wi-Fi/DIRCON ou QZ MQTT.

### Instalação e abertura

Na primeira execução, rode o instalador:

```bash
python setup.py
```

Para abrir com terminal de debug:

```bash
python run.py
```

No Windows, para abrir sem terminal:

```bash
python run.pyw
```

O launcher verifica a versão do Python, instala dependências com `pip install -e
cycling_overlay` quando necessário e mantém um cache local em `.deps_checked`
para evitar reinstalações repetidas.

### Idioma da interface

A interface abre em inglês por padrão. Use o botão `PT` no topo da janela para
trocar para português. Quando a interface está em português, o botão mostra
`EN`.

A escolha fica salva no `config.json` local do usuário. Dados vindos de sensores,
treinos, Intervals.icu, QZ e nomes de dispositivos não são traduzidos
automaticamente.

### Perfil do atleta

O painel de atleta aceita duas fontes:

- `Manual`: peso e FTP digitados pelo usuário.
- `Intervals.icu`: peso e FTP sincronizados com API Key e Athlete ID.

Para usar Intervals.icu, informe a API Key e o Athlete ID e clique em salvar.
Se a API não retornar peso ou FTP, o app mantém a configuração disponível e
mostra uma mensagem de status.

### Carregar treinos

Na aba de treino, escolha uma fonte:

- `Test workout`: treino interno para testar o overlay.
- `Paste intervals.icu text`: cole texto de treino e clique em analisar.
- `Fetch from intervals.icu`: busca eventos próximos usando a API Key e o
  Athlete ID salvos.
- `Load ZWO folder`: seleciona uma pasta e lista arquivos Zwift `.zwo`.

O app usa o FTP atual para converter potências percentuais em watts quando o
formato do treino exige essa conversão.

### Sensores BLE

Na aba de sensores:

1. Clique em escanear sensores.
2. Clique em um dispositivo disponível para conectar.
3. Clique em um dispositivo conectado para desconectar.

O app reconhece sensores de frequência cardíaca, potência, cadência/velocidade
e rolos inteligentes FTMS. Sensores conhecidos e seleções ficam salvos na
configuração local.

### QZ Wi-Fi/DIRCON e MQTT

Na aba avançada QZ:

- Ative QZ Wi-Fi automático para procurar dispositivos DIRCON na rede.
- Use conexão DIRCON manual informando host e porta quando a descoberta
  automática não encontrar o dispositivo.
- Ative QZ MQTT para receber métricas publicadas pelo QDomyos-Zwift.

Valores como host, porta, usuário, senha e tópico/dispositivo MQTT ficam salvos
no `config.json` local.

### Overlay

Ao iniciar o treino, o overlay aparece no topo da tela. Ele pode ser arrastado
com o mouse. Durante o treino, mostra métricas atuais, alvo do intervalo, watts
por quilo e nome do intervalo atual ou próximo.

### Configuração e dados sensíveis

As configurações são salvas em um `config.json` no diretório de configuração do
usuário definido por `platformdirs`. Esse arquivo fica fora do repositório, mas
pode conter dados sensíveis:

- API Key do Intervals.icu.
- Athlete ID.
- Usuário e senha MQTT.
- Hosts e portas da rede local.
- Sensores salvos.

Não envie esse arquivo ao GitHub, não compartilhe logs com segredos e remova
credenciais antes de anexar arquivos em issues.

## English

### What It Is

Cycling Overlay is a desktop app for indoor cycling workouts. It shows an
always-on-top overlay with power, cadence, heart rate, interval target, watts per
kilogram, and workout progress.

The app can read BLE sensors, QDomyos-Zwift (QZ) data through Wi-Fi/DIRCON or
MQTT, and workouts from Intervals.icu text, the Intervals.icu API, or Zwift
`.zwo` files.

### Requirements

- Python 3.11 or newer.
- `pip` available in the Python installation.
- Bluetooth enabled for BLE sensors.
- Local network access when using QZ Wi-Fi/DIRCON or QZ MQTT.

### Install and Run

On first run, start the installer:

```bash
python setup.py
```

To open with a debug terminal:

```bash
python run.py
```

On Windows, to open without a terminal:

```bash
python run.pyw
```

The launcher checks the Python version, installs dependencies with `pip install
-e cycling_overlay` when needed, and keeps a local `.deps_checked` cache to avoid
reinstalling dependencies too often.

### Interface Language

The interface starts in English by default. Use the `PT` button at the top of the
window to switch to Portuguese. When the interface is in Portuguese, the button
shows `EN`.

The selected language is saved in the user's local `config.json`. Data received
from sensors, workouts, Intervals.icu, QZ, and device names is not translated
automatically.

### Athlete Profile

The athlete panel supports two sources:

- `Manual`: weight and FTP entered by the user.
- `Intervals.icu`: weight and FTP synchronized with API Key and Athlete ID.

To use Intervals.icu, enter the API Key and Athlete ID, then save. If the API
does not return weight or FTP, the app keeps the available configuration and
shows a status message.

### Loading Workouts

In the workout tab, choose a source:

- `Test workout`: built-in workout for testing the overlay.
- `Paste intervals.icu text`: paste workout text and analyze it.
- `Fetch from intervals.icu`: fetch upcoming events using the saved API Key and
  Athlete ID.
- `Load ZWO folder`: select a folder and list Zwift `.zwo` files.

The app uses the current FTP to convert percentage-based workout power into
watts when the workout format requires it.

### BLE Sensors

In the sensors tab:

1. Click scan sensors.
2. Click an available device to connect.
3. Click a connected device to disconnect.

The app recognizes heart rate, power, cadence/speed, and FTMS smart trainer
sensors. Known devices and selected sensors are saved in the local configuration.

### QZ Wi-Fi/DIRCON and MQTT

In the advanced QZ tab:

- Enable automatic QZ Wi-Fi to discover DIRCON devices on the network.
- Use manual DIRCON connection with host and port when automatic discovery does
  not find the device.
- Enable QZ MQTT to receive metrics published by QDomyos-Zwift.

Values such as host, port, username, password, and MQTT device/topic are saved
in the local `config.json`.

### Overlay

When a workout starts, the overlay appears on top of the screen. It can be
dragged with the mouse. During the workout, it shows current metrics, interval
target, watts per kilogram, and the current or next interval name.

### Configuration and Sensitive Data

Settings are saved in a `config.json` file in the user config directory resolved
by `platformdirs`. This file is outside the repository, but it may contain
sensitive data:

- Intervals.icu API Key.
- Athlete ID.
- MQTT username and password.
- Local network hosts and ports.
- Saved sensors.

Do not commit this file to GitHub, do not share logs with secrets, and remove
credentials before attaching files to issues.
