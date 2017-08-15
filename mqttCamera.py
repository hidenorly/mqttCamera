#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 2017 hidenorly
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time
import sys
import codecs
import datetime
import subprocess
from optparse import OptionParser, OptionValueError
from pkg_resources import parse_version

import cv2
import paho.mqtt.client as mqtt

cset = 'utf-8'

reload(sys)
sys.setdefaultencoding(cset)
sys.stdin = codecs.getreader(cset)(sys.stdin)
sys.stdout = codecs.getwriter(cset)(sys.stdout)

OPCV3 = parse_version(cv2.__version__) >= parse_version('3')

# --- camera
class OpenCvCamera:
	@staticmethod
	def getCapAttrId(prop):
	  return getattr(cv2 if OPCV3 else cv2.cv,
	    ("" if OPCV3 else "CV_") + "CAP_PROP_" + prop)

	@staticmethod
	def captureImage(captureIndex, width, height, filename, skipFrame):
		cap = cv2.VideoCapture(captureIndex)

		if cap:
			if width and height:
				cap.set(getCapAttrId("FRAME_WIDTH"), width)
				cap.set(getCapAttrId("FRAME_HEIGHT"), height)
				#print "Request:{}x{} Current:{}x{}".format(width,height, cap.get(getCapAttrId("FRAME_WIDTH")), cap.get(getCapAttrId("FRAME_HEIGHT")))

			for i in range(skipFrame):
				cap.read()

			ret, frame = cap.read()
			cv2.imwrite(filename,frame)

			# When everything done, release the capture
			cap.release()

	@staticmethod
	def getResolution(resolution):
		resolutions=[]
		if resolution:
			resolutions = resolution.split("x")
		if len(resolutions):
			return int(resolutions[0]), int(resolutions[1])
		else:
			return None, None

# --- MQTT
class MQTTManager:
	def __init__(self, clientId, server, port, username, password, bSecure=False):
		self.server = server
		self.port = port
		self.username = username
		self.password = password
		self.bSecure = bSecure
		self.subscribers = {}
		self.clientId = clientId
		self.client = mqtt.Client(client_id=clientId, clean_session=True, protocol=mqtt.MQTTv311, userdata=self)
		self.client.on_connect = self.onConnect
		self.client.on_message = self.onMessage

	def __del__(self):
		self.disconnect()

	def addSubscriber(self, key, aSubscriber):
		self.subscribers[key] = aSubscriber

	def publish(self, topic, val, qos=0, retain=0):
		self.client.publish(topic, val, qos, retain)

	def setTls(self, ca_certs, certfile=None, keyfile=None, cert_reqs=mqtt.ssl.CERT_REQUIRED, tls_version=mqtt.ssl.PROTOCOL_TLSv1, ciphers=None):
		self.ca_certs = ca_certs
		self.certfile = certfile
		self.keyfile = keyfile
		self.cert_reqs = cert_reqs
		self.tls_version = tls_version
		self.ciphers = ciphers
		self.bSecure = True

	def connect(self):
		if self.bSecure:
			self.client.tls_set(self.ca_certs, self.certfile, self.keyfile, self.cert_reqs, self.tls_version, self.ciphers)
		self.client.connect(self.server, port=self.port, keepalive=60)

	def disconnect(self):
		self.client.disconnect()

	def loop(self):
		self.client.loop_forever()

	def enableSubscriber(self, key, bEnable):
		if self.subscribers.has_key(key):
			if bEnable:
				self.client.subscribe( self.subscribers[key].topic )
			else:
				self.client.unsubscribe( self.subscribers[key].topic )

	@staticmethod
	def onConnect(client, pSelf, flags, result):
		print("Connected with result code " + str(result))

	@staticmethod
	def onMessage(client, pSelf, msg):
		for topic, aSubscriber in pSelf.subscribers.iteritems():
			if aSubscriber.canHandle(msg.topic):
				aSubscriber.onMessage(msg)

