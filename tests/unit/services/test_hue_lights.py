# # This file is part of Scarlett.
# # Copyright 2014, Behanceops.

# import scarlett
# import os
# import sys
# from tests.unit import unittest, ScarlettTestCase
# from nose.plugins.attrib import attr
# from scarlett.features.hue_lights import FeatureHueLights
# import responses
# import requests
# import json
# from pprint import pprint
# import ast

# # POST
# # body: {"devicetype":"test user","username":"newdeveloper"}
# # Command response:
# # [
# #   {
# #     "error": {
# #       "type": 101,
# #       "address": "",
# #       "description": "link button not pressed"
# #     }
# #   }
# # ]

# # GET: /api/newdeveloper/lights

# # _FAKE_GET_LIGHTS_RESPONSE={
# #   "1": {
# #     "name": "Family Room"
# #   },
# #   "2": {
# #     "name": "Hallway"
# #   },
# #   "3": {
# #     "name": "Bathroom"
# #   },
# #   "4": {
# #     "name": "Bed Room"
# #   }
# # }

# # GET: /api/newdeveloper/lights/1
# # {
# #   "state": {
# #     "on": true,
# #     "bri": 174,
# #     "hue": 59183,
# #     "sat": 66,
# #     "xy": [
# #       0.3662,
# #       0.5015
# #     ],
# #     "ct": 0,
# #     "alert": "none",
# #     "effect": "none",
# #     "colormode": "hs",
# #     "reachable": true
# #   },
# #   "type": "Extended color light",
# #   "name": "Family Room",
# #   "modelid": "LCT001",
# #   "swversion": "65003148",
# #   "pointsymbol": {
# #     "1": "none",
# #     "2": "none",
# #     "3": "none",
# #     "4": "none",
# #     "5": "none",
# #     "6": "none",
# #     "7": "none",
# #     "8": "none"
# #   }
# # }

# # In [3]: b = Bridge(ip='192.168.2.11',config_file_path="/home/pi/.python_hue")

