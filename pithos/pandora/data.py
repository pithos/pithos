client_keys = {
    'android-generic':{
        'deviceModel': 'android-generic',
        'username': 'android',
        'password': 'AC7IBG09A3DTSYM4R41UJWL07VLN8JI7',
        'rpcUrl': '://tuner.pandora.com/services/json/?',
        'encryptKey': '6#26FRL$ZWD',
        'decryptKey': 'R=U!LH$O2B#',
        'version' : '5',
    },
    'pandora-one':{
        'deviceModel': 'D01',
        'username': 'pandora one',
        'password': 'TVCKIBGS9AO9TSYLNNFUML0743LH82D',
        'rpcUrl': '://internal-tuner.pandora.com/services/json/?',
        'encryptKey': '2%3WCL*JU$MP]4',
        'decryptKey': 'U#IO$RZPAB%VX2',
        'version' : '5',
    }
}
default_client_id = "android-generic"
default_one_client_id = "pandora-one"

# See http://pan-do-ra-api.wikia.com/wiki/Json/5/station.getPlaylist
valid_audio_formats = [
    ('highQuality', 'High'),
    ('mediumQuality', 'Medium'),
    ('lowQuality', 'Low'),
]
default_audio_quality = 'mediumQuality'
