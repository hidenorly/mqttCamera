# What's mqttCamera.py

This is Camera application which capture is triggered by MQTT.

# How to use

## Preparation

For OpenCV preparation,

```
$ sudo apt-get install libopencv-dev python-opencv
```

For MQTT Python library preparation,

```
$ pip install paho-mqtt
```

On Ubuntu environment, you need to use ```sudo pip install paho-mqtt``` instead.

## Basic usage

```
$ ./mqttCamera.py --host=192.168.10.1 -t /hidenorly/camera -f 10
```

And you can trigger by MQTT subscriber such as https://github.com/hidenorly/simpleMqttClient

```
$ ./simpleMqttClient.py --host 192.168.10.1 -t "/hidenorly/camera" -v "take"
```

If you want to send the photo as attachment, [mail.py](https://github.com/hidenorly/mailpy) might be helpful as follows:

```
$ ./mqttCamera.py --host=192.168.10.1 -t /hidenorly/camera -f 10 --exec="echo mqttCamera | /opt/mailpy/mail.py hoge@gmail.com -s mqttCamera -a "
```