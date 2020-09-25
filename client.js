var pc = null;

// data channel
var dc = null, dcInterval = null;

var vc = null;

var uuid = null;

function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}


function negotiate() {
    return pc.createOffer().then(function(offer) {
        return pc.setLocalDescription(offer);
    }).then(function() {
        // wait for ICE gathering to complete
        return new Promise(function(resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function() {
        var offer = pc.localDescription;
        return fetch('/offer', {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
                uuid: uuid
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function(response) {
        return response.json();
    }).then(function(answer) {
        return pc.setRemoteDescription(answer);
    }).catch(function(e) {
        alert(e);
    });
}

function addVideo() {
   if (vc == null) {
     vc = pc.addTransceiver('video', {direction: 'recvonly'});
     negotiate(true);
      console.log("Add Video")
   }
}

function start() {
    // New session uuid each start
    uuid = uuidv4();
    
    var config = {
        sdpSemantics: 'unified-plan'
    };

    // Always use stun server
   config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];

    pc = new RTCPeerConnection(config);

    // Create Data Channel
   dc = pc.createDataChannel('chat', {"ordered": false, "maxRetransmits": 0});
   dc.onclose = function() {
      clearInterval(dcInterval);
   };
   dc.onopen = function() {
      dcInterval = setInterval(function() {
         var message = 'ping hello there';
         dc.send(message);
      }, 1000);
   };
   dc.onmessage = function(evt) {
      console.log("Data channel reply: " + evt.data)

      if (evt.data.substring(0, 4) === 'pong') {
      }
      if (evt.data.substring(0, 5) === 'start') {
         addVideo();
      }
   };



    // connect video
    pc.addEventListener('track', function(evt) {
        if (evt.track.kind == 'video') {
            console.log("Adding track" + evt.track.kind);
            document.getElementById('video').srcObject = evt.streams[0];
        }
    });


   //pc.onnegotiationneeded = function() {
   //   negotiate();
   //}


    negotiate();

    document.getElementById('start').style.display = 'none';
    document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
    document.getElementById('start').style.display = 'inline-block';
    document.getElementById('stop').style.display = 'none';

    // close data channel
    if (dc) {
        dc.close();
    }

    // close transceivers
    if (pc.getTransceivers) {
        pc.getTransceivers().forEach(function(transceiver) {
            if (transceiver.stop) {
                transceiver.stop();
            }
        });
        vc = null;
    }

    // close peer connection
    setTimeout(function() {
        pc.close();
        pc = null;
    }, 500);
}
