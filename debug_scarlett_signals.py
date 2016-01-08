#!/usr/bin/env python

import dbus
import pprint
pp = pprint.PrettyPrinter(indent=4)

# Proxy object from the object in receiver
obj = dbus.SessionBus().get_object('com.example.service', '/com/example/service')

pp.pprint(obj)
print obj.KeywordRecognizedSignal(dbus_interface='tld.domain.sub.TestInterface', "  ScarlettListener caught a keyword match",
                                  "pi-listening")

# METHODS
# @dbus.service.method("com.example.service.emitKeywordRecognizedSignal",
#                          in_signature='',
#                          out_signature='s')
#     def emitKeywordRecognizedSignal(self):
#         global SCARLETT_LISTENING
#         # you emit signals by calling the signal's skeleton method
#         self.KeywordRecognizedSignal(self._status_kw_match, SCARLETT_LISTENING)
#         return SCARLETT_LISTENING

#     @dbus.service.method("com.example.service.emitCommandRecognizedSignal",
#                          in_signature='',
#                          out_signature='s')
#     def emitCommandRecognizedSignal(self, command):
#         global SCARLETT_RESPONSE
#         self.CommandRecognizedSignal(self._status_cmd_match,
#                                      SCARLETT_RESPONSE,
#                                      command)
#         return SCARLETT_RESPONSE

#     @dbus.service.method("com.example.service.emitSttFailedSignal",
#                          in_signature='',
#                          out_signature='s')
#     def emitSttFailedSignal(self):
#         global SCARLETT_FAILED
#         self.SttFailedSignal(self._status_stt_failed, SCARLETT_FAILED)
#         return SCARLETT_FAILED

#     @dbus.service.method("com.example.service.emitListenerCancelSignal",
#                          in_signature='',
#                          out_signature='s')
#     def emitListenerCancelSignal(self):
#         global SCARLETT_CANCEL
#         self.ListenerCancelSignal(self._status_cmd_cancel, SCARLETT_CANCEL)
#         return SCARLETT_CANCEL

#     @dbus.service.method("com.example.service.emitListenerReadySignal",
#                          in_signature='',
#                          out_signature='s')
#     def emitListenerReadySignal(self):
#         global SCARLETT_LISTENING
#         self.ListenerReadySignal(self._status_ready, SCARLETT_LISTENING)
#         return SCARLETT_LISTENING

#     @dbus.service.method("com.example.service.emitConnectedToListener",
#                          in_signature='',
#                          out_signature='s')
#     def emitConnectedToListener(self, scarlett_plugin):
#         print "  sending message"
#         self.ConnectedToListener(scarlett_plugin)
#         return " {} is connected to ScarlettListener".format(scarlett_plugin)

#     @dbus.service.method("com.example.service.Message",
#                          in_signature='',
#                          out_signature='s')
#     def get_message(self):
#         print "  sending message"
#         return self._message

#     @dbus.service.method("com.example.service.Quit",
#                          in_signature='',
#                          out_signature='')
#     def quit(self):
#         print "  shutting down"
#         self.pipeline.set_state(gst.STATE_NULL)
#         self._loop.quit()

#     @dbus.service.method("com.example.service.StatusReady",
#                          in_signature='',
#                          out_signature='s')
#     def listener_ready(self):
#         print " {}".format(self._status_ready)
#         return self._status_ready

# print obj.foo(dbus_interface='tld.domain.sub.TestInterface')

# # Exceptions are passed through dbus
# try:
#     obj.fail(dbus_interface='tld.domain.sub.TestInterface')
# except Exception, e:
#     print str(e)

# # Call the stop method of the proxxied object which will stop the
# # receivers main loop
# print obj.stop(dbus_interface='tld.domain.sub.TestInterface')

# @dbus.service.signal("com.example.service.event")
#  def KeywordRecognizedSignal(self, message, scarlett_sound):
#      logger.debug(" sending message: {}".format(message))

#  @dbus.service.signal("com.example.service.event")
#  def CommandRecognizedSignal(self, message, scarlett_sound, scarlett_cmd):
#      logger.debug(" sending message: {}".format(message))

#  @dbus.service.signal("com.example.service.event")
#  def SttFailedSignal(self, message, scarlett_sound):
#      logger.debug(" sending message: {}".format(message))

#  @dbus.service.signal("com.example.service.event")
#  def ListenerCancelSignal(self, message, scarlett_sound):
#      logger.debug(" sending message: {}".format(message))

#  @dbus.service.signal("com.example.service.event")
#  def ListenerReadySignal(self, message, scarlett_sound):
#      logger.debug(" sending message: {}".format(message))

#  @dbus.service.signal("com.example.service.event")
#  def ConnectedToListener(self, scarlett_plugin):
#      pass
#      # logger.debug(
#      #     " {} is connected to ScarlettListener".format(scarlett_plugin))