# #### In [4]: b.get_api()
# #### Out[4]:
# #### {u'config': {u'UTC': u'2014-12-13T02:07:44',
# ####   u'dhcp': True,
# ####   u'gateway': u'192.168.2.1',
# ####   u'ipaddress': u'192.168.2.11',
# ####   u'linkbutton': False,
# ####   u'mac': u'00:17:88:10:24:3c',
# ####   u'name': u'Philips hue',
# ####   u'netmask': u'255.255.255.0',
# ####   u'portalservices': False,
# ####   u'proxyaddress': u'',
# ####   u'proxyport': 0,
# ####   u'swupdate': {u'notify': False,
# ####    u'text': u'',
# ####    u'updatestate': 0,
# ####    u'url': u''},
# ####   u'swversion': u'01003542',
# ####   u'whitelist': {u'12748326e1528241821617210c53c9f': {u'create date': u'2014-12-13T02:01:35',
# ####     u'last use date': u'2014-10-15T02:23:03',
# ####     u'name': u'python_hue'},
# ####    u'1bf65ff514536e0e70a846a26cacb459': {u'create date': u'2014-12-10T01:41:21',
# ####     u'last use date': u'2014-10-15T02:23:03',
# ####     u'name': u'node-hue-cli'},
# ####    u'1e0141d23f9487f7162d99ee27fc7a23': {u'create date': u'2014-10-15T02:18:13',
# ####     u'last use date': u'2014-10-15T02:23:03',
# ####     u'name': u'python_hue'},
# ####    u'1f7544cd0146dabbc26e0ea218cba3e9': {u'create date': u'2013-08-03T03:54:25',
# ####     u'last use date': u'2013-09-06T09:53:23',
# ####     u'name': u'Malcolm Jones\u2019s iPhone'},
# ####    u'2582b1c681b4dc4157ee6123b534bbf': {u'create date': u'2014-12-13T02:01:42',
# ####     u'last use date': u'2014-10-15T02:23:03',
# ####     u'name': u'python_hue'},
# ####    u'2D4735B381AF2AD1A2A4430FDF8ED5CC': {u'create date': u'2013-12-28T04:37:39',
# ####     u'last use date': u'2013-12-28T04:37:41',
# ####     u'name': u'HueDisco'},
# ####    u'306ccf04d8f8a85336dccdfc7de4a5e8': {u'create date': u'2013-08-04T01:56:26',
# ####     u'last use date': u'2013-08-03T03:54:26',
# ####     u'name': u"Malcolm's iPhone"},
# ####    u'37bf0bccd571a0f2bcab7a4dcb1a7': {u'create date': u'2014-12-13T02:05:17',
# ####     u'last use date': u'2014-12-13T02:07:44',
# ####     u'name': u'python_hue'},
# ####    u'605C252603438E825667FDA735175A3C': {u'create date': u'2013-08-03T03:56:43',
# ####     u'last use date': u'2013-10-12T03:42:12',
# ####     u'name': u'HueDisco'},
# ####    u'61ad34042f1e420d68d2c0b70532606c': {u'create date': u'2013-06-21T03:02:39',
# ####     u'last use date': u'2013-06-21T03:32:05',
# ####     u'name': u'Stampsuser\u2019s iPhone'},
# ####    u'9qsYLjDI3dkoxqkj': {u'create date': u'2013-12-28T04:37:40',
# ####     u'last use date': u'2013-12-28T04:38:01',
# ####     u'name': u"#heron's iPad"},
# ####    u'SKwzUDyD6rzRpAlw': {u'create date': u'2013-09-22T21:48:52',
# ####     u'last use date': u'2013-08-03T03:54:26',
# ####     u'name': u'Malcolm Jones\u2019s iPhone'},
# ####    u'TfN6hQ4FTdwnThca': {u'create date': u'2013-10-31T00:11:13',
# ####     u'last use date': u'2013-12-03T14:14:47',
# ####     u'name': u"Malcolm's iPhone"},
# ####    u'newdeveloper': {u'create date': u'2014-12-13T00:39:42',
# ####     u'last use date': u'2014-12-13T00:43:19',
# ####     u'name': u'test user'}}},
# ####  u'groups': {},
# ####  u'lights': {u'1': {u'modelid': u'LCT001',
# ####    u'name': u'Family Room',
# ####    u'pointsymbol': {u'1': u'none',
# ####     u'2': u'none',
# ####     u'3': u'none',
# ####     u'4': u'none',
# ####     u'5': u'none',
# ####     u'6': u'none',
# ####     u'7': u'none',
# ####     u'8': u'none'},
# ####    u'state': {u'alert': u'none',
# ####     u'bri': 174,
# ####     u'colormode': u'hs',
# ####     u'ct': 0,
# ####     u'effect': u'none',
# ####     u'hue': 59183,
# ####     u'on': True,
# ####     u'reachable': True,
# ####     u'sat': 66,
# ####     u'xy': [0.3662, 0.5015]},
# ####    u'swversion': u'65003148',
# ####    u'type': u'Extended color light'},
# ####   u'2': {u'modelid': u'LCT001',
# ####    u'name': u'Hallway',
# ####    u'pointsymbol': {u'1': u'none',
# ####     u'2': u'none',
# ####     u'3': u'none',
# ####     u'4': u'none',
# ####     u'5': u'none',
# ####     u'6': u'none',
# ####     u'7': u'none',
# ####     u'8': u'none'},
# ####    u'state': {u'alert': u'none',
# ####     u'bri': 254,
# ####     u'colormode': u'ct',
# ####     u'ct': 369,
# ####     u'effect': u'none',
# ####     u'hue': 14922,
# ####     u'on': True,
# ####     u'reachable': True,
# ####     u'sat': 144,
# ####     u'xy': [0.4595, 0.4105]},
# ####    u'swversion': u'65003148',
# ####    u'type': u'Extended color light'},
# ####   u'3': {u'modelid': u'LCT001',
# ####    u'name': u'Bathroom',
# ####    u'pointsymbol': {u'1': u'none',
# ####     u'2': u'none',
# ####     u'3': u'none',
# ####     u'4': u'none',
# ####     u'5': u'none',
# ####     u'6': u'none',
# ####     u'7': u'none',
# ####     u'8': u'none'},
# ####    u'state': {u'alert': u'none',
# ####     u'bri': 0,
# ####     u'colormode': u'hs',
# ####     u'ct': 0,
# ####     u'effect': u'none',
# ####     u'hue': 0,
# ####     u'on': True,
# ####     u'reachable': True,
# ####     u'sat': 0,
# ####     u'xy': [0.0, 0.0]},
# ####    u'swversion': u'65003148',
# ####    u'type': u'Extended color light'},
# ####   u'4': {u'modelid': u'LCT001',
# ####    u'name': u'Bed Room',
# ####    u'pointsymbol': {u'1': u'none',
# ####     u'2': u'none',
# ####     u'3': u'none',
# ####     u'4': u'none',
# ####     u'5': u'none',
# ####     u'6': u'none',
# ####     u'7': u'none',
# ####     u'8': u'none'},
# ####    u'state': {u'alert': u'none',
# ####     u'bri': 254,
# ####     u'colormode': u'ct',
# ####     u'ct': 369,
# ####     u'effect': u'none',
# ####     u'hue': 14922,
# ####     u'on': True,
# ####     u'reachable': True,
# ####     u'sat': 144,
# ####     u'xy': [0.4595, 0.4105]},
# ####    u'swversion': u'66009663',
# ####    u'type': u'Extended color light'}},
# ####  u'schedules': {}}



# class HueTestCase(ScarlettTestCase):

#     def setUp(self):
#         super(HueTestCase, self).setUp()

#     @attr(hue=True)
#     @responses.activate
#     def test_hue_lights_names(self):
#         light_resp_path     = os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','fixtures/http/hue_api_lights_resp.json')
#         #light_resp_path     = "%s/tests/fixtures/http/hue_api_lights_resp.json" % (os.environ['MAIN_DIR'])
#         with open(light_resp_path) as json_file:
#              _hue_api_lights_resp = json.load(json_file)
#         json_file.close

#         _hue_ip = scarlett.config.get("hue","bridge")
#         _base_url = "http://{0}/".format(_hue_ip)
#         _full_endpoint = "{0}/python_hue/lights".format(_base_url)

#         responses.add(responses.GET, _full_endpoint,
#                   body=json.dumps(_hue_api_lights_resp), status=200,
#                   content_type='application/json')

#         resp = requests.get(_full_endpoint)

#         assert resp.json() == _hue_api_lights_resp

#         assert len(responses.calls) == 1
#         assert responses.calls[0].request.url == _full_endpoint
#         assert responses.calls[0].response.text == json.dumps(_hue_api_lights_resp).encode('utf-8')

# def suite():
#     return unittest.TestLoader().loadTestsFromName(__name__)

# if __name__ == '__main__':
#     unittest.main(defaultTest='suite')
