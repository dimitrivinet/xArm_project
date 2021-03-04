
import wave
import os
import sys
import requests
import robot_control

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

from voice_recog_vosk.voice_recog import recog 

dirname = os.path.dirname(__file__)
# print(dirname)
sys.path.append(dirname)


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
#cors = CORS(app)

socketio = SocketIO(app)

HTTP_SERVER_PORT = 8000
HTTP_SERVER_HOST = "localhost"

sampleRate = 44100
bitsPerSample = 16
channels = 1

numfile = 0


def extract_to_write(message: str) -> str:
    try:
        if message[0:7] == "Entendu":
            to_write = message[25:-1]
            print(f"to write: {to_write}")
            return to_write
        else:
            print("pas de mot à écrire dans le message")
            return -1
    except:
        print("pas de mot à écrire dans le message")
        return -1
        

def send_rasa(message: str) -> str:
    r = requests.post("http://localhost:5005/webhooks/rest/webhook", json={"sender": "alfred_user", "message": message})
    return r.json()[0]["text"]

def genHeader():
    global sampleRate
    global bitsPerSample
    global channels

    datasize = 2000*10**6
    o = bytes("RIFF",'ascii')                                               # (4byte) Marks file as RIFF
    o += (datasize + 36).to_bytes(4,'little')                               # (4byte) File size in bytes excluding this and RIFF marker
    o += bytes("WAVE",'ascii')                                              # (4byte) File type
    o += bytes("fmt ",'ascii')                                              # (4byte) Format Chunk Marker
    o += (16).to_bytes(4,'little')                                          # (4byte) Length of above format data
    o += (1).to_bytes(2,'little')                                           # (2byte) Format type (1 - PCM)
    o += (channels).to_bytes(2,'little')                                    # (2byte)
    o += (sampleRate).to_bytes(4,'little')                                  # (4byte)
    o += (sampleRate * channels * bitsPerSample // 8).to_bytes(4,'little')  # (4byte)
    o += (channels * bitsPerSample // 8).to_bytes(2,'little')               # (2byte)
    o += (bitsPerSample).to_bytes(2,'little')                               # (2byte)
    o += bytes("data",'ascii')                                              # (4byte) Data Chunk Marker
    o += (datasize).to_bytes(4,'little')                                    # (4byte) Data size in bytes
    return o

@socketio.on('message')
def handle_message(data):
    if type(data) == str:
        print('from client: ' + data)
    else:
        print(data)

@socketio.on('connect')
def connect():
    print("client connected")

@socketio.on('audio_stream')
def handle_stream(data):
    # print(data)
    # print("end of byte stream")

    # with open("test.wav", mode="wb") as f:
    #     f.write(genHeader() + data)
    global numfile
    global dirname
    # print(data)

    with wave.open(f"{dirname}/wavs/file_{numfile}.wav", "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(16 // 8)
        f.setframerate(44100)
        # f.setnframes(1)
        f.setcomptype("NONE", "not compressed")
        f.writeframes(genHeader() + data)
    
    print(f"file written")
    print(f"recognizing...")
    stt = recog(f"file_{numfile}.wav")
    print(f"recognized: {stt}")

    emit('audio_stream_response', stt)

    print("_" * 16)
    print("")

    # numfile += 1

    rasa_response = send_rasa(stt)
    # print(rasa_response)
    emit('rasa_response', rasa_response)

    to_write = extract_to_write(rasa_response)

@socketio.on('manual_stream')
def handle_manual_stream(data):
    rasa_response = send_rasa(data)

    to_write = extract_to_write(rasa_response)

    emit('rasa_response', rasa_response)


@app.route('/')
def page():
    return render_template('index.html', )


if __name__ == '__main__':
    arm = robot_control.Arm()
    print('server launched.')
    socketio.run(app, host=HTTP_SERVER_HOST, port = HTTP_SERVER_PORT)