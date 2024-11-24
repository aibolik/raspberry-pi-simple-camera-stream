#!/usr/bin/python3

import io
import logging
import socketserver
from http import server
from threading import Condition
import telepot
import socket
import time

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

PAGE = """\
<html>
<head>
<title>Raspberry PI Camera stream</title>
</head>
<body>
<h1>PI Camera stream</h1>
<img src="stream.mjpg" width="640" height="480" />
</body>
</html>
"""

TELEGRAM_BOT_TOKEN = "REPLACE_WITH_TOKEN"
MY_CHAT_ID = "REPLACE_WITH_CHAT_ID"

# Some delay until the Raspberry PI gets initialised
print("Starting the service(with 5s delay)...")
time.sleep(5)
print("Delay has passed. Initialising the bot")

bot = telepot.Bot(TELEGRAM_BOT_TOKEN)
print("Bot is initialised")

def get_my_ip():
    try:
        print("Getting IP address")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        print(f"Current IP address is {ip}")
        return ip
    except Exception as e:
        print(f"An error occured while getting IP {e}. Returning default 192.168.0.18")
        return "192.168.0.18"
    finally:
        s.close()

def send_telegram_message():
    myip = get_my_ip()
    text = "PI Camera has started!\n\nOpen the stream at http://{}:{}".format(myip, "8000")
    print("Sending a message to telegram")
    bot.sendMessage(chat_id=MY_CHAT_ID, text=text)

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning('Removed streaming client %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
output = StreamingOutput()
picam2.start_recording(MJPEGEncoder(), FileOutput(output))


try:
    address = ('', 8000)
    send_telegram_message()
    print("Starting a streaming server")
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    picam2.stop_recording()
