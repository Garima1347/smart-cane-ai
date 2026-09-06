# Smart Cane AI

## AI-Based Smart Cane for Visually Impaired People

Smart Cane AI is a project designed to help visually impaired people detect obstacles and hazards while walking.

The main idea is simple: a normal cane helps a person detect obstacles by touching them. Our project adds AI and sensors to provide information about obstacles before the user reaches them.

The system uses a camera, AI-based object detection, ultrasonic sensors, voice feedback, and vibration feedback.

The goal is not to replace the traditional cane. It is to add an extra layer of information and safety.

---

## Problem

For a visually impaired person, walking in an unfamiliar environment can be difficult.

A normal cane can help detect physical obstacles, but it cannot tell the user what an object is.

For example, the user may know that something is in front of them, but they may not know whether it is a person, door, vehicle, or another object.

Ground hazards such as potholes, steps, and sudden changes in the ground can also be difficult to identify.

This is the problem we are trying to address.

---

## Our Approach

Our system uses different components for different purposes.

The camera is used to understand what is around the user.

The ultrasonic sensor in the front is used to measure how close an obstacle is.

The downward-facing ultrasonic sensor is used to identify changes in the ground, such as possible potholes, steps, or drop-offs.

The system combines this information and gives an alert through voice and vibration.

---

## How It Works

The basic process is:

Camera
→ AI object detection
→ Detect object and direction

Front ultrasonic sensor
→ Measure obstacle distance

Downward ultrasonic sensor
→ Check ground level

All this information
→ Obstacle logic
→ Alert system
→ Voice and vibration

The system also has an SOS button for a local emergency alert.

---

## AI Object Detection

The current project uses multiple YOLO models.

### YOLO11n

The `yolo11n.pt` model is used for general object detection.

It detects objects from the camera feed and provides information such as:

* Object type
* Object location
* Confidence
* Approximate direction

The detected object can be classified as being on the left, center, or right side of the camera view.

For example:

"Person on your left"

or

"Object ahead"

---

## Door Detection

The project also contains a custom model called:

`best_door.pt`

This model is used for detecting doors.

A separate model is useful because it allows us to train the system specifically for the type of detection we need.

---

## Pothole and Road Hazard Detection

The project also contains:

`best_pothole.pt`

This model is used for detecting road-related hazards.

The exact objects detected by this model depend on the classes used during training.

The purpose of this model is to identify hazards that may not be handled well by a general object detection model.

---

## Ultrasonic Sensors

The project uses two HC-SR04 ultrasonic sensors.

### Front Sensor

The front sensor measures the distance between the cane and an obstacle.

The sensor sends an ultrasonic signal and measures the time taken for the signal to return after hitting an object.

The basic formula is:

Distance = (Time × Speed of Sound) / 2

The division by two is because the signal travels to the object and then comes back.

The front sensor mainly answers:

"How close is the obstacle?"

---

## Ground Sensor

The second ultrasonic sensor is positioned downward to monitor the ground in front of the cane.

The system first gets a normal ground measurement and uses it as a reference.

Later measurements are compared with this reference.

A large change can indicate a possible:

* Pothole
* Drop-off
* Step
* Curb
* Other ground-level change

This sensor provides information that is different from the camera.

---

## Sensor Fusion

The project does not depend on only one sensor.

The camera tells us what an object may be.

The front ultrasonic sensor tells us how close an obstacle is.

The ground sensor checks for changes in the ground.

The system combines this information before generating an alert.

For example:

The camera detects a person.

The ultrasonic sensor detects that the obstacle is close.

The system can then generate a higher-priority warning.

---

## Voice Alerts

The system provides voice feedback to the user.

Examples include:

* Person ahead
* Obstacle on the left
* Door ahead
* Possible pothole
* Ground hazard detected

The project uses offline text-to-speech, so basic voice feedback does not require an internet connection.

---

## Vibration Alerts

The cane also provides vibration feedback.

Different vibration patterns can be used for different levels of warning.

For example:

Slow vibration can indicate a warning.

Faster or repeated vibration can indicate a more urgent situation.

Using vibration along with voice feedback is useful because voice alerts may be difficult to hear in noisy environments.

---

## Adaptive Alerts

The system does not always give warnings at the same frequency.

If an obstacle is far away or the user is not moving quickly toward it, repeated warnings may not be necessary.

If the obstacle is getting closer quickly, the system can provide warnings more frequently.

This helps reduce unnecessary alerts while still providing faster warnings when the situation becomes more urgent.

---

## SOS Button

The project includes an SOS button.

When the button is pressed, the system can provide a local emergency alert using voice and vibration.

Currently, the SOS feature does not send an SMS or GPS location.

These features can be added in the future.

---

## Real-Time Processing

The system has several tasks running continuously:

* Camera capture
* AI detection
* Ultrasonic sensing
* Ground monitoring
* Alert generation

The project uses separate processing threads for some of these tasks so that one operation does not unnecessarily block another.

