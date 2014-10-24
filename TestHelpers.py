#!/usr/bin/env python
from __future__ import unicode_literals

import os, re, sys
import cookielib
import io, json
import socket, time

from datetime import datetime
from urlparse import parse_qs


try:	
	import requests
except ImportError, e:
	print "Missing requests module.  Install with: sudo pip install requests"
	print "If you don't have pip, do this first: sudo easy_install pip"
	exit( 2 )



class TestHelpers():	
	#
	#	Begin helper block
	#
	def __init__( self, configuration, cookieJar, debug = False, useProxy = False ):
		self.configuration = configuration
		self.debug = debug
		self.cookieJar = cookieJar
		
		self.testsAlreadyExecuted = {}
		self.testResultsDict = {}
		self.testResultsDict[ 'tests' ] = {}
	
		self.jenkinsEnvVars = []
		
		self.failedTests = False
		self.failedTestsText = ""

		
		self.session = requests.session()
		self.useProxy = useProxy
		
		self.whichOauthHeader = 'initial'
		
		self.oauth_token = None
		self.oauth_token_secret = None
		self.oauth_token_verifier = None
		
		
		print "\n\npython version: " + sys.version
		print "requests version: " + requests.__version__	
		
		
	def getTestConfig( self, testName ):
		config = self.configuration[ 'tests' ][ testName ]
		
		if ( self.debug ):
			print "DEBUG: [Config for " + testName
			print config
			print "]"
			
		return config
		
	
	def debugPrint( self, message ):
		if self.debug:
			formattedMessage = "DEBUG: ["
			formattedMessage += str( message )
			formattedMessage += "]"
			
			print formattedMessage
	
	
	def parseForString( self, string, search ):
		return re.search( ".*" + search + ".*", string )
	
	

	def printTestStatus( self, testName, testSuccess, time, message, warning = False ):
		if ( warning ):
			testStatusText = "WARNING"
		elif ( testSuccess ):
			testStatusText = "SUCCESS"
		else:
			testStatusText = "FAILURE"
			
		if time:
			timeText = ( '%.0f ms' % ( time, ) ).rstrip( '0' ).rstrip( '.' )
		else:
			timeText = 'NaN'


		print testName.ljust( 40 ), testStatusText.ljust( 10 ), timeText.ljust( 8 ), message.ljust( 40 )

		self.testsAlreadyExecuted[ testName ] = testSuccess




	def canRunTest( self, testName ):
		testConfig = self.getTestConfig( testName )
		retVal = True
		dependentTest = ''
		message = ''
		
		"""
		First check to see if all the required tests failed.  If so, then we just exist.  Because
		"""
		for requiredTest in self.configuration[ 'requiredTests' ]:
			if not self.testsAlreadyExecuted[ requiredTest ]:
				message = "Test: " + testName + " could not be run because one of the absolutely required tests (" + requiredTest + ") failed.  There's no use going on"
				retVal = False
		
		dependentTests = []
		
		
		if 'dependentUpon' in testConfig and retVal:
			if isinstance( testConfig[ 'dependentUpon' ], basestring ):
				dependentTests.append( testConfig[ 'dependentUpon' ] )
			elif isinstance( testConfig[ 'dependentUpon'], list ):
				dependentTests = testConfig[ 'dependentUpon' ]
			
			
			"""
			Here's what I should do:
				1.  If it's a string, convert it to a list with one entry.
				
				2.  Write a loop
			"""
			
			for dependentTest in dependentTests:
				if dependentTest not in self.testsAlreadyExecuted:
					retVal = False
					message += "Test: " + testName + " could not be run because one of it's dependencies (" + dependentTest + ") wasn't run first\n"
				else:
					#Check to see if a dependent test failed
					if not self.testsAlreadyExecuted[ dependentTest ]:
						retVal = False
						message += "Test: " + testName + " could not be run because one of it's dependencies (" + dependentTest + ") failed\n"
		
		
		if not retVal:
			print message
			
		return retVal
	
	
	
	
	def checkStatus( self, testName, appendToURI = 'APPEND_TO_URI', checkContentTypeFor = 'CONTENT_TYPE', helperTestBaseUrl = 'HELPER_TEST_BASE_URL', postPayload = None ):
		testSuccess = True
		message = ''
		time = 0.0
		testConfig = self.getTestConfig( testName )
		url = ''
		
		if ( 'URL' in testConfig ):
			url = testConfig[ 'URL' ]
		else:			
			tcURI = ''

			#if testConfig[ 'URI' ] != "OVERLOAD":
			if 'URI' in testConfig:
				tcURI = testConfig[ 'URI' ]

			"""
			This whole bit about baseUrl is a little weird because I had to hack the else in here
				for the helper test... need to figure out how to do that.
			"""
			if helperTestBaseUrl == 'HELPER_TEST_BASE_URL':
				url = self.configuration[ testConfig[ 'baseUrl' ] ] + tcURI
			else:
				url = self.configuration[ helperTestBaseUrl ] + tcURI
				
				
		if ( appendToURI != 'APPEND_TO_URI' ):
			appendToURI = re.sub( "^\/", "", appendToURI )
			url = url + appendToURI
			self.debugPrint( "Appending to URI: [" + appendToURI + "]" )
		
		self.debugPrint ( "checkStatus URL: " + url )
		( result, time ) = self.timedHttpRequest( url, testName, postPayload = postPayload )

		self.debugPrint( "\nRESULT.txt for: " + testName + "[" + url + "]: " + result.text + "\n\n" )



		if ( result.status_code != requests.codes.ok ):
			testSuccess = False
			message = "Request returned " + str( result.status_code )
		
		if ( testSuccess and ( checkContentTypeFor != 'CONTENT_TYPE' ) ):
			self.debugPrint( "Check the content type..." )

			match = re.search( ".*" + checkContentTypeFor + ".*", result.headers.get( 'content-type' ) )
			if not match:
				testSuccess = False
				message = "Improper content type, should contain " + checkContentTypeFor

			if checkContentTypeFor.lower() == "json":
				self.debugPrint( "See if we can parse the JSON..." )
				
				#Just doing this for the time being, in case we get the failed json parsing again.  I want to see the full result.
				#print result.text
				
				
				try:
					tempJSON = result.json()
				except ValueError:
					testSuccess = False
					message = 'JSON Parsing Failed'
					

		return ( result, testSuccess, time, message )



	def printHeaders( self, result ):
		print "Headers: ["
		print result.headers
		print "]"
		
		
	def buildOauthHeader( self ):
		client_key = self.configuration[ 'oauth' ][ 'key' ]
		client_secret = self.configuration[ 'oauth' ][ 'secret' ]
		
		
		if self.whichOauthHeader.lower() == 'initial':
			return OAuth1( client_key, client_secret = client_secret )
		elif self.whichOauthHeader.lower() == 'verifier':
			return OAuth1( client_key, client_secret = client_secret, resource_owner_key = self.oauth_token, resource_owner_secret = self.oauth_token_secret, verifier = self.oauth_token_verifier, signature_type = 'auth_header' )
		else:
			return OAuth1( client_key, client_secret = client_secret, resource_owner_key = self.oauth_token, resource_owner_secret = self.oauth_token_secret, signature_type = 'auth_header' )
		
		
		
	def timedHttpRequest( self, url, testName, postPayload ):
		beginDT = datetime.now()
		
		httpMethod = "GET"
		proxies = {}
		
		oauthHeader = None;
		
		if( 'httpMethod' in self.configuration[ 'tests' ][ testName ].keys() ):
			httpMethod = self.configuration[ 'tests' ][ testName ][ 'httpMethod' ]
		
		
		if( self.useProxy ):
			self.debugPrint( "Trying to use a proxy..." )
			
			if ( 'proxies' in self.configuration ):
				if (
					( 'http' in self.configuration[ 'proxies' ] ) and
					( 'https' in self.configuration[ 'proxies' ] )
				):
					proxies = self.configuration[ 'proxies' ]
					
					
		if not proxies and self.useProxy:
			print "\tyou indicated you wanted to use proxies, but there are no proxies in the configuration file"
		
		
		"""
		We treat existence of self.configuration[ 'oauth' ] as meaning they want to use oauth
		"""
		if 'oauth' in self.configuration:
			oauthHeader = self.buildOauthHeader()
		
		
		if httpMethod.lower() == "post":
			if postPayload == None:
				postPayload = {}
				
			self.debugPrint( "POST PAYLOAD: " ) 
			self.debugPrint( postPayload )
			
			if oauthHeader != None:
				r = self.session.post( url, verify = True, cookies = self.cookieJar, proxies = proxies, auth = oauthHeader, data = postPayload )
			else:
				r = self.session.post( url, verify = True, cookies = self.cookieJar, proxies = proxies, data = postPayload )
		else:
			if oauthHeader != None:
				r = self.session.get( url, verify = True, cookies = self.cookieJar, proxies = proxies, auth = oauthHeader )
			else:
				r = self.session.get( url, verify = True, cookies = self.cookieJar, proxies = proxies )




		#
		#	Have to do this explicitly since requests 1.0.4 seems borked
		#
		for cookie in r.cookies:
			self.cookieJar.set_cookie(cookie)
			
		endDT = datetime.now()

		totalTimeDelta = beginDT - endDT
		time = totalTimeDelta.microseconds / 1000
		
		
		return ( r, time )


	#
	#	This where we save more detail about the failed tests, so we can print it out at the end of the run
	#
	def setTestDetails( self, result, testSuccess, testName, time, message  ):
		#self.testResultsDict = {}
		
		if ( time ):
			timeText = ( '%.0f ms' % ( time, ) ).rstrip( '0' ).rstrip( '.' )
		else:
			timeText = 'NaN'
			
		self.testResultsDict[ 'tests' ][ testName ] = {}
		self.testResultsDict[ 'tests' ][ testName ][ 'success' ] = testSuccess
		self.testResultsDict[ 'tests' ][ testName ][ 'timeToExecute' ] = timeText
		self.testResultsDict[ 'tests' ][ testName ][ 'message' ] = message
		
		
		tmpFailText = ""
		
		
		if not testSuccess:
			self.failedTests = True
			self.failedTestsText += "\nFail details for " + testName + "\n"
			self.failedTestsText += '-' * 75 + "\n"

			if result != None:
					
				tmpFailText += "Result: \n"
				tmpFailText += "Headers: " + str( result.headers ) + "\n"
				tmpFailText += "Cookie Jar: \n"
				tmpFailText += str( self.cookieJar )
				tmpFailText += "\nbody: " + str( result.text ) + "\n"
				
				tmpFailText += "---\nRequest: \n"
				tmpFailText += "Headers: " + str( result.request.headers ) + "\n"
				tmpFailText += "URL: " + str( result.request.url ) + "\n"
					
			else:
				tmpFailText = "\nNo more details\n"

			self.failedTestsText += tmpFailText
			self.failedTestsText += '-' * 75 + "\n"
				
		self.testResultsDict[ 'tests' ][ testName ][ 'failText' ] = tmpFailText
	

	def getAllTestDetails( self ):
		return ( self.failedTests, self.failedTestsText )


	def someTestsFailed( self ):
		return self.failedTests


	def getFailedTestsText( self ):
		return self.failedTestsText
		
		
	def getTestResultsDict( self ):
		return self.testResultsDict
		

	def writeTestsJSON( self, fileName ):
		outFile = open( fileName, "w" )
		outFile.write( json.dumps( self.testResultsDict ) )
		

	def execute_command( command ):
		debugPrint( command )
		debugPrint( "CWD: [" + os.getcwd() + "] command: [" + command + "]" )
		os.system( command )


	"""
	self.testHelpers.debugPrint( result.text )
	#self.testHelpers.setTestDetails( result, testSuccess, testName, time, message  )
	#self.testHelpers.printTestStatus( testName, testSuccess, time, message )
	
	self.testHelpers.testComplete( result, testSuccess, testName, time, message )
	"""
	def testComplete( self, result, testSuccess, testName, time, message ):
		self.setTestDetails( result, testSuccess, testName, time, message  )
		self.printTestStatus( testName, testSuccess, time, message )
		
		
	#
	#	End Helper Block
	#