class MQTTSubscriber(object):
	def __init__(self, topic):
		self.topic = topic
		self.wildCard = False
		if topic.endswith("#"):
			self.wildCard = True
			self._topic = topic[0:len(topic)-1]

	def onMessage(self, msg):
		print(msg.topic + " " + str(msg.payload))

	def canHandle(self, topic):
		if self.topic == topic or (self.wildCard==True and topic.startswith(self._topic)):
			return True
		return False

# --- App part
class FileUtils:
	@staticmethod
	def getYMDHMSFilename(rootPath):
		now = datetime.datetime.today()
		return now.strftime("%Y%m%d-%H%M%S")

class SystemUtils:
	@staticmethod
	def getExecResult(cmd, chdir=None):
		p = None
		if chdir:
			p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=chdir)
		else:
			p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		stdout_data, stderr_data = p.communicate()
		return stdout_data, stderr_data


class MqttCameraSubscriber(MQTTSubscriber):
	def __init__(self, topic, width, height, captureIndex, skipFrame, outputPath, execCommand):
		super(MqttCameraSubscriber, self).__init__(topic)
		self.width = width
		self.height = height
		self.captureIndex = captureIndex
		self.skipFrame = skipFrame
		self.outputPath = outputPath
		self.execCommand = execCommand
		self.count = 0

	def onMessage(self, msg):
		#print("MySubscriber:" + msg.topic + " " + str(msg.payload))
		filename = self.outputPath+"/"+FileUtils.getYMDHMSFilename(self.outputPath)+".jpg"

		trialCount=3
		while trialCount>0:
			trialCount = trialCount - 1
			OpenCvCamera.captureImage(
				self.captureIndex, 
				self.width, 
				self.height, 
				filename, 
				self.skipFrame
			)
			if os.path.getsize(filename)!=0:
				break
			else:
				time.sleep(1)
				print("Camera capture is failed.")

		if self.execCommand:
			exec_cmd = self.execCommand+" "+filename
			result_stdout, result_stderr = SystemUtils.getExecResult(exec_cmd)

if __name__ == '__main__':
	parser = OptionParser()

	parser.add_option("-c", "--clientId", action="store", type="string", dest="clientId", help="Specify client Id", default="mqttCamera")
	parser.add_option("-s", "--host", action="store", type="string", dest="host", help="Specify mqtt server")
	parser.add_option("-p", "--port", action="store", type="int", dest="port", help="Specify mqtt port", default=1883)
	parser.add_option("-u", "--username", action="store", type="string", dest="username", help="Specify username", default=None)
	parser.add_option("-k", "--password", action="store", type="string", dest="password", help="Specify password", default=None)
	parser.add_option("-t", "--topic", action="store", type="string", dest="topic", help="Specify subscribing topic", default="#")

	parser.add_option("-i", "--captureIndex", action="store", type="int", dest="captureIndex", help="Specify capture Index (set 0 if /dev/video0)", default="0")
	parser.add_option("-r", "--resolution", action="store", type="string", dest="resolution", help="Specify resolution")
	parser.add_option("-f", "--skip", action="store", type="int", dest="skipFrame", help="Specify skip frame", default="0")
	parser.add_option("-o", "--outputPath", action="store", type="string", dest="outputPath", help="Specify captured image output path", default=".")
	parser.add_option("-e", "--exec", action="store", type="string", dest="execCommand", help="Specify executing command (the argument is the filename)", default=None)

	(options, args) = parser.parse_args()

	mqtt = MQTTManager(options.clientId, options.host, options.port, options.username, options.password, False)

	mqtt.connect()

	width, height = OpenCvCamera.getResolution(options.resolution)
	aSubscriber = MqttCameraSubscriber(
		options.topic, 
		width, 
		height, 
		options.captureIndex, 
		options.skipFrame, 
		options.outputPath, 
		options.execCommand
	)
	mqtt.addSubscriber( aSubscriber.topic, aSubscriber )
	mqtt.enableSubscriber( aSubscriber.topic, True )
	mqtt.loop()

	cv2.destroyAllWindows()
	mqtt.disconnect()
