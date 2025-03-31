all:
	PYTHONPATH=`pwd` python3 razzle/SpecGo.py

debug:
	spike -d ./build/victim