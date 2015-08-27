#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lambert <flambert@redhat.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# Requirments: python
#
# Pods : Allow you to check if pods registry and router are running.
# Nodes : Check if nodes status isn't Running

import sys
import argparse
import subprocess
import httplib
import json


STATE_OK = 0
STATE_WARNING = 1
STATE_CRITICAL = 2
STATE_UNKNOWN = 3

STATE_TEXT = ['Ok', 'Warning', 'Critical', 'Unknow']

STATE = STATE_OK
OUTPUT_MESSAGE = ''

PARSER = argparse.ArgumentParser(description='Openshift check pods')
PARSER.add_argument("-proto", "--protocol", type=str,
                    required=False,
                    help='Protocol openshift (Default : https)',
                    default="https")
PARSER.add_argument("-H", "--host", type=str,
                    required=False,
                    help='Host openshift (Default : 127.0.0.1)',
                    default="127.0.0.1")
PARSER.add_argument("-P", "--port", type=str,
                    required=False,
                    help='Port openshift (Default : 8443)',
                    default=8443)
PARSER.add_argument("-u", "--username", type=str,
                    required=False,
                    help='Username openshift (ex : sensu)')
PARSER.add_argument("-p", "--password", type=str,
                    required=False,
                    help='Password openshift')
PARSER.add_argument("-t", "--token", type=str,
                    required=False,
                    help='Token openshift (use token or user/pass')
PARSER.add_argument("--check_nodes", action='store_true',
                    required=False,
                    help='Check status of all nodes')
PARSER.add_argument("--check_pods", action='store_true',
                    required=False,
                    help='Check status of pods ose-haproxy-router and ose-docker-registry')
PARSER.add_argument("--check_regions", action='store_true',
                    required=False,
                    help='Check if your nodes are in your "OFFLINE" region. Only warning (define by --region_offline)')
PARSER.add_argument("--region_offline", type=str,
                    required=False,
                    help='Your "OFFLINE" region name (Default: OFFLINE)',
                    default="OFFLINE")
ARGS = PARSER.parse_args()

