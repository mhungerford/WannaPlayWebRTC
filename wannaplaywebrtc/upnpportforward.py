import upnpy
import socket
import atexit
    
class UPNPPortForward():
  def __init__(self):
    self.service = None
    self.external_ip = None
    self.internal_ip = '127.0.0.1'
    self.portlist = []

    upnp = upnpy.UPnP()
    upnp.discover()
    device = upnp.get_igd()
    for service in device.get_services():
      if 'WANIPConn1' in service.id:
        self.service = device['WANIPConn1']
        self.external_ip = self.service.GetExternalIPAddress().get('NewExternalIPAddress')

    if self.service is None:
      print("Router doesn't support UPNP, or UPNP is not enabled")
      print("Error: Cannot port forward")

    if self.external_ip is not None:
      s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      s.connect((self.external_ip, 80))
      self.internal_ip = s.getsockname()[0]
      s.close()
    #make sure we close these ports when CTRL+C closed
    atexit.register(self.__del__)

  def __del__(self):
    for forward in self.portlist:
      print("Close Port:{} Protocol:{}".format(*forward))
      self.delete_port(*forward)

  def get_internal_ip(self):
    return self.internal_ip

  def get_external_ip(self):
    return self.external_ip

  def delete_port(self, port=8080, protocol='TCP'):
    if self.external_ip is not None:
      self.service.DeletePortMapping(
          NewRemoteHost='0.0.0.0',
          NewExternalPort=port,
          NewProtocol=protocol
          )

  def forward_port(self, port=8080, protocol='TCP', name='PyUPNP'):
    if self.external_ip is not None:
      self.portlist.append((port, protocol))
      self.service.AddPortMapping(
          NewRemoteHost='0.0.0.0',
          NewExternalPort=port,
          NewProtocol=protocol,
          NewInternalPort=port,
          NewInternalClient=self.internal_ip,
          NewEnabled=1,
          NewPortMappingDescription=name + " " + protocol,
          NewLeaseDuration=0
          )