This is important because the system needs to respond to sensor changes and obstacles in real time.

---

## Hardware

The main hardware used in the project is:

| Component            | Purpose                          |
| -------------------- | -------------------------------- |
| Raspberry Pi 5       | Main processing unit             |
| Camera               | Captures the surroundings        |
| HC-SR04              | Measures front obstacle distance |
| HC-SR04              | Monitors ground level            |
| Vibration motor      | Provides haptic feedback         |
| Speaker/audio output | Provides voice feedback          |
| SOS button           | Emergency/local alert            |

A transistor or MOSFET driver is used to control the vibration motor safely.

A voltage divider is used with the ultrasonic sensor's Echo signal because Raspberry Pi GPIO uses 3.3V logic.

---

## Software

The project is mainly written in Python.

Important technologies used include:

* Python
* YOLO
* OpenCV
* Raspberry Pi
* Ultrasonic sensors
* Offline text-to-speech
* GPIO
* Multithreading

---

## Project Structure

```text
smart-cane-ai/
│
├── main.py
├── config.yaml
├── export_for_pi.py
│
├── model/
│   ├── yolo11n.pt
│   ├── best_door.pt
│   └── best_pothole.pt
│
└── src/
    ├── vision/
    ├── sensors/
    ├── navigation/
    ├── audio/
    └── utilities/
```

Each part of the project has a separate responsibility.

The vision files handle the camera and AI detection.

The sensor files handle ultrasonic sensors and the SOS button.

The navigation files handle obstacle-related decisions.

The audio files handle voice and alert management.

The utility files handle functions such as vibration and data logging.

---

## Configuration

The main configuration is stored in:

`config.yaml`

Some important settings include:

* Confidence threshold: 0.45
* Inference size: 320
* Frame skip: 1
* Threaded camera capture: enabled

Keeping these values in a configuration file makes it easier to change the system without modifying the main code.

---

## Running the Project

### 1. Clone the repository

```bash
git clone https://github.com/Garima1347/smart-cane-ai.git
cd smart-cane-ai
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

### 3. Install the required packages

```bash
pip install -r requirements.txt
```

### 4. Make sure the model files are available

The required models are placed in the `model` directory:

```text
model/
├── yolo11n.pt
├── best_door.pt
└── best_pothole.pt
```

### 5. Run the project

```bash
python main.py
```

---

## Development and Testing

The project can be developed and tested on a normal computer using simulated hardware where required.

The final system is intended to run on a Raspberry Pi 5 with the actual camera and sensors.

This makes development easier because the software can be tested without having the complete physical cane connected all the time.

---

## Current Limitations

This is a prototype, so there are some limitations.

### AI detection is not perfect

The AI model can sometimes miss an object or detect an object incorrectly.

Performance can be affected by:

* Poor lighting
* Camera angle
* Occlusion
* Motion blur
* Unusual objects
* Unfamiliar environments

### Vision-based distance is approximate

The camera-based proximity estimation is based on the size of the detected object in the image. It should not be treated as an exact distance measurement.

The ultrasonic sensor is used for physical distance measurement.

### Ultrasonic sensors have limitations

Their readings can be affected by:

* Object shape
* Surface material
* Object angle
* Sensor position
* Environmental conditions

### Multiple models require more processing

The system uses multiple AI models, so running them on a Raspberry Pi requires more processing power than running a single small model.

Actual performance should therefore be measured on the final hardware.

### SOS is currently local

The current SOS system does not send an SMS or GPS location.

---

## Future Improvements

Some possible future improvements are:

* GPS integration
* SMS emergency alerts
* Mobile application
* Emergency contact system
* Better distance estimation
* More accurate ground-hazard detection
* More training data
* Better performance on low-light images
* Faster AI inference
* Model optimization for Raspberry Pi
* Better sensor fusion
* Support for multiple languages
* Improved battery life
* Smaller and lighter hardware

---

## What Makes This Project Different?

Smart canes and assistive navigation systems already exist.

We are not claiming that the idea of a smart cane is completely new.

Our focus is on combining different technologies into one system.

The camera provides information about objects.

The ultrasonic sensors provide distance and ground information.

The alert system converts this information into simple voice and vibration feedback.

The goal is to provide the user with more information about their surroundings without removing the benefits of a traditional cane.

---

## Project Goal

The goal of Smart Cane AI is to explore how AI and embedded systems can be used to provide additional awareness to visually impaired people while walking.

We want the system to answer three simple questions:

1. What is around me?
2. How close is it?
3. Is the ground ahead safe?

By combining computer vision, ultrasonic sensing, and accessible feedback, we hope to make each step a little safer and more informed.

---

## Disclaimer

Smart Cane AI is a prototype project and has not been designed or certified as a medical or safety device.

The system can make incorrect predictions or miss hazards. It should therefore be considered an assistive technology prototype and should not be used as the sole method of navigation.
