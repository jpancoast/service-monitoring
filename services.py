#!/usr/bin/env python


import sys
import getopt


try:
	import yaml
except ImportError, e:
	print "Missing PY-YAML module.  Install with: sudo pip install pyyaml"
	print "If you don't have pip, do this first: sudo easy_install pip"
	exit( 2 )


try:	
	import requests
except ImportError, e:
	print "Missing requests module.  Install with: sudo pip install requests"
	print "If you don't have pip, do this first: sudo easy_install pip"
	exit( 2 )

try:
	import inspect
except ImportError, e:
	print "Missing inspect module.  Install with: sudo pip install inspect"
	print "If you don't have pip, do this first: sudo easy_install pip"	
	exit( 2 )


debug = False



def main( argv ):
	( config_file, userName, printTestInfo, testToRun, useProxy, debug, password ) = parse_options()
	
	debugPrint( "\nStart service testing (" + config_file + ")\n\n" )	
	
	configuration = loadConfig( config_file )
	

		
	#
	#	Dynamically import the test class
	#
	if 'testClass' in configuration:
		className = configuration[ 'testClass' ]
		
		try:
			testModule = __import__( className, fromlist = [ className ] )
			
			testClass = getattr( testModule, className )
			testInstance = testClass( configuration, debug, userName = userName, useProxy = useProxy, password = password )
		except ImportError:
			print "No module named " + className + " found"
			exit( 2 )
	else:
		print "testClass not defined in configuration file.  You should define one."
		exit( 2 )
	
	if printTestInfo:
		testInstance.help()
		exit( 0 )

	if ( debug ):
		print configuration
		print "\n\n"
		print configuration[ 'tests' ]
	
		
	testHelpers = testInstance.getTestHelpers()
	
	
	#
	#	the required tests MUST be run first AND in the order given in the config
	#		they get/set the cookies, login, etc.
	#
	for rtest in configuration[ 'requiredTests' ]:
		debugPrint( "Required Test: " + rtest )

		try:
			func = getattr( testInstance, rtest )
		except AttributeError:
			print "Missing test (" + rtest + ")"
		else:
			result = func()



	if testToRun == None:
		for precedence in configuration[ 'possiblePrecedencesInOrder' ]:
			for test in configuration[ 'tests' ].keys():
				if configuration[ 'tests' ][ test ][ 'precedence' ] == precedence:
				
					if not ( test in configuration[ 'requiredTests' ] ):
						debugPrint( "Test: " + test )
						try:
							func = getattr( testInstance, test )
						except AttributeError:
							print "Missing test (" + test + ")"
						else:
							result = func()
	else:
		print "Specific Test To run: " + testToRun
		#Check to see if test has edpendencies... if so, run them first.
		#		If not, just run the test



	testHelpers.writeTestsJSON( "serviceTestResults.json" )
		
	( failedTests, failedTestsText ) = testHelpers.getAllTestDetails()
	if failedTests:
		print failedTestsText
		exit( 1 )
	else:
		print "All Tests Successful!"




def loadConfig( config_file ):
	f = open( config_file )
	
	dataMap = yaml.safe_load( f )
	f.close()
	
	return dataMap
	


def parse_options():
	#
	#	Options Parsing.  All are required.
	options, remainder = getopt.getopt( sys.argv[ 1: ], 'c:utrxdp',
		[ 
			'config=',
			'userName=',
			'testInfo',
			'testToRun=',
			'useProxy',
			'debug',
			'password='
		]
	 )

	userName = None
	password = None
	
	config_file = "CONFIG_FILE"
	testInfo = False
	testToRun = None
	useProxy = False
	debug = False
	

	for opt, arg in options:
		if opt in ( '-c', '--config' ):
			config_file = arg
		if opt in ( '-u', '--userName' ):
			userName = arg
		if opt in ( '-t', '--testInfo' ):
			testInfo = True
		if opt in ( '-r', '--testToRun' ):
			testToRun = arg
		if opt in ( '-x', '--useProxy' ):
			useProxy = True
		if opt in ( '-d', '--debug' ):
			debug = True
		if opt in ( '-p', '--password' ):
			password = arg
			
	if ( 
			config_file == 'CONFIG_FILE'
		):
		usage()
		exit( 2 )
		

	return( config_file, userName, testInfo, testToRun, useProxy, debug, password )
	

def debugPrint( message ):
	if debug:
		print "DEBUG: [" + message + "]"
		

def usage():
	print "\nUsage: " + sys.argv[ 0 ] + " --config=<path to YAML config file> --userName=<user to use> --testInfo --testToRun=<Specific Test To Run> --useProxy --debug --password=<password for user if not in config file>"
	print "\t--config REQUIRED"
	print "\t--userName OPTIONAL"
	print "\t--testInfo OPTIONAL"
	print "\t--testToRun OPTIONAL"
	print "\t--useProxy OPTIONAL"
	print "\t--debug OPTIONAL"
	print ""



if __name__ == "__main__":
	main( sys.argv )