class Openshift(object):
  """
  A little object for use REST openshift v3 api
  """

  proto = 'https'
  host = '127.0.0.1'
  port = 8443
  username = None
  password = None
  token = None
  headers = None
  response = None
  base_uri = None
  base_api = '/api/v1beta3/'
  verbose = False
  debug = False
  namespace = "default"
  os_STATE = 0
  os_OUTPUT_MESSAGE = ''

  def __init__(self, host=None, port=8443, username=username, password=password, token=None, debug=False, verbose=False, proto=None, headers=None):
     if proto is not None:
         self.proto = proto

     if host is not None:
         self.host = host

     if username:
         self.username = username

     if password:
         self.password = password

     if headers:
         self.headers = headers

     if verbose:
         self.verbose = verbose

     self.debug = debug
     self.base_uri = self.proto + "://" + host +  self.base_api

     if token:
         self.token = token
     else:
         self.token=self._auth()

  def _auth(self):
     cmd="oc login %s:%s -u%s -p%s --insecure-skip-tls-verify=True 2>&1 > /dev/null" % (self.host, self.port, self.username, self.password)
     subprocess.check_output(cmd, shell=True)

     cmd="oc whoami -t"
     stdout = subprocess.check_output(cmd, shell=True)

     return stdout.strip()

  def get_nodes(self):

     self.os_OUTPUT_MESSAGE += ' Nodes: '

     api_nodes = self.base_api + 'nodes'
     headers = {"Authorization": 'Bearer ' + self.token}
     conn = httplib.HTTPSConnection(self.host, self.port)
     conn.request("GET", api_nodes, "", headers)
     r1 = conn.getresponse()
     rjson = r1.read()
     conn.close()
     parsed_json = json.loads(rjson)

     all_nodes_names=''
     for item in parsed_json["items"]:
       all_nodes_names+=item["metadata"]["name"] + ' '

       #print item["metadata"]["name"]
       #print item["status"]["addresses"][0]["address"]
       #print item["status"]["conditions"][0]["type"]
       #print item["status"]["conditions"][0]["status"]
       #print item["status"]["conditions"][0]["reason"]

       #if status not ready
       if item["status"]["conditions"][0]["status"] != "True":
          self.os_STATE = 2
          self.os_OUTPUT_MESSAGE += item["metadata"]["name"] + '/' + item["status"]["addresses"][0]["address"] + ': ['+ item["status"]["conditions"][0]["status"] + ' ' + item["status"]["conditions"][0]["reason"] + '] '
     
     if self.os_STATE == 0:
        self.os_OUTPUT_MESSAGE += all_nodes_names + '[Ready]'

     
  def get_pods(self,namespace=None):

     self.os_OUTPUT_MESSAGE += ' Pods: '

     if namespace:
         self.namespace = namespace
     api_pods = self.base_api + 'namespaces/' + self.namespace + '/pods'

     headers = {"Authorization": 'Bearer ' + self.token}
     conn = httplib.HTTPSConnection(self.host, self.port)
     conn.request("GET", api_pods, "", headers)
     r1 = conn.getresponse()
     rjson = r1.read()
     conn.close()
     parsed_json = json.loads(rjson)

     pods = {}
     for item in parsed_json["items"]:
       #print item["metadata"]["name"]
       #print item["metadata"]["labels"]["deploymentconfig"]
       #print item["status"]["phase"]
       #print item["status"]["Condition"][0]["type"]
       #print item["status"]["Condition"][0]["status"]

       try:
         if item["status"]["Condition"][0]["status"] != "True":
            pods[item["metadata"]["labels"]["deploymentconfig"]] = item["metadata"]["name"] + ': [' + item["status"]["phase"] + ' ' + item["status"]["Condition"][0]["status"] + '] '
            self.os_STATE = 2
         else:
            pods[item["metadata"]["labels"]["deploymentconfig"]] = item["metadata"]["name"] + ': [' + item["status"]["phase"] + '] '

       except ValueError:
         pass


     registry_dc_name = 'docker-registry'
     router_dc_name = 'router'

     if registry_dc_name in pods:
        self.os_OUTPUT_MESSAGE += pods[registry_dc_name]
     else:
        self.os_OUTPUT_MESSAGE += registry_dc_name + ' [Missing] '
        self.os_STATE = 2

     if router_dc_name in pods:
        self.os_OUTPUT_MESSAGE += pods[router_dc_name]
     else:
        self.os_OUTPUT_MESSAGE += router_dc_name + ' [Missing] '
        self.os_STATE = 2

     # self.os_OUTPUT_MESSAGE += 
     #item["metadata"]["name"] + '/' + item["status"]["addresses"][0]["address"] + '['+ item["status"]["conditions"][0]["status"] + ' ' + item["status"]["conditions"][0]["reason"] + ']'
     
     #if self.os_STATE == 0:
     #   self.os_OUTPUT_MESSAGE = 'docker-registry and router [Running]'


  def get_regions(self,region_offline):

     self.os_OUTPUT_MESSAGE += ' Nodes: '

     api_nodes = self.base_api + 'nodes'
     headers = {"Authorization": 'Bearer ' + self.token}
     conn = httplib.HTTPSConnection(self.host, self.port)
     conn.request("GET", api_nodes, "", headers)
     r1 = conn.getresponse()
     rjson = r1.read()
     conn.close()
     parsed_json = json.loads(rjson)

     all_nodes_names=''
     for item in parsed_json["items"]:
       all_nodes_names+=item["metadata"]["name"] + ' '

       #print item["metadata"]["labels"]["region"]
       #print item["status"]["addresses"][0]["address"]
       #print item["status"]["conditions"][0]["type"]
       #print item["status"]["conditions"][0]["status"]
       #print item["status"]["conditions"][0]["reason"]
       #if status not ready
       if item["metadata"]["labels"]["region"] == region_offline:
          self.os_STATE = 1 #just warning
          self.os_OUTPUT_MESSAGE += item["metadata"]["name"] + '/' + item["status"]["addresses"][0]["address"] + ': [Region: '+ region_offline + '] '
     
     if self.os_STATE == 0:
        self.os_OUTPUT_MESSAGE += all_nodes_names + '[schedulable]'


if __name__ == "__main__":

   # https://docs.openshift.com/enterprise/3.0/rest_api/openshift_v1.html

   if ARGS.token:
      myos = Openshift(host=ARGS.host, port=ARGS.port, token=ARGS.token, proto=ARGS.protocol)
   elif ARGS.username and ARGS.password:
      myos = Openshift(host=ARGS.host, port=ARGS.port, username=ARGS.username, password=ARGS.password, proto=ARGS.protocol)
   else:
      PARSER.print_help()
      sys.exit(STATE_UNKNOWN)

   if ARGS.check_nodes:
      myos.get_nodes()

   if ARGS.check_pods:
      myos.get_pods()

   if ARGS.check_regions:
      myos.get_regions(ARGS.region_offline)

   try:
     STATE = myos.os_STATE
     OUTPUT_MESSAGE = myos.os_OUTPUT_MESSAGE

     print "%s:%s" % (STATE_TEXT[STATE], OUTPUT_MESSAGE)
     sys.exit(STATE)
   except ValueError:
     print "Oops!  cant return STATE"
