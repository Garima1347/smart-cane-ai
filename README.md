# Smart Navigation Cane — IoT + YOLO + Voice + Haptics

A voice-and-vibration guided smart cane system for visually impaired
navigation. Fuses a YOLOv8 object detector (camera), a forward ultrasonic
sensor, and a **second downward-facing ultrasonic sensor for pothole/curb
detection** into real-time spoken and haptic alerts.

Runs identically on:
- **macOS** (development/testing) — webcam + mocked sensors/motor/button
- **Raspberry Pi 5** (deployment) — Pi Camera/USB cam + real GPIO hardware

The code auto-detects the platform at runtime (`src/utils/platform_utils.py`)
and swaps hardware backends accordingly — write and test on Mac, then run
the exact same `main.py` on the Pi.

---

## 1. Features

- **Object detection (YOLOv8n)** — identifies obstacles (person, chair,
  car, pole, etc.) and their left/center/right direction.
- **Forward ultrasonic distance** — precise close-range distance, always
  spoken **in meters** ("Caution, person 1.8 meters ahead").
- **Pothole / drop-off / step-up detection** — a second, downward-angled
  ultrasonic sensor auto-calibrates to "flat ground" on startup, then flags
  sudden deviations: a much-farther reading means a hole/drop-off/missing
  step; a much-closer reading means a curb or step-up. This is checked
  independently of the camera, since potholes are low-contrast and easy for
  a vision model to miss entirely.
- **Voice alerts (offline TTS)** — no internet needed, works outdoors.
- **Haptic (vibration motor) alerts** — a silent backup channel. Pulses
  fast for danger, slower for warnings — useful on loud streets or when the
  user can't hear the voice alert clearly.
