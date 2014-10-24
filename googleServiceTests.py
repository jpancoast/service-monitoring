#!/usr/bin/env python



import sys
import getopt
import cookielib
import hashlib
import urllib
import datetime
import string, random
import requests

from TestHelpers import TestHelpers
from urlparse import parse_qs

try:
	import inspect
except ImportError, e:
	print "Missing inspect module.  Install with: sudo pip install inspect"
	print "If you don't have pip, do this first: sudo easy_install pip"	
	exit( 2 )



class googleServiceTests():

	def __init__( self, configuration, debug = False, userName = 'jpancoast', useProxy = False, password = None ):
		self.configuration = configuration
		self.debug = debug
		self.userName = 'jpancoast'	#system5 is the default username.
		
		self.cookieJar = cookielib.CookieJar()
		self.testHelpers = TestHelpers( self.configuration, self.cookieJar, debug = debug, useProxy = useProxy )
		

		print "\nRunning Googles Service test"


		now = datetime.datetime.now()
		print now.strftime("%Y-%m-%d %H:%M")
		print '-' * 75

		if self.debug:
			print "DEBUG: [self.configuration: "
			print self.configuration
			print "]"



	#
	#	This is here so the services.py script can have access to the same testhelpers object
	#
	def getTestHelpers( self ):
		return self.testHelpers


	def vipTest( self ):
		testName = inspect.stack()[ 0 ][ 3 ]
		
		#if self.testHelpers.canRunTest( testName ):
		( result, testSuccess, time, message ) = self.testHelpers.checkStatus( testName, checkContentTypeFor = 'html' )
		self.testHelpers.testComplete( result, testSuccess, testName, time, message )
			
		if result:
			self.testHelpers.debugPrint( result.text )

