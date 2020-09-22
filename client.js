var peer = null;

function negotiate() {
    peer.addTransceiver('video', {direction: 'recvonly'});
    peer.addTransceiver('audio', {direction: 'recvonly'});
    return peer.createOffer().then(function(offer) {
        return peer.setLocalDescription(offer);
    }).then(function() {
        // wait for ICE gathering to complete
        return new Promise(function(resolve) {
            if (peer.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (peer.iceGatheringState === 'complete') {
                        peer.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                peer.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function() {
        var offer = peer.localDescription;
        return fetch('/offer', {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function(response) {
        return response.json();
    }).then(function(answer) {
        return peer.setRemoteDescription(answer);
    }).catch(function(e) {
        alert(e);
    });
}

function start() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    if (document.getElementById('use-stun').checked) {
        config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];
    }

    peer = new RTCPeerConnection(config);

    // connect audio / video
    peer.addEventListener('track', function(evt) {
        if (evt.track.kind == 'video') {
            console.log("Adding track" + evt.track.kind);
            document.getElementById('video').srcObject = evt.streams[0];
        } else {
            document.getElementById('audio').srcObject = evt.streams[0];
        }
    });

    document.getElementById('start').style.display = 'none';
    negotiate();
    document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
    document.getElementById('stop').style.display = 'none';

    // close peer connection
    setTimeout(function() {
        peer.close();
    }, 500);
}
