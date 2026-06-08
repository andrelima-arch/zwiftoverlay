# Tutorial / Tutorial

Step-by-step tutorials for the most common scenarios.

Tutoriais passo-a-passo para os cenários mais comuns.

---

## Table of Contents / Sumário

1. [First Run / Primeira Execução](#1-first-run--primeira-execução)
2. [Set Up a Manual Profile / Configurar Perfil Manual](#2-set-up-a-manual-profile--configurar-perfil-manual)
3. [Connect with Intervals.icu / Conectar com Intervals.icu](#3-connect-with-intervalsicu--conectar-com-intervalsicu)
4. [Connect a BLE Sensor / Conectar Sensor BLE](#4-connect-a-ble-sensor--conectar-sensor-ble)
5. [Load the Test Workout / Carregar Treino de Teste](#5-load-the-test-workout--carregar-treino-de-teste)
6. [Load a Zwift .zwo Workout / Carregar Treino .zwo do Zwift](#6-load-a-zwift-zwo-workout--carregar-treino-zwo-do-zwift)
7. [Fetch a Workout from Intervals.icu / Buscar Treino do Intervals.icu](#7-fetch-a-workout-from-intervalsicu--buscar-treino-do-intervalsicu)
8. [Connect QZ via Wi-Fi/DIRCON / Conectar QZ por Wi-Fi/DIRCON](#8-connect-qz-via-wi-fidircon--conectar-qz-por-wi-fidircon)
9. [Connect QZ via MQTT / Conectar QZ por MQTT](#9-connect-qz-via-mqtt--conectar-qz-por-mqtt)
10. [Use the Overlay During a Workout / Usar o Overlay Durante o Treino](#10-use-the-overlay-during-a-workout--usar-o-overlay-durante-o-treino)

---

## 1. First Run / Primeira Execução

### English

1. Open a terminal in the project folder.
2. Run `python setup.py` to install dependencies.
3. Run `python run.py` (with terminal) or `python run.pyw` (Windows, no terminal).
4. The setup window opens with four tabs: **Profile**, **Workout**, **Sensors**, **Advanced QZ**.
5. The interface starts in English. Click the **PT** button at the top right to switch to Portuguese.
6. The app loads a built-in test workout automatically. You can start it right away or configure your profile first.

### Português

1. Abra um terminal na pasta do projeto.
2. Rode `python setup.py` para instalar as dependências.
3. Rode `python run.py` (com terminal) ou `python run.pyw` (Windows, sem terminal).
4. A janela de configuração abre com quatro abas: **Perfil**, **Treino**, **Sensores**, **QZ avançado**.
5. A interface abre em inglês. Clique no botão **PT** no canto superior direito para trocar para português.
6. O app carrega um treino de teste automaticamente. Você pode iniciá-lo imediatamente ou configurar seu perfil primeiro.

---

## 2. Set Up a Manual Profile / Configurar Perfil Manual

### English

1. Open the **Profile** tab.
2. In the **Source** dropdown, select **Manual**.
3. Enter your weight in kilograms in the **Weight (kg)** field.
4. Enter your FTP in watts in the **FTP (watts)** field.
5. Values are saved automatically when you move focus away from the field.
6. The FTP value is used to convert percentage-based workout power targets into watts.

### Português

1. Abra a aba **Perfil**.
2. No dropdown **Fonte**, selecione **Manual**.
3. Digite seu peso em quilogramas no campo **Peso (kg)**.
4. Digite seu FTP em watts no campo **FTP (watts)**.
5. Os valores são salvos automaticamente quando você tira o foco do campo.
6. O valor do FTP é usado para converter alvos de potência percentuais dos treinos em watts.

---

## 3. Connect with Intervals.icu / Conectar com Intervals.icu

### English

1. Open the **Profile** tab.
2. In the **Source** dropdown, select **Intervals.icu**.
3. Enter your **Intervals API Key** (found in your Intervals.icu account settings).
4. Enter your **Athlete ID** (your numeric ID from Intervals.icu).
5. Click **Save Intervals.icu**.
6. The app syncs your profile. If weight and FTP are found, the status shows: `Profile updated: 75kg, 250w`.
7. If the API does not return weight or FTP, the status shows: `Intervals.icu did not return weight/FTP.`
8. On the next app startup, the profile syncs automatically when the source is set to Intervals.icu.

### Português

1. Abra a aba **Perfil**.
2. No dropdown **Fonte**, selecione **Intervals.icu**.
3. Digite sua **API Key do Intervals** (encontrada nas configurações da sua conta Intervals.icu).
4. Digite seu **ID do Atleta** (seu ID numérico do Intervals.icu).
5. Clique em **Salvar Intervals.icu**.
6. O app sincroniza seu perfil. Se peso e FTP forem encontrados, o status mostra: `Perfil atualizado: 75kg, 250w`.
7. Se a API não retornar peso ou FTP, o status mostra: `Intervals.icu não retornou peso/FTP.`
8. Na próxima abertura do app, o perfil sincroniza automaticamente quando a fonte estiver como Intervals.icu.

---

## 4. Connect a BLE Sensor / Conectar Sensor BLE

### English

1. Make sure Bluetooth is enabled on your computer.
2. Open the **Sensors** tab.
3. Click **Scan sensors**.
4. Wait for devices to appear. The app groups devices into: **Saved**, **Queue**, **Recent**, **Unknown**.
5. Each device shows its type: **Heart Rate**, **Power**, **Cadence**, **Smart Trainer (FTMS)**.
6. Click an available device to connect. The status changes to **Connected**.
7. Click a connected device to disconnect.
8. Selected sensors are saved automatically and reconnect on the next startup.

**Tip:** If a sensor type is not identified, the app shows: `Sensor type was not identified from BLE advertisement.` The compatibility layer may still parse data from the device.

### Português

1. Certifique-se de que o Bluetooth está ativo no computador.
2. Abra a aba **Sensores**.
3. Clique em **Escanear sensores**.
4. Aguarde os dispositivos aparecerem. O app agrupa dispositivos em: **Salvos**, **Fila**, **Recentes**, **Desconhecidos**.
5. Cada dispositivo mostra seu tipo: **Frequência Cardíaca**, **Potência**, **Cadência**, **Rolo Inteligente (FTMS)**.
6. Clique em um dispositivo disponível para conectar. O status muda para **Conectados**.
7. Clique em um dispositivo conectado para desconectar.
8. Sensores selecionados são salvos automaticamente e reconectam na próxima abertura.

**Dica:** Se o tipo do sensor não for identificado, o app mostra: `Tipo do sensor não identificado pelo anúncio BLE.` A camada de compatibilidade ainda pode interpretar dados do dispositivo.

---

## 5. Load the Test Workout / Carregar Treino de Teste

### English

1. The app loads a built-in test workout on startup. You can see it in the bottom bar: `Test workout | 16 intervals`.
2. Click **▶ Start Workout** at the bottom of the window.
3. The overlay appears on top of the screen.
4. If no sensors are connected, the overlay shows `Pedal to start`.
5. When sensor data arrives, the overlay shows current power, cadence, heart rate, W/kg, and the current interval name.
6. Click **■ Stop Workout** to end the session.

### Português

1. O app carrega um treino de teste interno na abertura. Você pode ver na barra inferior: `Treino de teste | 16 intervalos`.
2. Clique em **▶ Iniciar Treino** na parte inferior da janela.
3. O overlay aparece no topo da tela.
4. Se nenhum sensor estiver conectado, o overlay mostra `Pedale para iniciar`.
5. Quando dados de sensores chegam, o overlay mostra potência, cadência, frequência cardíaca, W/kg e nome do intervalo atual.
6. Clique em **■ Parar Treino** para encerrar a sessão.

---

## 6. Load a Zwift .zwo Workout / Carregar Treino .zwo do Zwift

### English

1. Open the **Workout** tab.
2. In the **Workout source** dropdown, select **Load ZWO folder**.
3. Click **Select folder** and choose a folder containing `.zwo` files.
4. The app lists all `.zwo` files found. If none are found, it shows: `No .zwo files found.`
5. Use the **Search** field to filter workouts by name.
6. Click a workout to load it. The bottom bar updates with the workout title and interval count.
7. Click **▶ Start Workout** to begin.

**Note:** The app uses your current FTP to convert percentage-based power targets into watts.

### Português

1. Abra a aba **Treino**.
2. No dropdown **Fonte do treino**, selecione **Carregar pasta ZWO**.
3. Clique em **Selecionar pasta** e escolha uma pasta com arquivos `.zwo`.
4. O app lista todos os arquivos `.zwo` encontrados. Se nenhum for encontrado, mostra: `Nenhum arquivo .zwo encontrado.`
5. Use o campo **Buscar** para filtrar treinos por nome.
6. Clique em um treino para carregá-lo. A barra inferior atualiza com o título do treino e contagem de intervalos.
7. Clique em **▶ Iniciar Treino** para começar.

**Nota:** O app usa seu FTP atual para converter alvos de potência percentuais em watts.

---

## 7. Fetch a Workout from Intervals.icu / Buscar Treino do Intervals.icu

### English

1. Make sure your **API Key** and **Athlete ID** are saved in the **Profile** tab.
2. Open the **Workout** tab.
3. In the **Workout source** dropdown, select **Fetch from intervals.icu**.
4. Click **Fetch workouts**.
5. The app searches for upcoming events in the next 7 days.
6. If events are found, the status shows: `Found 2 event(s).`
7. Select a workout from the list to load it.
8. If no events are found, the status shows: `No workouts found in the next 7 days.`

**Tip:** The profile syncs automatically when fetching workouts. If weight or FTP is updated, the status shows the new values.

### Português

1. Certifique-se de que sua **API Key** e **Athlete ID** estão salvos na aba **Perfil**.
2. Abra a aba **Treino**.
3. No dropdown **Fonte do treino**, selecione **Buscar do intervals.icu**.
4. Clique em **Buscar treinos**.
5. O app busca eventos programados nos próximos 7 dias.
6. Se eventos forem encontrados, o status mostra: `Encontrados 2 evento(s).`
7. Selecione um treino da lista para carregá-lo.
8. Se nenhum evento for encontrado, o status mostra: `Nenhum treino encontrado nos próximos 7 dias.`

**Dica:** O perfil sincroniza automaticamente ao buscar treinos. Se peso ou FTP forem atualizados, o status mostra os novos valores.

---

## 8. Connect QZ via Wi-Fi/DIRCON / Conectar QZ por Wi-Fi/DIRCON

### English

**Automatic discovery (mDNS):**

1. Open the **Advanced QZ** tab.
2. Enable **QZ Wi-Fi automatic (DIRCON)**.
3. The app searches for DIRCON devices on the local network using mDNS.
4. When a device is found, it appears in the **Sensors** tab as **QZ Wi-Fi / Wahoo DIRCON**.
5. Click the device to connect.

**Manual connection:**

1. Open the **Advanced QZ** tab.
2. Enter the DIRCON **host** (IP address) and **port**.
3. Click **Connect DIRCON manually**.
4. The status shows the connection result.

**Tip:** If automatic discovery does not find the device, check that QDomyos-Zwift is running and that both devices are on the same network.

### Português

**Descoberta automática (mDNS):**

1. Abra a aba **QZ avançado**.
2. Ative **QZ Wi-Fi automático (DIRCON)**.
3. O app procura dispositivos DIRCON na rede local usando mDNS.
4. Quando um dispositivo é encontrado, ele aparece na aba **Sensores** como **QZ Wi-Fi / Wahoo DIRCON**.
5. Clique no dispositivo para conectar.

**Conexão manual:**

1. Abra a aba **QZ avançado**.
2. Digite o **host** (endereço IP) e **porta** do DIRCON.
3. Clique em **Conectar DIRCON manual**.
4. O status mostra o resultado da conexão.

**Dica:** Se a descoberta automática não encontrar o dispositivo, verifique se o QDomyos-Zwift está rodando e se ambos os dispositivos estão na mesma rede.

---

## 9. Connect QZ via MQTT / Conectar QZ por MQTT

### English

1. Open the **Advanced QZ** tab.
2. Enable **QZ MQTT (QDomyos-Zwift app)**.
3. Enter the MQTT **host** (broker address).
4. Enter the **port** (default: 1883).
5. Enter **username** and **password** if required by your broker.
6. Enter the **device/topic** name (use `+` to subscribe to all devices).
7. Click **Connect MQTT**.
8. The status shows the connection result.
9. Click **Disconnect** to stop receiving MQTT data.

**Note:** MQTT credentials are saved in the local `config.json`. Do not share this file.

### Português

1. Abra a aba **QZ avançado**.
2. Ative **QZ MQTT (app QDomyos-Zwift)**.
3. Digite o **host** MQTT (endereço do broker).
4. Digite a **porta** (padrão: 1883).
5. Digite **usuário** e **senha** se exigido pelo seu broker.
6. Digite o nome do **dispositivo/tópico** (use `+` para assinar todos os dispositivos).
7. Clique em **Conectar MQTT**.
8. O status mostra o resultado da conexão.
9. Clique em **Desconectar** para parar de receber dados MQTT.

**Nota:** Credenciais MQTT são salvas no `config.json` local. Não compartilhe esse arquivo.

---

## 10. Use the Overlay During a Workout / Usar o Overlay Durante o Treino

### English

1. Load a workout and connect at least one sensor.
2. Click **▶ Start Workout**.
3. The overlay window appears on top of all other windows.
4. **Drag** the overlay with the mouse to position it anywhere on screen.
5. The overlay shows:
   - **Power** (current watts)
   - **Cadence** (RPM)
   - **Heart Rate** (BPM)
   - **W/kg** (watts per kilogram, based on your profile weight)
   - **Target power** (current interval target in watts)
   - **Interval name** (current or next interval)
   - **Progress bar** (percentage of current interval completed)
6. When you stop pedaling, the overlay shows: `⏸ Pedal to continue`.
7. When the workout finishes, the overlay shows: `Workout complete!`
8. Click **■ Stop Workout** to close the overlay.

**Tip:** The overlay position is saved automatically and restored on the next workout.

### Português

1. Carregue um treino e conecte pelo menos um sensor.
2. Clique em **▶ Iniciar Treino**.
3. A janela do overlay aparece por cima de todas as outras janelas.
4. **Arraste** o overlay com o mouse para posicioná-lo em qualquer lugar da tela.
5. O overlay mostra:
   - **Potência** (watts atuais)
   - **Cadência** (RPM)
   - **Frequência Cardíaca** (BPM)
   - **W/kg** (watts por quilo, baseado no peso do seu perfil)
   - **Potência alvo** (alvo do intervalo atual em watts)
   - **Nome do intervalo** (intervalo atual ou próximo)
   - **Barra de progresso** (percentual do intervalo atual concluído)
6. Quando você para de pedalar, o overlay mostra: `⏸ Pedale para continuar`.
7. Quando o treino termina, o overlay mostra: `Treino concluído!`
8. Clique em **■ Parar Treino** para fechar o overlay.

**Dica:** A posição do overlay é salva automaticamente e restaurada no próximo treino.

---

## Troubleshooting / Solução de Problemas

### English

| Problem | Solution |
|---|---|
| No BLE devices found | Check that Bluetooth is enabled and the sensor is powered on. Move the sensor closer to the computer. |
| QZ Wi-Fi not discovered | Verify QDomyos-Zwift is running and both devices are on the same network. Try manual DIRCON connection. |
| MQTT connection failed | Check the broker address, port, and credentials. Verify the broker is running. |
| Overlay not showing | Click **▶ Start Workout**. The overlay only appears during an active workout. |
| Wrong power values | Check that your FTP is set correctly in the **Profile** tab. |
| App does not start | Run `python setup.py` again to reinstall dependencies. Check Python version: `python --version` (requires 3.11+). |

### Português

| Problema | Solução |
|---|---|
| Nenhum dispositivo BLE encontrado | Verifique se o Bluetooth está ativo e o sensor está ligado. Aproxime o sensor do computador. |
| QZ Wi-Fi não descoberto | Verifique se o QDomyos-Zwift está rodando e ambos os dispositivos estão na mesma rede. Tente conexão DIRCON manual. |
| Conexão MQTT falhou | Verifique endereço do broker, porta e credenciais. Confirme que o broker está rodando. |
| Overlay não aparece | Clique em **▶ Iniciar Treino**. O overlay só aparece durante um treino ativo. |
| Valores de potência errados | Verifique se seu FTP está configurado corretamente na aba **Perfil**. |
| App não inicia | Rode `python setup.py` novamente para reinstalar dependências. Verifique a versão do Python: `python --version` (requer 3.11+). |