- **Emergency SOS button** — hold for 2 seconds to trigger a repeating
  "help needed" voice + vibration alert. (See "Extending with SOS
  notifications" below for adding SMS/GPS.)
- **Walking-speed-adaptive alerts** — if you're closing in on an obstacle
  quickly, alert cooldowns automatically shrink so warnings repeat faster.
  Standing still near something doesn't spam you; walking briskly toward it
  does warn you more urgently.
- **CSV obstacle logging** — every alert is timestamped and saved locally,
  so a caregiver can review a session afterward ("lots of pothole alerts on
  this route").
- **Threaded camera capture** — camera I/O runs on its own thread so YOLO
  inference is never stalled waiting on frame capture — meaningfully
  improves FPS on Pi 5.

---

## 2. Folder Structure

```
smart_cane/
├── README.md
├── requirements.txt
├── config.yaml                  # ALL tunables — thresholds, GPIO pins, etc.
├── main.py                      # entry point — starts everything
├── models/                      # YOLO weights downloaded here
├── scripts/
│   ├── setup_mac.sh
│   └── setup_pi.sh
├── src/
│   ├── vision/
│   │   ├── camera.py            # cross-platform camera capture (cv2 / Picamera2)
│   │   ├── camera_stream.py     # threaded wrapper — always-latest-frame, better FPS
│   │   └── detector.py          # YOLOv8 wrapper — detects + direction + rough distance
│   ├── sensors/
│   │   ├── ultrasonic.py        # HC-SR04 (forward sensor) — real on Pi, mocked on Mac
│   │   ├── ground_detector.py   # pothole / drop-off / step-up detection logic
│   │   ├── sensor_manager.py    # background polling thread per sensor
│   │   └── sos_button.py        # GPIO button (Pi) / keyboard substitute (Mac)
│   ├── audio/
│   │   ├── voice_alert.py       # offline TTS engine
│   │   ├── alert_manager.py     # priority + cooldown + haptic + logging dispatch
│   │   └── haptic.py            # vibration motor control (real on Pi, mock on Mac)
│   ├── navigation/
│   │   └── obstacle_logic.py    # fuses everything into alerts, meters phrasing,
│   │                             # closing-speed-adaptive cooldowns
│   └── utils/
│       ├── platform_utils.py    # Mac vs Pi detection
│       ├── logger.py            # console + file logging
│       └── data_logger.py       # CSV obstacle/alert history
└── tests/
    └── test_sensors.py
```

---

## 3. How it works

```
Camera Thread ──► YOLO Detector ──────────────┐
                                                ├──► Obstacle Fusion ──► Alert Manager ──┬─► Voice (TTS)
Forward Ultrasonic Thread ──► Distance (cm) ───┤    (obstacle_logic.py)                  ├─► Haptic Motor
                                                │                                          └─► CSV Log
Ground Ultrasonic Thread ──► Hazard Detector ──┘
                                                
SOS Button (background) ──► Emergency Alert (bypasses cooldowns, clears queue)
```

- Forward ultrasonic gives fast, precise "how close" — the primary urgency
  signal, always converted to **meters** in spoken phrases.
- Ground ultrasonic feeds a rolling baseline calibration; sudden deviations
  trigger hole/step alerts independent of everything else.
- YOLO adds "what it is" and left/center/right direction on top.
- A closing-speed tracker watches how fast the forward distance is
  shrinking and shortens alert cooldowns proportionally when you're walking
  briskly toward something.
- The alert manager fans each triggered alert out to voice + haptic + CSV
  log simultaneously.

---

## 4. Setup — macOS (development)

```bash
cd smart_cane
chmod +x scripts/setup_mac.sh
./scripts/setup_mac.sh
source venv/bin/activate
python main.py
```

On Mac: webcam via OpenCV, forward + ground sensors are **simulated**
(`MockUltrasonicSensor`), haptic motor is a no-op that logs what it would
have done, and the SOS button becomes a keyboard substitute — type `s` +
Enter in the terminal to simulate holding it.

Use `--interactive-sensor` to type distance values manually and test the
full alert pipeline (including pothole/step detection) without hardware:
```bash
python main.py --interactive-sensor --show-preview
```

## 5. Setup — Raspberry Pi 5 (deployment)

```bash
cd smart_cane
chmod +x scripts/setup_pi.sh
./scripts/setup_pi.sh
source venv/bin/activate
python main.py
```

Installs `gpiozero` + `lgpio` (Pi 5's RP1 chip needs `lgpio`, **not** the
older `RPi.GPIO`), `picamera2`, and `espeak-ng` for offline TTS.

### Wiring — Forward ultrasonic (HC-SR04 #1)
| HC-SR04 pin | Pi 5 pin |
|---|---|
| VCC | 5V (pin 2) |
| GND | GND (pin 6) |
| TRIG | GPIO23 (pin 16) |
| ECHO | GPIO24 (pin 18) — **via voltage divider (1kΩ+2kΩ), ECHO is 5V, Pi GPIO is 3.3V-only** |

Mount facing forward at roughly chest/hand height on the cane.

### Wiring — Ground/pothole ultrasonic (HC-SR04 #2)
| HC-SR04 pin | Pi 5 pin |
|---|---|
| VCC | 5V (another 5V pin, e.g. pin 4) |
| GND | GND (pin 9) |
| TRIG | GPIO17 (pin 11) |
| ECHO | GPIO27 (pin 13) — **same voltage divider requirement** |

Mount angled ~30-45° downward, aimed roughly 50-70cm ahead of the cane tip
— far enough to give you reaction time, close enough to stay accurate.

### Wiring — Vibration motor
A GPIO pin cannot drive a motor directly (not enough current) — use a small
NPN transistor (e.g. 2N2222) or a driver like a low-side MOSFET:
```
GPIO18 (pin 12) ──[1kΩ resistor]──► Transistor base
Motor (+) ──► 5V
Motor (−) ──► Transistor collector
Transistor emitter ──► GND
Flyback diode (1N4001) across the motor terminals (protects the GPIO/transistor)
```

### Wiring — SOS button
```
GPIO22 (pin 15) ──► Button ──► GND
```
(gpiozero's `Button` uses an internal pull-up by default, so no external
resistor is needed — just wire the button between the GPIO pin and ground.)

If you get a GPIO permission error:
```bash
sudo usermod -aG gpio $USER   # then log out and back in
```

---

## 6. Running

```bash
python main.py                          # normal run
python main.py --no-camera               # ultrasonic + ground sensor + voice only, skip YOLO
python main.py --interactive-sensor       # Mac: type a distance to test alerts
python main.py --show-preview             # OpenCV debug window with detection boxes
python main.py --config custom.yaml
```
Press `Ctrl+C` to stop — this speaks a session summary ("14 alerts this
walk, 3 urgent") before shutting down cleanly.

Hold the SOS button (or press `s`+Enter on Mac) at any time to trigger an
emergency alert. Note: on Mac, `--interactive-sensor` and the keyboard SOS
substitute both need stdin, so the SOS keyboard substitute is disabled
automatically while `--interactive-sensor` is active (not an issue on the
real Pi — the SOS button uses a dedicated GPIO pin, not the keyboard).

---

## 7. Configuration

Everything tunable lives in `config.yaml`:
- `alerts.danger_distance_cm` / `warning_distance_cm` — forward sensor thresholds
- `sensors.ground.drop_threshold_cm` / `raise_threshold_cm` — pothole/step sensitivity
- `alerts.adaptive_speed_cooldown` — toggle the walking-speed-adaptive alert timing
- `haptic.enabled` / `haptic.pin` — vibration motor
- `sos_button.enabled` / `sos_button.pin` / `sos_button.hold_seconds`
- `logging.log_obstacles_csv` — toggle CSV history logging
- `vision.threaded_capture` — toggle the threaded camera performance optimization

---

## 8. Performance notes for Pi 5

- `yolov8n.pt` at 320×320 gets ~8-15 FPS on Pi 5 CPU — plenty for
  walking-pace obstacle detection. Larger YOLO variants (s/m/l) aren't
  recommended without a Coral/Hailo accelerator.
- `vision.threaded_capture: true` (default) decouples camera I/O from
  inference — recovers real FPS on Pi 5 vs. reading synchronously.
- Ultrasonic and ground sensors each run on their own thread — precise
  close-range/hazard alerts never wait on a slow camera frame.
- Set `vision.frame_skip` higher (e.g. 2 or 3) if you need more CPU
  headroom for other sensors/threads; the ultrasonic/ground sensors keep
  running at full rate regardless.
- Watch the periodic `Detection FPS: X.X` line in the logs (DEBUG level) to
  tune these settings for your specific Pi 5 + camera combination.

---

## 9. Extending with SOS notifications

The SOS button currently triggers a local voice + vibration alert only. To
send an actual message to a caregiver, add hardware and hook into
`handle_sos()` in `main.py`:
- **GSM module (e.g. SIM800L)** — send an SMS with a fixed message or GPS coordinates.
- **GPS module (e.g. NEO-6M)** — read live coordinates to include in the SMS.
- **WiFi + a notification service** (e.g. Pushover, Twilio, a Telegram bot)
  if the Pi has internet access — simpler than GSM but depends on connectivity.

These aren't included by default since they need extra hardware/accounts,
but the codebase is structured so adding them is a small, contained change.
